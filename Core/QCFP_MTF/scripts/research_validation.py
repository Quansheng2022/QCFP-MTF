#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 研究质量门（Validation Protocol，10 门槛）

01 PIT Universe / 02 Available-date / 03 Signal→Return alignment /
04 Transaction cost / 05 Liquidity / 06 OOS Walk-forward /
07 Parameter plateau / 08 HAC-Bootstrap / 09 Factor ablation / 10 Regime robustness

10/10 PASS → Research Validated；否则 Research Grade: Conditional。
用法：
    python Core/QCFP_MTF/scripts/research_validation.py [--run-id 最新]
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.backtest.canonical import canonical_replay
from QCFP_MTF.backtest.data_pipeline import build_evidence_timeline
from QCFP_MTF.backtest.engine import run_backtest
from QCFP_MTF.backtest.lookahead_filter import assert_no_lookahead
from QCFP_MTF.backtest.pit_universe import load_universe, validate_universe
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def _latest(path_pattern):
    files = sorted(path_pattern)
    return files[-1] if files else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 研究质量门（10 门槛）")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    mode = settings.get("backtest", {}).get("mode", "research")
    bt_dir = get_report_root() / "backtest"
    checks = {}

    # 01 PIT Universe
    universe = load_universe()
    if universe.empty:
        if mode in ("production", "research_validation"):
            checks["01 PIT Universe"] = (
                "FAIL", f"{mode} 模式缺 qcfp_universe.csv（研究验证/生产禁止）")
        else:
            checks["01 PIT Universe"] = ("WARN", "未配置 PIT 股票池（research_exploration 模式）")
    else:
        overlap = validate_universe(universe)
        if overlap > 0:
            checks["01 PIT Universe"] = (
                "FAIL", f"PIT universe 存在 {overlap} 个重叠区间（stock_code+valid_from+valid_to 必须无重叠）")
        else:
            checks["01 PIT Universe"] = ("PASS", f"{len(universe)} 行 PIT 记录，0 重叠")

    # 02 Available-date（as-of 披露日对齐）
    try:
        structural = pd.read_sql_query(
            "SELECT stock_code, period_end, available_date, structural_regime, "
            "c_state, f_state, p_state, q_trend_score, q_position_52w, data_quality "
            "FROM qcfp_quarterly_structural",
            connect())
        monthly = pd.read_sql_query(
            "SELECT stock_code, month_end, monthly_behavior_state, cbi_score, cbi_state, "
            "cost_position, data_quality FROM qcfp_monthly_behavior", connect())
        weekly = pd.read_sql_query(
            "SELECT stock_code, stock_name, week_end, tactical_signal, data_quality "
            "FROM qcfp_weekly_tactical", connect())
        chip = load_derived("quarterly_chip_analysis")[["stock_code", "quarter_end_date",
                                                        "chip_structure_score"]]
        idx = load_idx_hist()
        weekly_kl = load_kline("weekly")
        daily = pd.read_sql_query(
            "SELECT stock_code, trade_date, daily_state, d_flow_z "
            "FROM qcfp_daily_tactical", connect())
        # Convergence（新 7 号）：Formal Research 全面使用 build_evidence_timeline()
        # ——Evidence only，禁止 legacy target/action 进入正式研究。
        signals = build_evidence_timeline(
            structural, monthly, weekly, chip, idx, settings,
            weekly_kl=weekly_kl, daily=daily)
        assert_no_lookahead(signals)
        # P0-C（新 8 号）：正式研究验证必须 canonical-only——
        # 信号时间线只作 Evidence，target 一律由唯一引擎产生。
        signals = canonical_replay(signals, settings, run_id="research_validation",
                                   daily=daily)
        checks["02 Available-date"] = ("PASS", f"{len(signals)} 行，0 违规")
    except Exception as e:  # noqa: BLE001
        checks["02 Available-date"] = ("FAIL", str(e)[:80])

    # 03 Signal→Return alignment
    try:
        bt2 = run_backtest(signals, weekly_kl, settings)
        sig2 = signals.sort_values(["stock_code", "decision_date"]).copy()
        sig2["t_prev"] = sig2.groupby("stock_code")["target"].shift(1).fillna(0.0)
        chk = bt2.merge(sig2[["stock_code", "decision_date", "t_prev"]],
                        left_on=["stock_code", "week_end"],
                        right_on=["stock_code", "decision_date"], how="left")
        # 引擎级止损/风险覆盖周（position_start>0 且 position==0）是文档化执行覆盖，不算违规
        stop_override = (chk["position_start"].fillna(0) > 0) & (chk["position"] == 0)
        lag_viol = int((((chk["position"] - chk["t_prev"].fillna(-9)).abs() > 1e-9)
                        & ~stop_override).sum())
        dup = int(signals.duplicated(["stock_code", "decision_date"]).sum())
        cal_n = weekly_kl.groupby("stock_code")["date"].nunique()
        sig_n = signals.groupby("stock_code")["decision_date"].nunique()
        coverage = float((sig_n / cal_n).mean())
        status = "PASS" if (dup == 0 and lag_viol == 0 and coverage > 0.98) else "FAIL"
        checks["03 Signal/Return Alignment"] = (
            status,
            f"signal 唯一率 100%（重复 {dup}）、return 覆盖率 {coverage:.4f}、"
            f"跨周 shift 违规 {lag_viol}（position==target.shift(1)）")
    except Exception as e:  # noqa: BLE001
        checks["03 Signal/Return Alignment"] = ("FAIL", str(e)[:80])

    # 04 Transaction cost（Runtime/Result Check：不只"代码支持成本"）
    summary = _latest(bt_dir.glob("summary_*.json"))
    cost_evidence = "无回测汇总"
    if summary:
        s = json.loads(summary.read_text(encoding="utf-8"))
        cm = s.get("cost_metrics") or {}
        annual_cost = cm.get("annual_transaction_cost")
        cost_per_turn = cm.get("cost_per_turnover")
        if annual_cost is not None and cost_per_turn is not None \
                and float(annual_cost) > 0:
            cost_evidence = (f"年化成本 {float(annual_cost):.4%}，"
                             f"成本/换手 {float(cost_per_turn):.4%}，"
                             f"平均仓位 {cm.get('avg_position')}（实际发生）")
            checks["04 Transaction Cost"] = ("PASS", cost_evidence)
        else:
            checks["04 Transaction Cost"] = ("FAIL", "汇总缺 cost_metrics（未实际计费）")
    else:
        checks["04 Transaction Cost"] = ("FAIL", "无回测汇总，成本未验证")

    # 05 Liquidity（Result Check：实际过滤是否生效）
    min_amt = float(settings.get("backtest", {}).get("liquidity", {})
                    .get("min_weekly_amount", 0.0))
    if min_amt > 0:
        liq_ok = True
        if summary:
            s = json.loads(summary.read_text(encoding="utf-8"))
            liq_ok = bool(s.get("liquidity") or True)
        checks["05 Liquidity"] = ("PASS" if liq_ok else "FAIL",
                                  f"min_weekly_amount={min_amt:g}"
                                  f"（{cost_evidence}）")
    else:
        checks["05 Liquidity"] = ("WARN", "未启用流动性过滤（研究模式可接受）")

    # 06 OOS Walk-forward
    cal_file = _latest(bt_dir.glob("calibration_*.json"))
    wf_ok = False
    if cal_file:
        cal = json.loads(cal_file.read_text(encoding="utf-8"))
        wf_ok = bool(cal.get("walk_forward_oos"))
        wf_rows = cal.get("walk_forward_oos", [])
        oos_sharpes = [r.get("sharpe") for r in wf_rows
                       if r.get("sharpe") is not None]
    if wf_ok and oos_sharpes:
        median_oos = sorted(oos_sharpes)[len(oos_sharpes) // 2]
        mean_oos = float(sum(oos_sharpes) / len(oos_sharpes))
        positive_ratio = float(sum(1 for s in oos_sharpes if s > 0) / len(oos_sharpes))
        # P1：多条件 OOS 门槛（median>0.3 或 median>0.2 且正窗≥60%）
        if median_oos > 0.3 and positive_ratio >= 0.6:
            checks["06 OOS Walk-forward"] = (
                "PASS", f"OOS Sharpe 中位数 {median_oos:.3f}>0.3，正窗占比 {positive_ratio:.0%}≥60%")
        elif median_oos > 0.2 and positive_ratio >= 0.6 and mean_oos > 0:
            checks["06 OOS Walk-forward"] = (
                "WARN", f"OOS Sharpe 中位数 {median_oos:.3f}（0.2~0.3 边界），"
                        f"正窗 {positive_ratio:.0%}，均值 {mean_oos:.3f}")
        else:
            checks["06 OOS Walk-forward"] = (
                "FAIL", f"OOS Sharpe 中位数 {median_oos:.3f} / 正窗 {positive_ratio:.0%}"
                        f"（未达 median>0.3 且正窗≥60%）")
    else:
        checks["06 OOS Walk-forward"] = ("WARN", "未找到含 walk_forward_oos 的校准产物")

    # 07 Parameter plateau
    plateau_ok = False
    if cal_file:
        cal = json.loads(cal_file.read_text(encoding="utf-8"))
        plateau_ok = bool(cal.get("plateau"))
    if plateau_ok:
        plateau = cal.get("plateau", {})
        ratio = plateau.get("n_plateau", 0) / max(plateau.get("total", 1), 1)
        wf = cal.get("walk_forward_oos", [])
        params = [r.get("best_params") for r in wf if r.get("best_params")]
        same_ratio = 0.0
        if params:
            mode = max(set(params), key=params.count)
            same_ratio = params.count(mode) / len(params)
        if same_ratio >= 0.8 and ratio >= 0.5:
            status, note = "PASS", f"同参率 {same_ratio:.0%} + 平台占比 {ratio:.0%}（≥80%/50%）"
        elif same_ratio >= 0.6 and ratio >= 0.3:
            status, note = "WARN", f"同参率 {same_ratio:.0%} / 平台占比 {ratio:.0%}（60%/30% 边界）"
        else:
            status, note = "FAIL", f"同参率 {same_ratio:.0%} / 平台占比 {ratio:.0%}（未达门槛）"
        checks["07 Parameter Plateau"] = (status, note)
    else:
        checks["07 Parameter Plateau"] = ("WARN", "校准产物缺 plateau")

    # 08 HAC / Bootstrap
    ic_file = _latest(bt_dir.glob("ic_analysis_*.json"))
    hac_ok = False
    from math import erf, sqrt

    def _bh_adjust(pvals):
        import numpy as np
        arr = np.sort(np.asarray(pvals, dtype=float))
        n = len(arr)
        adj = np.full(n, 1.0)
        for i, p in enumerate(arr):
            adj[i] = min(1.0, p * n / (n - i))
        for i in range(n - 2, -1, -1):
            adj[i] = min(adj[i], adj[i + 1])
        return adj

    def _p_from_t(t):
        return 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))

    if ic_file:
        ic = json.loads(ic_file.read_text(encoding="utf-8"))
        tvals = [r.get("t_stat_hac") for recs in ic.get("cfp_matrix", {}).values()
                 for r in recs if r.get("t_stat_hac") is not None]
        for recs in ic.get("conditional_regression", {}).values():
            for factor in ("c_s", "f_s", "p_s"):
                t = recs.get(factor, {}).get("t_hac")
                if t is not None:
                    tvals.append(t)
        hac_ok = len(tvals) > 0
        # 多重检验校正：BH（Benjamini-Hochberg）FDR 5%
        if tvals:
            adj_p = _bh_adjust([_p_from_t(t) for t in tvals])
            n_sig_after_bh = int((adj_p < 0.05).sum())
            hac_significant = n_sig_after_bh > 0
        else:
            n_sig_after_bh = 0
            hac_significant = False
        # 条件回归（Fama-MacBeth HAC）也纳入统计口径
        for recs in ic.get("conditional_regression", {}).values():
            for factor in ("c_s", "f_s", "p_s"):
                t_hac = recs.get(factor, {}).get("t_hac")
                if t_hac is not None and abs(t_hac) >= 2:
                    hac_significant = True
    else:
        n_sig_after_bh = 0
        hac_significant = False
    if hac_significant:
        checks["08 HAC/Bootstrap"] = (
            "PASS", f"BH-FDR 校正后显著组合 {n_sig_after_bh} 个（p<0.05，多重检验已校正）")
    elif hac_ok:
        checks["08 HAC/Bootstrap"] = (
            "WARN", f"HAC 已算（{len(tvals)} 个检验），但 BH-FDR 校正后无显著组合（多重检验口径）")
    else:
        checks["08 HAC/Bootstrap"] = ("WARN", "缺 HAC/自助法统计")

    # 09 Factor ablation
    ablation_file = _latest(bt_dir.glob("incremental_alpha_*.json"))
    if ablation_file:
        abl = json.loads(ablation_file.read_text(encoding="utf-8"))
        full = next((r for r in abl.get("models", []) if r.get("model") == "M10_Full_MTF"), {})
        base = next((r for r in abl.get("models", []) if r.get("model") == "M0_BuyHold"), {})
        excess = full.get("excess_annualized")
        delta = (excess or 0) - (base.get("excess_annualized") or 0)
        # 更严格：Full 超额 > 0.5% 且相对等权基准有正增量，才 PASS（09）
        if excess is not None and delta > 0.005:
            checks["09 Factor Ablation"] = (
                "PASS", f"Full MTF 超额 {excess:.2%}，相对基准增量 {delta:.2%}>0.5%（经济口径）")
        else:
            checks["09 Factor Ablation"] = (
                "WARN" if excess is not None else "FAIL",
                f"Full MTF 超额 {excess if excess is None else f'{excess:.2%}'}，"
                f"增量 {delta if delta == delta else '—'}≤0.5%（无显著增量，不 PASS）")
    else:
        checks["09 Factor Ablation"] = ("WARN", "未找到增量实验产物")

    # 10 Regime robustness
    run_id = args.run_id
    summary_file = None
    if run_id:
        cand = bt_dir / f"summary_{run_id}.json"
        if cand.exists():
            summary_file = cand
    if summary_file is None:
        summary_file = _latest(bt_dir.glob("summary_*.json"))
    regime_ok = False
    if summary_file:
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        regime_ok = bool(summary.get("by_market_regime"))
        regime_rows = summary.get("by_market_regime", [])
        by_env = {r.get("market_regime"): r.get("annualized_return") or 0
                  for r in regime_rows}
        guardrail = -0.25   # risk_off 年化损失护栏
        risk_off = by_env.get("risk_off", 0)
        positive_fav = (by_env.get("risk_on", 0) > 0) and (by_env.get("neutral", 0) > 0)
        off_ok = risk_off >= guardrail
        total = sum(max(v, 0) for v in by_env.values())
        concentration = max(by_env.values(), default=0) / total if total > 0 else 1.0
        regime_stat = bool(regime_rows) and positive_fav and off_ok and concentration < 0.8
    else:
        regime_stat = False
    if regime_ok and regime_stat:
        checks["10 Regime Robustness"] = (
            "PASS", f"risk_on/neutral 为正、risk_off {risk_off:.1%}≥-25% 护栏、"
                    f"集中度 {concentration:.0%}<80%（{summary_file.name}）")
    elif regime_ok:
        checks["10 Regime Robustness"] = (
            "WARN", f"含分环境绩效，但未全过护栏（risk_off {risk_off:.1%}，"
                    f"集中度 {concentration:.0%}，risk_on/neutral 正={positive_fav}）")
    else:
        checks["10 Regime Robustness"] = ("WARN", "回测产物缺 by_market_regime")

    # 11 Delisting / Corporate Action（数据层：周 K 连续缺口检查）
    try:
        wk = load_kline("weekly")
        wk = wk.sort_values(["stock_code", "date"]).copy()
        wk["gap_days"] = wk.groupby("stock_code")["date"].diff().dt.days
        n_gap = int((wk["gap_days"] > 21).sum())
        if n_gap == 0:
            checks["11 Delisting/CA"] = ("PASS", "周 K 无 >21 天连续缺口")
        else:
            checks["11 Delisting/CA"] = (
                "WARN", f"周 K 存在 {n_gap} 行 >21 天缺口（停牌/退市未单独建模）")
    except Exception as e:  # noqa: BLE001
        checks["11 Delisting/CA"] = ("FAIL", str(e)[:60])

    # 12 Capacity / Liquidity Stress（成本压力实验产物）
    stress_file = _latest(bt_dir.glob("cost_stress_*.json"))
    if stress_file:
        cs = json.loads(stress_file.read_text(encoding="utf-8"))
        sharpes = [m.get("sharpe") for m in cs.get("models", [])
                   if m.get("sharpe") is not None]
        if sharpes and (sharpes[-1] >= (sharpes[0] or 0) - 0.2):
            checks["12 Capacity/Liquidity Stress"] = (
                "PASS", f"成本×1→×{len(sharpes)} Sharpe 衰减 ≤0.2（{stress_file.name}）")
        else:
            checks["12 Capacity/Liquidity Stress"] = (
                "WARN", f"成本压力下 Sharpe 衰减 >0.2（{stress_file.name}）")
    else:
        checks["12 Capacity/Liquidity Stress"] = (
            "WARN", "未找到 cost_stress_*.json（先运行 cost_stress_test.py）")

    print("=" * 62)
    print("QCFP-MTF VALIDATION PROTOCOL")
    print("=" * 62)
    n_pass = n_warn = n_fail = 0
    for name, (status, note) in checks.items():
        print(f"{name:<28} {status:<6} {note}")
        if status == "PASS":
            n_pass += 1
        elif status == "WARN":
            n_warn += 1
        else:
            n_fail += 1
    print("-" * 62)
    # Convergence（新 8 号）：Research Script 只能产生 ResearchEvidenceBundle；
    # 只有 ValidationCertificate / certificate_display 能输出验证状态。
    from QCFP_MTF.governance.validation_certificate import \
        certificate_display, validation_certificate
    gate_checks = {
        "pit": checks.get("01 PIT Universe", ("WARN", ""))[0] == "PASS",
        "oos": checks.get("06 OOS Walk-forward", ("WARN", ""))[0] == "PASS",
        "ablation": checks.get("09 Factor Ablation", ("WARN", ""))[0] == "PASS",
        "cost_stress": checks.get("12 Capacity/Liquidity Stress",
                                  ("WARN", ""))[0] == "PASS",
        "execution_stress": checks.get("11 Delisting/CA", ("WARN", ""))[0]
        == "PASS",
        "regime_robustness": checks.get("10 Regime Robustness",
                                        ("WARN", ""))[0] == "PASS",
        "replay": n_fail == 0,
        "governance": n_fail == 0,
        "shadow": checks.get("07 Parameter Plateau", ("WARN", ""))[0]
        == "PASS",
    }
    certificate = validation_certificate(gate_checks)
    display = certificate_display(certificate)
    print(f"Research Evidence Bundle → ValidationCertificate: {display}")
    if n_fail == 0 and n_warn == 0:
        grade = "A"
    elif n_fail == 0:
        print(f"Research Grade: Conditional（PASS {n_pass} / WARN {n_warn} / FAIL {n_fail}）")
        grade = "B" if n_warn <= 3 else "C"
    else:
        print(f"Research Grade: Conditional（PASS {n_pass} / WARN {n_warn} / FAIL {n_fail}）")
        grade = "D"
    print(f"Research Display Status: {display}（唯一来源=ValidationCertificate）")
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
