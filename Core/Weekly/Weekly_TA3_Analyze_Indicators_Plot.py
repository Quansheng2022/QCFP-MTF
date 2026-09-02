#!/usr/bin/env python
# coding: utf-8

"""
Name: Weekly_TA3_Analyze_Indicators_Plot.py
Function:
生成周线技术分析报告。
输入数据：SQLite数据库 (hk_weekly_kline_analysis表)
输出数据文件：{ticker}_weekly_TA_analysis.pdf
"""

# ==================== 标准库导入 ====================
import io                           # 字节/文本流处理（如内存文件）
import os                           # 文件和路径操作
from pathlib import Path             # 面向对象的路径操作
import sys                           # 系统相关功能（如解释器参数、路径）
import traceback                     # 异常追踪（打印详细错误栈）
from datetime import datetime        # 日期时间对象处理
import sqlite3                       # SQLite数据库操作
import logging                       # 日志记录
from logging.handlers import RotatingFileHandler  # 日志轮转

# ==================== 第三方库导入 ====================
import numpy as np                   # 科学计算基础（数组、矩阵运算）
import pandas as pd                  # 表格数据处理（DataFrame、CSV读写）

# ===== Windows平台Matplotlib配置（必须在导入pyplot之前） =====
import matplotlib
# 设置matplotlib后端为TkAgg（Windows下最稳定）
# 这样可以避免尝试加载macOS后端导致的错误
try:
    matplotlib.use('TkAgg')
    print("使用TkAgg后端")
except ImportError:
    try:
        # 备选Qt5Agg（如果已安装PyQt5）
        matplotlib.use('Qt5Agg')
        print("使用Qt5Agg后端")
    except ImportError:
        # 最后使用Agg（纯后端，适合生成图片文件）
        matplotlib.use('Agg')
        print("使用Agg后端（无交互式显示）")

# 现在可以安全地导入pyplot和其他模块
import matplotlib.pyplot as plt       # 核心绘图接口
import matplotlib.dates as mdates      # 日期坐标轴格式化
from matplotlib.backends.backend_pdf import PdfPages  # 多页PDF输出
from matplotlib.gridspec import GridSpec  # 复杂子图布局管理
from matplotlib.pylab import date2num  # 日期转换为Matplotlib数值格式
from mplfinance.original_flavor import candlestick_ohlc  # K线图绘制（mplfinance旧版风格）

# ==================== 日志配置 ====================
def setup_logger(log_dir):
    """配置日志系统 - 每次运行覆盖原有日志文件"""
    log_file = os.path.join(log_dir, 'Weekly_TA3_Analyze_Indicators_Plot.log')
    
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 如果日志文件已存在，删除它（实现覆盖）
    if os.path.exists(log_file):
        try:
            os.remove(log_file)
            print(f"已删除旧的日志文件: {log_file}")
        except Exception as e:
            print(f"删除旧日志文件失败: {e}")
    
    # 配置根日志记录器 - 修改这里，将名称改为空字符串或通用名称
    logger = logging.getLogger('')  # 使用根日志记录器，或改为其他名称如 'TA_Analyzer'
    logger.setLevel(logging.DEBUG)
    
    # 清除已有的处理器，避免重复
    if logger.handlers:
        logger.handlers.clear()
    
    # 文件处理器 - 使用 'w' 模式确保覆盖写入
    file_handler = logging.FileHandler(
        log_file, 
        mode='w',  # 'w' 模式会覆盖已有文件
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 设置格式 - 移除name字段或使用简写
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',  # 移除了 %(name)s
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
    
# 初始化logger（在GlobalConfig设置后调用）
logger = None

def get_logger():
    """获取logger实例"""
    global logger
    if logger is None:
        # 如果logger未初始化，创建一个默认的
        logger = logging.getLogger('')  # 使用根日志记录器
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',  # 移除了 %(name)s
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def check_breakthrough(df, ema_col, direction, window=10, consecutive=3):
    """检查最近window天内是否有consecutive天连续突破EMA（带反转条件）"""
    if ema_col not in df.columns or len(df) < window:
        return False, None

    # 获取最近window天的数据（按日期升序）并重置索引
    recent_data = df.tail(window)[['date', 'close', ema_col]].sort_values('date').reset_index(drop=True)

    # 寻找连续consecutive天满足条件的起始位置
    for i in range(len(recent_data) - consecutive + 1):
        window_data = recent_data.iloc[i:i+consecutive]

        # 检查连续consecutive天是否满足方向条件
        if direction == 'above' and all(window_data['close'] > window_data[ema_col]):
            # 检查前一天是否不满足条件（存在反转）
            if i > 0 and recent_data.iloc[i-1]['close'] <= recent_data.iloc[i-1][ema_col]:
                return True, recent_data.iloc[i]['date']  # 返回起始日期（datetime类型）
        elif direction == 'below' and all(window_data['close'] < window_data[ema_col]):
            # 检查前一天是否不满足条件（存在反转）
            if i > 0 and recent_data.iloc[i-1]['close'] >= recent_data.iloc[i-1][ema_col]:
                return True, recent_data.iloc[i]['date']  # 返回起始日期（datetime类型）

    return False, None


def load_data_from_db(ticker, start_date=None, end_date=None):
    """
    从SQLite数据库加载周线技术分析数据
    
    参数:
    ticker: 股票代码
    start_date: 可选的开始日期 (YYYY-MM-DD格式)
    end_date: 可选结束日期 (YYYY-MM-DD格式)
    
    返回:
    DataFrame: 包含周线技术指标数据
    """
    try:
        logger = get_logger()
        db_path = GlobalConfig.full_db_path
        
        if db_path is None or not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")
        
        # 连接数据库
        conn = sqlite3.connect(db_path)
        
        # 构建查询 - 使用 stock_code 而不是 ticker
        query = """
        SELECT * FROM hk_weekly_kline_analysis 
        WHERE stock_code = ?
        ORDER BY date ASC
        """
        params = [ticker]
        
        # 添加日期过滤
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        # 读取数据
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            logger.warning(f"股票 {ticker} 在数据库中无数据")
            return df
        
        logger.info(f"从数据库加载 {ticker} 数据: {len(df)} 行")
        return df
        
    except Exception as e:
        logger.error(f"从数据库加载数据失败: {str(e)}")
        traceback.print_exc()
        return pd.DataFrame()


def plot_weekly_chart(ticker, output_pdf, start_date=None, end_date=None):
    """
    从数据库读取数据并绘制周线图表，包含RSI区域和技术指标状态表，结果保存为PDF

    参数:
    ticker: 股票代码
    output_pdf: 输出PDF文件路径
    start_date: 可选的开始日期 (YYYY-MM-DD格式)，若为None则动态计算（3年前或最早日期）
    end_date: 可选结束日期 (YYYY-MM-DD格式)，默认为最新交易日
    """
    try:
        logger = get_logger()
        logger.info(f"开始生成 {ticker} 周线图表")
        
        # 1. 从数据库加载数据
        df = load_data_from_db(ticker, start_date, end_date)
        
        if df.empty:
            logger.error(f"股票 {ticker} 无数据，跳过")
            return
        
        # 确保所有列名都是小写（数据库查询已经是小写，但为了安全再转换一次）
        df.columns = df.columns.str.lower()
        
        # 确保日期列是datetime类型
        df['date'] = pd.to_datetime(df['date'])
        
        logger.info(f"成功加载 {len(df)} 行数据")
        if len(df) > 0:
            logger.info(f"数据日期范围: {df['date'].min()} 到 {df['date'].max()}")

        # 2. 确定结束日期
        if end_date is None:
            end_date = df['date'].max()  # 默认结束日期为最新交易日
        else:
            end_date = pd.to_datetime(end_date)  # 确保是datetime类型

        # 3. 动态计算起始日期：3年前的某周（周一） vs 数据最早日期
        three_years_ago = end_date - pd.DateOffset(years=3)
        start_of_week = three_years_ago - pd.Timedelta(days=three_years_ago.weekday())
        computed_start = max(start_of_week, df['date'].min())
        start_date = computed_start
        logger.info(f"动态计算起始日期: {start_date.date()} (3年前对应周周一: {start_of_week.date()}, 数据最早: {df['date'].min().date()})")

        # 4. 过滤指定日期范围的数据
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        df = df.loc[mask].copy()

        if df.empty:
            logger.error(f"在指定日期范围内没有数据 ({start_date.date()} 到 {end_date.date()})")
            return

        # ✅ 获取实际最后一个交易日（数据中存在的最新日期）
        actual_end_date = df['date'].max()

        # 5. 设置支持中文字符的字体
        plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
        plt.rcParams['axes.unicode_minus'] = False   # 解决负号显示问题

        # 6. 创建PDF对象
        with PdfPages(output_pdf) as pdf:
            # ========== 第一页: 价格图表 + 指标图表 ==========
            # 准备蜡烛图数据 - 使用小写列名
            df['date_num'] = df['date'].apply(mdates.date2num)
            ohlc = df[['date_num', 'open', 'high', 'low', 'close']].values

            # 创建图表 - 优化布局以容纳时间轴
            fig = plt.figure(figsize=(24, 24), dpi=100)
            gs = GridSpec(nrows=4, ncols=1, height_ratios=[4, 1.2, 1.2, 1.5], hspace=0.25)

            # 第一区域：价格图表
            ax1 = fig.add_subplot(gs[0])
            date_range_str = f"{start_date.strftime('%Y-%m-%d')} 至 {actual_end_date.strftime('%Y-%m-%d')}"
            ax1.set_title(f'{ticker} 周线图 - {date_range_str}', fontsize=24)

            # 动态调整蜡烛图宽度
            num_points = len(df)
            base_width = 1.0
            candle_width = base_width * (1.0 if num_points>100 else 1.1 if num_points>50 else 1.2)

            # 绘制蜡烛图
            candlestick_ohlc(ax1, ohlc, width=candle_width, colorup='g', colordown='r', alpha=0.8)

            # 绘制EMA均线 - 使用小写列名
            ema_cols = ['ema10', 'ema50']
            for ema in ema_cols:
                if ema in df.columns:
                    ax1.plot(df['date_num'], df[ema], label=ema.upper(), linewidth=2.5, alpha=0.9)
            ax1.set_ylabel('价格', fontsize=14)
            ax1.legend(loc='best', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.tick_params(axis='both', labelsize=12)
            ax1.set_xlim(df['date_num'].min()-candle_width*5, df['date_num'].max()+candle_width*5)

            # 第二区域：成交量
            ax2 = fig.add_subplot(gs[1], sharex=ax1)
            ax2.set_xlim(df['date_num'].min()-candle_width*5, df['date_num'].max()+candle_width*5)
            colors = ['g' if close>open_ else 'r' for open_, close in zip(df['open'], df['close'])]
            ax2.bar(df['date_num'], df['volume'], color=colors, width=candle_width, alpha=0.7, label='成交量')

            # 绘制成交量均线
            if 'vol_ema5' in df.columns:
                ax2.plot(df['date_num'], df['vol_ema5'], color='gold', linewidth=3, label='5日成交量均线')
            ax2.set_ylabel('成交量', fontsize=14)
            ax2.grid(True, alpha=0.3)
            ax2.legend(loc='best', fontsize=12)

            # 第三区域：MACD
            ax3 = fig.add_subplot(gs[2], sharex=ax1)
            ax3.set_xlim(df['date_num'].min()-candle_width*5, df['date_num'].max()+candle_width*5)
            macd_colors = ['g' if val>0 else 'r' for val in df['macd_histogram']]
            ax3.bar(df['date_num'], df['macd_histogram'], color=macd_colors, width=candle_width, alpha=0.7)
            ax3.plot(df['date_num'], df['macd_dif'], label='MACD_DIF', color='blue', linewidth=2.5, alpha=0.9)
            ax3.plot(df['date_num'], df['macd_signal'], label='MACD_Signal', color='orange', linewidth=2.5, alpha=0.9)
            ax3.set_ylabel('MACD_Histogram', fontsize=14)
            ax3.axhline(0, color='gray', linestyle='--', alpha=0.5)
            ax3.legend(loc='best', fontsize=12)
            ax3.grid(True, alpha=0.3)
            ax3.tick_params(axis='both', labelsize=12)

            # 第四区域：RSI
            ax4 = fig.add_subplot(gs[3], sharex=ax1)
            ax4.set_xlim(df['date_num'].min()-candle_width*5, df['date_num'].max()+candle_width*5)
            if 'rsi14' in df.columns:
                ax4.plot(df['date_num'], df['rsi14'], label='RSI14', color='blue', linewidth=2, alpha=0.9)
                ax4.axhline(70, color='red', linestyle='--', alpha=0.7, linewidth=1.5)
                ax4.axhline(30, color='green', linestyle='--', alpha=0.7, linewidth=1.5)
                ax4.axhline(50, color='gray', linestyle='-', alpha=0.5, linewidth=1.0)
                ax4.fill_between(df['date_num'], df['rsi14'], 70, where=df['rsi14']>=70, color='red', alpha=0.2)
                ax4.fill_between(df['date_num'], df['rsi14'], 30, where=df['rsi14']<=30, color='green', alpha=0.2)
                ax4.set_ylabel('RSI14', fontsize=14)
                ax4.set_ylim(0, 100)
                ax4.legend(loc='best', fontsize=12)
                ax4.grid(True, alpha=0.3)
                ax4.tick_params(axis='both', labelsize=12)
            else:
                ax4.axis('off')

            # 统一时间轴标签
            date_format = mdates.DateFormatter('%Y-%m-%d')
            tick_positions, tick_labels = [], []
            if len(df) < 30:
                tick_positions = df['date_num']
                tick_labels = [d.strftime('%Y-%m-%d') for d in df['date']]
            else:
                interval = max(1, len(df)//15)
                tick_positions = df['date_num'][::interval]
                tick_labels = [df['date'].iloc[i].strftime('%Y-%m-%d') for i in range(0, len(df), interval)]

            for ax in [ax1, ax2, ax3, ax4]:
                if ax.axison:
                    ax.xaxis.set_major_formatter(date_format)
                    ax.set_xticks(tick_positions)
                    plt.setp(ax.get_xticklabels(), rotation=30, ha='right', fontsize=10)

            plt.subplots_adjust(left=0.05, right=0.95, bottom=0.12, top=0.95, hspace=0.25)

            # 保存价格图表到PDF
            pdf_metadata = {
                'Title': f'{ticker} 周线分析图表',
                'Author': '量化分析系统',
                'Subject': f'{ticker} 技术分析 ({start_date.date()} 至 {actual_end_date.date()})',
                'Keywords': f'股票分析,技术分析,EMA,MACD,RSI14,成交量,{ticker}',
                'CreationDate': pd.Timestamp.now()
            }
            pdf.savefig(fig, bbox_inches='tight', metadata=pdf_metadata)
            plt.close(fig)

            # ========== 第二页: 技术指标状态表格 ==========
            fig_table = plt.figure(figsize=(24, 14), dpi=100)
            ax_table = fig_table.add_subplot(111)
            ax_table.axis('off')

            # 获取最后交易日数据
            last_row = df.iloc[-1]
            table_data = [["指标", "状态", "详细信息"]]
            streak_values = [None]

            # ===== 序列号1-4: EMA交叉指标 - 使用小写列名 =====
            ema_pairs = [("EMA5/10", "ema5_10_status", "ema5_10_streak"),
                         ("EMA5/20", "ema5_20_status", "ema5_20_streak"),
                         ("EMA10/50", "ema10_50_status", "ema10_50_streak"),
                         ("EMA20/50", "ema20_50_status", "ema20_50_streak")]
            for label, status_col, streak_col in ema_pairs:
                status = last_row.get(status_col, 'N/A')
                streak = last_row.get(streak_col, 'N/A')
                table_data.append([label, status, streak])
                streak_values.append(streak if status in ['Golden', 'Death'] else None)

            # ===== 序列号5-8: 均线突破确认法 =====
            ema20_break_above, start_date_above = check_breakthrough(df, 'ema20', 'above')
            if ema20_break_above:
                table_data.append(["确认突破EMA20", "TRUE", 
                                  f"最近10周连续3周高于EMA20（起始日：{start_date_above.strftime('%Y-%m-%d')}）"])
                streak_values.append(None)

            ema20_break_below, start_date_below = check_breakthrough(df, 'ema20', 'below')
            if ema20_break_below:
                table_data.append(["确认跌破EMA20", "TRUE", 
                                  f"最近10周连续3周低于EMA20（起始日：{start_date_below.strftime('%Y-%m-%d')}）"])
                streak_values.append(None)

            ema200_break_above, start_date_200_above = check_breakthrough(df, 'ema200', 'above')
            if ema200_break_above:
                table_data.append(["确认突破EMA200", "TRUE", 
                                  f"最近10周连续3周高于EMA200（起始日：{start_date_200_above.strftime('%Y-%m-%d')}）"])
                streak_values.append(None)

            ema200_break_below, start_date_200_below = check_breakthrough(df, 'ema200', 'below')
            if ema200_break_below:
                table_data.append(["确认跌破EMA200", "TRUE", 
                                  f"最近10周连续3周低于EMA200（起始日：{start_date_200_below.strftime('%Y-%m-%d')}）"])
                streak_values.append(None)

            # 序列号9: 周线EMA5/10/20黄金三角形
            if len(df) > 0 and 'golden_triangle' in df.columns:
                lookback_days = 30
                n = min(lookback_days, len(df))
                df_sub = df.tail(n).copy()
                golden_true = df_sub[df_sub['golden_triangle'] == True]
                if not golden_true.empty:
                    last_date = df['date'].iloc[-1]
                    first_golden_date = golden_true['date'].iloc[0]
                    delta_days = (last_date - first_golden_date).days
                    table_data.append([
                        "EMA5/10/20黄金三角形", 
                        "TRUE", 
                        f"{first_golden_date.strftime('%Y-%m-%d')}，已出现{delta_days}天"
                    ])
                    streak_values.append(delta_days)

            # 序列号10: 周线EMA5/10/20死亡三角形
            if len(df) > 0 and 'death_triangle' in df.columns:
                lookback_days = 30
                n = min(lookback_days, len(df))
                df_sub = df.tail(n).copy()
                death_true = df_sub[df_sub['death_triangle'] == True]
                if not death_true.empty:
                    last_date = df['date'].iloc[-1]
                    first_death_date = death_true['date'].iloc[0]
                    delta_days = (last_date - first_death_date).days
                    table_data.append([
                        "EMA5/10/20死亡三角形", 
                        "TRUE", 
                        f"{first_death_date.strftime('%Y-%m-%d')}，已出现{delta_days}天"
                    ])
                    streak_values.append(delta_days)

            # 序列号11: 短线多头等趋势判断
            trend_ema = [
                ("短线多头", ['ema5', 'ema10', 'ema20'], lambda x: x[0]>x[1]>x[2]),
                ("短线空头", ['ema5', 'ema10', 'ema20'], lambda x: x[0]<x[1]<x[2]),
                ("长线多头", ['ema20', 'ema50', 'ema200'], lambda x: x[0]>x[1]>x[2]),
                ("长线空头", ['ema20', 'ema50', 'ema200'], lambda x: x[0]<x[1]<x[2])
            ]
            for idx, (label, ema_list, condition) in enumerate(trend_ema, 11):
                ema_vals = [last_row.get(ema, float('nan')) for ema in ema_list]
                if not any(pd.isna(v) for v in ema_vals) and condition(ema_vals):
                    table_data.append([label, "TRUE", ""])
                    streak_values.append(None)

            # 序列号12: EMA20上方阳线
            last_date = df['date'].iloc[-1]
            ema20_up_yang = None
            ema20_up_yang_count = 0
            for i in range(len(df)-1, len(df)-11, -1):
                if i < 1: continue
                row, prev_row = df.iloc[i], df.iloc[i-1]
                if row['close'] <= row['open']: continue
                if prev_row['close'] < prev_row['ema20'] and row['close'] > row['ema20']:
                    ema20_up_yang = row['date'] if ema20_up_yang is None else ema20_up_yang
                    ema20_up_yang_count += 1
                elif row['ema20'] <= row['open'] <= row['ema20']*1.03 and row['close'] >= row['open']:
                    ema20_up_yang = row['date'] if ema20_up_yang is None else ema20_up_yang
                    ema20_up_yang_count += 1
            if ema20_up_yang is not None:
                delta_days = (last_date - ema20_up_yang).days
                table_data.append([
                    "EMA20上方阳线", 
                    "TRUE", 
                    f"{ema20_up_yang.strftime('%Y-%m-%d')}，已出现{delta_days}天，累计{ema20_up_yang_count}次"
                ])
                streak_values.append(None)

            # 序列号13: EMA20下方阴线
            ema20_down_yin = None
            ema20_down_yin_count = 0
            for i in range(len(df)-1, len(df)-11, -1):
                if i < 1: continue
                row, prev_row = df.iloc[i], df.iloc[i-1]
                if row['close'] >= row['open']: continue
                if prev_row['close'] > prev_row['ema20'] and row['close'] < row['ema20']:
                    ema20_down_yin = row['date'] if ema20_down_yin is None else ema20_down_yin
                    ema20_down_yin_count += 1
                elif row['ema20']*0.97 <= row['open'] <= row['ema20'] and row['close'] <= row['open']:
                    ema20_down_yin = row['date'] if ema20_down_yin is None else ema20_down_yin
                    ema20_down_yin_count += 1
            if ema20_down_yin is not None:
                delta_days = (last_date - ema20_down_yin).days
                table_data.append([
                    "EMA20下方阴线", 
                    "TRUE", 
                    f"{ema20_down_yin.strftime('%Y-%m-%d')}，已出现{delta_days}天，累计{ema20_down_yin_count}次"
                ])
                streak_values.append(None)

            # 序列号14: 跳空高开阳线
            up_red, up_red_count = 0, 0
            start_idx = max(0, len(df)-10)
            for i in range(start_idx, len(df)-1):
                if i < 1: continue
                row, prev_row = df.iloc[i], df.iloc[i-1]
                if row['open'] > prev_row['high'] and row['close'] > row['open']:
                    up_red += 1
                    up_red_count += 1
            if up_red > 0:
                table_data.append([
                    "跳空高开阳线", 
                    "TRUE", 
                    f"10周数量: {up_red_count}，最近出现: {df['date'].iloc[-up_red].strftime('%Y-%m-%d')}"
                ])
                streak_values.append(None)

            # 序列号15: 跳空低开阴线
            down_black, down_black_count = 0, 0
            for i in range(start_idx, len(df)-1):
                if i < 1: continue
                row, prev_row = df.iloc[i], df.iloc[i-1]
                if row['open'] < prev_row['low'] and row['close'] < row['open']:
                    down_black += 1
                    down_black_count += 1
            if down_black > 0:
                table_data.append([
                    "跳空低开阴线", 
                    "TRUE", 
                    f"10周数量: {down_black_count}，最近出现: {df['date'].iloc[-down_black].strftime('%Y-%m-%d')}"
                ])
                streak_values.append(None)

            # 序列号16: KDJ线金叉
            has_kdj = all(col in df.columns for col in ['kdj_k', 'kdj_d', 'kdj_j'])
            kdj_golden, kdj_death = None, None
            if has_kdj:
                lookback_window = df.tail(10).copy()
                for i in range(1, len(lookback_window)):
                    prev, curr = lookback_window.iloc[i-1], lookback_window.iloc[i]
                    if curr['kdj_j'] <= 30 and prev['kdj_k'] < prev['kdj_d'] and curr['kdj_k'] > curr['kdj_d']:
                        kdj_golden = {'date': curr['date'], 'days': (df['date'].iloc[-1] - curr['date']).days}
                        break
                    if curr['kdj_j'] >= 70 and prev['kdj_k'] > prev['kdj_d'] and curr['kdj_k'] < curr['kdj_d']:
                        kdj_death = {'date': curr['date'], 'days': (df['date'].iloc[-1] - curr['date']).days}
                        break
            if kdj_golden:
                table_data.append([
                    "KDJ线金叉", "TRUE", 
                    f"金叉日期: {kdj_golden['date'].strftime('%Y-%m-%d')}, 持续天数: {kdj_golden['days']}"
                ])
                streak_values.append(kdj_golden['days'])
            if kdj_death:
                table_data.append([
                    "KDJ线死叉", "TRUE", 
                    f"死叉日期: {kdj_death['date'].strftime('%Y-%m-%d')}, 持续天数: {kdj_death['days']}"
                ])
                streak_values.append(kdj_death['days'])

            # 序列号18: MACD（修复显示持续周数，兼容中英文状态）
            macd_status_raw = last_row.get('macd_status', '')
            macd_cross_raw = last_row.get('macd_cross', '')
            macd_value = f"{last_row.get('macd_histogram', 'N/A'):.4f}" if 'macd_histogram' in df.columns else 'N/A'

            is_golden = False
            is_death = False
            status_display = macd_status_raw if macd_status_raw else macd_cross_raw

            if macd_status_raw in ['Golden', '金叉', '金叉延续']:
                is_golden = True
                status_display = '金叉'
            elif macd_status_raw in ['Death', '死叉', '死叉延续']:
                is_death = True
                status_display = '死叉'
            elif macd_cross_raw in ['Golden', '金叉']:
                is_golden = True
                status_display = '金叉'
            elif macd_cross_raw in ['Death', '死叉']:
                is_death = True
                status_display = '死叉'

            macd_details = macd_value
            streak_weeks = 0

            if is_golden:
                streak_weeks = last_row.get('macd_golden_streak', 0)
                if pd.notna(streak_weeks):
                    macd_details += f" / 金叉持续: {int(streak_weeks)}周"
                else:
                    macd_details += " / 金叉"
            elif is_death:
                streak_weeks = last_row.get('macd_death_streak', 0)
                if pd.notna(streak_weeks):
                    macd_details += f" / 死叉持续: {int(streak_weeks)}周"
                else:
                    macd_details += " / 死叉"
            else:
                macd_details = macd_value

            table_data.append(["MACD", status_display, macd_details])
            streak_values.append(streak_weeks if (is_golden or is_death) else None)

            # 序列号19: 成交量
            volume = f"{last_row['volume']:,.0f}"
            volume_ratio = f"{last_row.get('volume_ratio', 1):.2f}x" if 'volume_ratio' in df.columns else 'N/A'
            table_data.append(["成交量", volume, volume_ratio])
            streak_values.append(None)

            # 序列号20: RSI14
            rsi_value = f"{last_row.get('rsi14', 'N/A'):.1f}" if 'rsi14' in df.columns else 'N/A'
            table_data.append(["RSI14", rsi_value, last_row.get('rsi14_status', 'N/A')])
            streak_values.append(None)

            # 序列号21-22: 集中度指标
            conc_cols = [
                ("价格振幅集中度", "price_amp_market_chip_concentration"),
                ("成本价差集中度", "cost_spread_chip_concentration")
            ]
            for label, col in conc_cols:
                if col in df.columns:
                    value = f"{last_row[col]:.2f}" if not pd.isna(last_row[col]) else 'N/A'
                    table_data.append([label, value, ""])
                    streak_values.append(None)

            # 序列号23: 收盘价
            close_price = f"{last_row['close']:.2f}"
            table_data.append(["收盘价", close_price, ""])
            streak_values.append(None)

            # ========== 计算 EMA5 趋势（含连续三周 r 值、上行、下行、横摆、蓄势待发、弱势横摆、拐点识别）==========
            ema5_trend = {'status': 'N/A', 'detail': '', 'color': None}
            if 'ema5' in df.columns and len(df) >= 3:
                # 准备数据
                df_ema5 = df[['date', 'ema5', 'close']].copy()
                # 计算周增长率 r
                df_ema5['r'] = (df_ema5['ema5'] / df_ema5['ema5'].shift(1) - 1) * 100
                # 取最后连续三周（无缺失值）
                last_3 = df_ema5.tail(3)
                r_vals = last_3['r'].values if len(last_3) == 3 and not last_3['r'].isnull().any() else []
                close_vals = last_3['close'].values if len(last_3) == 3 else []
                ema5_vals = last_3['ema5'].values if len(last_3) == 3 else []

                # 构造 r 字符串（用于详细信息）
                if len(r_vals) == 3:
                    r_str = ', '.join([f"{r:.2f}%" for r in r_vals])
                else:
                    avail_r = [f"{v:.2f}%" for v in last_3['r'].values if not pd.isna(v)]
                    r_str = ', '.join(avail_r) if avail_r else "无有效数据"

                if len(r_vals) == 3:
                    # ----- 1. 严格连续趋势（上行 / 下行）-----
                    if all(r >= 1.0 for r in r_vals):
                        ema5_trend = {
                            'status': '上行',
                            'detail': f"连续3周 r: [{r_str}] (≥1.0%)",
                            'color': '#90EE90'   # 绿色
                        }
                    elif all(r <= -1.0 for r in r_vals):
                        ema5_trend = {
                            'status': '下行',
                            'detail': f"连续3周 r: [{r_str}] (≤-1.0%)",
                            'color': '#FFFF99'   # 黄色
                        }
                    elif all(-1.0 < r < 1.0 for r in r_vals):
                        # ----- 2. 横摆区间细分（蓄势待发 / 弱势横摆 / 普通横摆）-----
                        close_last = close_vals[-1]
                        ema5_last = ema5_vals[-1]
                        if all(r > 0 for r in r_vals) and close_last > ema5_last:
                            ema5_trend = {
                                'status': '蓄势待发',
                                'detail': f"连续3周 r: [{r_str}]，均>0，收盘价{close_last:.2f}站上EMA5，蓄势上攻",
                                'color': '#CCFFCC'   # 浅绿
                            }
                        elif all(r < 0 for r in r_vals) and close_last < ema5_last:
                            ema5_trend = {
                                'status': '弱势横摆',
                                'detail': f"连续3周 r: [{r_str}]，均<0，收盘价跌破EMA5，弱势整理",
                                'color': '#E0E0E0'   # 浅灰
                            }
                        else:
                            ema5_trend = {
                                'status': '横摆',
                                'detail': f"连续3周 r: [{r_str}] (-1%~1%)，方向不一",
                                'color': None
                            }
                    else:
                        # ----- 3. 混合趋势（包含大于1%或小于-1%的情况）-----
                        # 先检查是否为温和上行或温和下行
                        r_last = r_vals[-1]
                        close_last = close_vals[-1]
                        ema5_last = ema5_vals[-1]
                        
                        # 3.1 温和上行：所有r>0，但至少有一个<1.0%（即不完全满足严格上行）
                        if all(r > 0 for r in r_vals):
                            ema5_trend = {
                                'status': '温和上行',
                                'detail': f"连续3周 r: [{r_str}] (均>0，但未达1.0%阈值)，温和上涨趋势",
                                'color': '#C8E6C9'   # 浅绿色
                            }
                        # 3.2 温和下行：所有r<0，但至少有一个>-1.0%（即不完全满足严格下行）
                        elif all(r < 0 for r in r_vals):
                            ema5_trend = {
                                'status': '温和下行',
                                'detail': f"连续3周 r: [{r_str}] (均<0，但未达-1.0%阈值)，温和下跌趋势",
                                'color': '#FFE0B2'   # 浅橙色
                            }
                        # 3.3 识别拐点（最近一周收于EMA5上方、r_last > 0、且前两周至少有一周为负）
                        elif close_last > ema5_last and r_last > 0 and any(r < 0 for r in r_vals[:-1]):
                            ema5_trend = {
                                'status': '拐点向上',
                                'detail': f"最近3周 r: [{r_str}]，收盘价{close_last:.2f}站上EMA5，周增长率由负转正",
                                'color': '#90EE90'   # 绿色（与上行一致）
                            }
                        # 拐点向下：最近一周收于EMA5下方、r_last < 0、且前两周至少有一周为正
                        elif close_last < ema5_last and r_last < 0 and any(r > 0 for r in r_vals[:-1]):
                            ema5_trend = {
                                'status': '拐点向下',
                                'detail': f"最近3周 r: [{r_str}]，收盘价跌破EMA5，周增长率由正转负",
                                'color': '#FFFF99'   # 黄色（与下行一致）
                            }
                        else:
                            ema5_trend = {
                                'status': '趋势不明',
                                'detail': f"最近3周 r: [{r_str}]，无明确连续信号",
                                'color': None
                            }
                else:
                    # 数据不足3周或存在缺失
                    ema5_trend = {
                        'status': 'N/A',
                        'detail': f"可用数据{len(last_3)}周，r: [{r_str}]，无法判断连续趋势",
                        'color': None
                    }
            else:
                ema5_trend = {
                    'status': 'N/A',
                    'detail': 'EMA5列缺失或数据不足3周',
                    'color': None
                }

            # ===== 序列号24-30: EMA均线（修改 EMA5 行）=====
            ema_list = ["ema5", "ema10", "ema20", "ema50", "ema60", "ema100", "ema200"]
            for idx, ema in enumerate(ema_list, 24):
                if ema in df.columns:
                    value = f"{last_row[ema]:.2f}" if not pd.isna(last_row[ema]) else 'N/A'
                    if ema == 'ema5':
                        status = ema5_trend['status']
                        detail = f"{value} {ema5_trend['detail']}" if ema5_trend['detail'] else value
                        table_data.append(['EMA5', status, detail])
                    else:
                        table_data.append([ema.upper(), value, ""])
                    streak_values.append(None)

            # 创建表格
            table = ax_table.table(cellText=table_data, cellLoc='center', loc='center', colWidths=[0.2, 0.2, 0.4])
            table.auto_set_font_size(False)
            table.set_fontsize(16)
            table.scale(1, 1.8)
            plt.suptitle(f'{ticker} 周线图技术指标状态 {date_range_str}', fontsize=24, y=0.95)

            # 单元格背景色高亮逻辑
            for key, cell in table.get_celld().items():
                row, col = key
                if row == 0:
                    cell.set_text_props(weight='bold', size=18)
                    cell.set_facecolor('#CCCCFF')
                    continue
                if row >= len(table_data): continue
                indicator = table_data[row][0]
                status = table_data[row][1]
                if col == 1:
                    if indicator in ["EMA5/10", "EMA5/20", "EMA10/50", "EMA20/50", "MACD"]:
                        if status in ["金叉", "金叉延续"]:
                            cell.set_facecolor('#90EE90')
                        elif status in ["死叉", "死叉延续"]:
                            cell.set_facecolor('#FFCCCB')
                    elif indicator == "RSI14":
                        try:
                            rsi_val = float(status)
                            if rsi_val < 30:
                                cell.set_facecolor('#90EE90')
                            elif rsi_val > 70:
                                cell.set_facecolor('#FFCCCB')
                        except:
                            pass
                    elif status == "TRUE":
                        if indicator.startswith("确认突破"):
                            cell.set_facecolor('#90EE90')
                        elif indicator.startswith("确认跌破"):
                            cell.set_facecolor('#FFCCCB')
                        elif indicator == "EMA5/10/20黄金三角形":
                            cell.set_facecolor('#90EE90')
                        elif indicator == "EMA5/10/20死亡三角形":
                            cell.set_facecolor('#FFCCCB')
                        elif indicator == "跳空高开阳线":
                            cell.set_facecolor('#90EE90')
                        elif indicator == "跳空低开阴线":
                            cell.set_facecolor('#FFCCCB')
                        elif "多头" in indicator or "上方阳线" in indicator:
                            cell.set_facecolor('#90EE90')
                        elif "空头" in indicator or "下方阴线" in indicator:
                            cell.set_facecolor('#FFCCCB')
                        elif "金叉" in indicator:
                            cell.set_facecolor('#90EE90')
                        elif "死叉" in indicator:
                            cell.set_facecolor('#FFCCCB')
                    elif status in ["Golden", "Death"]:
                        cell.set_facecolor('#90EE90' if status=="Golden" else '#FFCCCB')
                elif col == 2:
                    if indicator == "RSI14":
                        try:
                            rsi_val = float(status)
                            if rsi_val < 30:
                                cell.set_facecolor('#90EE90')
                            elif rsi_val > 70:
                                cell.set_facecolor('#FFCCCB')
                        except:
                            pass
                    elif indicator == "成交量":
                        try:
                            ratio = float(table_data[row][2].split('x')[0])
                            if ratio > 1.5:
                                cell.set_facecolor('#FFFF99')
                        except:
                            pass

            # 针对 EMA5 趋势高亮（覆盖之前的收盘价比较）
            for (row, col), cell in table.get_celld().items():
                if row == 0 or row >= len(table_data):
                    continue
                if col == 1:
                    indicator = table_data[row][0]
                    if indicator == 'EMA5':
                        if ema5_trend['color']:
                            cell.set_facecolor(ema5_trend['color'])

            # EMA均线收盘价比较高亮（跳过 EMA5）
            for data_row_idx in range(1, len(table_data)):
                indicator = table_data[data_row_idx][0]
                if indicator == 'EMA5':
                    continue
                if indicator in [e.upper() for e in ema_list]:
                    close_price_val = last_row['close']
                    ema_value = last_row.get(indicator.lower())
                    if ema_value is not None and not pd.isna(ema_value):
                        cell = table.get_celld().get((data_row_idx, 1))
                        if cell:
                            if close_price_val >= ema_value:
                                cell.set_facecolor('#90EE90')
                            else:
                                cell.set_facecolor('#FFCCCB')

            pdf.savefig(fig_table, bbox_inches='tight')
            plt.close(fig_table)

            logger.info(f"图表已成功保存为PDF: {output_pdf}")

    except Exception as e:
        logger.error(f"处理数据或绘制图表时出错: {str(e)}")
        traceback.print_exc()
        return
		
# === 添加UTL路径到系统路径 ===
# 当前脚本所在目录：
script_dir = Path(__file__).resolve().parent

# 将 Core 目录加入 sys.path，以便导入 utl 包
core_dir = script_dir.parent   # TA_Workflow/Core
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

# 从 utl.stock_analysis_utl 导入 get_project_root（该函数返回 Core 目录）
from utl.stock_analysis_utl import get_project_root

# 利用该函数获取 Core 目录，再取其父目录得到项目根目录 (TA_Workflow)
core_dir_from_utils = get_project_root()   # Path 对象，指向 Core
project_dir = core_dir_from_utils.parent  # TA_Workflow

# 确保项目根目录也在 sys.path（便于其他模块使用，虽非必需）
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

# 从 utl.stock_analysis_utl 导入所需工具（同在 utl 目录下）
try:
    from utl.stock_analysis_utl import (
        load_config,
        setup_windows_encoding,
        GlobalConfig
    )
except ImportError as e:
    print("=" * 60)
    print("❌ 严重错误：无法导入 utl.stock_analysis_utl 模块")
    print(f"   期望路径: {core_dir / 'utl' / 'stock_analysis_utl.py'}")
    print(f"   请确认该文件存在，且 utl 包中有 __init__.py")
    print(f"   详细错误: {e}")
    print("=" * 60)
    sys.exit(1)
# === 强制UTF-8编码输出 ===
if 'get_ipython' not in globals():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
else:
    # 在Jupyter环境中添加兼容处理
    import ipykernel
    if ipykernel:
        sys.stdout.encoding = 'utf-8'
        sys.stderr.encoding = 'utf-8'

# 执行Windows编码设置
setup_windows_encoding()   

def main():
    """主函数，程序的入口点"""
    global logger
    
    try:
        # ========== 主程序路径配置 ==========        
        # 构建配置文件路径：父目录下的config文件夹中的stock_data_analysis.par
        config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')

        # ========== 加载配置 ==========
        # 使用load_config函数加载配置
        CONFIG = load_config(config_path, project_dir)
        print(f"配置文件加载成功: {config_path}")

        # 更新全局路径配置
        GlobalConfig.update_paths(CONFIG, project_dir)
        
        # 初始化日志系统
        logger = setup_logger(GlobalConfig.full_log_dir)
        logger.info("=" * 60)
        logger.info("Weekly_TA3_Analyze_Indicators_Plot 启动")
        logger.info("=" * 60)

        # ========== 打印配置信息 ==========
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        logger.info(f"数据库路径: {GlobalConfig.full_db_path}")

        start_date = None
        end_date = None

        if CONFIG.get('tickers'):
            tickers = CONFIG['tickers']
            logger.info(f"股票代码数量: {len(tickers)}")
            if len(tickers) > 5:
                logger.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                logger.info(f"股票代码: {tickers}")                
        else:
            logger.warning("配置文件中未找到tickers设置")

        if not tickers:
            logger.error("无法整合交易数据 - 没有配置股票代码")
        else:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"{current_time} 开始分析周技术分析指标...")
            
            success_count = 0
            fail_count = 0
            
            for ticker in tickers:
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"\n{current_time} 正在分析 {ticker} 的周线数据...")

                try:
                    # 生成PDF报告
                    output_pdf_file = os.path.join(GlobalConfig.full_report_dir, f"{ticker}_weekly_TA_analysis.pdf")
                    plot_weekly_chart(ticker, output_pdf_file, start_date, end_date)
                    
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"{current_time} {ticker} 周线分析完成")
                    success_count += 1
                    
                except Exception as e:
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logger.error(f"{current_time} {ticker} 分析失败: {str(e)}")
                    traceback.print_exc()
                    fail_count += 1

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"{current_time} ✅ 全部周技术分析指标分析完成！")
            logger.info(f"成功: {success_count}, 失败: {fail_count}, 总计: {len(tickers)}")
            logger.info("=" * 60)

    except Exception as e:
        error_msg = f"发生未知错误: {type(e).__name__}: {e}"
        if logger:
            logger.error(error_msg)
        else:
            print(error_msg)
        traceback.print_exc()

        if 'get_ipython' not in globals():
            sys.exit(1)
        else:
            print("在Jupyter环境中运行，程序继续但可能无法正常工作")

if __name__ == "__main__":
    main()