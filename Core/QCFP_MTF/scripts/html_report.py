#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF —— 回测 HTML 报告生成器（轻量、零依赖、内联 SVG）

读取回测 summary JSON + equity CSV，生成自包含 HTML：
净值曲线 / 分年度收益柱状图 / 市场环境分层柱状图 / 指标表。

用法：
    python Core/QCFP_MTF/scripts/html_report.py --run-id bt_v2_risk_capped_20260820
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

from QCFP_MTF.common.paths import get_report_root


def _svg_line(series, width=760, height=260, title="", color="#2563eb"):
    s = series.dropna()
    if s.empty:
        return f"<div>无数据：{title}</div>"
    lo, hi = float(s.min()), float(s.max())
    pad = (hi - lo) * 0.1 if hi > lo else 1.0
    lo, hi = lo - pad, hi + pad
    xs = list(range(len(s)))
    pts = []
    for i, v in enumerate(s):
        x = 50 + i / max(len(s) - 1, 1) * (width - 70)
        y = height - 30 - (v - lo) / (hi - lo) * (height - 60)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    labels = [f"{s.index[0]}", f"{s.index[-1]}"]
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{title}">
      <title>{title}</title>
      <text x="50" y="18" font-size="14" fill="#333">{title}</text>
      <polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2"/>
      <text x="45" y="{height-12}" font-size="11" fill="#666">{labels[0]}</text>
      <text x="{width-110}" y="{height-12}" font-size="11" fill="#666">{labels[1]}</text>
      <text x="14" y="30" font-size="11" fill="#666">{hi:.2f}</text>
      <text x="14" y="{height-40}" font-size="11" fill="#666">{lo:.2f}</text>
    </svg>"""


def _svg_bars(items, width=760, height=240, title="", color="#2563eb"):
    if not items:
        return f"<div>无数据：{title}</div>"
    vals = [float(v) for _, v in items]
    lo, hi = min(0.0, min(vals)), max(vals)
    pad = (hi - lo) * 0.1 if hi > lo else 1.0
    hi += pad
    n = len(items)
    bw = (width - 90) / n
    bars = []
    for i, (label, v) in enumerate(items):
        x = 55 + i * bw
        h = (v - lo) / (hi - lo) * (height - 60)
        y = height - 30 - h
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.7:.1f}" '
                    f'height="{h:.1f}" fill="{color}"/>')
        bars.append(f'<text x="{x+bw*0.35:.1f}" y="{height-12}" font-size="10" '
                    f'text-anchor="middle" fill="#666">{label}</text>')
        bars.append(f'<text x="{x+bw*0.35:.1f}" y="{y-4:.1f}" font-size="10" '
                    f'text-anchor="middle" fill="#333">{v:.1%}</text>')
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{title}">
      <title>{title}</title>
      <text x="50" y="18" font-size="14" fill="#333">{title}</text>
      {''.join(bars)}
    </svg>"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 回测 HTML 报告")
    parser.add_argument("--run-id", default=None,
                        help="回测 run_id（缺省自动匹配该股票最新回测）")
    parser.add_argument("--stock", help="对应回测的股票代码（文件名后缀）")
    args = parser.parse_args(argv)

    backtest_dir = get_report_root() / "backtest"
    run_id = args.run_id
    if not run_id:
        # 自动匹配该股票最新回测（summary_{run_id}_{stock}.json 或 summary_{run_id}.json）
        pattern = f"summary_*_{args.stock}.json" if args.stock else "summary_*.json"
        candidates = sorted(backtest_dir.glob(pattern),
                            key=lambda p: p.stat().st_mtime)
        if not candidates:
            print(f"❌ 未找到 {'该股票' if args.stock else '任何'}回测产物"
                  f"（需先运行 backtest_runner.py）")
            return 1
        latest = candidates[-1]
        name = latest.stem[len("summary_"):]  # 形如 bt_20260822_01951 / bt_20260822
        if args.stock and name.endswith(f"_{args.stock}"):
            run_id = name[: -len(args.stock) - 1]
        else:
            run_id = name
        print(f"自动匹配回测 run_id={run_id}（{latest.name}）")
    fname = f"{run_id}_{args.stock}" if args.stock else run_id
    summary_path = backtest_dir / f"summary_{fname}.json"
    equity_path = backtest_dir / f"equity_{fname}.csv"
    if not summary_path.exists() or not equity_path.exists():
        print(f"❌ 未找到 {args.run_id} 的回测产物（需先运行 backtest_runner.py）")
        return 1

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    equity = pd.read_csv(equity_path, dtype={"stock_code": str})
    port = equity.groupby("week_end")["pnl"].mean()
    port.index = pd.to_datetime(port.index)
    port = port.sort_index()
    equity_curve = (1 + port).cumprod()
    drawdown = equity_curve / equity_curve.cummax() - 1
    roll_sharpe = port.rolling(52, min_periods=26).apply(
        lambda x: x.mean() / x.std(ddof=0) * 52 ** 0.5
        if x.std(ddof=0) > 0 else 0.0, raw=False)

    by_year = summary.get("by_year", [])
    regime = summary.get("by_market_regime", [])
    overall = summary.get("overall", {})
    bench = summary.get("benchmark", {})
    risk = summary.get("portfolio_risk", {})
    wf = summary.get("walk_forward_oos", [])

    def metric_row(label, value):
        return f"<tr><td>{label}</td><td>{value}</td></tr>"

    html = f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QCFP-MTF 回测报告 {args.run_id}</title>
<style>
body {{ font-family: "Microsoft YaHei", "Aptos Display", Arial, sans-serif; margin: 24px; color: #1f2937; }}
h1 {{ font-size: 20px; }} h2 {{ font-size: 16px; margin-top: 24px; }}
table {{ border-collapse: collapse; margin: 8px 0; }}
td, th {{ border: 1px solid #e5e7eb; padding: 4px 10px; font-size: 13px; }}
th {{ background: #f3f4f6; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
</style></head><body>
<h1>QCFP-MTF 回测报告</h1>
<p>run_id：{args.run_id}｜区间：{summary.get('start')} ~ {summary.get('end')}｜模型：{summary.get('model_version')}</p>
<h2>总体绩效</h2>
<table>{''.join(metric_row(k, f"{v:.4f}" if isinstance(v, float) else v) for k, v in overall.items())}</table>
<div class="grid">
<div>{_svg_line(equity_curve, title="组合净值曲线")}</div>
<div>{_svg_line(drawdown, title="回撤曲线（水下周期）", color="#dc2626")}</div>
<div>{_svg_line(roll_sharpe, title="滚动 12M Sharpe", color="#7c3aed")}</div>
<div>{_svg_bars([(str(r.get('year')), r.get('annualized_return', 0)) for r in by_year], title="分年度年化收益")}</div>
<div>{_svg_bars([(r.get('market_regime'), r.get('annualized_return', 0)) for r in regime], title="市场环境年化收益", color="#7c3aed")}</div>
</div>
<h2>基准与组合风险</h2>
<table>
{metric_row("等权基准年化超额", f"{bench.get('buy_hold', {}).get('excess_annualized'):.2%}")}
{metric_row("等权基准 IR", bench.get('buy_hold', {}).get('information_ratio'))}
{metric_row("恒指基准年化超额", f"{bench.get('hsi', {}).get('excess_annualized'):.2%}")}
{metric_row("恒指基准 IR", bench.get('hsi', {}).get('information_ratio'))}
{metric_row("VaR95", f"{risk.get('var95'):.2%}")}
{metric_row("年化波动", f"{risk.get('annualized_vol'):.2%}")}
{metric_row("平均暴露", f"{risk.get('avg_exposure'):.1%}")}
</table>
<h2>Walk-forward OOS</h2>
<table><tr><th>窗口</th><th>测试期</th><th>年化</th><th>Sharpe</th><th>回撤</th></tr>
{''.join(f"<tr><td>{r.get('window')}</td><td>{r.get('test_start')}~{r.get('test_end')}</td>"
         f"<td>{r.get('annualized_return'):.2%}</td><td>{r.get('sharpe')}</td>"
         f"<td>{r.get('max_drawdown'):.2%}</td></tr>" for r in wf)}
</table>
</body></html>"""

    out_path = backtest_dir / f"report_{fname}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"HTML 报告已生成: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
