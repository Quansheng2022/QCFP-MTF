#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =======================================================================
# Gen_Stock_Research_DSS_Prompt.py -- 个股研究与投资决策支持系统报告提示词。
# 功能：从机构与牛散视角研究个股，并提供辅助投资决策的报告。
# 改进：支持三种模式（scan/research/review），集成日/周/月线数据，集成港股宏观仪表盘
# 依赖：无。可直接提问。
# 输入：PROJECT ROOT\code_prompt\个股_research_DSS_超级Prompt_V7.md, 
#      C:\Users\Quansheng\Documents\projects\TA_Workflow\Report\HK_Macro_Dashboard.txt
# 输出：PROJECT ROOT\prompt\research_DSS\Prompt_DSS_[mode]_[stock_code]_[stock_name].md
# =======================================================================

import os
from datetime import datetime
from pathlib import Path
import logging
import json
import sqlite3
import pandas as pd
import argparse

# ==================== 配置参数 ====================
# 日线数据：最近 N 个交易日
DAYS_LIMIT = 250
# 周线数据：最近 N 周
WEEKS_LIMIT = 160
# 月线数据：全部数据（通过 LIMIT 一个较大值获取全部）
MONTHS_LIMIT = 999
# 港股宏观仪表盘文件路径
HK_MACRO_DASHBOARD_PATH = r'C:\Users\Quansheng\Documents\projects\TA_Workflow\Report\HK_Macro_Dashboard.txt'

# ==================== 项目根目录与输出路径 ====================
def get_project_root():
    """返回项目根目录（TA_Workflow2）"""
    return Path(__file__).resolve().parent.parent

def get_work_root():
    """返回当前脚本所在目录（用于查找 stock_list.json）"""
    return Path(__file__).resolve().parent

def get_prompt_dir():
    """返回prompt输出目录，并确保该目录存在"""
    root = get_project_root()
    prompt_dir = root / 'prompt' / 'research_DSS'
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return prompt_dir

def get_db_path():
    """获取SQLite数据库路径"""
    project_dir = get_project_root()
    db_dir = project_dir / 'SQLiteDB'
    db_path = db_dir / 'HK_Stock.db'
    return str(db_path)

# ==================== 加载股票列表 ====================
def load_stock_list():
    """
    从当前工作目录（脚本所在目录）的 stock_list.json 文件中读取股票列表
    返回列表，每个元素为字典，包含 'stock_code' 和 'stock_name'
    """
    work_dir = get_work_root()
    json_path = work_dir / 'stock_list.json'
    if not json_path.exists():
        logger.error(f"股票列表文件不存在: {json_path}")
        raise FileNotFoundError(f"请确保 {json_path} 存在且格式正确")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        stocks = data.get('stocks', [])
        if not stocks:
            logger.warning("股票列表为空")
        for s in stocks:
            if 'stock_code' not in s or 'stock_name' not in s:
                raise ValueError(f"股票条目缺少 'stock_code' 或 'stock_name' 字段: {s}")
        logger.info(f"成功加载 {len(stocks)} 只股票")
        return stocks
    except json.JSONDecodeError as e:
        logger.error(f"解析 JSON 文件失败: {e}")
        raise
    except Exception as e:
        logger.error(f"加载股票列表时出错: {e}")
        raise

# ==================== 辅助函数 ====================
def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def read_file_content(filepath):
    """读取文件内容，若文件不存在返回None"""
    if not filepath.exists():
        logger.warning(f"文件不存在: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取文件失败 {filepath}: {e}")
        return None

def write_file_content(filepath, content):
    """写入内容到文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"已生成: {filepath}")
        return True
    except Exception as e:
        logger.error(f"写入文件失败 {filepath}: {e}")
        return False

def extract_prompt_content(content):
    """
    提取模板中的核心提示词内容（去掉可能的YAML front matter）
    """
    if not content:
        return content
    
    # 如果内容以 --- 开头，移除YAML front matter
    if content.strip().startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content

def load_hk_macro_dashboard():
    """
    加载港股宏观仪表盘数据
    
    返回:
    宏观看板内容的字符串，若加载失败返回None
    """
    macro_path = Path(HK_MACRO_DASHBOARD_PATH)
    if not macro_path.exists():
        logger.warning(f"港股宏观仪表盘文件不存在: {macro_path}")
        return None
    
    try:
        with open(macro_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if content.strip():
            logger.info(f"成功加载港股宏观仪表盘数据")
            return content
        else:
            logger.warning("港股宏观仪表盘文件为空")
            return None
    except Exception as e:
        logger.error(f"读取港股宏观仪表盘文件失败 {macro_path}: {e}")
        return None

def clean_moneyflow_data(df, period_name="行"):
    """
    清理和修复资金流数据
    对于资金流为0但K线数据存在的周期，使用前一期的数据填充
    
    参数:
    df: 包含资金流数据的DataFrame
    period_name: 周期名称（用于日志）
    
    返回:
    清洗后的DataFrame
    """
    if df is None or df.empty:
        return df
    
    cleaned_df = df.copy()
    moneyflow_cols = ['institutional_flow', 'individual_flow', 'inst_5ma', 'ind_5ma']
    existing_cols = [col for col in moneyflow_cols if col in cleaned_df.columns]
    
    if not existing_cols:
        logger.warning("DataFrame中不存在资金流字段")
        return cleaned_df
    
    fixed_count = 0
    for idx in range(len(cleaned_df)):
        row = cleaned_df.iloc[idx]
        is_all_zero = True
        for col in existing_cols:
            val = row[col]
            if pd.isna(val) or val == 0:
                continue
            else:
                is_all_zero = False
                break
        
        if is_all_zero:
            for j in range(idx-1, -1, -1):
                prev_row = cleaned_df.iloc[j]
                has_valid = False
                for col in existing_cols:
                    val = prev_row[col]
                    if not pd.isna(val) and val != 0:
                        has_valid = True
                        break
                if has_valid:
                    for col in existing_cols:
                        cleaned_df.at[cleaned_df.index[idx], col] = prev_row[col]
                    fixed_count += 1
                    break
    
    if fixed_count > 0:
        logger.info(f"已修复 {fixed_count} {period_name}资金流数据")
    
    return cleaned_df

def format_dataframe_table(df, is_price=True):
    """
    格式化DataFrame为Markdown表格
    
    参数:
    df: 要格式化的DataFrame
    is_price: 是否为价格数据（决定小数位格式）
    
    返回:
    Markdown格式的表格字符串
    """
    if df is None or df.empty:
        return "（无数据）"
    
    formatted = df.copy()
    
    # 日期格式化
    if 'date' in formatted.columns:
        formatted['date'] = pd.to_datetime(formatted['date']).dt.strftime('%Y-%m-%d')
    
    # 数值格式化规则
    format_rules = {
        'open': '{:.2f}',
        'high': '{:.2f}',
        'low': '{:.2f}',
        'close': '{:.2f}',
        'change_percent': '{:.2f}%',
        'month_change_pct': '{:.2f}%',
        'week_change_pct': '{:.2f}%',
        'volume_ratio': '{:.3f}',
        'volume_ratio5': '{:.3f}',
        'turnover_rate': '{:.2f}%',
        'ema5': '{:.3f}',
        'ema20': '{:.3f}',
        'ema100': '{:.3f}',
        'ema200': '{:.3f}',
        'macd_histogram': '{:.4f}',
        'macd_status': '{:.0f}',
        'rsi14': '{:.2f}',
        'institutional_flow': '{:,.0f}',
        'individual_flow': '{:,.0f}',
        'inst_5ma': '{:,.0f}',
        'ind_5ma': '{:,.0f}'
    }
    
    for col, fmt in format_rules.items():
        if col in formatted.columns:
            formatted[col] = pd.to_numeric(formatted[col], errors='coerce')
            formatted[col] = formatted[col].apply(
                lambda x: fmt.format(x) if pd.notna(x) else ''
            )
    
    # 转换为Markdown表格
    return formatted.to_markdown(index=False)

# ==================== 数据加载函数 ====================
def load_daily_data_from_db(ticker, days=DAYS_LIMIT):
    """
    从SQLite数据库加载日线数据，连接日线K线和资金流表
    
    参数:
    ticker: 股票代码
    days: 获取最近多少个交易日的数据
    
    返回:
    DataFrame
    """
    try:
        db_path = get_db_path()
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return None
        
        conn = sqlite3.connect(db_path)
        
        query = f"""
        WITH recent_days AS (
            SELECT 
                date, stock_code, open, high, low, close,
                change_percent, volume_ratio5, turnover_rate,
                ema5, ema20, ema100, ema200,
                macd_histogram, macd_status
            FROM hk_daily_kline_analysis
            WHERE stock_code = '{ticker}'
            ORDER BY date DESC
            LIMIT {days}
        )
        SELECT 
            k.date, k.open, k.high, k.low, k.close,
            k.change_percent, k.volume_ratio5, k.turnover_rate,
            k.ema5, k.ema20, k.ema100, k.ema200,
            k.macd_histogram, k.macd_status,
            COALESCE(m.institutional_flow, 0) as institutional_flow,
            COALESCE(m.individual_flow, 0) as individual_flow,
            COALESCE(m.inst_5ma, 0) as inst_5ma,
            COALESCE(m.ind_5ma, 0) as ind_5ma
        FROM recent_days k
        LEFT JOIN hk_daily_moneyflow_analysis m 
            ON m.stock_code = k.stock_code AND m.date = k.date
        ORDER BY k.date ASC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return None
        
        # 清洗资金流数据
        df = clean_moneyflow_data(df, "日线")
        
        logger.info(f"加载日线数据: {len(df)} 条")
        return df
        
    except Exception as e:
        logger.error(f"加载日线数据失败 {ticker}: {e}")
        return None

def load_weekly_data_from_db(ticker, weeks=WEEKS_LIMIT):
    """
    从SQLite数据库加载周线数据，连接周线K线和资金流表
    
    参数:
    ticker: 股票代码
    weeks: 获取最近多少周的数据
    
    返回:
    DataFrame
    """
    try:
        db_path = get_db_path()
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return None
        
        conn = sqlite3.connect(db_path)
        
        query = f"""
        WITH recent_weeks AS (
            SELECT 
                date, stock_code, open, high, low, close,
                change_percent, volume_ratio, turnover_rate,
                ema5, ema20, ema100, ema200,
                macd_histogram, macd_status, rsi14
            FROM hk_weekly_kline_analysis
            WHERE stock_code = '{ticker}'
            ORDER BY date DESC
            LIMIT {weeks}
        )
        SELECT 
            k.date, k.open, k.high, k.low, k.close,
            k.change_percent as week_change_pct, k.volume_ratio, k.turnover_rate,
            k.ema5, k.ema20, k.ema100, k.ema200,
            k.macd_histogram, k.macd_status, k.rsi14,
            COALESCE(m.institutional_flow, 0) as institutional_flow,
            COALESCE(m.individual_flow, 0) as individual_flow,
            COALESCE(m.inst_5ma, 0) as inst_5ma,
            COALESCE(m.ind_5ma, 0) as ind_5ma
        FROM recent_weeks k
        LEFT JOIN hk_weekly_moneyflow_analysis m 
            ON m.stock_code = k.stock_code AND m.date = k.date
        ORDER BY k.date ASC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return None
        
        # 清洗资金流数据
        df = clean_moneyflow_data(df, "周线")
        
        logger.info(f"加载周线数据: {len(df)} 条")
        return df
        
    except Exception as e:
        logger.error(f"加载周线数据失败 {ticker}: {e}")
        return None

def load_monthly_data_from_db(ticker, months=MONTHS_LIMIT):
    """
    从SQLite数据库加载月线数据，连接月线K线和资金流表
    
    参数:
    ticker: 股票代码
    months: 获取最近多少个月的数据（使用大值获取全部）
    
    返回:
    DataFrame
    """
    try:
        db_path = get_db_path()
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return None
        
        conn = sqlite3.connect(db_path)
        
        query = f"""
        WITH recent_months AS (
            SELECT 
                date, stock_code, open, high, low, close,
                change_percent, volume_ratio, turnover_rate,
                ema5, ema20, ema100, ema200,
                macd_histogram, macd_status, rsi14
            FROM hk_monthly_kline_analysis
            WHERE stock_code = '{ticker}'
            ORDER BY date DESC
            LIMIT {months}
        )
        SELECT 
            k.date, k.open, k.high, k.low, k.close,
            k.change_percent as month_change_pct, k.volume_ratio, k.turnover_rate,
            k.ema5, k.ema20, k.ema100, k.ema200,
            k.macd_histogram, k.macd_status, k.rsi14,
            COALESCE(m.institutional_flow, 0) as institutional_flow,
            COALESCE(m.individual_flow, 0) as individual_flow,
            COALESCE(m.inst_5ma, 0) as inst_5ma,
            COALESCE(m.ind_5ma, 0) as ind_5ma
        FROM recent_months k
        LEFT JOIN hk_monthly_moneyflow_analysis m 
            ON m.stock_code = k.stock_code AND m.date = k.date
        ORDER BY k.date ASC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return None
        
        # 清洗资金流数据
        df = clean_moneyflow_data(df, "月线")
        
        logger.info(f"加载月线数据: {len(df)} 条")
        return df
        
    except Exception as e:
        logger.error(f"加载月线数据失败 {ticker}: {e}")
        return None

# ==================== 生成报告内容 ====================
def generate_header(mode, stock_code, stock_name):
    """
    根据模式生成报告头部
    """
    if mode == 'scan':
        return f"针对 {stock_code} {stock_name} 启动 Quick Scan  模式。 （只要结论和风险，先看看有没有雷）"
    elif mode == 'research':
        stringA = f"针对 {stock_code} {stock_name} 启动 Deep Research 模式，要求创建深度研究报告：20层完整机构级Deep Research "
        stringB = f"\n按照Prompt_DSS_Research_{stock_code}_{stock_name}.md 中的分析框架，结合2026年中期财报、2025财报及2025ESG报告，采用Deep Research模式，授权AI联网获取最新数据（南向资金、沽空数据、最新公告、机构评级等，提供个股完整机构级深度研究报告。"
        return stringA + stringB
    elif mode == 'review':
        return f"针对 {stock_code} {stock_name}，上次已经出过一份 Deep Research 底稿了，现在半年报出来了，请切换到 Review Mode 更新报告。"
    else:
        return f"针对 {stock_code} {stock_name} 启动分析。"

def generate_filename(mode, stock_code, stock_name):
    """
    根据模式生成输出文件名
    """
    safe_name = stock_name.replace(' ', '_')
    mode_map = {
        'scan': 'Scan',
        'research': 'Research',
        'review': 'Review'
    }
    mode_str = mode_map.get(mode, 'Research')
    return f"Prompt_DSS_{mode_str}_{stock_code}_{safe_name}.md"

def build_report_content(mode, stock_code, stock_name, template_content):
    """
    构建完整的报告内容
    """
    today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 加载港股宏观仪表盘数据
    macro_content = load_hk_macro_dashboard()
    
    # 加载各类数据
    daily_df = load_daily_data_from_db(stock_code, DAYS_LIMIT)
    weekly_df = load_weekly_data_from_db(stock_code, WEEKS_LIMIT)
    monthly_df = load_monthly_data_from_db(stock_code, MONTHS_LIMIT)
    
    # 生成各数据表格
    daily_table = format_dataframe_table(daily_df)
    weekly_table = format_dataframe_table(weekly_df)
    monthly_table = format_dataframe_table(monthly_df)
    
    # 数据统计信息
    daily_info = f"日线数据: {len(daily_df) if daily_df is not None else 0} 条"
    weekly_info = f"周线数据: {len(weekly_df) if weekly_df is not None else 0} 条"
    monthly_info = f"月线数据: {len(monthly_df) if monthly_df is not None else 0} 条"
    
    # 构建报告
    content = []
    content.append(f"# {stock_code} {stock_name} 投资决策支持报告")
    content.append("")
    content.append(f"**模式**: {mode.upper()}")
    content.append(f"**生成时间**: {today}")
    content.append("")
    content.append("---")
    content.append("")
    
    # 添加模式特定的头部
    header = generate_header(mode, stock_code, stock_name)
    content.append(f"> {header}")
    content.append("")
    content.append("---")
    content.append("")
    
    # 添加港股宏观仪表盘（放在日线数据前面）
    content.append("## 0. 港股宏观仪表盘")
    content.append("")
    content.append("> 以下为港股市场整体宏观数据，用于评估当前市场环境和系统性风险")
    content.append("")
    if macro_content:
        content.append(macro_content)
        content.append("")
    else:
        content.append("（当前无法获取港股宏观仪表盘数据，请检查文件是否存在）")
        content.append("")
    content.append("---")
    content.append("")
    
    # 添加数据部分
    content.append("## 1. 日线技术分析数据 (最近250个交易日)")
    content.append("")
    content.append(f"数据量: {daily_info}")
    content.append("")
    content.append(daily_table)
    content.append("")
    content.append("---")
    content.append("")
    
    content.append("## 2. 周线技术分析数据 (最近160周)")
    content.append("")
    content.append(f"数据量: {weekly_info}")
    content.append("")
    content.append(weekly_table)
    content.append("")
    content.append("---")
    content.append("")
    
    content.append("## 3. 月线技术分析数据 (全部历史数据)")
    content.append("")
    content.append(f"数据量: {monthly_info}")
    content.append("")
    content.append(monthly_table)
    content.append("")
    content.append("---")
    content.append("")
    
    # 添加分析框架
    content.append("## 4. 投资决策分析框架")
    content.append("")
    if template_content:
        content.append(template_content)
    else:
        content.append("（请加载 个股_research_DSS_超级Prompt_V7.md 获取完整分析框架）")
    
    content.append("")
    content.append("---")
    content.append("")
    content.append(f"*报告生成时间: {today}*")
    
    return "\n".join(content)

# ==================== 主流程 ====================
def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='生成个股研究与投资决策支持报告')
    parser.add_argument('--mode', '-m', 
                        choices=['scan', 'research', 'review'],
                        default='research',
                        help='运行模式: scan(快速扫描), research(深度研究), review(回顾更新)')
    parser.add_argument('--stock', '-s',
                        help='指定单个股票代码（可选，不指定则处理所有股票）')
    args = parser.parse_args()
    
    mode = args.mode
    logger.info(f"运行模式: {mode}")
    
    prompt_dir = get_prompt_dir()
    logger.info(f"Prompt 输出目录: {prompt_dir}")
    
    # 加载模板文件
    template_path = get_project_root() / 'code_prompt' / '个股_research_DSS_超级Prompt_V7.md'
    template_content = None
    if template_path.exists():
        template_content = read_file_content(template_path)
        if template_content:
            template_content = extract_prompt_content(template_content)
            logger.info("模板文件加载成功")
    else:
        logger.warning(f"模板文件不存在: {template_path}")
    
    # 加载股票列表
    try:
        stock_list = load_stock_list()
    except Exception as e:
        print(f"加载股票列表失败: {e}")
        return
    
    # 如果指定了单个股票，只处理该股票
    if args.stock:
        stock_list = [s for s in stock_list if s['stock_code'] == args.stock]
        if not stock_list:
            print(f"未找到股票代码: {args.stock}")
            return
    
    success_count = 0
    fail_count = 0
    
    for stock in stock_list:
        code = stock["stock_code"]
        name = stock["stock_name"]
        logger.info(f"处理 {name} ({code})，模式: {mode}")
        
        try:
            # 构建报告内容
            report_content = build_report_content(mode, code, name, template_content)
            
            # 生成输出文件名
            filename = generate_filename(mode, code, name)
            output_path = prompt_dir / filename
            
            if write_file_content(output_path, report_content):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logger.error(f"处理 {code} ({name}) 时出错: {e}")
            fail_count += 1
    
    print(f"\n处理完成: 成功 {success_count} 只，失败 {fail_count} 只")
    logger.info(f"程序执行完成: 成功 {success_count}, 失败 {fail_count}")

if __name__ == "__main__":
    main()
    