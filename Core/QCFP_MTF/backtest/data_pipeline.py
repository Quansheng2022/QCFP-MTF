# coding: utf-8
"""回测信号时间线（防 Look-ahead）

与 P4 融合引擎的关键差异：季度结构按 available_date（实际披露日或估算可用日）对齐，
而非 period_end，从而杜绝"季度末后 45 天窗口"的未来数据泄漏。

P0-A（新 1 号）：Evidence Builder 不再拥有 target/action 决策权。
    build_signal_timeline() 仅作 Legacy Shadow Comparator，输出带
    authority=SHADOW_ONLY / non_certifiable=True 标记；
    正式路径必须使用 build_evidence_timeline() → canonical_replay() →
    engine.evaluate() → DecisionSnapshot。
"""

import pandas as pd

from ..common.asof import (apply_disclosure_overrides, asof_join_latest,
                           load_disclosure_overrides)
from ..decision.action_generator import generate_action
from ..decision.catalyst_quality import (calc_catalyst_quality, catalyst_type,
                                         time_stop_weeks)
from ..decision.downside_risk import apply_downside_risk
from ..decision.position_sizing import effective_position_cqs
from ..decision.risk_evaluator import evaluate_risk
from ..fusion.chip_confidence import compute_chip_confidence
from ..fusion.mtf_alignment import align_mtf


def _market_context(idx_df, dates, settings) -> pd.Series:
    cfg = settings.get("fusion", {}).get("market_context", {})
    win = int(cfg.get("hsi_return_window", 60))
    vhsi_off = float(cfg.get("vhsi_risk_off", 25))
    idx = idx_df[["date", "HSI", "VHSI"]].copy()
    idx["date"] = pd.to_datetime(idx["date"])
    idx = idx.sort_values("date").dropna(subset=["HSI"])
    idx["hsi_ret"] = idx["HSI"] / idx["HSI"].shift(win) - 1.0
    idx = idx[["date", "hsi_ret", "VHSI"]]
    asof = pd.DataFrame({"date": pd.DatetimeIndex(dates)})
    m = pd.merge_asof(asof, idx, on="date", direction="backward")

    def _ctx(r):
        if pd.isna(r["hsi_ret"]) or pd.isna(r["VHSI"]):
            return "neutral"
        if r["hsi_ret"] > 0.02 and r["VHSI"] < vhsi_off:
            return "risk_on"
        if r["hsi_ret"] < -0.02 or r["VHSI"] > vhsi_off:
            return "risk_off"
        return "neutral"

    return m.apply(_ctx, axis=1)


def build_signal_timeline(structural, monthly, weekly, chip, idx_df, settings,
                          stocks=None, weekly_kl=None, daily=None) -> pd.DataFrame:
    """构建防 Look-ahead 的信号时间线（每股票×每周）

    Args:
        structural: qcfp_quarterly_structural（含 available_date）
        monthly: qcfp_monthly_behavior
        weekly: qcfp_weekly_tactical
        chip: hk_quarterly_chip_analysis（chip_structure_score）
        idx_df: hk_idx_hist
        settings: QCFP 配置
    """
    grid = weekly[["stock_code", "stock_name", "week_end", "tactical_signal",
                   "data_quality"]].copy()
    if stocks:
        grid = grid[grid["stock_code"].isin(stocks)]
    grid["decision_dt"] = pd.to_datetime(grid["week_end"], errors="coerce")
    grid = grid.sort_values("decision_dt").reset_index(drop=True)

    lag_days = int(settings.get("institutional", {}).get("disclosure_lag_days", 45))
    structural = structural.copy()
    structural["available_date_dt"] = pd.to_datetime(
        structural["available_date"], errors="coerce")
    structural["available_date_dt"] = structural["available_date_dt"].fillna(
        pd.to_datetime(structural["period_end"], errors="coerce")
        + pd.Timedelta(days=lag_days))
    overrides = load_disclosure_overrides()
    if overrides:
        structural = apply_disclosure_overrides(structural, overrides)
    monthly = monthly.copy()
    monthly["month_end_dt"] = pd.to_datetime(monthly["month_end"], errors="coerce")
    chip = chip.copy()
    # P0-2：Chip 与 Structural 披露日统一——优先用结构表同一季度的 available_date
    #（含真实披露覆盖），无匹配才回退 quarter_end + lag。
    struct_disc = {(r["stock_code"], r["period_end"]): r["available_date_dt"]
                   for _, r in structural.iterrows()}
    chip["quarter_end"] = pd.to_datetime(
        chip["quarter_end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    chip["_disc"] = [
        struct_disc.get((r["stock_code"], r["quarter_end"])) for _, r in chip.iterrows()]
    chip["available_date_dt"] = pd.to_datetime(chip["_disc"], errors="coerce")
    chip["available_date_dt"] = chip["available_date_dt"].fillna(
        pd.to_datetime(chip["quarter_end_date"], errors="coerce")
        + pd.Timedelta(days=lag_days))

    out = asof_join_latest(
        grid, structural, "decision_dt", "available_date_dt",
        right_cols=["period_end", "structural_regime", "c_state", "f_state",
                    "p_state", "q_trend_score", "q_position_52w", "data_quality"],
        suffixes=("", "_q"))
    out = asof_join_latest(
        out, monthly, "decision_dt", "month_end_dt",
        right_cols=["monthly_behavior_state", "cbi_score", "cbi_state",
                    "cost_position", "data_quality"],
        suffixes=("", "_m"))
    out = asof_join_latest(
        out, chip, "decision_dt", "available_date_dt",
        right_cols=["chip_structure_score"], suffixes=("", "_c"))
    out = out.rename(columns={"data_quality": "weekly_data_quality",
                              "data_quality_q": "structural_data_quality",
                              "data_quality_m": "monthly_data_quality"})
    out["structural_available_date"] = out["available_date_dt"].dt.strftime("%Y-%m-%d")

    out["confidence_score"], out["chip_stability_confidence"] = zip(*[
        compute_chip_confidence(r["chip_structure_score"], r["cbi_score"],
                                r["c_state"], settings)
        for _, r in out.iterrows()])
    # 上一季度 F 状态（资金持续性）
    struct_sorted = structural.sort_values(["stock_code", "period_end"]).copy()
    struct_sorted["prev_f"] = struct_sorted.groupby("stock_code")["f_state"].shift(1)
    prev_f_map = {(r["stock_code"], r["period_end"]): r["prev_f"]
                  for _, r in struct_sorted.iterrows()}
    out["prev_f_state"] = [
        prev_f_map.get((r["stock_code"], r["period_end"])) for _, r in out.iterrows()]
    # 催化剂质量评分
    out["catalyst_score"] = [
        calc_catalyst_quality(r["f_state"], r["prev_f_state"],
                              r.get("q_trend_score"), r.get("q_position_52w"),
                              r.get("cbi_state"))
        for _, r in out.iterrows()]
    out["catalyst_type"] = out["catalyst_score"].map(catalyst_type)

    # 方案 B：空头结构下的战术试多（周线 Breakout + 52W 极低位）
    to_cfg = settings.get("decision", {}).get("tactical_override", {})
    to_enabled = bool(to_cfg.get("enabled", True))
    to_max_52w = float(to_cfg.get("max_52w_position", 0.15))
    min_trigger = to_cfg.get("min_trigger", "Breakout")
    if isinstance(min_trigger, str):
        min_trigger = tuple(x.strip() for x in min_trigger.split(",") if x.strip())
    else:
        min_trigger = tuple(min_trigger)
    out["mtf_regime"], out["align_method"] = zip(*[
        align_mtf(r["structural_regime"], r["monthly_behavior_state"],
                  r["tactical_signal"],
                  tactical_override=to_enabled,
                  position_52w=r.get("q_position_52w"),
                  max_52w_position=to_max_52w, min_trigger=min_trigger)
        for _, r in out.iterrows()])
    out["market_context"] = _market_context(idx_df, out["decision_dt"], settings)
    grades = out[["structural_data_quality", "monthly_data_quality",
                  "weekly_data_quality"]]
    order = {"A": 0, "B": 1, "C": 2, "D": 3}
    out["data_quality"] = grades.apply(
        lambda r: max(r.dropna(), key=lambda g: order.get(g, 3))
        if r.notna().any() else "D", axis=1)
    out["risk_level"], _, _ = zip(*[
        evaluate_risk(r["mtf_regime"], "Aligned", r["market_context"],
                      r["data_quality"], r["chip_stability_confidence"], settings)
        for _, r in out.iterrows()])
    out["action_signal"] = [
        generate_action(r["mtf_regime"], r["structural_regime"],
                        r["risk_level"], settings)
        for _, r in out.iterrows()]
    out["is_override"] = out["align_method"] == "tactical_override"
    out["target"] = [
        effective_position_cqs(r["mtf_regime"], r["risk_level"], settings,
                               catalyst_score=r["catalyst_score"],
                               tactical_override=r["is_override"])
        for _, r in out.iterrows()]
    # P0-A（新 1 号）：Legacy 决策列只能作为 Shadow Comparator。
    # 原列保留兼容旧研究脚本，但必须携带 SHADOW_ONLY 权威标记。
    out["legacy_action"] = out["action_signal"]
    out["legacy_target"] = out["target"]
    out["authority"] = "SHADOW_ONLY"
    out["non_certifiable"] = True
    out["engine_source"] = "legacy_comparator"
    # 时间止损：战术试多持仓超过 CQS 对应周数后强制归零
    out = out.sort_values(["stock_code", "week_end"])
    # 连续试多周数；周信号中断或新季度结构披露时重置（向量化分段累计）
    out["_prev_struct"] = out.groupby("stock_code")[
        "structural_available_date"].shift()
    out["_seg_reset"] = (~out["is_override"]) | (
        out["structural_available_date"] != out["_prev_struct"])
    out["_seg"] = out.groupby("stock_code")["_seg_reset"].cumsum()
    out["override_run_weeks"] = out.groupby(
        ["stock_code", "_seg"])["is_override"].cumsum().astype(float)
    out = out.drop(columns=["_prev_struct", "_seg_reset", "_seg"])
    out["time_stop_weeks"] = out["catalyst_score"].map(
        lambda sc: time_stop_weeks(sc, settings))
    # time_stop_high=None 表示不限时间止损 → 用极大值填充
    exceed = out["is_override"] & \
        (out["override_run_weeks"] > out["time_stop_weeks"].fillna(10 ** 9).astype(float))
    out.loc[exceed, "target"] = 0.0
    out["qcfp_score"] = out["mtf_regime"].map(
        lambda m: settings.get("fusion", {}).get("score_mapping", {}).get(m))

    out["decision_date"] = out["week_end"]
    # V18 下行风险层：DES + 风险下限 + 滞后解除 + 仓位单调性（需要周价格/日资金流证据）
    if weekly_kl is not None and not weekly_kl.empty:
        out = apply_downside_risk(out, weekly_kl, settings, daily=daily)
    else:
        out["des_score"] = 0
        out["des_band"] = "NORMAL"
        out["risk_floor"] = None
    cols = ["stock_code", "stock_name", "decision_date", "structural_regime",
            "c_state", "f_state", "p_state", "structural_available_date",
            "monthly_behavior_state",
            "tactical_signal", "cbi_score", "cbi_state", "cost_position",
            "q_trend_score", "q_position_52w",
            "chip_stability_confidence", "mtf_regime", "action_signal",
            "risk_level", "target", "qcfp_score", "market_context", "data_quality",
            "prev_f_state", "catalyst_score", "catalyst_type", "is_override",
            "time_stop_weeks", "override_run_weeks",
            "des_score", "des_band", "risk_floor",
            "legacy_action", "legacy_target", "authority",
            "non_certifiable", "engine_source"]
    return out[cols].reset_index(drop=True)


def build_evidence_timeline(structural, monthly, weekly, chip, idx_df,
                            settings, stocks=None, weekly_kl=None,
                            daily=None) -> pd.DataFrame:
    """正式 Evidence Timeline：只产出证据，不产出 target/action。

    与 canonical_replay 配合使用（P0-A 新 1 号）：
        build_evidence_timeline() → EvidenceSnapshot
            → canonical_replay() → evaluate() → DecisionSnapshot

    返回 build_signal_timeline 的完整证据列，但删除全部决策列
    （action_signal / target / legacy_action / legacy_target），
    使 Evidence Builder 不再拥有任何决策权。
    """
    signals = build_signal_timeline(
        structural, monthly, weekly, chip, idx_df, settings,
        stocks=stocks, weekly_kl=weekly_kl, daily=daily)
    decision_cols = [c for c in ("action_signal", "target",
                                 "legacy_action", "legacy_target",
                                 "authority", "non_certifiable",
                                 "engine_source")
                     if c in signals.columns]
    out = signals.drop(columns=decision_cols)
    out["evidence_authority"] = "EVIDENCE_ONLY"
    return out


def assert_evidence_no_decision_authority(signals: pd.DataFrame) -> dict:
    """P0-A 契约：正式路径禁止直接消费 Evidence 层的 target/action。

    若 DataFrame 含决策列，必须带 authority=SHADOW_ONLY（Legacy
    Comparator）或 canonical 来源列；否则抛 ValueError。
    """
    decision_cols = [c for c in ("action_signal", "target",
                                 "legacy_action", "legacy_target")
                     if c in (signals.columns if signals is not None
                              else [])]
    if not decision_cols:
        return {"decision_cols": [], "violation": False,
                "verdict": "EVIDENCE_ONLY"}
    authority = (signals["authority"].iloc[0]
                 if "authority" in signals.columns
                 and not signals.empty else "")
    canonical = ("canonical_target" in signals.columns
                 or "canonical_provenance" in signals.columns)
    if authority == "SHADOW_ONLY" or canonical:
        return {"decision_cols": decision_cols,
                "violation": False,
                "verdict": "SHADOW_COMPARATOR" if not canonical
                else "CANONICAL",
                "note": "Legacy 决策列仅供 Shadow Comparator，"
                        "非正式结果来源"}
    raise ValueError(
        "P0-A 违反：Evidence 层出现无 SHADOW_ONLY 标记的决策列 "
        f"{decision_cols}——只有 Canonical Governance 能产生正式 "
        "FinalTarget。")


def assert_all_inputs_asof(signals: pd.DataFrame, settings=None) -> int:
    """Evidence Timeline Contract（2.3）：每条输入的 usable_at <= decision_time

    检查信号面板中所有 *_available_date / *_asof 类列都不晚于决策日；
    违反即抛错（防止 Q/M/W/D/Flow/Market 任一输入"看着正确但时间越界"）。
    返回检查到的 as-of 列数（正常 = 0 违规）。
    """
    if signals is None or signals.empty:
        return 0
    dt = pd.to_datetime(signals["decision_date"], errors="coerce")
    asof_cols = [c for c in signals.columns
                 if c.endswith("_available_date") or c.endswith("_asof")]
    n_bad = 0
    for col in asof_cols:
        av = pd.to_datetime(signals[col], errors="coerce")
        bad = av.notna() & dt.notna() & (av > dt)
        n_bad += int(bad.sum())
        if bad.any():
            raise ValueError(
                f"Evidence Timeline Contract 违反：{col} > decision_date "
                f"共 {int(bad.sum())} 行（如 "
                f"{signals.loc[bad, 'decision_date'].head(3).tolist()}）")
    return len(asof_cols)
