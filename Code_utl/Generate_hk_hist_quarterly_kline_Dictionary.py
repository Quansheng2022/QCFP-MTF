#!/usr/bin/env python
# coding: utf-8

"""
Generate_hk_hist_quarterly_kline_Dictionary.py
生成 hk_hist_quarterly_kline 表的数据字典

功能：
1. 读取 SQLite 数据库中的 hk_hist_quarterly_kline 表结构
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
    JSON_FILENAME = "hk_hist_quarterly_kline_dictionary.json"
    MARKDOWN_FILENAME = "hk_hist_quarterly_kline_dictionary.md"
    EXCEL_FILENAME = "hk_hist_quarterly_kline_dictionary.xlsx"
    
    # 表名
    TABLE_NAME = "hk_hist_quarterly_kline"

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
            'stock_name': '股票名称（如：腾讯控股）',
            'date': '交易日期（格式：YYYY-MM-DD，每季度最后一个交易日）',
            'open': '开盘价（元）',
            'high': '最高价（元）',
            'low': '最低价（元）',
            'close': '收盘价（元）',
            'volume': '成交量（股）',
            'amount': '成交金额（元）',
            'turnover_rate': '换手率（%）',
            'amplitude': '振幅（%）',
            'change_amount': '涨跌额（元）',
            'change_percent': '涨跌幅（%）',
            'ema5': '5季度指数移动平均线',
            'ema10': '10季度指数移动平均线',
            'ema20': '20季度指数移动平均线',
            'ema50': '50季度指数移动平均线',
            'ema100': '100季度指数移动平均线',
            'ema200': '200季度指数移动平均线',
            'macd_dif': 'MACD指标-DIF线',
            'macd_signal': 'MACD指标-信号线（DEA）',
            'macd_histogram': 'MACD指标-柱状线（MACD）'
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
            
            # 字段详细统计
            f.write("## 字段详细统计\n\n")
            for field in dictionary['fields']:
                if field['statistics'].get('min') is not None:
                    f.write(f"### {field['field_name']}\n\n")
                    stats_info = field['statistics']
                    if 'min' in stats_info:
                        f.write(f"- **最小值**: {stats_info['min']}\n")
                        f.write(f"- **最大值**: {stats_info['max']}\n")
                        f.write(f"- **平均值**: {stats_info.get('avg', 'N/A')}\n")
                        f.write(f"- **不同值数量**: {stats_info.get('distinct_count', 'N/A')}\n")
                    f.write(f"- **空值数量**: {stats_info['null_count']}\n")
                    f.write(f"- **非空数量**: {stats_info['non_null_count']}\n")
                    f.write(f"- **空值比例**: {stats_info['null_percentage']:.2f}%\n")
                    f.write("\n")
            
            # 示例数据
            if 'sample_data' in dictionary and dictionary['sample_data']:
                f.write("## 示例数据\n\n")
                f.write("| " + " | ".join(dictionary['sample_data'][0].keys()) + " |\n")
                f.write("|" + "|".join(["--------"] * len(dictionary['sample_data'][0])) + "|\n")
                
                for sample in dictionary['sample_data']:
                    f.write("| " + " | ".join([str(v) for v in sample.values()]) + " |\n")
                
                f.write("\n")
        
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
                df_samples = pd.DataFrame(dictionary['sample_data'])
                df_samples.to_excel(writer, sheet_name='示例数据', index=False)
        
        print(f"✅ Excel数据字典已保存: {output_path}")

# ==================== 主函数 ====================
def main():
    """主函数"""
    print("=" * 60)
    print("生成 hk_hist_quarterly_kline 数据字典")
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
        print("1. 请先运行 Import_HK_Hist_Quarterly_KLine.py 导入数据")
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
                print("请先运行 Import_HK_Hist_Quarterly_KLine.py 创建表并导入数据")
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