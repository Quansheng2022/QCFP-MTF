#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 方案 B 触发器宽度敏感性回测

对比 decision.tactical_override.min_trigger 变体：
    [Breakout] / [Breakout, Pullback] / [Breakout, Pullback, Consolidation] / []（任意触发）
在 空头季度结构 + 52W 极低位 + CQS 动态仓位 + 时间止损 下：
    - 全市场组合绩效（年化 / Sharpe / 回撤 / 换手 / 暴露）
    - 重点股票（--focus 默认 01951）2024-02~10 波段收益、持仓周数、试多周数
    - override 触发统计（行数 / 股票数 / 平均目标仓位 / 时间止损归零周数）

用法：
    python Core/QCFP_MTF/scripts/trigger_sensitivity.py
        [--focus 01951] [--start 2021-01-01] [--end 2026-08-21]
        [--variants "Breakout;B+Pullback;B+Pullback+Consolidation;ANY"]
        [--buffers 0.02,0.05,0.08]
"""

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.performance import evaluate
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import _deep_merge, load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def _variants(spec: str):
    """'OFF;Breakout;B+Pullback;B+P+C;ANY' -> [(label, trigger_list_or_None)]"""
    out = []
    for token in (x.strip() for x in spec.split(";") if x.strip()):
        if token.upper() == "OFF":
            out.append(("OFF(禁用方案B)", None))
        elif token.upper() == "ANY":
            out.append(("ANY(全部触发)", []))
        elif token == "B":
            out.append(("Breakout", ["Breakout"]))
        elif token == "B+Pullback":
            out.append(("Breakout+Pullback", ["Breakout", "Pullback"]))
        elif token == "B+P+C":
            out.append(("Breakout+Pullback+Consolidation",
                        ["Breakout", "Pullback", "Consolidation"]))
        else:
            out.append((token, [x.strip() for x in token.split("+") if x.strip()]))
    return out


def _wave_metrics(signals, bt, focus, wave_start, wave_end):
    wave_sig = signals[(signals["stock_code"] == focus) &
                       (signals["decision_date"] >= wave_start) &
                       (signals["decision_date"] <= wave_end)]
    wave_bt = bt[(bt["stock_code"] == focus) &
                 (bt["week_end"] >= wave_start) &
                 (bt["week_end"] <= wave_end)]
    wave_ret = float((1 + wave_bt["pnl"]).prod() - 1) if len(wave_bt) else None
    time_stop_cap = 10 ** 9
    stopped = wave_sig["is_override"] & (
        wave_sig["override_run_weeks"] >
        wave_sig["time_stop_weeks"].fillna(time_stop_cap).astype(float))
    return {
        "wave_return": round(wave_ret, 6) if wave_ret is not None else None,
        "wave_pos_weeks": int((wave_bt["position"] > 0).sum()),
        "wave_weeks": int(len(wave_bt)),
        "wave_override_weeks": int(wave_sig["is_override"].sum()),
        "wave_time_stopped_weeks": int(stopped.sum()),
        "wave_avg_override_target": round(float(
            wave_sig.loc[wave_sig["is_override"], "target"].mean()), 4)
        if wave_sig["is_override"].any() else None,
    }


def _html_table(result, focus, wave_start, wave_end, wave_bh) -> str:
    """自包含 HTML：敏感性结果对比表（按组合 Sharpe 降序，零外部依赖）"""
    rows_html = []
    df = result.sort_values("sharpe", ascending=False, na_position="last")
    for _, r in df.iterrows():
        wave = r.get(f"{focus}_wave_return")
        wave_td = f"<td>{wave:.2%}</td>" if wave is not None else "<td>—</td>"
        rows_html.append(
            "<tr>"
            f"<td>{r['variant']}</td>"
            f"<td>{r['buffer_pct']:.0%}</td>"
            f"<td>{r['sharpe']:.4f}</td>"
            f"<td>{r['annualized_return']:.2%}</td>"
            f"<td>{r['max_drawdown']:.2%}</td>"
            f"<td>{r['annual_turnover']:.2f}</td>" + wave_td +
            f"<td>{int(r[f'{focus}_wave_pos_weeks'])}/{int(r[f'{focus}_wave_weeks'])}</td>"
            "</tr>")
    body = "".join(rows_html)
    return f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>QCFP-MTF 触发器×缓冲敏感性</title>
<style>
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;margin:24px;color:#1f2937}}
h1{{font-size:19px}} h2{{font-size:15px}}
table{{border-collapse:collapse;margin:10px 0;width:100%;font-size:13px}}
td,th{{border:1px solid #d1d5db;padding:5px 9px;text-align:right}}
th{{background:#f3f4f6;text-align:center}}
td:first-child,th:first-child{{text-align:left}}
.best{{background:#ecfdf5;font-weight:600}}
</style></head><body>
<h1>QCFP-MTF 方案 B 敏感性（触发器 × 移动止损缓冲）</h1>
<p>重点股票：{focus}，波段 {wave_start} ~ {wave_end}，买入持有 {wave_bh:.2%}；按组合 Sharpe 降序。</p>
<table>
<tr><th>触发器变体</th><th>buffer_pct</th><th>Sharpe</th><th>组合年化</th>
<th>最大回撤</th><th>年化换手</th><th>{focus} 波段收益</th><th>波段持仓周</th></tr>
{body}
</table>
<p>说明：移动止损为收盘跌破建仓周 K 线最低价×(1-buffer)；时间止损仅纯脉冲（CQS&lt;0）保留 2 周。</p>
</body></html>"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 方案 B 触发器宽度敏感性")
    parser.add_argument("--focus", default="01951", help="重点观察股票")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument(
        "--variants", default="OFF;Breakout;B+Pullback;B+P+C;ANY",
        help="分号分隔变体：OFF / Breakout / B+Pullback / B+P+C / ANY")
    parser.add_argument(
        "--buffers", default="0.02,0.05,0.08",
        help="逗号分隔的移动止损缓冲（buffer_pct），默认 0.02,0.05,0.08")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    logger = setup_logger("trigger_sensitivity",
                          log_file="trigger_sensitivity.log", mode="a")
    logger.info("=== 方案 B 触发器宽度敏感性启动 ===")

    structural = pd.read_sql_query(
        "SELECT stock_code, stock_name, period_end, available_date, structural_regime, "
        "c_state, f_state, p_state, q_trend_score, q_position_52w, data_quality "
        "FROM qcfp_quarterly_structural", connect())
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
    end = args.end or weekly["week_end"].max()

    wave_start, wave_end = "2024-02-02", "2024-10-31"
    wf = weekly_kl[weekly_kl["stock_code"] == args.focus].copy()
    wf["week_end"] = pd.to_datetime(wf["date"]).dt.strftime("%Y-%m-%d")
    wf = wf.sort_values("week_end")
    wf["ret"] = wf.groupby("stock_code")["close"].pct_change()
    wave_bh = (1 + wf[(wf["week_end"] >= wave_start) &
                      (wf["week_end"] <= wave_end)]["ret"].fillna(0)).prod() - 1
    logger.info(f"{args.focus} 波段买入持有（{wave_start}~{wave_end}）: {wave_bh:.2%}")

    base_cfg = settings.get("decision", {}).get("tactical_override", {})
    buffer_list = [float(x) for x in args.buffers.split(",") if x.strip()]
    rows = []
    for label, trigger_list in _variants(args.variants):
        for buf in buffer_list:
            variant_settings = copy.deepcopy(settings)
            if trigger_list is None:
                variant_settings["decision"]["tactical_override"] = {
                    **base_cfg, "enabled": False}
            else:
                variant_settings["decision"]["tactical_override"] = {
                    **base_cfg, "min_trigger": trigger_list}
            variant_settings["decision"]["stop_loss_policy"] = {
                **variant_settings.get("decision", {}).get("stop_loss_policy", {}),
                "buffer_pct": buf}
            signals = build_signal_timeline(structural, monthly, weekly, chip, idx,
                                            variant_settings,
                                            weekly_kl=weekly_kl, daily=daily)
            bt = run_backtest(signals, weekly_kl, variant_settings,
                              start=args.start, end=end)
            port = portfolio_returns(bt)
            perf = evaluate(port["portfolio_return"], turnover=port["avg_turnover"])
            ov = signals[signals["is_override"]]
            time_stop_cap = 10 ** 9
            stopped = ov["override_run_weeks"] > \
                ov["time_stop_weeks"].fillna(time_stop_cap).astype(float)
            wave = _wave_metrics(signals, bt, args.focus, wave_start, wave_end)
            rows.append({
                "variant": label,
                "buffer_pct": buf,
                "min_trigger": ("DISABLED" if trigger_list is None
                                else json.dumps(trigger_list, ensure_ascii=False)),
                "annualized_return": perf.get("annualized_return"),
                "sharpe": perf.get("sharpe"),
                "sortino": perf.get("sortino"),
                "calmar": perf.get("calmar"),
                "max_drawdown": perf.get("max_drawdown"),
                "annual_turnover": perf.get("annual_turnover"),
                "avg_exposure": round(float(bt["position"].mean()), 4),
                "n_override_rows": int(len(ov)),
                "n_override_stocks": int(ov["stock_code"].nunique()),
                "n_time_stopped_rows": int(stopped.sum()),
                "avg_override_target": round(float(ov["target"].mean()), 4)
                if len(ov) else None,
                f"{args.focus}_wave_return": wave["wave_return"],
                f"{args.focus}_wave_pos_weeks": wave["wave_pos_weeks"],
                f"{args.focus}_wave_weeks": wave["wave_weeks"],
                f"{args.focus}_wave_override_weeks": wave["wave_override_weeks"],
                f"{args.focus}_wave_time_stopped_weeks": wave["wave_time_stopped_weeks"],
                f"{args.focus}_wave_avg_override_target": wave["wave_avg_override_target"],
            })
            wv = f"{wave['wave_return']:.2%}" if wave["wave_return"] is not None else "—"
            logger.info(
                f"{label} @ buf={buf:.0%}: 组合年化 {perf['annualized_return']:.2%}  "
                f"Sharpe {perf['sharpe']}  回撤 {perf['max_drawdown']:.2%}  "
                f"换手 {perf['annual_turnover']:.2f}  | 试多 {len(ov)} 行/"
                f"{ov['stock_code'].nunique()} 股  | {args.focus} 波段 {wv} "
                f"（持仓 {wave['wave_pos_weeks']}/{wave['wave_weeks']} 周，"
                f"试多 {wave['wave_override_weeks']} 周）")

    result = pd.DataFrame(rows)
    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"trigger_sensitivity_{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "focus": args.focus,
                    "wave": {"start": wave_start, "end": wave_end,
                             "buy_hold": round(float(wave_bh), 6)},
                    "variants": result.to_dict(orient="records")},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result.to_csv(report_root / f"trigger_sensitivity_{stamp}.csv",
                  index=False, encoding="utf-8-sig")
    (report_root / f"trigger_sensitivity_{stamp}.html").write_text(
        _html_table(result, args.focus, wave_start, wave_end, wave_bh),
        encoding="utf-8")
    if not result.empty:
        by_sharpe = result.sort_values("sharpe", ascending=False, na_position="last")
        logger.info("=== 按组合 Sharpe 排序（Top 3）===")
        for _, r in by_sharpe.head(3).iterrows():
            wv = r.get(f"{args.focus}_wave_return")
            logger.info(
                f"  {r['variant']} @ buf={r['buffer_pct']:.0%}: Sharpe {r['sharpe']}  "
                f"年化 {r['annualized_return']:.2%}  回撤 {r['max_drawdown']:.2%}  | "
                f"{args.focus} 波段 {wv:.2%}" if wv is not None
                else f"  {r['variant']} @ buf={r['buffer_pct']:.0%}: Sharpe {r['sharpe']}  "
                f"年化 {r['annualized_return']:.2%}  回撤 {r['max_drawdown']:.2%}")
        wave_col = f"{args.focus}_wave_return"
        best_wave = result.loc[result[wave_col].fillna(-9).idxmax()]
        logger.info(
            f"{args.focus} 波段最优: {best_wave['variant']} @ buf={best_wave['buffer_pct']:.0%} "
            f"→ {best_wave[wave_col]:.2%}（买入持有 {wave_bh:.2%}）")
    logger.info(
        f"敏感性报告已保存: Report/QCFP_MTF/backtest/trigger_sensitivity_{stamp}.{{json,csv,html}}")
    logger.info("trigger_sensitivity 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
