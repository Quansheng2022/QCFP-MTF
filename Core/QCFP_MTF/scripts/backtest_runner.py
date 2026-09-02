#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF P6 —— 回测运行器

构建防 Look-ahead 信号时间线 → 向量化回测 → 绩效/分层/扩展窗口
→ 写 qcfp_backtest_results + 回测报告

用法：
    python Core/QCFP_MTF/scripts/backtest_runner.py [--stock 00700]
        [--start 2021-01-01] [--end 2026-08-14] [--run-id bt_20260820]
"""

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

import pandas as pd

from QCFP_MTF.backtest.cross_validation import run_expanding, rolling_oos_evaluation
from QCFP_MTF.backtest.data_pipeline import (assert_all_inputs_asof,
                                             build_signal_timeline)
from QCFP_MTF.backtest.engine import portfolio_returns, run_backtest
from QCFP_MTF.backtest.benchmark import buy_hold_returns, excess_stats, hsi_returns
from QCFP_MTF.backtest.lookahead_filter import assert_no_lookahead
from QCFP_MTF.backtest.performance import by_year, evaluate
from QCFP_MTF.backtest.portfolio_constraints import apply_portfolio_governance
from QCFP_MTF.backtest.research_gate import evaluate_research_gate
from QCFP_MTF.backtest.pit_universe import (filter_by_universe,
                                            filter_price_universe, load_universe,
                                            universe_incomplete)
from QCFP_MTF.decision.versions import (DECISION_RULE_VERSION,
                                        MODEL_VERSION)
from QCFP_MTF.backtest.portfolio_risk import portfolio_risk
from QCFP_MTF.backtest.robustness import by_market_regime
from QCFP_MTF.backtest.run_status import cost_metrics, disclosure_mode, run_status
from QCFP_MTF.common.db import connect
from QCFP_MTF.common.logger import setup_logger
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import get, load_qcfp_settings


def canonical_only_gate(engine_source, shadow_comparator=False) -> tuple:
    """P0-1 Canonical-only 门：
        canonical → (True, 'canonical')
        legacy + shadow_comparator → (True, 'legacy_shadow_comparator')
        legacy 无显式声明 → (False, 'legacy_requires_shadow_comparator')
    """
    src = str(engine_source or "canonical")
    if src == "canonical":
        return True, "canonical"
    if src == "legacy":
        if shadow_comparator:
            return True, "legacy_shadow_comparator"
        return False, "legacy_requires_shadow_comparator"
    return False, f"unknown_engine:{src}"
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 回测运行器")
    parser.add_argument("--stock", help="只回测指定股票")
    parser.add_argument("--start", default="2021-01-01", help="回测开始（默认 2021-01-01）")
    parser.add_argument("--end", default=None, help="回测结束（默认最新）")
    parser.add_argument("--run-id", default=None, help="回测运行标识")
    parser.add_argument("--dry-run", action="store_true", help="不写库")
    parser.add_argument("--engine", choices=["legacy", "canonical"],
                        default=None,
                        help="legacy=旧管道 target；canonical=唯一决策引擎 target")
    parser.add_argument("--shadow-comparator", action="store_true",
                        help="显式声明 legacy 仅供 Shadow Comparator（非正式结果）")
    parser.add_argument("--constraints", action="store_true",
                        help="启用组合层暴露约束（单股≤30%、行业≤50%、总暴露≤100%）")
    parser.add_argument("--require-universe", action="store_true",
                        help="PIT 股票池缺失时报错（正式回测模式）")
    args = parser.parse_args(argv)

    settings = load_qcfp_settings()
    model_version = get(settings, "model.version", MODEL_VERSION)
    if args.run_id:
        run_id = args.run_id
    else:
        base = f"bt_{datetime.now():%Y%m%d}"
        run_id = base
        n = 2
        while (get_report_root() / "backtest"
               / f"equity_{run_id}_{args.stock}.csv" if args.stock
               else get_report_root() / "backtest" / f"equity_{run_id}.csv").exists():
            run_id = f"{base}_{n}"
            n += 1
    logger = setup_logger("backtest_runner",
                          log_file=f"backtest_runner_{args.stock}.log" if args.stock
                          else "backtest_runner.log", mode="a")
    logger.info(f"=== 回测启动 run_id={run_id} 股票={args.stock or '全部'} "
                f"{args.start} ~ {args.end or '最新'} ===")

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

    stocks = [args.stock] if args.stock else None
    signals = build_signal_timeline(structural, monthly, weekly, chip, idx,
                                    settings, stocks=stocks,
                                    weekly_kl=weekly_kl, daily=daily)
    if signals.empty:
        logger.error("无可回测信号")
        return 1
    assert_no_lookahead(signals)
    logger.info(f"信号时间线 {len(signals)} 行，Look-ahead 检查通过")
    assert_all_inputs_asof(signals)
    logger.info("Evidence Timeline Contract 检查通过（所有输入 usable_at ≤ decision_time）")
    universe = load_universe()
    mode = settings.get("backtest", {}).get("mode", "research")
    strict_pit = mode in ("research_validation", "production")
    incomplete_stocks = universe_incomplete(universe) if not universe.empty else []
    if not universe.empty:
        signals = filter_by_universe(signals, universe, strict=strict_pit)
        logger.info(f"PIT 股票池过滤后 {len(signals)} 行")
        if incomplete_stocks:
            logger.warning(
                f"PIT universe 记录不完整 {len(incomplete_stocks)} 只"
                f"（如 {','.join(incomplete_stocks[:5])}）→ "
                f"{'strict 过滤已剔除' if strict_pit else 'exploration 按 valid-forever'}")
    else:
        if args.require_universe or mode == "production":
            logger.error("正式回测要求 Config/qcfp_universe.csv（PIT 股票池），缺失禁止产出绩效")
            return 2
        logger.warning("未配置 qcfp_universe.csv，回退为信号表全部股票（研究模式，存在幸存者偏差风险）")
    # P0：基准与策略同口径——Buy&Hold 也只用 PIT Universe 内股票
    bench_kl = filter_price_universe(weekly_kl, universe) if not universe.empty else weekly_kl

    engine_source = args.engine or settings.get("backtest", {}).get(
        "engine_source", "canonical")
    engine_ok, engine_mode = canonical_only_gate(
        engine_source, args.shadow_comparator)
    if not engine_ok:
        logger.error(
            "P0-1 Canonical-only：legacy 引擎已禁用为正式回测来源；"
            "如需 Shadow Comparator 对比，必须显式加 --shadow-comparator")
        return 3
    if engine_mode == "legacy_shadow_comparator":
        logger.warning(
            "legacy 引擎仅供 Shadow Comparator 使用，不是正式结果来源")
    run_id = args.run_id or f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if engine_source == "canonical":
        from QCFP_MTF.backtest.canonical import canonical_replay
        from QCFP_MTF.decision.decision_ledger import record_snapshot
        logger.info("Canonical Engine 重放：target 由唯一决策引擎产生")
        sig_c, snap_objs = canonical_replay(
            signals, settings, run_id=run_id, daily=daily,
            return_snapshots=True)
        if args.stock:
            sig_c = sig_c[sig_c["stock_code"] == args.stock]
        # 写入决策台账（不写交易，仅事实源）
        if not args.dry_run:
            from QCFP_MTF.common.db import connect as _connect
            conn = _connect()
            try:
                for s in snap_objs:
                    record_snapshot(conn, s, run_id, settings=settings)
            finally:
                conn.close()
            logger.info(f"决策台账已写入 {len(snap_objs)} 条"
                        f"（run_id={run_id}）")
        signals = sig_c
    logger.info(f"回测引擎源：{engine_source}")

    if args.constraints:
        sector_map = {}
        try:
            c2 = connect()
            try:
                for r in c2.execute(
                        "SELECT stock_code, sector FROM hk_stock_info"):
                    if r["sector"]:
                        sector_map[str(r["stock_code"]).zfill(5)] = r["sector"]
            finally:
                c2.close()
        except Exception:
            sector_map = {}
        pc = dict(settings.get("backtest", {}).get(
            "portfolio_constraints", {}))
        pc["enabled"] = True
        signals = apply_portfolio_governance(
            signals, {"backtest": {"portfolio_constraints": pc}}, sector_map)
        logger.info("组合级治理已应用"
                    "（单股/行业/总暴露 + 现金储备 + 总风险预算 + 高相关上限）")

    bt = run_backtest(signals, weekly_kl, settings, start=args.start, end=args.end)
    if bt.empty:
        logger.error("回测结果为空")
        return 1

    port = portfolio_returns(bt).set_index("week_end")
    regime_map = bt.groupby("week_end")["market_regime"].first()
    port["market_regime"] = regime_map.reindex(port.index).fillna("neutral")
    perf = evaluate(port["portfolio_return"], turnover=port["avg_turnover"])
    logger.info("=== 总体绩效 ===")
    logger.info(f"  区间 {bt['week_end'].min()} ~ {bt['week_end'].max()}，"
                f"样本 {perf['n']} 周")
    logger.info(f"  累计 {perf['total_return']:.2%}  年化 {perf['annualized_return']:.2%}  "
                f"Sharpe {perf['sharpe']}  Sortino {perf['sortino']}  "
                f"Calmar {perf['calmar']}  最大回撤 {perf['max_drawdown']:.2%}  "
                f"年化换手 {perf['annual_turnover']:.2f}")

    by_year_df = by_year(port["portfolio_return"], port.index)
    regime_df = by_market_regime(port["portfolio_return"], port["market_regime"],
                                 turnover=port["avg_turnover"])
    expand_df = run_expanding(signals, weekly_kl, settings, args.start,
                              args.end or bt["week_end"].max(), step_days=365)
    oos_df = rolling_oos_evaluation(signals, weekly_kl, settings, args.start,
                                    args.end or bt["week_end"].max())
    bench_bh = buy_hold_returns(bench_kl).reindex(port.index)
    bench_hsi = hsi_returns(idx, port.index)
    excess_bh = excess_stats(port["portfolio_return"], bench_bh)
    excess_hsi = excess_stats(port["portfolio_return"], bench_hsi)
    exposure = bt.groupby("week_end")["position"].mean().reindex(port.index)
    risk = portfolio_risk(port["portfolio_return"], exposure)
    logger.info("=== 分年度 ===")
    for _, r in by_year_df.iterrows():
        logger.info(f"  {int(r['year'])}: 年化 {r['annualized_return']:.2%}  "
                    f"Sharpe {r['sharpe']}  回撤 {r['max_drawdown']:.2%}")
    logger.info("=== 市场环境分层 ===")
    for _, r in regime_df.iterrows():
        logger.info(f"  {r['market_regime']}: 年化 {r['annualized_return']:.2%}  "
                    f"Sharpe {r['sharpe']}  胜率 {r['win_rate']}")
    logger.info("=== Rolling OOS（固定参数，分测试窗）===")
    for _, r in oos_df.iterrows():
        logger.info(f"  {r['window']}: 年化 {r['annualized_return']:.2%}  "
                    f"Sharpe {r['sharpe']}  回撤 {r['max_drawdown']:.2%}")
    logger.info("=== Benchmark / 超额收益 ===")
    logger.info(f"  等权买入持有基准：年化超额 {excess_bh.get('excess_annualized'):.2%}  "
                f"IR {excess_bh.get('information_ratio')}  相关性 {excess_bh.get('correlation')}")
    logger.info(f"  恒指基准：年化超额 {excess_hsi.get('excess_annualized'):.2%}  "
                f"IR {excess_hsi.get('information_ratio')}  相关性 {excess_hsi.get('correlation')}")
    logger.info(f"  组合风险：VaR95 {risk.get('var95'):.2%}  年化波动 {risk.get('annualized_vol'):.2%}  "
                f"平均暴露 {risk.get('avg_exposure'):.1%}  现金占比 {risk.get('cash_ratio'):.1%}")
    rstatus = run_status(settings, universe.empty, incomplete_stocks)
    cm = cost_metrics(bt)
    logger.info(f"RUN STATUS: {rstatus['status']}（{'；'.join(rstatus['checks'])}）")
    logger.info(f"成本口径：毛换手 {cm['annual_gross_turnover']:.2f}  交易成本 "
                f"{cm['annual_transaction_cost']:.4%}  成本/换手 "
                f"{cm['cost_per_turnover'] or float('nan'):.2%}  平均仓位 {cm['avg_position']:.1%}")

    report_root = get_report_root() / "backtest"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    fname = f"{run_id}_{args.stock}" if args.stock else run_id
    bt.to_csv(report_root / f"equity_{fname}.csv", index=False, encoding="utf-8-sig")
    summary = {
        "run_id": run_id, "model_version": model_version,
        "stock": args.stock, "start": args.start, "end": args.end or bt["week_end"].max(),
        "overall": perf, "by_year": by_year_df.to_dict(orient="records"),
        "by_market_regime": regime_df.to_dict(orient="records"),
        "expanding_windows": expand_df.to_dict(orient="records"),
        "rolling_oos_evaluation": oos_df.to_dict(orient="records"),
        "benchmark": {"buy_hold": excess_bh, "hsi": excess_hsi},
        "portfolio_risk": risk,
        "run_status": rstatus,
        "pit_disclosure_mode": disclosure_mode(settings),
        "pit_grade": rstatus.get("pit_grade"),
        "config_hash": hashlib.sha1(
            json.dumps(settings, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12],
        "cost_model_version": "directional_v2",
        "cost_metrics": cm,
    }
    summary["research_gate"] = evaluate_research_gate(
        summary, {"cost_stress_breakeven": None, "t_plus_1_verified": True,
                  "ledger_ok": True,
                  "model_version": model_version,
                  "rule_version": DECISION_RULE_VERSION,
                  "schema_version": "DECISION-1.1"})
    logger.info(
        f"RESEARCH GATE: {summary['research_gate']['overall']}"
        f"（{summary['research_gate']['status_label']}）"
        f"——{' '.join(g['gate'] + ':' + g['status']
                       for g in summary['research_gate']['gates'])}")
    (report_root / f"summary_{fname}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info(f"报告已保存: Report/QCFP_MTF/backtest/{run_id}")
    # P3 研究清单（Research Manifest）：run_id → 代码/配置/数据/口径 可追溯
    import hashlib as _hash
    from QCFP_MTF.common.db import connect as _connect
    _hc = _connect()
    try:
        snap = {t: _hc.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("qcfp_quarterly_structural", "qcfp_monthly_behavior",
                          "qcfp_weekly_tactical", "qcfp_daily_tactical",
                          "qcfp_mtf_decision")}
    finally:
        _hc.close()
    code_files = [
        PROJECT_ROOT / "Core" / "QCFP_MTF" / "backtest" / "engine.py",
        PROJECT_ROOT / "Core" / "QCFP_MTF" / "backtest" / "data_pipeline.py",
        PROJECT_ROOT / "Core" / "QCFP_MTF" / "backtest" / "cost_model.py",
        PROJECT_ROOT / "Core" / "QCFP_MTF" / "backtest" / "run_status.py",
        PROJECT_ROOT / "Core" / "QCFP_MTF" / "decision" / "downside_risk.py",
    ]
    code_hash = _hash.sha1()
    for f in code_files:
        if f.exists():
            code_hash.update(f.read_bytes())
    manifest = {
        "run_id": run_id, "model_version": model_version,
        "git_commit": "n/a（非 git 工作区）",
        "config_hash": summary.get("config_hash"),
        "code_hash": code_hash.hexdigest()[:12],
        "data_snapshot": {k: v for k, v in snap.items()},
        "pit_mode": summary.get("pit_disclosure_mode"),
        "pit_grade": summary.get("pit_grade"),
        "universe_version": "none" if universe.empty else f"{len(universe)} 行 PIT",
        "start": args.start, "end": args.end or bt["week_end"].max(),
        "cost_model_version": summary.get("cost_model_version"),
        "parameter_hash": summary.get("config_hash"),
    }
    (report_root / f"research_manifest_{fname}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info(f"研究清单已保存: research_manifest_{fname}.json")

    if not args.dry_run:
        conn = connect()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = [(r["stock_code"], r["week_end"], r["action_signal"],
                     r["position"], r["pnl"], r["mtf_regime"], r["market_regime"],
                     model_version, run_id, now)
                    for _, r in bt.iterrows()]
            conn.executemany(
                """INSERT INTO qcfp_backtest_results
                   (stock_code, signal_date, action_signal, position, pnl,
                    mtf_regime, market_regime, model_version, run_id, update_time)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""", rows)
            conn.commit()
            logger.info(f"已写入 qcfp_backtest_results {len(rows)} 行（run_id={run_id}）")
        finally:
            conn.close()
    else:
        logger.info("--dry-run 模式：未写库")
    logger.info("backtest_runner 完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
