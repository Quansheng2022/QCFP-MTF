#!/usr/bin/env python
# coding: utf-8
"""
Generate_qcfp_Dictionaries.py
生成 QCFP-MTF 六张表的数据字典：
    qcfp_quarterly_structural / qcfp_monthly_behavior / qcfp_weekly_tactical
    qcfp_mtf_decision / qcfp_backtest_results / qcfp_data_quality_audit

输出：Config/qcfp_*_dictionary.{json,md,xlsx}
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
DB_PATH = project_dir / "SQLiteDB" / "HK_Stock.db"
OUTPUT_DIR = project_dir / "Config"

TABLE_LIST = [
    "qcfp_quarterly_structural",
    "qcfp_monthly_behavior",
    "qcfp_weekly_tactical",
    "qcfp_daily_tactical",
    "qcfp_mtf_decision",
    "qcfp_backtest_results",
    "qcfp_data_quality_audit",
]

FIELD_DESCRIPTIONS = {
    "qcfp_quarterly_structural": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字，如 00700）",
        "stock_name": "股票名称",
        "period_end": "季度结束日期（YYYY-MM-DD）",
        "available_date": "数据真实可用日期（推算时用季度末+披露滞后，data_quality 降级）",
        "inst_ownership_pct_chg": "机构持股比例变化（百分点，来自 TA4C）",
        "holder_quantity_chg_pct": "股东户数变化（%）",
        "inst_participation_chg": "机构数量变化（%）",
        "q_inst_flow_raw": "季度机构资金净流入（原始值，IDR/FBI 派生）",
        "q_inst_flow_z": "季度机构资金净流入 Z-Score",
        "q_ifa_zscore": "机构资金优势 Z-Score",
        "q_return": "季度收益率（%）",
        "q_trend_score": "季度趋势评分（0~100，季末快照窗口）",
        "q_position_52w": "52 周价格位置（0~1，季末快照）",
        "c_state": "筹码方向状态（C↑/C→/C↓）",
        "f_state": "资金方向状态（F↑/F→/F↓）",
        "p_state": "价格方向状态（P↑/P→/P↓）",
        "structural_regime": "季度结构状态（6 种：STRUCTURAL_BULLISH 等）",
        "core_score": "季度核心评分（0~100，State-First）",
        "source_period": "来源季度标识（如 2026/Q2）",
        "model_version": "模型版本号（QCFP-MTF-2.1.1）",
        "data_quality": "数据质量等级（A/B/C/D）",
        "update_time": "更新时间",
    },
    "qcfp_monthly_behavior": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字）",
        "stock_name": "股票名称",
        "month_end": "月份结束日期（YYYY-MM-DD）",
        "m_turnover_zscore": "月换手率 Z-Score",
        "m_turnover_pctl": "月换手率 52W 百分位（0~1）",
        "m_turnover_ma_ratio": "月换手率 / MA6",
        "m_volume_ma_ratio": "月成交量 / MA6",
        "m_volume_accel": "成交量加速度（VE_t / VE_{t-3} - 1）",
        "m_vwap_deviation": "收盘价 vs 月 VWAP 偏离（%）",
        "m_turnover_efficiency": "换手效率",
        "m_vp_regime": "量价矩阵状态（9 种，如 VP_EXPANSION）",
        "turnover_liquidity_regime": "换手-流动性状态（T1~T5）",
        "monthly_behavior_state": "月线阶段（Improving/Stable/Deteriorating）",
        "model_version": "模型版本号",
        "data_quality": "数据质量等级（A/B/C/D）",
        "update_time": "更新时间",
    },
    "qcfp_weekly_tactical": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字）",
        "stock_name": "股票名称",
        "week_end": "周结束日期（YYYY-MM-DD）",
        "w_turnover_deviation": "周换手偏离度（%）",
        "w_turnover_spike": "是否极端换手（1/0）",
        "w_volume_breakout": "是否放量突破（1/0）",
        "w_vwap_deviation": "收盘价 vs 周 VWAP 偏离（%）",
        "w_ma_slope": "周均线斜率方向（5/10/20 周二阶差分）",
        "w_breakout": "是否有效突破（1/0）",
        "w_breakdown": "是否有效破位（1/0）",
        "tactical_signal": "战术信号（Breakout/Pullback/Consolidation/Breakdown）",
        "model_version": "模型版本号",
        "data_quality": "数据质量等级（A/B/C/D）",
        "update_time": "更新时间",
    },
    "qcfp_daily_tactical": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字）",
        "stock_name": "股票名称",
        "trade_date": "交易日（YYYY-MM-DD）",
        "daily_state": "日线战术状态（DAILY_BREAKOUT/ACCUMULATION/PULLBACK/DISTRIBUTION/NEUTRAL）",
        "d_breakout": "日线突破标记（1/0）：收盘>前20日高+量比≥1.5+站上20日VWAP",
        "d_distribution": "日线派发标记（1/0）：接近前高+放量滞涨+资金流出",
        "d_pullback": "日线回调标记（1/0）：中期趋势向上+短期回调",
        "d_accumulation": "日线吸筹标记（1/0）：资金改善+量结构改善+价格未突破",
        "d_trend_score": "日线趋势评分（0~100）",
        "d_vol_ratio": "当日量 / 前 5 日均量",
        "d_near_high": "收盘 / 前 N 日最高（<1）",
        "d_inst_flow": "日机构净流入代理（超大单+大单净额）",
        "d_flow_z": "日资金流 PIT Z（60 日滚动）",
        "d_flow_slope": "资金流改善斜率（5 日均-20 日均）",
        "model_version": "模型版本号",
        "data_quality": "数据质量等级（A/B/C/D）",
        "update_time": "更新时间",
    },
    "qcfp_mtf_decision": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字）",
        "stock_name": "股票名称",
        "decision_date": "决策日期（YYYY-MM-DD）",
        "structural_regime": "季度结构状态（继承 FSM-1）",
        "monthly_behavior_state": "月线阶段（继承）",
        "tactical_signal": "周线信号（继承）",
        "cbi_score": "CBI 筹码行为指数（0~100）",
        "cost_position": "成本位置（COST_ADVANTAGE/NEUTRAL/DISADVANTAGE）",
        "chip_stability_confidence": "筹码稳定置信度（High/Medium/Low）",
        "mtf_regime": "MTF 状态（5 种：BULLISH_CONFIRMED 等）",
        "qcfp_score": "QCFP 综合评分（0~100，辅助参考）",
        "action_signal": "行动信号（BUY/ADD/HOLD/REDUCE/EXIT/WAIT）",
        "risk_level": "风险等级（Low/Medium/High/Extreme）",
        "market_context": "大盘环境上下文（来自 hk_idx_hist 派生）",
        "evidence_summary": "证据等级摘要",
        "align_method": "对齐方法（matrix/fallback/tactical_override/data_insufficient）",
        "alignment_override": "对齐层覆盖标记（1=战术覆盖 TEST_BUY，0=否）",
        "base_action": "风险层干预前的基础动作（如 REDUCE）",
        "final_action": "风险层干预后的最终动作（如 EXIT）",
        "base_target": "风险层干预前的基础目标仓位",
        "final_target": "风险层干预后的最终目标仓位（EXIT=0）",
        "risk_override_active": "下行风险覆盖是否激活（DES≥5 或风险下限）",
        "des_score": "下行证据评分（0~12+）",
        "des_band": "下行证据档位（NORMAL/WATCH/REDUCE/DE-RISK）",
        "model_version": "模型版本号",
        "data_quality": "数据质量等级（A/B/C/D）",
        "update_time": "更新时间",
    },
    "qcfp_backtest_results": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字）",
        "signal_date": "信号日期",
        "action_signal": "行动信号",
        "position": "仓位（0~1）",
        "pnl": "收益（%）",
        "mtf_regime": "当时 MTF 状态",
        "market_regime": "市场环境（牛/熊/震荡）",
        "model_version": "模型版本号",
        "run_id": "回测运行标识",
        "update_time": "更新时间",
    },
    "qcfp_data_quality_audit": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字；IDX 表示大盘指数）",
        "data_type": "数据源类型（如 daily_kline / institutional_holdings）",
        "grade": "质量等级（A/B/C/D）",
        "rows": "记录数",
        "first_date": "首条日期",
        "last_date": "末条日期",
        "core_missing_rate": "核心字段缺失率（0~1）",
        "anomalies": "异常值数量",
        "reasons": "降级原因说明",
        "model_version": "模型版本号",
        "audit_date": "审计日期（YYYY-MM-DD）",
        "update_time": "更新时间",
    },
}


def get_table_columns(conn, table_name):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    return cur.fetchall()


def build_dictionary(conn, table_name):
    cols = get_table_columns(conn, table_name)
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    total = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(DISTINCT stock_code) FROM {table_name}")
    stocks = cur.fetchone()[0]

    desc_map = FIELD_DESCRIPTIONS.get(table_name, {})
    fields = []
    for col in cols:
        name, typ = col[1], col[2]
        fields.append({
            "field_name": name,
            "data_type": typ,
            "description": desc_map.get(name, ""),
            "sample": None,
        })

    cur.execute(f"SELECT * FROM {table_name} LIMIT 3")
    sample_rows = cur.fetchall()
    samples = []
    if sample_rows:
        col_names = [d[0] for d in cur.description]
        for row in sample_rows:
            samples.append({k: v for k, v in zip(col_names, row)})

    return {
        "table_name": table_name,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "database_path": str(DB_PATH),
        "statistics": {"total_records": total, "stock_count": stocks},
        "field_count": len(fields),
        "fields": fields,
        "sample_data": samples,
    }


def save_json(dictionary, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ JSON数据字典已保存: {path}")


def save_markdown(dictionary, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {dictionary['table_name']} 数据字典\n\n")
        f.write(f"- **表名**: `{dictionary['table_name']}`\n")
        f.write(f"- **生成时间**: {dictionary['generated_at']}\n")
        f.write(f"- **总记录数**: {dictionary['statistics']['total_records']}\n")
        f.write(f"- **股票数量**: {dictionary['statistics']['stock_count']}\n\n")
        f.write("| 字段名 | 数据类型 | 描述 |\n")
        f.write("|--------|----------|------|\n")
        for field in dictionary["fields"]:
            f.write(f"| {field['field_name']} | {field['data_type']} | {field['description']} |\n")
        f.write("\n")
    print(f"✅ Markdown数据字典已保存: {path}")


def save_excel(dictionary, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame({
            "项目": ["表名", "生成时间", "总记录数", "股票数量"],
            "值": [dictionary["table_name"], dictionary["generated_at"],
                   dictionary["statistics"]["total_records"],
                   dictionary["statistics"]["stock_count"]],
        }).to_excel(writer, sheet_name="基本信息", index=False)
        pd.DataFrame(dictionary["fields"]).to_excel(writer, sheet_name="字段信息", index=False)
        if dictionary["sample_data"]:
            pd.DataFrame(dictionary["sample_data"]).to_excel(writer, sheet_name="示例数据", index=False)
    print(f"✅ Excel数据字典已保存: {path}")


def main():
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        for table in TABLE_LIST:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cur.fetchone():
                print(f"❌ 表 {table} 不存在（请先运行 init_db）")
                continue
            print(f"📊 生成 {table} 数据字典...")
            dictionary = build_dictionary(conn, table)
            save_json(dictionary, OUTPUT_DIR / f"{table}_dictionary.json")
            save_markdown(dictionary, OUTPUT_DIR / f"{table}_dictionary.md")
            save_excel(dictionary, OUTPUT_DIR / f"{table}_dictionary.xlsx")
    finally:
        conn.close()
    print("=" * 60)
    print("✅ QCFP 数据字典生成完成！")


if __name__ == "__main__":
    main()
