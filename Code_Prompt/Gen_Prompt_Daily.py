#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ==================================================
# Gen_Daily_Prompt.py -- 构建提问模板（近日走势复盘分析专用）
# 功能：自动处理股票列表，生成复盘分析提问，输出最近5个交易日的数据表格
# 改进：从SQLite数据库读取数据，连接hk_daily_kline_analysis和hk_daily_moneyflow_analysis两个表
# 改进：同时将结果输出到屏幕和指定的文本文件
# 改进：使用项目根目录，输出到prompt文件夹，生成综合文件和个股文件
# 改进：股票列表从stock_list.json读取，不再硬编码
# ==================================================

import pandas as pd
import os
from datetime import datetime
import sys
import sqlite3
from pathlib import Path
import logging
import json

# ==================== 配置参数 ====================
# 复盘区间：取最近 N 个交易日
REVIEW_DAYS = 30

# 需要输出的字段（从两个表连接后选择）
OUTPUT_COLUMNS = [
    "date", "close", "ema5", "ema20", "ema100", "ema200",
    "volume_ratio5", "macd_histogram", "macd_status",
    "institutional_flow", "individual_flow", "inst_5ma", "ind_5ma",
    "turnover_rate"
]

# ==================== 项目根目录与输出路径 ====================
def get_project_root():
    """返回项目根目录（TA_Workflow2）"""
    return Path(__file__).resolve().parent.parent

def get_work_root():
    """返回当前路径"""
    return Path(__file__).resolve().parent
    
def get_prompt_dir():
    """返回prompt输出目录，并确保该目录存在"""
    root = get_project_root()
    prompt_dir = root / 'prompt'
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return prompt_dir

def get_combined_filepath():
    """返回综合输出文件路径"""
    return get_prompt_dir() / 'Prompt_Daily.txt'

def get_individual_filepath(stock_code, stock_name):
    """返回个股输出文件路径，文件名中空格替换为下划线"""
    safe_name = stock_name.replace(' ', '_')
    filename = f"Prompt_Daily_{stock_code}_{safe_name}.txt"
    return get_prompt_dir() / filename

# ==================== 加载股票列表 ====================
def load_stock_list():
    """
    从项目根目录的 stock_list.json 文件中读取股票列表
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
        # 确保每个股票至少包含 stock_code 和 stock_name
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

# ==================== 数据库路径设置 ====================
def get_db_path():
    """获取SQLite数据库路径"""
    project_dir = get_project_root()
    db_dir = project_dir / 'SQLiteDB'
    db_path = db_dir / 'HK_Stock.db'
    return str(db_path)

# ==================== 辅助函数 ====================
def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

# 初始化日志
logger = setup_logging()

def load_stock_data_from_db(ticker, days):
    """
    从SQLite数据库加载股票数据，连接两个表
    
    参数:
    ticker: 股票代码
    days: 获取最近多少个交易日的数据
    
    返回:
    df: 连接后的DataFrame
    """
    try:
        db_path = get_db_path()
        logger.info(f"从数据库加载股票 {ticker} 的数据...")
        
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return None
        
        conn = sqlite3.connect(db_path)
        
        query = f"""
        SELECT 
            k.date,
            k.close,
            k.ema5,
            k.ema20,
            k.ema100,
            k.ema200,
            k.volume_ratio5,
            k.macd_histogram,
            k.macd_status,
            k.turnover_rate,
            COALESCE(m.institutional_flow, 0) as institutional_flow,
            COALESCE(m.individual_flow, 0) as individual_flow,
            COALESCE(m.inst_5ma, 0) as inst_5ma,
            COALESCE(m.ind_5ma, 0) as ind_5ma
        FROM hk_daily_kline_analysis k
        LEFT JOIN hk_daily_moneyflow_analysis m 
            ON m.stock_code = k.stock_code 
            AND m.date = k.date
        WHERE k.stock_code = '{ticker}'
        ORDER BY k.date DESC
        LIMIT {days}
        """
        
        logger.debug(f"执行查询...")
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            logger.warning(f"股票 {ticker} 在数据库中无数据")
            return None
        
        # 按日期升序排列
        df = df.sort_values('date').reset_index(drop=True)
        
        # 转换日期列为datetime类型
        df['date'] = pd.to_datetime(df['date'])
        
        logger.info(f"成功加载股票 {ticker} 的 {len(df)} 行数据")
        logger.info(f"日期范围: {df['date'].min().date()} 到 {df['date'].max().date()}")
        
        # 检查资金流数据
        if 'institutional_flow' in df.columns:
            has_data = (df['institutional_flow'] != 0).sum()
            logger.info(f"资金流数据: {has_data}/{len(df)} 行有数据")
            if has_data > 0:
                logger.info(f"资金流数据范围 - 机构: {df['institutional_flow'].min():.0f} 到 {df['institutional_flow'].max():.0f}")
                logger.info(f"资金流数据范围 - 散户: {df['individual_flow'].min():.0f} 到 {df['individual_flow'].max():.0f}")
            else:
                logger.warning(f"股票 {ticker} 的资金流数据全部为0！")
                # 直接查询数据库验证
                conn2 = sqlite3.connect(db_path)
                check_query = f"""
                SELECT COUNT(*) as cnt
                FROM hk_daily_moneyflow_analysis
                WHERE stock_code = '{ticker}'
                """
                df_check = pd.read_sql_query(check_query, conn2)
                logger.info(f"资金流表中该股票记录数: {df_check['cnt'][0]}")
                conn2.close()
        
        return df
        
    except sqlite3.Error as e:
        logger.error(f"数据库错误 - 股票 {ticker}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"加载数据时出错 - 股票 {ticker}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_recent_data(df, days):
    """获取最近 days 个交易日的数据切片，返回 (start_date, end_date, data_slice)"""
    if df is None or df.empty:
        return None, None, None
    
    df_sorted = df.sort_values('date').reset_index(drop=True)
    data_slice = df_sorted.tail(days).copy()
    
    if data_slice.empty:
        return None, None, None
    
    start_date = data_slice['date'].min()
    end_date = data_slice['date'].max()
    return start_date, end_date, data_slice

def format_dataframe(df):
    """
    格式化数据表格：日期字符串、数值保留指定位数，空值处理为空字符串
    """
    formatted = df.copy()
    formatted['date'] = formatted['date'].dt.strftime('%Y-%m-%d')
    
    format_rules = {
        'close': '{:.2f}',
        'ema5': '{:.3f}',
        'ema20': '{:.3f}',
        'ema100': '{:.3f}',
        'ema200': '{:.3f}',
        'volume_ratio5': '{:.3f}',
        'macd_histogram': '{:.4f}',
        'institutional_flow': '{:,.0f}',
        'individual_flow': '{:,.0f}',
        'inst_5ma': '{:,.0f}',
        'ind_5ma': '{:,.0f}',
        'turnover_rate': '{:.2f}'
    }
    
    for col, fmt in format_rules.items():
        if col in formatted.columns:
            formatted[col] = pd.to_numeric(formatted[col], errors='coerce')
            formatted[col] = formatted[col].apply(
                lambda x: fmt.format(x) if pd.notna(x) and x != 0 else ''
            )
    
    return formatted

def generate_question(stock_name, stock_code, start_date, end_date):
    """生成问题标题文本"""
    start_str = start_date.strftime('%Y年%m月%d日')
    end_str = end_date.strftime('%Y年%m月%d日')
    return f"问题: 对{stock_name} ({stock_code})近日走势进行复盘分析，复盘区间：{start_str} – {end_str}"

def write_and_print(file_obj, text):
    """将文本同时写入文件对象和控制台"""
    print(text)
    if file_obj:
        file_obj.write(text + "\n")

# ==================== 主流程 ====================
def main():
    # 确保prompt目录存在
    prompt_dir = get_prompt_dir()
    combined_filepath = get_combined_filepath()
    logger.info(f"综合输出文件: {combined_filepath}")
    logger.info(f"个股文件将保存在: {prompt_dir}")
    
    # 检查数据库是否存在
    db_path = get_db_path()
    logger.info(f"数据库路径: {db_path}")
    if not os.path.exists(db_path):
        logger.error(f"数据库文件不存在: {db_path}")
        print(f"错误: 数据库文件不存在: {db_path}")
        return
    
    # 加载股票列表
    try:
        stock_list = load_stock_list()
    except Exception as e:
        print(f"加载股票列表失败: {e}")
        return
    
    # 打开综合输出文件
    with open(combined_filepath, 'w', encoding='utf-8') as combined_f:
        header = "=" * 80 + "\n近日走势复盘分析 - 自动生成提问模板\n" + "=" * 80
        write_and_print(combined_f, header)
        write_and_print(combined_f, "")
        
        success_count = 0
        fail_count = 0
        
        for stock in stock_list:
            code = stock["stock_code"]
            name = stock["stock_name"]
            log_msg = f"\n处理 {name} ({code}) ..."
            write_and_print(combined_f, log_msg)
            
            df = load_stock_data_from_db(code, REVIEW_DAYS)
            
            if df is None:
                skip_msg = f"  跳过 {code}（数据加载失败）"
                write_and_print(combined_f, skip_msg)
                fail_count += 1
                continue
            
            if len(df) < 2:
                skip_msg = f"  跳过 {code}（数据不足，仅 {len(df)} 条）"
                write_and_print(combined_f, skip_msg)
                fail_count += 1
                continue
            
            start_date, end_date, data_slice = get_recent_data(df, REVIEW_DAYS)
            
            if data_slice is None or data_slice.empty:
                skip_msg = f"  跳过 {code}（无足够数据）"
                write_and_print(combined_f, skip_msg)
                fail_count += 1
                continue
            
            # 调试资金流数据
            print(f"  {name} 资金流数据检查:")
            if 'institutional_flow' in data_slice.columns:
                non_zero = (data_slice['institutional_flow'] != 0).sum()
                print(f"    机构资金流非零行数: {non_zero}/{len(data_slice)}")
                if non_zero > 0:
                    print(f"    机构资金流范围: {data_slice['institutional_flow'].min():.0f} 到 {data_slice['institutional_flow'].max():.0f}")
            
            formatted_df = format_dataframe(data_slice)
            question = generate_question(name, code, start_date, end_date)
            
            # ---- 写入综合文件 ----
            write_and_print(combined_f, "\n" + question)
            table_str = formatted_df.to_string(index=False)
            write_and_print(combined_f, table_str)
            write_and_print(combined_f, "\n" + "-" * 80)
            
            # ---- 写入个股文件 ----
            individual_filepath = get_individual_filepath(code, name)
            try:
                with open(individual_filepath, 'w', encoding='utf-8') as ind_f:
                    ind_f.write(question + "\n\n")
                    ind_f.write(table_str + "\n")
                    ind_f.write("\n" + "-" * 80 + "\n")
                    ind_f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                logger.info(f"个股文件已生成: {individual_filepath}")
            except Exception as e:
                logger.error(f"写入个股文件失败 {individual_filepath}: {str(e)}")
            
            success_count += 1
        
        # 写入完成提示
        completion_msg = f"\n处理完成: 成功 {success_count} 只股票，失败 {fail_count} 只"
        write_and_print(combined_f, completion_msg)
        write_and_print(combined_f, f"输出已保存至：{combined_filepath}")
        
        logger.info(f"程序执行完成: 成功 {success_count}, 失败 {fail_count}")

if __name__ == "__main__":
    main()