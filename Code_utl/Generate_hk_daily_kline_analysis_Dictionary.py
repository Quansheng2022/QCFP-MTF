#!/usr/bin/env python
# coding: utf-8

"""
Generate_hk_daily_kline_analysis_Dictionary.py
生成 hk_daily_kline_analysis 表的数据字典

功能：
1. 读取 SQLite 数据库中的 hk_daily_kline_analysis 表结构
2. 生成包含字段名称、数据类型、说明、示例值等信息的字典
3. 支持多种输出格式：JSON、Markdown、Excel
4. 可配置输出路径
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

# === 添加UTL路径到系统路径 ===
script_dir = Path(__file__).resolve().parent
core_dir = script_dir.parent / "Core"
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

try:
    from utl.stock_analysis_utl import get_project_root
    # get_project_root() 返回的是 Core 目录
    core_root = get_project_root()
    # 项目根目录是 Core 的父目录
    project_dir = core_root.parent
    print(f"✅ 项目根目录: {project_dir}")
except ImportError:
    # 如果无法导入，使用默认路径
    project_dir = script_dir.parent
    print(f"⚠️ 使用默认项目根目录: {project_dir}")

# ==================== 配置 ====================
class Config:
    """配置类"""
    # 数据库路径 - 在项目根目录下的 SQLiteDB 中
    DB_PATH = project_dir / "SQLiteDB" / "HK_Stock.db"
    
    # 输出目录 - 在项目根目录下的 Config 中
    OUTPUT_DIR = project_dir / "Config"
    
    # 输出文件名
    JSON_FILENAME = "hk_daily_kline_analysis_dictionary.json"
    MARKDOWN_FILENAME = "hk_daily_kline_analysis_dictionary.md"
    EXCEL_FILENAME = "hk_daily_kline_analysis_dictionary.xlsx"
    
    # 表名
    TABLE_NAME = "hk_daily_kline_analysis"

# ==================== 数据字典生成器 ====================
class DataDictionaryGenerator:
    """数据字典生成器"""
    
    def __init__(self, db_path: Path):
        """
        初始化生成器
        
        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """连接数据库"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()
        
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
            
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def get_table_schema(self, table_name: str) -> List[Dict]:
        """
        获取表结构
        
        Args:
            table_name: 表名
            
        Returns:
            List[Dict]: 字段信息列表
        """
        # 获取表结构
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        columns = self.cursor.fetchall()
        
        # 字段信息
        schema = []
        for col in columns:
            schema.append({
                'cid': col[0],
                'name': col[1],
                'type': col[2],
                'notnull': bool(col[3]),
                'dflt_value': col[4],
                'pk': bool(col[5])
            })
        
        return schema
    
    def get_table_statistics(self, table_name: str) -> Dict:
        """
        获取表统计信息
        
        Args:
            table_name: 表名
            
        Returns:
            Dict: 统计信息
        """
        stats = {}
        
        try:
            # 总记录数
            self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            stats['total_records'] = self.cursor.fetchone()[0]
            
            # 股票数量
            self.cursor.execute(f"SELECT COUNT(DISTINCT stock_code) FROM {table_name}")
            stats['stock_count'] = self.cursor.fetchone()[0]
            
            # 日期范围
            self.cursor.execute(f"SELECT MIN(date), MAX(date) FROM {table_name}")
            row = self.cursor.fetchone()
            stats['min_date'] = row[0] if row[0] else None
            stats['max_date'] = row[1] if row[1] else None
            
        except sqlite3.Error as e:
            stats['error'] = str(e)
            
        return stats
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict]:
        """
        获取示例数据
        
        Args:
            table_name: 表名
            limit: 示例数据条数
            
        Returns:
            List[Dict]: 示例数据列表
        """
        try:
            sql = f"SELECT * FROM {table_name} LIMIT {limit}"
            self.cursor.execute(sql)
            columns = [desc[0] for desc in self.cursor.description]
            rows = self.cursor.fetchall()
            
            samples = []
            for row in rows:
                sample = {}
                for i, col in enumerate(columns):
                    sample[col] = row[i]
                samples.append(sample)
                
            return samples
            
        except sqlite3.Error as e:
            return [{'error': str(e)}]
    
    def get_field_samples(self, table_name: str, field_name: str, limit: int = 3) -> List[Any]:
        """
        获取字段的示例值
        
        Args:
            table_name: 表名
            field_name: 字段名
            limit: 示例值数量
            
        Returns:
            List[Any]: 示例值列表
        """
        try:
            sql = f"SELECT {field_name} FROM {table_name} WHERE {field_name} IS NOT NULL LIMIT {limit}"
            self.cursor.execute(sql)
            rows = self.cursor.fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error:
            return []
    
    def get_field_statistics(self, table_name: str, field_name: str, field_type: str) -> Dict:
        """
        获取字段统计信息
        
        Args:
            table_name: 表名
            field_name: 字段名
            field_type: 字段类型
            
        Returns:
            Dict: 字段统计信息
        """
        stats = {
            'null_count': 0,
            'non_null_count': 0,
            'null_percentage': 0.0
        }
        
        try:
            # 统计空值
            sql = f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT({field_name}) as non_null,
                    COUNT(*) - COUNT({field_name}) as null_count
                FROM {table_name}
            """
            self.cursor.execute(sql)
            row = self.cursor.fetchone()
            
            total = row[0] if row[0] > 0 else 1
            stats['null_count'] = row[2]
            stats['non_null_count'] = row[1]
            stats['null_percentage'] = (stats['null_count'] / total) * 100
            
            # 如果是数值类型，计算统计值
            if field_type.upper() in ['REAL', 'FLOAT', 'DOUBLE', 'INTEGER', 'INT', 'NUMERIC', 'DECIMAL']:
                try:
                    sql = f"""
                        SELECT 
                            MIN({field_name}) as min_val,
                            MAX({field_name}) as max_val,
                            AVG({field_name}) as avg_val,
                            COUNT(DISTINCT {field_name}) as distinct_count
                        FROM {table_name}
                        WHERE {field_name} IS NOT NULL
                    """
                    self.cursor.execute(sql)
                    row = self.cursor.fetchone()
                    
                    if row and row[0] is not None:
                        stats['min'] = row[0]
                        stats['max'] = row[1]
                        stats['avg'] = row[2]
                        stats['distinct_count'] = row[3]
                except:
                    pass
                    
            # 如果是文本类型，获取不同值数量
            elif field_type.upper() in ['VARCHAR', 'CHAR', 'TEXT', 'STRING']:
                try:
                    sql = f"""
                        SELECT COUNT(DISTINCT {field_name})
                        FROM {table_name}
                        WHERE {field_name} IS NOT NULL
                    """
                    self.cursor.execute(sql)
                    row = self.cursor.fetchone()
                    if row:
                        stats['distinct_count'] = row[0]
                except:
                    pass
                    
        except sqlite3.Error:
            pass
            
        return stats
    
    def generate_dictionary(self, table_name: str, include_samples: bool = True) -> Dict:
        """
        生成数据字典
        
        Args:
            table_name: 表名
            include_samples: 是否包含示例数据
            
        Returns:
            Dict: 数据字典
        """
        # 获取表结构
        schema = self.get_table_schema(table_name)
        
        # 获取统计信息
        stats = self.get_table_statistics(table_name)
        
        # 构建字段信息
        fields = []
        for col in schema:
            field_info = {
                'field_name': col['name'],
                'data_type': col['type'],
                'nullable': not col['notnull'],
                'primary_key': col['pk'],
                'default_value': col['dflt_value'],
                'description': self._get_field_description(col['name']),
                'statistics': self.get_field_statistics(table_name, col['name'], col['type'])
            }
            
            # 添加示例值
            if include_samples:
                field_info['samples'] = self.get_field_samples(table_name, col['name'], 3)
            
            fields.append(field_info)
        
        # 构建数据字典
        dictionary = {
            'table_name': table_name,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'database_path': str(self.db_path),
            'statistics': stats,
            'field_count': len(fields),
            'fields': fields
        }
        
        # 添加示例数据
        if include_samples:
            dictionary['sample_data'] = self.get_sample_data(table_name, 5)
        
        return dictionary
    
    def _get_field_description(self, field_name: str) -> str:
        """
        获取字段描述
        
        Args:
            field_name: 字段名
            
        Returns:
            str: 字段描述
        """
        descriptions = {
            'id': '主键，自增ID',
            'stock_code': '股票代码（如：00700）',
            'stock_name': '股票名称',
            'date': '交易日期（格式：YYYY-MM-DD）',
            'open': '开盘价',
            'high': '最高价',
            'low': '最低价',
            'close': '收盘价',
            'volume': '成交量（股）',
            'amount': '成交金额（元）',
            'amplitude': '振幅（%）',
            'change_percent': '涨跌幅（%）',
            'change_amount': '涨跌额',
            'turnover_rate': '换手率（%）',
            'previous_close': '前日收盘价',
            'avg_price': '均价（成交金额/成交量）',
            'close_chgpct': '收盘价变动百分比',
            
            # 均线相关
            'avg_volume_5d': '5日均量',
            'volume_ratio5': '量比（5日）',
            'avg_volume_20d': '20日均量',
            'volume_ratio20': '量比（20日）',
            'ema5': '5日指数移动平均线',
            'ema8': '8日指数移动平均线',
            'ema10': '10日指数移动平均线',
            'ema12': '12日指数移动平均线',
            'ema13': '13日指数移动平均线',
            'ema20': '20日指数移动平均线',
            'ema21': '21日指数移动平均线',
            'ema26': '26日指数移动平均线',
            'ema30': '30日指数移动平均线',
            'ema34': '34日指数移动平均线',
            'ema50': '50日指数移动平均线',
            'ema60': '60日指数移动平均线',
            'ema63': '63日指数移动平均线',
            'ema100': '100日指数移动平均线',
            'ema120': '120日指数移动平均线',
            'ema200': '200日指数移动平均线',
            'ema250': '250日指数移动平均线',
            
            # 乖离率
            'bias5': '5日乖离率（%）',
            'bias10': '10日乖离率（%）',
            'bias20': '20日乖离率（%）',
            'bias50': '50日乖离率（%）',
            'bias60': '60日乖离率（%）',
            'bias100': '100日乖离率（%）',
            'bias120': '120日乖离率（%）',
            'bias200': '200日乖离率（%）',
            'bias250': '250日乖离率（%）',
            
            # 成交量相关
            'vol_ema5': '5日成交量指数移动平均',
            'vol_ema10': '10日成交量指数移动平均',
            'vol_ema20': '20日成交量指数移动平均',
            'volume_oscillator': '成交量震荡指标（%）',
            'obv': '能量潮（On-Balance Volume）',
            
            # 布林带
            'bollinger_middle': '布林带中轨（20日均线）',
            'bollinger_upper': '布林带上轨',
            'bollinger_lower': '布林带下轨',
            
            # 其他技术指标
            'vwap': '成交量加权平均价',
            'parabolic_sar': '抛物线转向指标',
            
            # 成交量交叉信号
            'vol_ema5_20_cross_status': '成交量5日与20日EMA交叉状态（1:金叉, -1:死叉）',
            'vol_ema5_20_cross_streak': '成交量5日与20日EMA交叉持续天数',
            'vol_ema5_10_cross_status': '成交量5日与10日EMA交叉状态（1:金叉, -1:死叉）',
            'vol_ema5_10_cross_streak': '成交量5日与10日EMA交叉持续天数',
            
            # ATR相关
            'tr': '真实波幅（True Range）',
            'atr14': '14日平均真实波幅',
            
            # KDJ指标
            'kdj_k': 'KDJ指标K值',
            'kdj_d': 'KDJ指标D值',
            'kdj_j': 'KDJ指标J值',
            
            # MACD指标
            'macd_dif': 'MACD指标DIF线',
            'macd_signal': 'MACD指标信号线（DEA）',
            'macd_histogram': 'MACD指标柱状图',
            
            # RSI指标
            'rsi6': '6日相对强弱指标',
            'rsi14': '14日相对强弱指标',
            
            # CCI指标
            'cci14': '14日商品通道指标',
            
            # Williams %R
            'williams_r': '威廉指标（%R）',
            
            # DMI指标
            'pdi14': '14日上升方向指标（+DI）',
            'mdi14': '14日下降方向指标（-DI）',
            'adx14': '14日平均趋向指标',
            'atr30': '30日平均真实波幅',
            'pdi30': '30日上升方向指标（+DI）',
            'mdi30': '30日下降方向指标（-DI）',
            'adx30': '30日平均趋向指标',
            'atr60': '60日平均真实波幅',
            'pdi60': '60日上升方向指标（+DI）',
            'mdi60': '60日下降方向指标（-DI）',
            'adx60': '60日平均趋向指标',
            'atr100': '100日平均真实波幅',
            'pdi100': '100日上升方向指标（+DI）',
            'mdi100': '100日下降方向指标（-DI）',
            'adx100': '100日平均趋向指标',
            
            # MFI指标
            'mfi': '资金流量指标（Money Flow Index）',
            
            # 交叉信号
            'ema_golden_cross': 'EMA金叉信号（1:出现, 0:无）',
            'ema_death_cross': 'EMA死叉信号（1:出现, 0:无）',
            'golden_triangle': '黄金三角信号（1:出现, 0:无）',
            'death_triangle': '死亡三角信号（1:出现, 0:无）',
            'macd_golden_cross': 'MACD金叉信号（1:出现, 0:无）',
            'macd_death_cross': 'MACD死叉信号（1:出现, 0:无）',
            
            # 价格相关
            'open_close_change_pct': '开盘收盘变动百分比',
            'high_30d': '30日最高价',
            'low_30d': '30日最低价',
            'close_3d_ago': '3日前收盘价',
            'high_125d': '125日最高价',
            'low_125d': '125日最低价',
            'high_250d': '250日最高价',
            'low_250d': '250日最低价',
            
            # 成交量500日统计
            'volume_min_500d': '500日最小成交量',
            'volume_max_500d': '500日最大成交量',
            'volume_10th_percentile_500d': '500日成交量第10百分位数',
            'volume_25th_percentile_500d': '500日成交量第25百分位数',
            'volume_50th_percentile_500d': '500日成交量第50百分位数（中位数）',
            'volume_75th_percentile_500d': '500日成交量第75百分位数',
            'volume_90th_percentile_500d': '500日成交量第90百分位数',
            
            # 成交金额500日统计
            'amount_min_500d': '500日最小成交金额',
            'amount_max_500d': '500日最大成交金额',
            'amount_10th_percentile_500d': '500日成交金额第10百分位数',
            'amount_25th_percentile_500d': '500日成交金额第25百分位数',
            'amount_50th_percentile_500d': '500日成交金额第50百分位数（中位数）',
            'amount_75th_percentile_500d': '500日成交金额第75百分位数',
            'amount_90th_percentile_500d': '500日成交金额第90百分位数',
            
            # 振幅500日统计
            'amplitude_min_500d': '500日最小振幅',
            'amplitude_max_500d': '500日最大振幅',
            'amplitude_10th_percentile_500d': '500日振幅第10百分位数',
            'amplitude_25th_percentile_500d': '500日振幅第25百分位数',
            'amplitude_50th_percentile_500d': '500日振幅第50百分位数（中位数）',
            'amplitude_75th_percentile_500d': '500日振幅第75百分位数',
            'amplitude_90th_percentile_500d': '500日振幅第90百分位数',
            
            # 涨跌幅500日统计
            'change_percent_min_500d': '500日最小涨跌幅',
            'change_percent_max_500d': '500日最大涨跌幅',
            'change_percent_10th_percentile_500d': '500日涨跌幅第10百分位数',
            'change_percent_25th_percentile_500d': '500日涨跌幅第25百分位数',
            'change_percent_50th_percentile_500d': '500日涨跌幅第50百分位数（中位数）',
            'change_percent_75th_percentile_500d': '500日涨跌幅第75百分位数',
            'change_percent_90th_percentile_500d': '500日涨跌幅第90百分位数',
            
            # 涨跌额500日统计
            'change_amount_min_500d': '500日最小涨跌额',
            'change_amount_max_500d': '500日最大涨跌额',
            'change_amount_10th_percentile_500d': '500日涨跌额第10百分位数',
            'change_amount_25th_percentile_500d': '500日涨跌额第25百分位数',
            'change_amount_50th_percentile_500d': '500日涨跌额第50百分位数（中位数）',
            'change_amount_75th_percentile_500d': '500日涨跌额第75百分位数',
            'change_amount_90th_percentile_500d': '500日涨跌额第90百分位数',
            
            # 换手率500日统计
            'turnover_rate_min_500d': '500日最小换手率',
            'turnover_rate_max_500d': '500日最大换手率',
            'turnover_rate_10th_percentile_500d': '500日换手率第10百分位数',
            'turnover_rate_25th_percentile_500d': '500日换手率第25百分位数',
            'turnover_rate_50th_percentile_500d': '500日换手率第50百分位数（中位数）',
            'turnover_rate_75th_percentile_500d': '500日换手率第75百分位数',
            'turnover_rate_90th_percentile_500d': '500日换手率第90百分位数',
            
            # 量比500日统计
            'volume_ratio5_min_500d': '500日5日量比最小值',
            'volume_ratio5_max_500d': '500日5日量比最大值',
            'volume_ratio5_10th_percentile_500d': '500日5日量比第10百分位数',
            'volume_ratio5_25th_percentile_500d': '500日5日量比第25百分位数',
            'volume_ratio5_50th_percentile_500d': '500日5日量比第50百分位数（中位数）',
            'volume_ratio5_75th_percentile_500d': '500日5日量比第75百分位数',
            'volume_ratio5_90th_percentile_500d': '500日5日量比第90百分位数',
            'volume_ratio20_min_500d': '500日20日量比最小值',
            'volume_ratio20_max_500d': '500日20日量比最大值',
            'volume_ratio20_10th_percentile_500d': '500日20日量比第10百分位数',
            'volume_ratio20_25th_percentile_500d': '500日20日量比第25百分位数',
            'volume_ratio20_50th_percentile_500d': '500日20日量比第50百分位数（中位数）',
            'volume_ratio20_75th_percentile_500d': '500日20日量比第75百分位数',
            'volume_ratio20_90th_percentile_500d': '500日20日量比第90百分位数',
            
            # 价格振幅筹码分布（20日）
            'price_amp_market_chip_concentration_20_70': '20日价格振幅市场筹码集中度（70%区间）',
            'price_amp_chip_price_range_20_70': '20日价格振幅筹码价格范围（70%区间）',
            'price_amp_chip_min_20_70': '20日价格振幅筹码最低价（70%区间）',
            'price_amp_chip_max_20_70': '20日价格振幅筹码最高价（70%区间）',
            'price_amp_market_chip_concentration_20_90': '20日价格振幅市场筹码集中度（90%区间）',
            'price_amp_chip_price_range_20_90': '20日价格振幅筹码价格范围（90%区间）',
            'price_amp_chip_min_20_90': '20日价格振幅筹码最低价（90%区间）',
            'price_amp_chip_max_20_90': '20日价格振幅筹码最高价（90%区间）',
            
            # 价格振幅筹码分布（60日）
            'price_amp_market_chip_concentration_60_70': '60日价格振幅市场筹码集中度（70%区间）',
            'price_amp_chip_price_range_60_70': '60日价格振幅筹码价格范围（70%区间）',
            'price_amp_chip_min_60_70': '60日价格振幅筹码最低价（70%区间）',
            'price_amp_chip_max_60_70': '60日价格振幅筹码最高价（70%区间）',
            'price_amp_market_chip_concentration_60_90': '60日价格振幅市场筹码集中度（90%区间）',
            'price_amp_chip_price_range_60_90': '60日价格振幅筹码价格范围（90%区间）',
            'price_amp_chip_min_60_90': '60日价格振幅筹码最低价（90%区间）',
            'price_amp_chip_max_60_90': '60日价格振幅筹码最高价（90%区间）',
            
            # 价格振幅筹码分布（250日）
            'price_amp_market_chip_concentration_250_70': '250日价格振幅市场筹码集中度（70%区间）',
            'price_amp_chip_price_range_250_70': '250日价格振幅筹码价格范围（70%区间）',
            'price_amp_chip_min_250_70': '250日价格振幅筹码最低价（70%区间）',
            'price_amp_chip_max_250_70': '250日价格振幅筹码最高价（70%区间）',
            'price_amp_market_chip_concentration_250_90': '250日价格振幅市场筹码集中度（90%区间）',
            'price_amp_chip_price_range_250_90': '250日价格振幅筹码价格范围（90%区间）',
            'price_amp_chip_min_250_90': '250日价格振幅筹码最低价（90%区间）',
            'price_amp_chip_max_250_90': '250日价格振幅筹码最高价（90%区间）',
            
            # 价格振幅筹码分布（全历史）
            'price_amp_market_chip_concentration': '全历史价格振幅市场筹码集中度',
            'price_amp_chip_price_range': '全历史价格振幅筹码价格范围',
            'price_amp_chip_min': '全历史价格振幅筹码最低价',
            'price_amp_chip_max': '全历史价格振幅筹码最高价',
            
            # 成本分布筹码（20日）
            'cost_spread_chip_min_20_70': '20日成本分布筹码最低价（70%区间）',
            'cost_spread_chip_max_20_70': '20日成本分布筹码最高价（70%区间）',
            'cost_spread_chip_price_range_20_70': '20日成本分布筹码价格范围（70%区间）',
            'cost_spread_chip_concentration_20_70': '20日成本分布筹码集中度（70%区间）',
            'cost_spread_chip_min_20_90': '20日成本分布筹码最低价（90%区间）',
            'cost_spread_chip_max_20_90': '20日成本分布筹码最高价（90%区间）',
            'cost_spread_chip_price_range_20_90': '20日成本分布筹码价格范围（90%区间）',
            'cost_spread_chip_concentration_20_90': '20日成本分布筹码集中度（90%区间）',
            
            # 成本分布筹码（60日）
            'cost_spread_chip_min_60_70': '60日成本分布筹码最低价（70%区间）',
            'cost_spread_chip_max_60_70': '60日成本分布筹码最高价（70%区间）',
            'cost_spread_chip_price_range_60_70': '60日成本分布筹码价格范围（70%区间）',
            'cost_spread_chip_concentration_60_70': '60日成本分布筹码集中度（70%区间）',
            'cost_spread_chip_min_60_90': '60日成本分布筹码最低价（90%区间）',
            'cost_spread_chip_max_60_90': '60日成本分布筹码最高价（90%区间）',
            'cost_spread_chip_price_range_60_90': '60日成本分布筹码价格范围（90%区间）',
            'cost_spread_chip_concentration_60_90': '60日成本分布筹码集中度（90%区间）',
            
            # 成本分布筹码（250日）
            'cost_spread_chip_min_250_70': '250日成本分布筹码最低价（70%区间）',
            'cost_spread_chip_max_250_70': '250日成本分布筹码最高价（70%区间）',
            'cost_spread_chip_price_range_250_70': '250日成本分布筹码价格范围（70%区间）',
            'cost_spread_chip_concentration_250_70': '250日成本分布筹码集中度（70%区间）',
            'cost_spread_chip_min_250_90': '250日成本分布筹码最低价（90%区间）',
            'cost_spread_chip_max_250_90': '250日成本分布筹码最高价（90%区间）',
            'cost_spread_chip_price_range_250_90': '250日成本分布筹码价格范围（90%区间）',
            'cost_spread_chip_concentration_250_90': '250日成本分布筹码集中度（90%区间）',
            
            # 成本分布筹码（全历史）
            'cost_spread_chip_concentration': '全历史成本分布筹码集中度',
            
            # 密集交易区间
            'intensive_trading_min': '密集交易区间最低价',
            'intensive_trading_max': '密集交易区间最高价',
            
            # EMA交叉状态
            'ema5_10_status': 'EMA5与EMA10交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema5_10_streak': 'EMA5与EMA10交叉持续天数',
            'ema5_20_status': 'EMA5与EMA20交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema5_20_streak': 'EMA5与EMA20交叉持续天数',
            'ema10_20_status': 'EMA10与EMA20交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema10_20_streak': 'EMA10与EMA20交叉持续天数',
            'ema20_50_status': 'EMA20与EMA50交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema20_50_streak': 'EMA20与EMA50交叉持续天数',
            'ema50_200_status': 'EMA50与EMA200交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema50_200_streak': 'EMA50与EMA200交叉持续天数',
            'ema20_200_status': 'EMA20与EMA200交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema20_200_streak': 'EMA20与EMA200交叉持续天数',
            'ema12_26_status': 'EMA12与EMA26交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema12_26_streak': 'EMA12与EMA26交叉持续天数',
            'ema5_13_status': 'EMA5与EMA13交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema5_13_streak': 'EMA5与EMA13交叉持续天数',
            'ema5_34_status': 'EMA5与EMA34交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema5_34_streak': 'EMA5与EMA34交叉持续天数',
            'ema13_34_status': 'EMA13与EMA34交叉状态（1:金叉, -1:死叉, 0:无）',
            'ema13_34_streak': 'EMA13与EMA34交叉持续天数',
            'ema5_13_34_status': 'EMA5、EMA13、EMA34三线状态（2:多头排列, -2:空头排列, 0:震荡）',
            'ema5_13_34_streak': 'EMA5、EMA13、EMA34三线状态持续天数',
            
            # MACD状态
            'macd_status': 'MACD状态（1:金叉, -1:死叉, 0:无）',
            'macd_golden_streak': 'MACD金叉持续天数',
            'macd_death_streak': 'MACD死叉持续天数',
            
            # 信号条件
            'bottom_signal_cond': '底部信号（1:出现, 0:无）',
            'top_signal_cond': '顶部信号（1:出现, 0:无）',
            'bottom_entry_signal_cond': '底部入场信号（1:出现, 0:无）',
            'top_exit_signal_cond': '顶部出场信号（1:出现, 0:无）',
            'continuation_signal_cond': '上涨延续信号（1:出现, 0:无）',
            'decline_continuation_cond': '下跌延续信号（1:出现, 0:无）',
            'accumulation_cond': '吸筹信号（1:出现, 0:无）',
            'distribution_cond': '派发信号（1:出现, 0:无）',
            'multi_timeframe_chip_confirm_bottom_cond': '多周期筹码确认底部信号（1:出现, 0:无）',
            'multi_timeframe_chip_confirm_top_cond': '多周期筹码确认顶部信号（1:出现, 0:无）',
            
            # 信号质量
            'signal_quality': '信号质量评级（A/B/C/D）'
        }
        
        return descriptions.get(field_name, '')
    
    def save_json(self, dictionary: Dict, output_path: Path):
        """
        保存为JSON格式
        
        Args:
            dictionary: 数据字典
            output_path: 输出路径
        """
        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dictionary, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"✅ JSON数据字典已保存: {output_path}")
    
    def save_markdown(self, dictionary: Dict, output_path: Path):
        """
        保存为Markdown格式
        
        Args:
            dictionary: 数据字典
            output_path: 输出路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # 标题
            f.write(f"# {dictionary['table_name']} 数据字典\n\n")
            
            # 基本信息
            f.write("## 基本信息\n\n")
            f.write(f"- **表名**: `{dictionary['table_name']}`\n")
            f.write(f"- **生成时间**: {dictionary['generated_at']}\n")
            f.write(f"- **数据库路径**: `{dictionary['database_path']}`\n")
            f.write(f"- **字段数量**: {dictionary['field_count']}\n\n")
            
            # 统计信息
            stats = dictionary.get('statistics', {})
            if stats and 'error' not in stats:
                f.write("## 统计信息\n\n")
                f.write(f"- **总记录数**: {stats.get('total_records', 0):,}\n")
                f.write(f"- **股票数量**: {stats.get('stock_count', 0)}\n")
                if stats.get('min_date'):
                    f.write(f"- **日期范围**: {stats['min_date']} 至 {stats['max_date']}\n")
                f.write("\n")
            
            # 字段信息
            f.write("## 字段信息\n\n")
            f.write("| 字段名 | 数据类型 | 可空 | 主键 | 默认值 | 描述 | 空值比例 | 示例值 |\n")
            f.write("|--------|----------|------|------|--------|------|----------|--------|\n")
            
            for field in dictionary['fields']:
                samples = field.get('samples', [])
                sample_str = ', '.join([str(s) for s in samples[:2]]) if samples else ''
                
                null_pct = field['statistics'].get('null_percentage', 0)
                null_str = f"{null_pct:.1f}%"
                
                f.write(f"| {field['field_name']} ")
                f.write(f"| {field['data_type']} ")
                f.write(f"| {'是' if field['nullable'] else '否'} ")
                f.write(f"| {'是' if field['primary_key'] else '否'} ")
                f.write(f"| {field['default_value'] or ''} ")
                f.write(f"| {field['description']} ")
                f.write(f"| {null_str} ")
                f.write(f"| {sample_str} |\n")
            
            f.write("\n")
            
            # 字段详细统计（只显示有统计值的字段）
            f.write("## 字段详细统计\n\n")
            for field in dictionary['fields']:
                stats_info = field['statistics']
                if stats_info.get('min') is not None or stats_info.get('distinct_count') is not None:
                    f.write(f"### {field['field_name']}\n\n")
                    if 'min' in stats_info and stats_info['min'] is not None:
                        f.write(f"- **最小值**: {stats_info['min']}\n")
                        f.write(f"- **最大值**: {stats_info['max']}\n")
                        f.write(f"- **平均值**: {stats_info.get('avg', 'N/A')}\n")
                    if 'distinct_count' in stats_info and stats_info['distinct_count'] is not None:
                        f.write(f"- **不同值数量**: {stats_info['distinct_count']}\n")
                    f.write(f"- **空值数量**: {stats_info['null_count']}\n")
                    f.write(f"- **非空数量**: {stats_info['non_null_count']}\n")
                    f.write(f"- **空值比例**: {stats_info['null_percentage']:.2f}%\n")
                    f.write("\n")
            
            # 示例数据
            if 'sample_data' in dictionary and dictionary['sample_data']:
                f.write("## 示例数据\n\n")
                # 只显示前10列，避免表格过宽
                sample = dictionary['sample_data'][0]
                keys = list(sample.keys())[:15]
                
                f.write("| " + " | ".join(keys) + " |\n")
                f.write("|" + "|".join(["--------"] * len(keys)) + "|\n")
                
                for sample in dictionary['sample_data']:
                    values = [str(sample.get(k, ''))[:50] for k in keys]  # 限制长度
                    f.write("| " + " | ".join(values) + " |\n")
                
                f.write("\n")
                f.write(f"*注：示例数据仅显示前15列，完整数据请查看JSON或Excel文件*\n")
        
        print(f"✅ Markdown数据字典已保存: {output_path}")
    
    def save_excel(self, dictionary: Dict, output_path: Path):
        """
        保存为Excel格式
        
        Args:
            dictionary: 数据字典
            output_path: 输出路径
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Sheet 1: 基本信息
            info_data = {
                '项目': ['表名', '生成时间', '数据库路径', '字段数量'],
                '值': [
                    dictionary['table_name'],
                    dictionary['generated_at'],
                    dictionary['database_path'],
                    dictionary['field_count']
                ]
            }
            df_info = pd.DataFrame(info_data)
            df_info.to_excel(writer, sheet_name='基本信息', index=False)
            
            # Sheet 2: 统计信息
            stats = dictionary.get('statistics', {})
            if stats and 'error' not in stats:
                stats_data = {
                    '统计项': ['总记录数', '股票数量', '最早日期', '最晚日期'],
                    '值': [
                        stats.get('total_records', 0),
                        stats.get('stock_count', 0),
                        stats.get('min_date', ''),
                        stats.get('max_date', '')
                    ]
                }
                df_stats = pd.DataFrame(stats_data)
                df_stats.to_excel(writer, sheet_name='统计信息', index=False)
            
            # Sheet 3: 字段信息
            fields_data = []
            for field in dictionary['fields']:
                fields_data.append({
                    '字段名': field['field_name'],
                    '数据类型': field['data_type'],
                    '可空': '是' if field['nullable'] else '否',
                    '主键': '是' if field['primary_key'] else '否',
                    '默认值': field['default_value'] or '',
                    '描述': field['description'],
                    '空值比例': f"{field['statistics'].get('null_percentage', 0):.2f}%",
                    '最小值': field['statistics'].get('min', ''),
                    '最大值': field['statistics'].get('max', ''),
                    '平均值': field['statistics'].get('avg', ''),
                    '不同值数量': field['statistics'].get('distinct_count', ''),
                    '示例值': ', '.join([str(s) for s in field.get('samples', [])])
                })
            
            df_fields = pd.DataFrame(fields_data)
            df_fields.to_excel(writer, sheet_name='字段信息', index=False)
            
            # Sheet 4: 示例数据
            if 'sample_data' in dictionary and dictionary['sample_data']:
                # 限制列数，避免Excel过宽
                sample = dictionary['sample_data'][0]
                keys = list(sample.keys())[:30]  # 显示前30列
                
                sample_data = []
                for s in dictionary['sample_data']:
                    row = {}
                    for k in keys:
                        row[k] = s.get(k, '')
                    sample_data.append(row)
                
                df_samples = pd.DataFrame(sample_data)
                df_samples.to_excel(writer, sheet_name='示例数据', index=False)
        
        print(f"✅ Excel数据字典已保存: {output_path}")

# ==================== 主函数 ====================
def main():
    """主函数"""
    print("=" * 60)
    print("生成 hk_daily_kline_analysis 数据字典")
    print("=" * 60)
    
    # 打印配置信息
    print(f"\n📁 项目目录: {project_dir}")
    print(f"📁 数据库路径: {Config.DB_PATH}")
    print(f"📁 输出目录: {Config.OUTPUT_DIR}")
    print()
    
    # 检查数据库是否存在
    if not Config.DB_PATH.exists():
        print(f"❌ 数据库文件不存在: {Config.DB_PATH}")
        print("\n可能的原因：")
        print("1. 数据库文件尚未创建")
        print("2. 路径解析错误")
        print("\n解决方案：")
        print("1. 请先运行 Import_hk_daily_kline_analysis.py 导入数据")
        print("2. 或者检查 stock_analysis_utl.py 中的 get_project_root() 函数")
        print("3. 检查数据库文件是否在正确的位置")
        sys.exit(1)
    
    try:
        # 创建生成器
        generator = DataDictionaryGenerator(Config.DB_PATH)
        
        with generator:
            print(f"✅ 已连接数据库: {Config.DB_PATH}")
            
            # 检查表是否存在
            generator.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (Config.TABLE_NAME,)
            )
            if not generator.cursor.fetchone():
                print(f"❌ 表 {Config.TABLE_NAME} 不存在")
                print("请先运行 Import_hk_daily_kline_analysis.py 创建表并导入数据")
                sys.exit(1)
            
            # 生成数据字典
            print(f"📊 正在生成 {Config.TABLE_NAME} 数据字典...")
            dictionary = generator.generate_dictionary(Config.TABLE_NAME, include_samples=True)
            
            print(f"✅ 数据字典生成完成")
            print(f"   - 字段数量: {dictionary['field_count']}")
            print(f"   - 总记录数: {dictionary['statistics'].get('total_records', 0):,}")
            print(f"   - 股票数量: {dictionary['statistics'].get('stock_count', 0)}")
            if dictionary['statistics'].get('min_date'):
                print(f"   - 日期范围: {dictionary['statistics']['min_date']} 至 {dictionary['statistics']['max_date']}")
            
            # 确保输出目录存在
            Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            # 保存为JSON
            json_path = Config.OUTPUT_DIR / Config.JSON_FILENAME
            generator.save_json(dictionary, json_path)
            
            # 保存为Markdown
            md_path = Config.OUTPUT_DIR / Config.MARKDOWN_FILENAME
            generator.save_markdown(dictionary, md_path)
            
            # 保存为Excel
            excel_path = Config.OUTPUT_DIR / Config.EXCEL_FILENAME
            generator.save_excel(dictionary, excel_path)
            
            print("\n" + "=" * 60)
            print("✅ 数据字典生成完成！")
            print(f"   JSON文件: {json_path}")
            print(f"   Markdown文件: {md_path}")
            print(f"   Excel文件: {excel_path}")
            print("=" * 60)
            
    except FileNotFoundError as e:
        print(f"❌ 文件不存在: {e}")
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"❌ 数据库错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 生成数据字典失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()