# Daily_TA4A_Convert_MoneyFlow.py
import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime
import logging
from pathlib import Path

# 配置日志
def setup_logging(log_dir):
    """设置日志配置"""
    log_file = os.path.join(log_dir, 'Daily_TA4A_Convert_MoneyFlow.log')
    
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

class MoneyFlowConverter:
    def __init__(self, db_path='HK_Stock.db', log_dir='logs'):
        """初始化转换器
        
        Args:
            db_path: SQLite数据库文件路径
            log_dir: 日志目录路径
        """
        self.db_path = db_path
        self.logger = setup_logging(log_dir)
        self.conn = None
        self.cursor = None
        
    def connect_db(self):
        """连接数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            self.logger.info(f"成功连接到数据库: {self.db_path}")
            return True
        except Exception as e:
            self.logger.error(f"连接数据库失败: {str(e)}")
            return False
    
    def close_db(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.logger.info("数据库连接已关闭")
    
    def create_table_if_not_exists(self):
        """创建数据表（如果不存在）"""
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS hk_hist_daily_moneyflow (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                date TEXT NOT NULL,
                Price_ChgPct REAL,
                Capital_Trend REAL,
                Extra_Large REAL,
                Large REAL,
                Medium REAL,
                Small REAL
            )
            """
            self.cursor.execute(create_table_sql)
            self.conn.commit()
            self.logger.info("数据表 hk_hist_daily_moneyflow 已就绪")
            return True
        except Exception as e:
            self.logger.error(f"创建数据表失败: {str(e)}")
            return False
    
    def clear_table_data(self):
        """清空表数据（可选，根据需求决定是否使用）"""
        try:
            self.cursor.execute("DELETE FROM hk_hist_daily_moneyflow")
            self.conn.commit()
            self.logger.info("已清空数据表 hk_hist_daily_moneyflow")
            return True
        except Exception as e:
            self.logger.error(f"清空数据表失败: {str(e)}")
            return False
    
    def convert_and_save_to_db(self, source_file_path):
        """转换资金流数据并保存到数据库
        
        Args:
            source_file_path: 源数据文件路径
        """
        if not os.path.exists(source_file_path):
            self.logger.error(f"源文件不存在: {source_file_path}")
            return False
        
        try:
            # 读取原始数据
            self.logger.info(f"开始读取文件: {source_file_path}")
            df = pd.read_csv(source_file_path, encoding='utf-8')
            self.logger.info(f"成功读取数据，共 {len(df)} 行")
            
            # 转换数据格式
            df_processed = self.process_data(df)
            
            # 保存到数据库
            success = self.save_to_database(df_processed)
            
            if success:
                self.logger.info(f"数据转换和保存完成，共处理 {len(df_processed)} 行记录")
                return True
            else:
                self.logger.error("数据保存失败")
                return False
                
        except Exception as e:
            self.logger.error(f"数据处理失败: {str(e)}")
            return False
    
    def process_data(self, df):
        """处理数据格式转换
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            处理后的DataFrame
        """
        # 复制数据，避免修改原始数据
        df_processed = df.copy()
        
        # 这里根据实际数据格式进行转换
        # 假设原始数据列名可能需要映射，根据实际情况调整
        # 例如: 如果原始数据列名与目标不同，需要进行映射
        
        # 确保必要的列存在
        required_columns = ['stock_code', 'stock_name', 'date', 'Price_ChgPct', 
                           'Capital_Trend', 'Extra_Large', 'Large', 'Medium', 'Small']
        
        # 如果列名不同，可以在这里进行映射
        # column_mapping = {
        #     'Code': 'stock_code',
        #     'Name': 'stock_name',
        #     # ... 其他列映射
        # }
        # df_processed = df_processed.rename(columns=column_mapping)
        
        # 检查必需列
        for col in required_columns:
            if col not in df_processed.columns:
                self.logger.warning(f"列 '{col}' 不存在，将创建空列")
                df_processed[col] = None
        
        # 只保留需要的列
        df_processed = df_processed[required_columns]
        
        # 数据类型转换
        numeric_columns = ['Price_ChgPct', 'Capital_Trend', 'Extra_Large', 
                          'Large', 'Medium', 'Small']
        for col in numeric_columns:
            df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
        
        # 日期格式标准化
        df_processed['date'] = pd.to_datetime(df_processed['date']).dt.strftime('%Y-%m-%d')
        
        self.logger.info(f"数据预处理完成，共 {len(df_processed)} 行")
        return df_processed
    
    def save_to_database(self, df):
        """保存数据到数据库
        
        Args:
            df: 要保存的DataFrame
            
        Returns:
            bool: 是否成功
        """
        try:
            # 确保表存在
            if not self.create_table_if_not_exists():
                return False
            
            # 批量插入数据
            data_to_insert = df.to_dict('records')
            
            insert_sql = """
            INSERT INTO hk_hist_daily_moneyflow 
            (stock_code, stock_name, date, Price_ChgPct, Capital_Trend, 
             Extra_Large, Large, Medium, Small)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # 分批插入，提高性能
            batch_size = 1000
            total_rows = len(data_to_insert)
            
            for i in range(0, total_rows, batch_size):
                batch = data_to_insert[i:i+batch_size]
                batch_data = []
                
                for row in batch:
                    batch_data.append((
                        row['stock_code'],
                        row['stock_name'],
                        row['date'],
                        row['Price_ChgPct'],
                        row['Capital_Trend'],
                        row['Extra_Large'],
                        row['Large'],
                        row['Medium'],
                        row['Small']
                    ))
                
                self.cursor.executemany(insert_sql, batch_data)
                self.conn.commit()
                self.logger.info(f"已插入 {min(i+batch_size, total_rows)}/{total_rows} 条记录")
            
            self.logger.info(f"成功保存 {total_rows} 条记录到数据库")
            return True
            
        except Exception as e:
            self.logger.error(f"保存数据到数据库失败: {str(e)}")
            self.conn.rollback()
            return False
    
    def get_statistics(self):
        """获取数据统计信息"""
        try:
            query = """
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT stock_code) as total_stocks,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM hk_hist_daily_moneyflow
            """
            
            result = pd.read_sql_query(query, self.conn)
            return result.iloc[0] if not result.empty else None
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}")
            return None

def main():
    """主函数"""
    # 配置路径
    log_dir = 'logs'
    db_path = 'HK_Stock.db'
    
    # 创建转换器实例
    converter = MoneyFlowConverter(db_path=db_path, log_dir=log_dir)
    
    # 连接数据库
    if not converter.connect_db():
        converter.logger.error("无法连接数据库，程序退出")
        return False
    
    try:
        # 这里应该根据实际情况指定源文件路径
        # 示例: source_file = 'data/source_moneyflow.csv'
        source_file = 'source_moneyflow.csv'  # 请根据实际情况修改
        
        # 执行转换
        success = converter.convert_and_save_to_db(source_file)
        
        if success:
            # 显示统计信息
            stats = converter.get_statistics()
            if stats:
                converter.logger.info(f"数据统计: 总记录数={stats['total_records']}, "
                                    f"股票数={stats['total_stocks']}, "
                                    f"日期范围={stats['earliest_date']} 至 {stats['latest_date']}")
            converter.logger.info("程序执行成功")
        else:
            converter.logger.error("程序执行失败")
        
        return success
        
    except Exception as e:
        converter.logger.error(f"程序执行异常: {str(e)}")
        return False
    finally:
        # 关闭数据库连接
        converter.close_db()

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
    