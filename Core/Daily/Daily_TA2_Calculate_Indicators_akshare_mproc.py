#!/usr/bin/env python
# coding: utf-8

"""
Step3. Calculate TA indicators
Source code: Daily_TA2_Calculate_Indicators_akshare_mproc.py
Function:
input data:  hk_hist_daily_kline
output data: hk_daily_kline_analysis
主要优化点：
1. 动量指标(RSI/K-D-J/MFI)完全向量化，消除逐行循环
2. 信号条件(signal_conditions)完全向量化，避免大型逐行循环
3. 成本价差法筹码集中度使用滚动分位数，向量化完成
4. 价格振幅法筹码集中度使用numpy底层数组切片，大幅加速
5. 密集交易区间改用numpy数组操作
6. 部分循环数据批量赋值为DataFrame直接赋值
7. 数据存储改为SQLite，不再使用CSV文件
"""

import pandas as pd
import numpy as np
import os
import sys
import io
from datetime import datetime, timedelta
import time
from pathlib import Path
import traceback
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import sqlite3
import warnings
warnings.filterwarnings('ignore')

# ========== Column Name Conversion Function ==========

def convert_columns_to_lowercase(df):
    """
    将所有列名转换为小写
    """
    if df is None or df.empty:
        return df
    
    # 创建列名映射字典
    column_mapping = {}
    for col in df.columns:
        # 转换为小写
        new_col = col.lower()
        
        # 处理特殊情况：如果转换后列名重复，添加后缀
        if new_col in column_mapping.values():
            # 添加数字后缀以避免重复
            counter = 1
            while f"{new_col}_{counter}" in column_mapping.values():
                counter += 1
            new_col = f"{new_col}_{counter}"
        
        column_mapping[col] = new_col
    
    # 重命名列
    df = df.rename(columns=column_mapping)
    
    print(f"  - 列名已转换为小写，共 {len(df.columns)} 列")
    return df

# 改进的安全除法函数
def safe_divide(a, b):
    """安全除法函数，避免除零错误，兼容pandas Series"""
    if isinstance(a, (pd.Series, pd.DataFrame)) or isinstance(b, (pd.Series, pd.DataFrame)):
        result = a / b
        result = result.replace([np.inf, -np.inf], 0)
        result = result.fillna(0)
        return result
    else:
        return np.divide(a, b, out=np.zeros_like(a), where=b != 0)

def calculate_percentiles_optimized(data, columns_to_analyze, window_size=500):
    """优化后的百分位数计算函数"""
    percentiles = [0.1, 0.25, 0.5, 0.75, 0.9]
    percentile_names = ['10th', '25th', '50th', '75th', '90th']

    new_columns_data = {}

    for col in columns_to_analyze:
        if col in data.columns:
            new_columns_data[f'{col}_min_{window_size}d'] = data[col].rolling(window_size).min()
            new_columns_data[f'{col}_max_{window_size}d'] = data[col].rolling(window_size).max()

            rolling_obj = data[col].rolling(window_size)
            for p_name, p_value in zip(percentile_names, percentiles):
                new_columns_data[f'{col}_{p_name}_percentile_{window_size}d'] = rolling_obj.quantile(p_value)

    new_columns_df = pd.DataFrame(new_columns_data, index=data.index)
    return pd.concat([data, new_columns_df], axis=1)

def calculate_basic_indicators(data):
    """计算基础技术指标"""
    data["avg_price"] = (data["high"] + data["low"] + 2 * data["close"]) / 4
    data["close_chg%"] = safe_divide(data["close"].diff(), data["close"].shift(1)) * 100

    data['avg_volume_5d'] = data['volume'].rolling(5).mean().shift(1)
    data['volume_ratio5'] = safe_divide(data['volume'], data['avg_volume_5d'])

    data['avg_volume_20d'] = data['volume'].rolling(20).mean()
    data['volume_ratio20'] = safe_divide(data['volume'], data['avg_volume_20d'])

    return data

def calculate_ema_indicators(data):
    """计算EMA相关指标"""
    ema_periods = [5, 8, 10, 12, 13, 20, 21, 26, 30, 34, 50, 60, 63, 100, 120, 200, 250]
    for period in ema_periods:
        data[f"ema{period}"] = data["close"].ewm(span=period, adjust=False).mean()

    bias_periods = [5, 10, 20, 50, 60, 100, 120, 200, 250]
    for period in bias_periods:
        ema_col = f"ema{period}"
        data[f"bias{period}"] = safe_divide(data["close"] - data[ema_col], data[ema_col]) * 100

    return data

def calculate_volume_indicators(data):
    """计算成交量相关指标"""
    vol_ema_periods = [5, 10, 20]
    for period in vol_ema_periods:
        data[f"vol_ema{period}"] = data["volume"].ewm(span=period, adjust=False).mean()

    short_vol = data["volume"].rolling(window=5).mean()
    long_vol = data["volume"].rolling(window=20).mean()
    vol_oscillator = safe_divide(short_vol - long_vol, long_vol) * 100
    data["volume_oscillator"] = vol_oscillator

    data['obv'] = (np.sign(data['close'].diff()) * data['volume']).fillna(0).cumsum()

    return data

def calculate_momentum_indicators(data):
    """计算动量指标 - 完全向量化版本"""
    # ATR (已包含在calculate_adx_indicators中，这里保留ATR14备用)
    high_low = data['high'] - data['low']
    high_close = (data['high'] - data['close'].shift()).abs()
    low_close = (data['low'] - data['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    data['tr'] = tr
    data['atr14'] = tr.rolling(14).mean()

    # KDJ (随机指标) - 向量化
    low_min = data['low'].rolling(9).min()
    high_max = data['high'].rolling(9).max()
    # 高低相等时分母为0会得到 inf，fillna 无法处理，统一先替换为NaN再取中性值50
    rsv = ((data['close'] - low_min) / (high_max - low_min).replace(0, np.nan) * 100).fillna(50)
    kdj_k = rsv.ewm(com=2, adjust=False).mean()
    kdj_d = kdj_k.rolling(3).mean()
    kdj_j = 3 * kdj_k - 2 * kdj_d
    data['kdj_k'] = kdj_k
    data['kdj_d'] = kdj_d
    data['kdj_j'] = kdj_j

    # MACD指标
    data['macd_dif'] = data['ema12'] - data['ema26']
    data['macd_signal'] = data['macd_dif'].ewm(span=9, adjust=False).mean()
    data['macd_histogram'] = (data['macd_dif'] - data['macd_signal']) * 2

    # RSI - 向量化计算
    delta = data["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # 使用简单移动平均
    avg_gain_6 = gain.rolling(6, min_periods=1).mean()
    avg_loss_6 = loss.rolling(6, min_periods=1).mean()
    rs6 = avg_gain_6 / avg_loss_6.replace(0, np.nan)
    data['rsi6'] = 100 - (100 / (1 + rs6)).fillna(50)

    avg_gain_14 = gain.rolling(14, min_periods=1).mean()
    avg_loss_14 = loss.rolling(14, min_periods=1).mean()
    rs14 = avg_gain_14 / avg_loss_14.replace(0, np.nan)
    data['rsi14'] = 100 - (100 / (1 + rs14)).fillna(50)

    # CCI14 - 商品通道指数
    typical_price = (data['high'] + data['low'] + data['close']) / 3
    sma_typical = typical_price.rolling(14).mean()
    mean_deviation = typical_price.rolling(14).apply(
        lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
    )
    data['cci14'] = (typical_price - sma_typical) / (0.015 * mean_deviation)

    # WilliamsR - 威廉指标
    highest_high = data['high'].rolling(14).max()
    lowest_low = data['low'].rolling(14).min()
    denom_wr = (highest_high - lowest_low).replace(0, np.nan)
    data['williamsr'] = (highest_high - data['close']) / denom_wr * -100

    # ADX指标
    data = calculate_adx_indicators(data)

    # MFI - 向量化
    typical_price = (data["high"] + data["low"] + data["close"]) / 3
    money_flow = typical_price * data["volume"]
    positive_flow = money_flow * (data["close"].diff() > 0)
    negative_flow = money_flow * (data["close"].diff() < 0)
    pos_flow_sum = positive_flow.rolling(14, min_periods=1).sum()
    neg_flow_sum = negative_flow.rolling(14, min_periods=1).sum()
    money_ratio = pos_flow_sum / neg_flow_sum.replace(0, np.nan)
    data["mfi"] = 100 - (100 / (1 + money_ratio)).fillna(50)

    return data

def calculate_adx_indicators(data):
    """计算多个周期的 ADX 系列指标（向量化）"""
    high_low = data['high'] - data['low']
    high_close_prev = (data['high'] - data['close'].shift(1)).abs()
    low_close_prev = (data['low'] - data['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)

    up_move = data['high'] - data['high'].shift(1)
    down_move = data['low'].shift(1) - data['low']
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    plus_dm = pd.Series(plus_dm, index=data.index)
    minus_dm = pd.Series(minus_dm, index=data.index)

    for p in [14, 30, 60, 100]:
        atr = tr.rolling(p).mean()
        data[f'atr{p}'] = atr
        plus_dm_avg = plus_dm.rolling(p).mean()
        minus_dm_avg = minus_dm.rolling(p).mean()
        plus_di = 100 * (plus_dm_avg / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm_avg / atr.replace(0, np.nan))
        plus_di = plus_di.fillna(0)
        minus_di = minus_di.fillna(0)
        data[f'pdi{p}'] = plus_di
        data[f'mdi{p}'] = minus_di
        di_sum = plus_di + minus_di
        dx = 100 * (abs(plus_di - minus_di) / di_sum.replace(0, np.nan))
        dx = dx.fillna(0)
        data[f'adx{p}'] = dx.rolling(p).mean()

    return data

def calculate_volatility_indicators(data):
    """计算波动率指标"""
    data['bollinger_middle'] = data['close'].rolling(20).mean()
    bb_std = data['close'].rolling(20).std()
    data['bollinger_upper'] = data['bollinger_middle'] + 2 * bb_std
    data['bollinger_lower'] = data['bollinger_middle'] - 2 * bb_std
    return data

def calculate_other_indicators(data):
    """计算其他重要指标"""
    typical_price = (data['high'] + data['low'] + data['close']) / 3
    cumulative_vwap = (typical_price * data['volume']).cumsum()
    cumulative_volume = data['volume'].cumsum()
    data['vwap'] = cumulative_vwap / cumulative_volume
    data = calculate_parabolic_sar(data)
    return data

def calculate_parabolic_sar(data, af_start=0.02, af_increment=0.02, af_max=0.2):
    """计算抛物线转向指标 (Parabolic SAR)"""
    high = data['high'].values
    low = data['low'].values
    close = data['close'].values

    if len(data) < 2:
        data['parabolicsar'] = pd.Series(low, index=data.index)
        return data

    sar = np.zeros(len(data))
    ep = np.zeros(len(data))
    af = np.zeros(len(data))
    trend = np.zeros(len(data), dtype=int)

    sar[0] = high[0] if close[0] < close[1] else low[0]
    trend[0] = 1 if close[0] > close[1] else -1
    ep[0] = high[0] if trend[0] == 1 else low[0]
    af[0] = af_start

    for i in range(1, len(data)):
        if trend[i-1] == 1:
            sar[i] = sar[i-1] + af[i-1] * (ep[i-1] - sar[i-1])
            sar[i] = min(sar[i], low[i-1], low[i-2] if i >= 2 else low[i-1])
            if high[i] > ep[i-1]:
                ep[i] = high[i]
                af[i] = min(af[i-1] + af_increment, af_max)
            else:
                ep[i] = ep[i-1]
                af[i] = af[i-1]
            if low[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep[i-1]
                ep[i] = low[i]
                af[i] = af_start
            else:
                trend[i] = 1
        else:
            sar[i] = sar[i-1] + af[i-1] * (ep[i-1] - sar[i-1])
            sar[i] = max(sar[i], high[i-1], high[i-2] if i >= 2 else high[i-1])
            if low[i] < ep[i-1]:
                ep[i] = low[i]
                af[i] = min(af[i-1] + af_increment, af_max)
            else:
                ep[i] = ep[i-1]
                af[i] = af[i-1]
            if high[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep[i-1]
                ep[i] = high[i]
                af[i] = af_start
            else:
                trend[i] = -1

    data['parabolicsar'] = sar
    return data

def calculate_cross_signals(data):
    """计算交叉信号"""
    data["ema_golden_cross"] = (data["ema5"] > data["ema20"]) & (data["ema5"].shift(1) <= data["ema20"].shift(1))
    data["ema_death_cross"] = (data["ema5"] < data["ema20"]) & (data["ema5"].shift(1) >= data["ema20"].shift(1))
    data["golden_triangle"] = (data["ema5"] > data["ema20"]) & (data["ema20"] > data["ema200"]) & (data["ema5"].shift(30) <= data["ema20"].shift(30)) & (data["ema20"].shift(30) <= data["ema200"].shift(30))
    data["death_triangle"] = (data["ema5"] < data["ema20"]) & (data["ema20"] < data["ema200"]) & (data["ema5"].shift(30) >= data["ema20"].shift(30)) & (data["ema20"].shift(30) >= data["ema200"].shift(30))
    data["macd_golden_cross"] = (data["macd_dif"] > data["macd_signal"]) & (data["macd_dif"].shift(1) <= data["macd_signal"].shift(1))
    data["macd_death_cross"] = (data["macd_dif"] < data["macd_signal"]) & (data["macd_dif"].shift(1) >= data["macd_signal"].shift(1))
    data["open_close_change_%"] = safe_divide(data["close"] - data["open"], data["open"]) * 100
    return data

def calculate_rolling_indicators(data):
    """计算滚动窗口指标"""
    columns_to_analyze = [
        'volume', 'amount', 'amplitude', 'change_percent', 'change_amount', 
        'turnover_rate', 'volume_ratio5', 'volume_ratio20'
    ]

    data['high_30d'] = data['high'].rolling(30).max()
    data['low_30d'] = data['low'].rolling(30).min()
    data['close_3d_ago'] = data['close'].shift(3)
    data['high_125d'] = data['high'].rolling(125).max()
    data['low_125d'] = data['low'].rolling(125).min()
    data['high_250d'] = data['high'].rolling(250).max()
    data['low_250d'] = data['low'].rolling(250).min()

    data = calculate_percentiles_optimized(data, columns_to_analyze, window_size=500)
    return data

def calculate_price_amplitude_chip_concentration(data, lookback_periods=[20, 60, 250], concentration_percentiles=[70, 90]):
    """价格振幅法计算筹码集中度 - numpy加速版本"""
    print("  - 计算价格振幅法筹码集中度...")
    n = len(data)
    # 转换为numpy数组加速
    low_arr = data['low'].values
    high_arr = data['high'].values
    avg_price_arr = data['avg_price'].values
    volume_arr = data['volume'].values

    # 预分配结果数组
    out_arrays = {}
    for lb in lookback_periods:
        for cp in concentration_percentiles:
            out_arrays[f'price_amp_market_chip_concentration_{lb}_{cp}'] = np.full(n, np.nan)
            out_arrays[f'price_amp_chip_price_range_{lb}_{cp}'] = np.full(n, np.nan)
            out_arrays[f'price_amp_chip_min_{lb}_{cp}'] = np.full(n, np.nan)
            out_arrays[f'price_amp_chip_max_{lb}_{cp}'] = np.full(n, np.nan)

    for lb in lookback_periods:
        print(f"    - 计算 {lb} 天价格振幅法筹码集中度...")
        min_periods = int(lb * 0.8)
        for i in range(min_periods - 1, n):
            start = max(0, i - lb + 1)
            window_low = low_arr[start:i+1]
            window_high = high_arr[start:i+1]
            window_avg = avg_price_arr[start:i+1]
            window_vol = volume_arr[start:i+1]
            if len(window_low) < min_periods:
                continue
            min_price = np.min(window_low)
            max_price = np.max(window_high)
            if min_price == max_price or np.isnan(min_price) or np.isnan(max_price):
                continue
            bins = np.linspace(min_price, max_price, 51)
            hist, bin_edges = np.histogram(window_avg, bins=bins, weights=window_vol)
            total_vol = np.sum(window_vol)
            if total_vol == 0:
                continue
            cum_hist = np.cumsum(hist) / total_vol
            for cp in concentration_percentiles:
                lower_perc = (100 - cp) / 2.0
                upper_perc = 100 - lower_perc
                low_idx = np.searchsorted(cum_hist, lower_perc/100)
                high_idx = np.searchsorted(cum_hist, upper_perc/100)
                low_idx = min(max(low_idx, 0), len(bin_edges)-2)
                high_idx = min(max(high_idx, 0), len(bin_edges)-2)
                chip_min = bin_edges[low_idx]
                chip_max = bin_edges[high_idx+1]
                price_range = chip_max - chip_min
                concentration = (price_range / (max_price - min_price)) * 100
                out_arrays[f'price_amp_market_chip_concentration_{lb}_{cp}'][i] = concentration
                out_arrays[f'price_amp_chip_price_range_{lb}_{cp}'][i] = price_range
                out_arrays[f'price_amp_chip_min_{lb}_{cp}'][i] = chip_min
                out_arrays[f'price_amp_chip_max_{lb}_{cp}'][i] = chip_max

    # 写回DataFrame
    for col_name, arr in out_arrays.items():
        data[col_name] = arr

    # 设置默认列
    if 60 in lookback_periods and 70 in concentration_percentiles:
        data['price_amp_market_chip_concentration'] = data['price_amp_market_chip_concentration_60_70']
        data['price_amp_chip_price_range'] = data['price_amp_chip_price_range_60_70']
        data['price_amp_chip_min'] = data['price_amp_chip_min_60_70']
        data['price_amp_chip_max'] = data['price_amp_chip_max_60_70']

    # 向前填充
    data = data.ffill()
    return data

def calculate_cost_spread_chip_concentration(data, windows=[20, 60, 250], percentiles=[70, 90]):
    """成本价差法计算筹码集中度 - 向量化滚动分位数版本"""
    print("  - 计算成本价差法筹码集中度...")
    for window in windows:
        for p in percentiles:
            low_pct = (100 - p) / 2.0
            high_pct = 100 - low_pct
            low_price = data['avg_price'].rolling(window, min_periods=window//2).quantile(low_pct/100)
            high_price = data['avg_price'].rolling(window, min_periods=window//2).quantile(high_pct/100)
            avg_price = (high_price + low_price) / 2
            concentration = (high_price - low_price) / avg_price.replace(0, np.nan) * 100
            concentration = concentration.fillna(0)
            data[f'cost_spread_chip_min_{window}_{p}'] = low_price
            data[f'cost_spread_chip_max_{window}_{p}'] = high_price
            data[f'cost_spread_chip_price_range_{window}_{p}'] = high_price - low_price
            data[f'cost_spread_chip_concentration_{window}_{p}'] = concentration

    if 60 in windows and 70 in percentiles:
        data['cost_spread_chip_concentration'] = data['cost_spread_chip_concentration_60_70']
    data = data.ffill()
    return data

def calculate_intensive_trading_range(data, lookback_period=126):
    """计算密集交易区间 - numpy加速"""
    print("  - 计算密集交易区间...")
    n = len(data)
    low_arr = data['low'].values
    high_arr = data['high'].values
    close_arr = data['close'].values
    volume_arr = data['volume'].values
    intensive_min = np.full(n, np.nan)
    intensive_max = np.full(n, np.nan)

    for i in range(lookback_period, n):
        start = i - lookback_period
        win_low = low_arr[start:i]
        win_high = high_arr[start:i]
        win_close = close_arr[start:i]
        win_vol = volume_arr[start:i]
        min_price = np.min(win_low)
        max_price = np.max(win_high)
        if min_price == max_price or np.isnan(min_price) or np.isnan(max_price):
            continue
        price_bins = np.linspace(min_price, max_price, 30)
        hist, bin_edges = np.histogram(win_close, bins=price_bins, weights=win_vol)
        if len(hist) == 0:
            continue
        max_bin_idx = np.argmax(hist)
        intensive_min[i] = bin_edges[max_bin_idx]
        intensive_max[i] = bin_edges[max_bin_idx + 1]

    data["intensive_trading_min"] = intensive_min
    data["intensive_trading_max"] = intensive_max
    return data

# 在 calculate_ema_cross_status 函数中，修正 numpy array 无法调用 .shift() 的问题
def calculate_ema_cross_status(data):
    """计算EMA交叉状态"""
    ema_pairs = [
        ('ema5', 'ema10', 'ema5_10'),
        ('ema5', 'ema20', 'ema5_20'),
        ('ema10', 'ema20', 'ema10_20'),
        ('ema20', 'ema50', 'ema20_50'),
        ('ema50', 'ema200', 'ema50_200'),
        ('ema20', 'ema200', 'ema20_200'),
        ('ema12', 'ema26', 'ema12_26'),
        ('ema5', 'ema13', 'ema5_13'),
        ('ema5', 'ema34', 'ema5_34'),
        ('ema13', 'ema34', 'ema13_34')
    ]

    for fast_col, slow_col, prefix in ema_pairs:
        if fast_col in data.columns and slow_col in data.columns:
            status = np.where(data[fast_col] > data[slow_col], 'Golden', 'Death')
            # 转换为 pandas Series 以便使用 .shift() 和 .groupby()
            status_series = pd.Series(status, index=data.index)
            data[f'{prefix}_status'] = status_series
            shifted = status_series != status_series.shift()
            data[f'{prefix}_streak'] = shifted.cumsum().groupby(shifted.cumsum()).cumcount() + 1

    # EMA5_13_34 复合状态
    def ema5_13_34_status(ema5, ema13, ema34):
        cond_golden = (ema5 > ema13) & (ema13 > ema34)
        cond_death = (ema5 < ema13) & (ema13 < ema34)
        res = np.where(cond_golden, 'Golden_Triangle', np.where(cond_death, 'Death_Triangle', 'Mixed'))
        return res

    status_arr = ema5_13_34_status(data['ema5'], data['ema13'], data['ema34'])
    status_series = pd.Series(status_arr, index=data.index)
    data['ema5_13_34_status'] = status_series
    shifted = status_series != status_series.shift()
    data['ema5_13_34_streak'] = shifted.cumsum().groupby(shifted.cumsum()).cumcount() + 1
    return data

# 同样修正 calculate_macd_status 函数
def calculate_macd_status(data):
    """计算MACD状态"""
    status = np.where(data['macd_dif'] > data['macd_signal'], 'Golden', 'Death')
    status_series = pd.Series(status, index=data.index)
    data['macd_status'] = status_series
    shifted = status_series != status_series.shift()
    streak = shifted.cumsum().groupby(shifted.cumsum()).cumcount() + 1
    data['macd_golden_streak'] = np.where(status_series == 'Golden', streak, 0)
    data['macd_death_streak'] = np.where(status_series == 'Death', streak, 0)
    return data

def calculate_cross_status_indicators(data):
    """计算交叉状态指标"""
    if 'vol_ema5' in data.columns and 'vol_ema20' in data.columns:
        data['vol_ema5_20_cross_status'] = np.where(data['vol_ema5'] >= data['vol_ema20'], 'golden', 'death')
        shifted = data['vol_ema5_20_cross_status'] != data['vol_ema5_20_cross_status'].shift()
        data['vol_ema5_20_cross_streak'] = shifted.cumsum().groupby(shifted.cumsum()).cumcount() + 1

    if 'vol_ema5' in data.columns and 'vol_ema10' in data.columns:
        data['vol_ema5_10_cross_status'] = np.where(data['vol_ema5'] >= data['vol_ema10'], 'golden', 'death')
        shifted = data['vol_ema5_10_cross_status'] != data['vol_ema5_10_cross_status'].shift()
        data['vol_ema5_10_cross_streak'] = shifted.cumsum().groupby(shifted.cumsum()).cumcount() + 1

    if 'macd_dif' in data.columns and 'macd_signal' in data.columns:
        data['macd_cross_status'] = np.where(data['macd_dif'] >= data['macd_signal'], 'golden', 'death')
        shifted = data['macd_cross_status'] != data['macd_cross_status'].shift()
        data['macd_cross_streak'] = shifted.cumsum().groupby(shifted.cumsum()).cumcount() + 1

    return data

def calculate_signal_conditions(data):
    """计算信号条件 - 完全向量化版本，确保所有信号列为布尔类型"""
    print("  - 计算信号条件...")

    # 初始化信号列 - 明确指定为布尔类型
    signal_cols = [
        'bottom_signal_cond', 'top_signal_cond', 
        'bottom_entry_signal_cond', 'top_exit_signal_cond',
        'continuation_signal_cond', 'decline_continuation_cond',
        'accumulation_cond', 'distribution_cond',
        'multi_timeframe_chip_confirm_bottom_cond', 
        'multi_timeframe_chip_confirm_top_cond'
    ]
    
    # 确保所有信号列为布尔类型
    for col in signal_cols:
        if col not in data.columns:
            data[col] = False  # 初始化为False
        data[col] = data[col].astype(bool)  # 强制转换为布尔类型

    # 初始化Signal_Quality为浮点数
    if 'signal_quality' not in data.columns:
        data['signal_quality'] = 0.0
    data['signal_quality'] = data['signal_quality'].astype(float)

    # 1. 底部信号
    bottom_signal = (
        data['price_amp_market_chip_concentration'] < 25
    ) & (
        data['volume'] < data['vol_ema20'] * 0.7
    ) & (
        data['close'] < data['price_amp_chip_max'] * 0.85
    )

    # 2. 顶部信号
    volume_divergence = (data['high'] >= data['high_30d']) & (data['volume'] < data['vol_ema20'] * 0.9)
    ema_resistance = (data['close'] < data['ema20']) & (data['ema20'] < data['ema60'])
    macd_top = (data['macd_dif'] < data['macd_signal']) & (data['macd_histogram'] < 0)
    kdj_top = (data['kdj_k'] > 80) & (data['kdj_k'] < data['kdj_d'])
    top_signal = (
        (data['price_amp_market_chip_concentration'] > 65) &
        (data['volume'] > data['vol_ema20'] * 1.3) &
        (data['close_chg%'] < 1.0) &
        (data['price_amp_chip_min'] > data['ema60'] * 1.15) &
        (volume_divergence | ema_resistance) &
        (macd_top | kdj_top)
    )

    # 3. 底部建仓条件
    bottom_entry = (
        (data['price_amp_market_chip_concentration'] < 30) &
        (data['close'] > data['price_amp_chip_max']) &
        (data['volume'] > data['vol_ema20'] * 1.8) &
        (data['volume_ratio5'] > 2.5) &
        (data['ema5'] > data['ema20']) &
        (data['macd_histogram'] > 0) &
        (data['macd_dif'] > 0)
    )

    # 4. 顶部离场条件
    atr_threshold = np.where(data['close'] > 0, safe_divide(data['atr14'], data['close']) * 100 * 1.2, 3.0)
    price_cond_top = (
        (data['close'] < data['ema5']) &
        (data['close_chg%'] < -np.maximum(1.5, atr_threshold)) &
        (data['volume'] > data['vol_ema20'] * 2)
    )
    div_cond = (data['rsi14'] > 70) & (data['close'] < data['close_3d_ago'])
    top_exit = price_cond_top | div_cond

    # 5. 上涨中继确认
    continuation = (
        (data['price_amp_market_chip_concentration'] > 30) &
        (data['price_amp_market_chip_concentration'] < 40) &
        (data['price_amp_chip_min'] > data['ema20']) &
        (data['mfi'] > 65)
    )

    # 6. 下跌中继确认
    decline_continuation = (
        (data['price_amp_market_chip_concentration'] > 60) &
        (data['volume'] < data['vol_ema20'] * 0.8) &
        (data['close'] < data['ema60'])
    )

    # 7. 机构吸筹/派发
    accumulation = (
        (data['volume_ratio5'] > 2.5) &
        (data['close'] > data['open']) &
        (data['close'] < data['price_amp_chip_max'] * 0.95)
    )
    distribution = (
        (data['volume_ratio5'] > 3.0) &
        (data['close'] < data['open']) &
        (data['close'] > data['price_amp_chip_min'] * 1.15)
    )

    # 8. 多周期共振
    daily_chip = data['price_amp_market_chip_concentration']
    # 计算周线筹码加权（450日加权移动平均）——向量化
    # 权重为线性递减 linspace(1.5, 0.5, m)：加权和 = 1.5*Σx - Σ(j*x)/(m-1)，Σw = m
    chip_vals = daily_chip.to_numpy(dtype=np.float64)
    n_rows = len(chip_vals)
    window_w = 450
    pos = np.arange(n_rows, dtype=np.float64)
    clean = np.where(np.isnan(chip_vals), 0.0, chip_vals)
    cum1 = np.cumsum(clean)
    cum2 = np.cumsum(clean * pos)
    cum_nan = np.cumsum(np.isnan(chip_vals))
    c1p = np.concatenate(([0.0], cum1))
    c2p = np.concatenate(([0.0], cum2))
    cnp = np.concatenate(([0.0], cum_nan))
    t_idx = np.arange(n_rows)
    m = np.minimum(t_idx + 1, window_w)
    start = (t_idx - m + 1).astype(np.int64)
    s1 = c1p[t_idx + 1] - c1p[start]
    s2 = c2p[t_idx + 1] - c2p[start]
    s2_rel = s2 - start * s1
    s_nan = cnp[t_idx + 1] - cnp[start]
    denom = np.where(m > 1, m - 1, 1)
    # 权重和：m>=2 时 linspace(1.5,0.5,m) 之和恰为 m；m=1 时只有一个权重 1.5
    weight_sum = np.where(m > 1, m, 1.5)
    with np.errstate(divide='ignore', invalid='ignore'):
        weighted_avg = (1.5 * s1 - s2_rel / denom) / weight_sum
    weekly_chip = pd.Series(np.where(s_nan > 0, np.nan, weighted_avg), index=data.index)
    monthly_trend = data['close'] > data['ema60']

    # 复用已有的交叉状态列
    ema_cond = data.get('ema20_50_status', pd.Series('Death')) == 'Death'
    macd_cond = (data.get('macd_cross_streak', pd.Series(0)) > 5) & (data.get('macd_cross_status', pd.Series('death')) == 'death')
    multi_timeframe_confirmed = ema_cond | macd_cond

    multi_bottom = (
        daily_chip.notna() & weekly_chip.notna() &
        (daily_chip < 35) &
        (weekly_chip < 40) &
        monthly_trend
    )

    multi_top = (
        daily_chip.notna() & weekly_chip.notna() &
        (daily_chip > 60) &
        (weekly_chip > 65) &
        (~monthly_trend) &
        multi_timeframe_confirmed &
        top_signal
    )

    # 9. Signal_Quality
    quality = np.zeros(len(data), dtype=float)
    # 底部信号质量
    mask_bot = bottom_signal
    chip_score_bot = np.maximum(0, 1 - daily_chip/100)
    vol_score_bot = np.maximum(0, 1 - np.minimum(1, data['volume_ratio5']))
    price_position = safe_divide(data['close'] - data['price_amp_chip_min'], data['price_amp_chip_max'] - data['price_amp_chip_min'])
    price_score_bot = np.maximum(0, 1 - price_position.fillna(0.5))
    quality[mask_bot] = (chip_score_bot[mask_bot]*0.4 + vol_score_bot[mask_bot]*0.3 + price_score_bot[mask_bot]*0.3)

    # 顶部信号质量
    mask_top = top_signal & ~bottom_signal  # 避免重叠
    chip_score_top = np.minimum(1, daily_chip/100)
    vol_score_top = np.minimum(1, data['volume_ratio5']/3)
    rsi_score_top = np.minimum(1, data['rsi14']/100)
    quality[mask_top] = (chip_score_top[mask_top]*0.4 + vol_score_top[mask_top]*0.3 + rsi_score_top[mask_top]*0.3)

    # 底部建仓质量
    mask_entry = bottom_entry & ~bottom_signal & ~top_signal
    quality[mask_entry] = (chip_score_bot[mask_entry]*0.4 + vol_score_top[mask_entry]*0.4 + 
                           np.minimum(1, np.maximum(0, data['macd_histogram'][mask_entry]/0.1))*0.2)

    # 顶部离场质量
    mask_exit = top_exit & ~(bottom_signal|top_signal|bottom_entry)
    quality[mask_exit] = (np.minimum(1, np.abs(data['close_chg%'][mask_exit])/5)*0.5 +
                          np.minimum(1, data['volume_ratio5'][mask_exit]/3)*0.3 +
                          np.minimum(1, data['rsi14'][mask_exit]/100)*0.2)

    quality = np.clip(quality, 0, 1)

    # 赋值 - 确保所有信号列为布尔类型
    data['bottom_signal_cond'] = bottom_signal.astype(bool)
    data['top_signal_cond'] = top_signal.astype(bool)
    data['bottom_entry_signal_cond'] = bottom_entry.astype(bool)
    data['top_exit_signal_cond'] = top_exit.astype(bool)
    data['continuation_signal_cond'] = continuation.astype(bool)
    data['decline_continuation_cond'] = decline_continuation.astype(bool)
    data['accumulation_cond'] = accumulation.astype(bool)
    data['distribution_cond'] = distribution.astype(bool)
    data['multi_timeframe_chip_confirm_bottom_cond'] = multi_bottom.astype(bool)
    data['multi_timeframe_chip_confirm_top_cond'] = multi_top.astype(bool)
    data['signal_quality'] = quality.astype(float)

    return data

# ========== SQLite 数据库操作函数 ==========

def get_db_connection(db_path):
    """获取SQLite数据库连接"""
    return sqlite3.connect(db_path)

def get_stock_latest_analysis_date(conn, stock_code):
    """
    获取某股票在hk_daily_kline_analysis表中的最新分析数据日期
    返回: (latest_analysis_date, stock_name) 或 (None, None)
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT date, stock_name 
            FROM hk_daily_kline_analysis 
            WHERE stock_code = ? 
            ORDER BY date DESC 
            LIMIT 1
        """, (stock_code,))
        result = cursor.fetchone()
        if result:
            return result[0], result[1]
        return None, None
    except sqlite3.OperationalError as e:
        # 表可能不存在
        print(f"  警告: 查询hk_daily_kline_analysis表时出错: {e}")
        return None, None

def get_stock_latest_kline_date(conn, stock_code):
    """
    获取某股票在hk_hist_daily_kline表中的最新原始K线数据日期
    返回: latest_kline_date 或 None
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT date 
            FROM hk_hist_daily_kline 
            WHERE stock_code = ? 
            ORDER BY date DESC 
            LIMIT 1
        """, (stock_code,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except sqlite3.OperationalError as e:
        print(f"  警告: 查询hk_hist_daily_kline表时出错: {e}")
        return None

def get_stock_name(conn, stock_code):
    """从hk_hist_daily_kline表获取股票名称"""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT stock_name 
            FROM hk_hist_daily_kline 
            WHERE stock_code = ? 
            LIMIT 1
        """, (stock_code,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None
    except sqlite3.OperationalError:
        return None

def save_analysis_to_db(conn, df, stock_code, stock_name):
    """
    将分析数据保存到hk_daily_kline_analysis表
    使用INSERT OR REPLACE避免重复
    """
    cursor = conn.cursor()
    
    # 获取表的列名（排除id，因为它是自增主键）
    cursor.execute("PRAGMA table_info(hk_daily_kline_analysis)")
    table_columns = [row[1] for row in cursor.fetchall()]
    
    # 过滤DataFrame列，只保留表中存在的列
    df_columns = [col for col in df.columns if col in table_columns]
    
    if not df_columns:
        print(f"  错误: DataFrame中没有与hk_daily_kline_analysis匹配的列")
        return 0
    
    # 准备数据
    df_to_save = df[df_columns].copy()
    
    # 确保日期格式为字符串
    if 'date' in df_to_save.columns:
        df_to_save['date'] = pd.to_datetime(df_to_save['date']).dt.strftime('%Y-%m-%d')
    
    # 定义需要转换的布尔列 - 所有信号条件列
    bool_columns = [
        'bottom_signal_cond', 'top_signal_cond', 
        'bottom_entry_signal_cond', 'top_exit_signal_cond',
        'continuation_signal_cond', 'decline_continuation_cond',
        'accumulation_cond', 'distribution_cond',
        'multi_timeframe_chip_confirm_bottom_cond', 
        'multi_timeframe_chip_confirm_top_cond'
    ]
    
    # 将布尔列转换为整数 (SQLite存储为0/1)
    for col in bool_columns:
        if col in df_to_save.columns:
            # 先确保是布尔类型，再转换为整数
            df_to_save[col] = df_to_save[col].astype(bool).astype(int)
    
    # 确保signal_quality为浮点数
    if 'signal_quality' in df_to_save.columns:
        df_to_save['signal_quality'] = df_to_save['signal_quality'].astype(float)
    
    # 构建INSERT OR REPLACE语句
    placeholders = ','.join(['?' for _ in df_columns])
    columns_str = ','.join([f'"{col}"' for col in df_columns])
    # 使用INSERT OR IGNORE忽略重复记录，或者使用INSERT OR REPLACE替换
    sql = f'INSERT OR IGNORE INTO hk_daily_kline_analysis ({columns_str}) VALUES ({placeholders})'
    
    # 批量插入
    records = df_to_save.to_records(index=False).tolist()
    cursor.executemany(sql, records)
    conn.commit()
    
    return len(records)
    
def convert_boolean_columns_from_db(df):
    """
    将从数据库加载的数据中的布尔列从整数转换为布尔类型
    """
    bool_columns = [
        'bottom_signal_cond', 'top_signal_cond', 
        'bottom_entry_signal_cond', 'top_exit_signal_cond',
        'continuation_signal_cond', 'decline_continuation_cond',
        'accumulation_cond', 'distribution_cond',
        'multi_timeframe_chip_confirm_bottom_cond', 
        'multi_timeframe_chip_confirm_top_cond'
    ]
    
    for col in bool_columns:
        if col in df.columns:
            # 数据库存储为0/1，转换为布尔类型
            df[col] = df[col].astype(bool)
    
    return df
    
def load_kline_data_from_db(conn, stock_code):
    """
    从hk_hist_daily_kline表加载某股票的原始K线数据
    返回: DataFrame
    """
    query = """
        SELECT 
            date,
            stock_code,
            stock_name,
            Open,
            High,
            Low,
            Close,
            Volume,
            Amount,
            Amplitude,
            Change_Percent,
            Change_Amount,
            Turnover_Rate,
            Previous_Close
        FROM hk_hist_daily_kline
        WHERE stock_code = ?
        ORDER BY date ASC
    """
    df = pd.read_sql_query(query, conn, params=(stock_code,))
    
    if df.empty:
        return df
    
    # 确保日期格式
    df['date'] = pd.to_datetime(df['date'])
    
    # 转换所有列名为小写
    df = convert_columns_to_lowercase(df)
    
    return df

def delete_stock_analysis(conn, stock_code):
    """删除某股票的所有分析数据"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hk_daily_kline_analysis WHERE stock_code = ?", (stock_code,))
    conn.commit()
    return cursor.rowcount

# ========== 核心计算函数 ==========

def calculate_technical_indicators_optimized_sqlite(stock_code, db_path):
    """
    优化后的技术指标计算函数 - 直接从SQLite读取，保存到SQLite
    """
    try:
        print(f"开始处理: {stock_code}")
        start_time = time.time()
        
        # 连接数据库
        conn = get_db_connection(db_path)
        
        try:
            # 1. 获取最新分析日期
            latest_analysis_date, existing_stock_name = get_stock_latest_analysis_date(conn, stock_code)
            
            # 2. 获取最新K线日期
            latest_kline_date = get_stock_latest_kline_date(conn, stock_code)
            
            # 3. 获取股票名称
            stock_name = get_stock_name(conn, stock_code)
            if not stock_name:
                print(f"  错误: 未找到股票 {stock_code} 的名称")
                return None
            
            # 4. 根据日期比较决定是否计算
            if latest_kline_date is None:
                print(f"  [股票代码]{stock_code} K线原始数据缺失，无法进行计算")
                return None
            
            # 转换为日期对象进行比较
            latest_kline_date_dt = pd.to_datetime(latest_kline_date).date()
            
            if latest_analysis_date:
                latest_analysis_date_dt = pd.to_datetime(latest_analysis_date).date()
                
                if latest_analysis_date_dt > latest_kline_date_dt:
                    print(f"  [股票代码]{stock_code} K线原始数据缺失或K线分析数据有误，需进行核查")
                    print(f"    分析日期: {latest_analysis_date_dt} > K线日期: {latest_kline_date_dt}")
                    return None
                    
                elif latest_analysis_date_dt == latest_kline_date_dt:
                    print(f"  [股票代码]{stock_code} K线分析数据已存在，无需重复计算")
                    return None
                    
                else:  # latest_analysis_date_dt < latest_kline_date_dt
                    print(f"  [股票代码]{stock_code} 需要更新分析数据")
                    print(f"    分析日期: {latest_analysis_date_dt} < K线日期: {latest_kline_date_dt}")
            
            else:
                print(f"  [股票代码]{stock_code} 首次计算分析数据")
            
            # 5. 加载原始K线数据 (列名已转换为小写)
            data = load_kline_data_from_db(conn, stock_code)
            
            if data.empty:
                print(f"  [股票代码]{stock_code} K线原始数据为空")
                return None
            
            # 6. 数据预处理 - 列名已经是小写了
            # 确保日期列正确
            data["date"] = pd.to_datetime(data["date"])
            data = data.drop_duplicates(subset=["date"], keep='first')
            data.sort_values("date", inplace=True)
            data.reset_index(drop=True, inplace=True)
            
            # 7. 计算技术指标
            print("  - 计算基础指标...")
            data = calculate_basic_indicators(data)
            print("  - 计算EMA指标...")
            data = calculate_ema_indicators(data)
            print("  - 计算成交量指标...")
            data = calculate_volume_indicators(data)
            print("  - 计算波动率指标...")
            data = calculate_volatility_indicators(data)
            print("  - 计算其他重要指标...")
            data = calculate_other_indicators(data)
            print("  - 计算交叉状态指标...")
            data = calculate_cross_status_indicators(data)
            print("  - 计算动量指标...")
            data = calculate_momentum_indicators(data)
            print("  - 计算交叉信号...")
            data = calculate_cross_signals(data)
            print("  - 计算滚动指标...")
            data = calculate_rolling_indicators(data)
            print("  - 计算价格振幅法筹码集中度...")
            data = calculate_price_amplitude_chip_concentration(data)
            print("  - 计算成本价差法筹码集中度...")
            data = calculate_cost_spread_chip_concentration(data)
            print("  - 计算密集交易区间...")
            data = calculate_intensive_trading_range(data)
            print("  - 计算EMA交叉状态...")
            data = calculate_ema_cross_status(data)
            print("  - 计算MACD状态...")
            data = calculate_macd_status(data)
            print("  - 计算信号条件...")
            data = calculate_signal_conditions(data)
            
            # 8. 保存到数据库 - 直接插入新记录，不删除旧数据
            print(f"  - 保存分析数据到数据库...")
            
            # 确保stock_code和stock_name在数据中
            data['stock_code'] = stock_code
            data['stock_name'] = stock_name
            
            # 修改：直接使用INSERT OR REPLACE，不预先删除旧数据
            # 但需要过滤掉已存在的日期记录，避免重复
            # 获取已存在的日期
            existing_dates = get_existing_analysis_dates(conn, stock_code)
            if existing_dates:
                # 过滤掉已存在的日期记录
                data_to_save = data[~data['date'].isin(existing_dates)]
                if data_to_save.empty:
                    print(f"    没有新的分析数据需要保存")
                    return data
                saved_count = save_analysis_to_db(conn, data_to_save, stock_code, stock_name)
                print(f"    成功保存 {saved_count} 条新分析数据 (跳过 {len(existing_dates)} 条已存在记录)")
            else:
                # 首次保存，直接保存所有数据
                saved_count = save_analysis_to_db(conn, data, stock_code, stock_name)
                print(f"    成功保存 {saved_count} 条分析数据")
            
            end_time = time.time()
            print(f"完成处理: {stock_code} - 耗时: {end_time - start_time:.2f}秒")
            return data
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"处理过程中发生错误 {stock_code}: {e}")
        traceback.print_exc()
        return None

def get_existing_analysis_dates(conn, stock_code):
    """
    获取某股票在hk_daily_kline_analysis表中已存在的分析日期列表
    返回: set of dates
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT date 
            FROM hk_daily_kline_analysis 
            WHERE stock_code = ?
        """, (stock_code,))
        results = cursor.fetchall()
        if results:
            # 将日期转换为datetime对象以便比较
            dates = set()
            for row in results:
                try:
                    # 尝试解析日期
                    date_obj = pd.to_datetime(row[0])
                    dates.add(date_obj)
                except:
                    pass
            return dates
        return set()
    except sqlite3.OperationalError as e:
        # 表可能不存在
        print(f"  警告: 查询hk_daily_kline_analysis表时出错: {e}")
        return set()
        
def process_single_stock_sqlite(args):
    """单个股票处理函数 - SQLite版本"""
    ticker, db_path = args
    return calculate_technical_indicators_optimized_sqlite(ticker, db_path)

def calculate_technical_indicators_parallel_sqlite(tickers, db_path, max_workers=None):
    """并行计算技术指标 - SQLite版本"""
    if max_workers is None:
        max_workers = min(mp.cpu_count(), len(tickers))
    print(f"使用 {max_workers} 个进程并行计算技术指标...")
    print(f"处理 {len(tickers)} 个股票")
    
    args_list = [(ticker, db_path) for ticker in tickers]
    results = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {executor.submit(process_single_stock_sqlite, args): args[0] for args in args_list}
        completed = 0
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1
                print(f"进度: {completed}/{len(tickers)} - 完成: {ticker}")
            except Exception as e:
                print(f"处理 {ticker} 时发生错误: {e}")
                completed += 1
                
    print("所有股票技术指标计算完成!")
    return results

# ========== 日志工具 ==========
def setup_logging(log_dir):
    """设置日志 - 每次运行时覆盖原有日志文件"""
    log_file = os.path.join(log_dir, 'Daily_TA2_Calculate_Indicators_akshare_mproc.log')
    
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    import logging
    
    # 配置日志 - 使用 'w' 模式覆盖原有日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8', mode='w'),  # mode='w' 表示覆盖写入
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)
    
# ========== 主程序 ==========

# === 添加UTL路径到系统路径 ===
script_dir = Path(__file__).resolve().parent

core_dir = script_dir.parent
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

from utl.stock_analysis_utl import get_project_root

core_dir_from_utils = get_project_root()
project_dir = core_dir_from_utils.parent

if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

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
    import ipykernel
    if ipykernel:
        sys.stdout.encoding = 'utf-8'
        sys.stderr.encoding = 'utf-8'

setup_windows_encoding()

def main():
    # 初始化日志
    log_dir = os.path.join(project_dir, 'Log')
    logger = setup_logging(log_dir)
    
    try:
        config_path = os.path.join(project_dir, 'config', 'stock_data_analysis.par')
        CONFIG = load_config(config_path, project_dir)
        logger.info(f"配置文件加载成功: {config_path}")
        GlobalConfig.update_paths(CONFIG, project_dir)
        
        logger.info("=" * 50)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"配置文件位置: {config_path}")
        logger.info(f"数据目录: {GlobalConfig.full_data_dir}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")
        logger.info(f"日志目录: {GlobalConfig.full_log_dir}")
        
        # 数据库路径
        db_path = os.path.join(project_dir, 'SQLiteDB', 'HK_Stock.db')
        if not os.path.exists(db_path):
            logger.error(f"数据库文件不存在: {db_path}")
            return
        
        tickers = CONFIG.get('tickers', [])
        if not tickers:
            logger.warning("配置文件中未找到tickers设置")
            return

        calculate_indicators = CONFIG.get('calculate_ta_indicators', False)
        use_multiprocessing = CONFIG.get('use_multiprocessing', True)
        max_workers = CONFIG.get('max_workers', None)

        if calculate_indicators:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"{current_time} 开始计算交易数据技术分析指标...")

            if use_multiprocessing and len(tickers) > 1:
                results = calculate_technical_indicators_parallel_sqlite(
                    tickers, 
                    db_path,
                    max_workers=max_workers
                )
                successful = sum(1 for r in results if r is not None)
            else:
                logger.info("使用单进程模式...")
                successful = 0
                for ticker in tickers:
                    result = calculate_technical_indicators_optimized_sqlite(ticker, db_path)
                    if result is not None:
                        successful += 1
            
            logger.info(f"成功处理 {successful}/{len(tickers)} 个股票")
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ✅ 交易数据技术分析指标计算完成！")
        else:
            logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 计算交易数据技术分析指标未启用，跳过此步骤。")
            
    except Exception as e:
        logger.error(f"发生未知错误: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        if 'get_ipython' not in globals():
            sys.exit(1)
        else:
            logger.info("在Jupyter环境中运行，程序继续但可能无法正常工作")

if __name__ == "__main__":
    mp.freeze_support()
    main()
