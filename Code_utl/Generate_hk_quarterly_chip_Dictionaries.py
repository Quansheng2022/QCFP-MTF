#!/usr/bin/env python
# coding: utf-8

"""
Generate_hk_quarterly_chip_Dictionaries.py
生成季度筹码分析两张表的数据字典：
1. hk_quarterly_institutional_holdings_analysis
2. hk_quarterly_chip_analysis

功能：
1. 读取 SQLite 数据库中的表结构
2. 生成包含字段名称、数据类型、说明、示例值等信息的字典
3. 支持 JSON、Markdown、Excel 三种输出格式
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd

# === 项目根目录解析 ===
script_dir = Path(__file__).resolve().parent
core_dir = script_dir.parent / "Core"
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

try:
    from utl.stock_analysis_utl import get_project_root
    core_root = get_project_root()
    project_dir = core_root.parent
except ImportError:
    project_dir = script_dir.parent

DB_PATH = project_dir / "SQLiteDB" / "HK_Stock.db"
OUTPUT_DIR = project_dir / "Config"

# ==================== 字段描述 ====================
FIELD_DESCRIPTIONS = {
    "hk_quarterly_institutional_holdings_analysis": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字，如 00700）",
        "stock_name": "股票名称",
        "quarter": "季度标识（如 2026/Q2）",
        "quarter_end_date": "季度结束日期（自然日，如 2026-06-30）",
        "institution_quantity": "机构持股账户/机构数量（原始值）",
        "holder_quantity": "持股数量（原始值）",
        "holder_pct": "持股比例（%，原始值）",
        "quarter_end_price": "季末价格",
        "institution_quantity_qoq": "机构数量环比变化（绝对值）",
        "institution_quantity_qoq_pct": "机构数量环比变化（%）",
        "holder_quantity_qoq": "持股数量环比变化（绝对值）",
        "holder_quantity_qoq_pct": "持股数量环比变化（%）",
        "holder_pct_qoq_pp": "持股比例环比变化（百分点）",
        "institution_quantity_yoy_pct": "机构数量同比变化（%）",
        "holder_quantity_yoy_pct": "持股数量同比变化（%）",
        "holder_pct_yoy_pp": "持股比例同比变化（百分点）",
        "institution_quantity_4q_change": "机构数量过去4个季度累计变化（绝对值）",
        "holder_quantity_4q_change": "持股数量过去4个季度累计变化（绝对值）",
        "holder_pct_4q_change_pp": "持股比例过去4个季度累计变化（百分点）",
        "institution_trend": "机构数量趋势编码（-2强降/-1降/0稳定/1升/2强升）",
        "holder_trend": "持股数量趋势编码（-2强降/-1降/0稳定/1升/2强升）",
        "holder_pct_trend": "持股比例趋势编码（-2强降/-1降/0稳定/1升/2强升）",
        "chip_migration_score": "筹码迁移评分（-1~+1，正=向机构集中，负=向外扩散）",
        "chip_migration_status": "筹码迁移状态（ACCUMULATION吸筹/DISTRIBUTION派发/DISPERSION分散/CONCENTRATION集中/NEUTRAL中性）",
        "institution_participation_score": "机构参与度评分（0-100）",
        "institutional_concentration_score": "集中度代理评分（0-100，以holder_pct为代理，真实集中度需机构明细）",
        "chip_structure_score": "筹码结构评分（0-100，六层加权合成）",
        "chip_regime": "筹码状态（极弱/弱/中性/强/极强）",
        "data_quality_flag": "数据质量标记（1=原始字段完整，0=存在缺失）",
        "corporate_action_flag": "公司行为提示（1=持股数量环比变动≥25%，可能受IPO/配股/拆分等影响）",
        "source_period": "原始季度标识（与 hk_hist_institutional_holdings.period_text 一致）",
        "data_source": "数据来源",
        "update_time": "更新时间",
    },
    "hk_quarterly_chip_analysis": {
        "id": "主键，自增ID",
        "stock_code": "股票代码（5位数字，如 00700）",
        "stock_name": "股票名称",
        "quarter": "季度标识（如 2026/Q2）",
        "quarter_end_date": "季度结束日期（自然日，如 2026-06-30）",
        "chip_structure_score": "筹码结构评分（0-100，来自TA4C）",
        "chip_regime": "筹码状态（极弱/弱/中性/强/极强）",
        "chip_migration_status": "筹码迁移状态（ACCUMULATION/DISTRIBUTION/DISPERSION/CONCENTRATION/NEUTRAL）",
        "chip_migration_score": "筹码迁移评分（-1~+1）",
        "institution_participation_score": "机构参与度评分（0-100）",
        "institutional_concentration_score": "集中度代理评分（0-100）",
        "holder_pct": "持股比例（%）",
        "holder_pct_qoq_pp": "持股比例环比变化（百分点）",
        "institution_quantity_qoq": "机构数量环比变化",
        "institutional_flow": "机构资金流（季度净额）",
        "individual_flow": "散户资金流（季度净额）",
        "idr": "机构主导比率 IDR",
        "fbi": "资金流平衡指标 FBI",
        "flow_bias": "资金流偏向（机构净流入/机构净流出/均衡）",
        "close": "季末收盘价",
        "change_percent": "季度涨跌幅（%）",
        "macd_status": "MACD 状态（金叉/死叉/延续等）",
        "ema5_10_status": "EMA5/10 状态（金叉/死叉/延续等）",
        "rsi14": "RSI14",
        "price_trend": "价格趋势（上行/下行/震荡）",
        "chip_direction": "筹码方向（+1偏多/-1偏空/0中性）",
        "flow_direction": "资金流方向（+1净流入/-1净流出/0均衡）",
        "price_direction": "价格方向（+1上行/-1下行/0震荡）",
        "chip_flow_alignment": "筹码与资金流对齐（共振/背离/中性）",
        "chip_price_alignment": "筹码与价格对齐（共振/背离/中性）",
        "flow_price_alignment": "资金流与价格对齐（共振/背离/中性）",
        "chip_flow_price_regime": "QCFP 状态（多头共振/空头共振/吸筹蓄势等）",
        "integrated_score": "综合评分（0-100，筹码40%+资金流30%+价格30%）",
        "signal_summary": "信号摘要文本",
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
            "description": desc_map.get(name, ''),
            "sample": None,
        })

    # 取示例值
    cur.execute(f"SELECT * FROM {table_name} LIMIT 3")
    sample_rows = cur.fetchall()
    if sample_rows:
        col_names = [d[0] for d in cur.description]
        samples = []
        for row in sample_rows:
            samples.append({k: v for k, v in zip(col_names, row)})
    else:
        samples = []

    return {
        "table_name": table_name,
        "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "database_path": str(DB_PATH),
        "statistics": {"total_records": total, "stock_count": stocks},
        "field_count": len(fields),
        "fields": fields,
        "sample_data": samples,
    }


def save_json(dictionary, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ JSON数据字典已保存: {path}")


def save_markdown(dictionary, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"# {dictionary['table_name']} 数据字典\n\n")
        f.write(f"- **表名**: `{dictionary['table_name']}`\n")
        f.write(f"- **生成时间**: {dictionary['generated_at']}\n")
        f.write(f"- **总记录数**: {dictionary['statistics']['total_records']}\n")
        f.write(f"- **股票数量**: {dictionary['statistics']['stock_count']}\n\n")
        f.write("| 字段名 | 数据类型 | 描述 |\n")
        f.write("|--------|----------|------|\n")
        for field in dictionary['fields']:
            f.write(f"| {field['field_name']} | {field['data_type']} | {field['description']} |\n")
        f.write("\n")
    print(f"✅ Markdown数据字典已保存: {path}")


def save_excel(dictionary, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        pd.DataFrame({
            '项目': ['表名', '生成时间', '总记录数', '股票数量'],
            '值': [dictionary['table_name'], dictionary['generated_at'],
                   dictionary['statistics']['total_records'],
                   dictionary['statistics']['stock_count']],
        }).to_excel(writer, sheet_name='基本信息', index=False)
        pd.DataFrame(dictionary['fields']).to_excel(writer, sheet_name='字段信息', index=False)
        if dictionary['sample_data']:
            pd.DataFrame(dictionary['sample_data']).to_excel(writer, sheet_name='示例数据', index=False)
    print(f"✅ Excel数据字典已保存: {path}")


def main():
    tables = [
        'hk_quarterly_institutional_holdings_analysis',
        'hk_quarterly_chip_analysis',
    ]
    if not DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        for table in tables:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if not cur.fetchone():
                print(f"❌ 表 {table} 不存在")
                continue
            print(f"📊 生成 {table} 数据字典...")
            dictionary = build_dictionary(conn, table)
            save_json(dictionary, OUTPUT_DIR / f"{table}_dictionary.json")
            save_markdown(dictionary, OUTPUT_DIR / f"{table}_dictionary.md")
            save_excel(dictionary, OUTPUT_DIR / f"{table}_dictionary.xlsx")
    finally:
        conn.close()
    print("=" * 60)
    print("✅ 季度筹码数据字典生成完成！")


if __name__ == "__main__":
    main()
