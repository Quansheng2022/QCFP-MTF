# Code_utl/Import_HK_Stock_Info.py
"""
导入港股股票信息到数据库
从 Config/stock_list.json 读取数据并导入到 hk_stock_info 表
"""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
import pytz

# 添加项目根目录到Python路径
# 当前文件在 Code_utl 目录下，需要返回到项目根目录
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent  # Code_utl的父目录就是项目根目录

# 确保项目根目录在sys.path中
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

print(f"项目根目录: {project_root}")

# 路径函数（原 utl.path_utils 中不存在这两个函数，直接在本地定义）
def get_config_path():
    return project_root / 'Config'


def get_db_path():
    return project_root / 'SQLiteDB'


class HKStockInfoImporter:
    """港股股票信息导入器"""
    
    def __init__(self, db_path=None):
        """
        初始化导入器
        
        Args:
            db_path: 数据库路径，如果为None则使用默认路径
        """
        if db_path is None:
            db_path = get_db_path() / 'HK_Stock.db'
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # 设置新加坡时区 (UTC+8)
        self.singapore_tz = pytz.timezone('Asia/Singapore')
        
    def get_current_time(self):
        """
        获取当前新加坡时间
        
        Returns:
            str: 格式化的时间字符串 'YYYY-MM-DD HH:MM:SS'
        """
        singapore_time = datetime.now(self.singapore_tz)
        return singapore_time.strftime('%Y-%m-%d %H:%M:%S')
        
    def connect(self):
        """连接数据库"""
        try:
            # 确保数据库目录存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.conn = sqlite3.connect(str(self.db_path))
            self.cursor = self.conn.cursor()
            print(f"成功连接到数据库: {self.db_path}")
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.conn:
            self.conn.close()
            print("数据库连接已关闭")
    
    def create_table(self):
        """创建表（如果不存在）"""
        create_sql = """
        CREATE TABLE IF NOT EXISTS hk_stock_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL UNIQUE,
            stock_name TEXT NOT NULL,
            sector TEXT,
            market TEXT DEFAULT 'HKEX',
            stock_type TEXT DEFAULT 'stock',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        try:
            self.cursor.execute(create_sql)
            self.conn.commit()
            print("表 hk_stock_info 创建成功（或已存在）")
            
            # 创建索引
            self.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_hk_stock_info_code ON hk_stock_info(stock_code)"
            )
            self.cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_hk_stock_info_sector ON hk_stock_info(sector)"
            )
            self.conn.commit()
            print("索引创建成功")
            return True
        except Exception as e:
            print(f"创建表失败: {e}")
            return False
    
    def load_stock_data(self, json_path=None):
        """
        从JSON文件加载股票数据
        
        Args:
            json_path: JSON文件路径，如果为None则使用默认路径
            
        Returns:
            list: 股票数据列表
        """
        if json_path is None:
            json_path = get_config_path() / 'stock_list.json'
        
        print(f"尝试加载文件: {json_path}")
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stocks = data.get('stocks', [])
            print(f"从 {json_path} 加载了 {len(stocks)} 条股票记录")
            
            # 打印元数据信息
            metadata = data.get('metadata', {})
            if metadata:
                print(f"数据版本: {metadata.get('version', 'N/A')}")
                print(f"最后更新: {metadata.get('last_updated', 'N/A')}")
            
            return stocks
        except FileNotFoundError:
            print(f"错误: 文件 {json_path} 不存在")
            print(f"当前工作目录: {Path.cwd()}")
            return []
        except json.JSONDecodeError as e:
            print(f"错误: JSON解析失败 - {e}")
            return []
        except Exception as e:
            print(f"加载数据失败: {e}")
            return []
    
    def import_data(self, stocks, update_existing=True):
        """
        导入股票数据到数据库
        
        Args:
            stocks: 股票数据列表
            update_existing: 是否更新已存在的记录
            
        Returns:
            tuple: (成功数, 失败数, 更新数)
        """
        if not stocks:
            print("没有数据需要导入")
            return (0, 0, 0)
        
        success_count = 0
        fail_count = 0
        update_count = 0
        
        # 准备SQL语句
        insert_sql = """
        INSERT OR IGNORE INTO hk_stock_info 
        (stock_code, stock_name, sector, market, stock_type, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        update_sql = """
        UPDATE hk_stock_info 
        SET stock_name = ?, sector = ?, market = ?, stock_type = ?, 
            is_active = ?, updated_at = ?
        WHERE stock_code = ?
        """
        
        # 检查现有记录
        check_sql = "SELECT stock_code FROM hk_stock_info WHERE stock_code = ?"
        
        current_time = self.get_current_time()
        print(f"当前新加坡时间: {current_time}")
        
        for stock in stocks:
            try:
                stock_code = stock.get('stock_code', '').strip()
                stock_name = stock.get('stock_name', '').strip()
                sector = stock.get('sector', '')
                market = stock.get('market', 'HKEX')
                
                # 判断股票类型（可根据命名规则或其他特征）
                stock_type = 'stock'
                if 'ETF' in sector or 'ETF' in stock_name:
                    stock_type = 'ETF'
                
                if not stock_code or not stock_name:
                    print(f"警告: 跳过无效记录 - stock_code={stock_code}, stock_name={stock_name}")
                    fail_count += 1
                    continue
                
                # 检查记录是否存在
                self.cursor.execute(check_sql, (stock_code,))
                exists = self.cursor.fetchone() is not None
                
                if exists and update_existing:
                    # 更新现有记录（只更新updated_at）
                    self.cursor.execute(update_sql, (
                        stock_name, sector, market, stock_type, 
                        1,  # is_active
                        current_time,  # updated_at
                        stock_code
                    ))
                    update_count += 1
                    print(f"更新记录: {stock_code} - {stock_name}")
                elif not exists:
                    # 插入新记录（同时设置created_at和updated_at）
                    self.cursor.execute(insert_sql, (
                        stock_code, stock_name, sector, market, stock_type,
                        1,  # is_active
                        current_time,  # created_at
                        current_time   # updated_at
                    ))
                    success_count += 1
                    print(f"新增记录: {stock_code} - {stock_name}")
                else:
                    # 记录已存在且不更新
                    print(f"跳过已存在的记录: {stock_code} - {stock_name}")
                    
            except Exception as e:
                print(f"处理记录 {stock.get('stock_code', 'unknown')} 时出错: {e}")
                fail_count += 1
        
        # 提交事务
        self.conn.commit()
        
        return (success_count, fail_count, update_count)
    
    def verify_data(self):
        """验证导入的数据"""
        try:
            # 统计总记录数
            self.cursor.execute("SELECT COUNT(*) FROM hk_stock_info")
            total = self.cursor.fetchone()[0]
            
            # 按行业统计
            self.cursor.execute("""
                SELECT sector, COUNT(*) as count 
                FROM hk_stock_info 
                GROUP BY sector 
                ORDER BY count DESC
            """)
            sector_stats = self.cursor.fetchall()
            
            # 按类型统计
            self.cursor.execute("""
                SELECT stock_type, COUNT(*) as count 
                FROM hk_stock_info 
                GROUP BY stock_type
            """)
            type_stats = self.cursor.fetchall()
            
            # 显示前10条记录（包含时间信息）
            self.cursor.execute("""
                SELECT stock_code, stock_name, sector, stock_type, created_at, updated_at
                FROM hk_stock_info 
                LIMIT 10
            """)
            sample_records = self.cursor.fetchall()
            
            print("\n" + "="*60)
            print("数据验证结果")
            print("="*60)
            print(f"总记录数: {total}")
            
            print("\n行业分布:")
            for sector, count in sector_stats:
                print(f"  {sector}: {count}")
            
            print("\n类型分布:")
            for stock_type, count in type_stats:
                print(f"  {stock_type}: {count}")
            
            print("\n示例数据（前10条）:")
            print("-"*80)
            print(f"{'代码':<10} {'名称':<20} {'行业':<15} {'类型':<10} {'创建时间':<20}")
            print("-"*80)
            for stock_code, stock_name, sector, stock_type, created_at, updated_at in sample_records:
                print(f"{stock_code:<10} {stock_name:<20} {sector:<15} {stock_type:<10} {created_at:<20}")
            print("="*60)
            
            return True
        except Exception as e:
            print(f"验证数据时出错: {e}")
            return False
    
    def get_statistics(self):
        """获取统计信息"""
        try:
            stats = {}
            
            # 总记录数
            self.cursor.execute("SELECT COUNT(*) FROM hk_stock_info")
            stats['total'] = self.cursor.fetchone()[0]
            
            # 活跃股票数
            self.cursor.execute(
                "SELECT COUNT(*) FROM hk_stock_info WHERE is_active = 1"
            )
            stats['active'] = self.cursor.fetchone()[0]
            
            # 行业数量
            self.cursor.execute(
                "SELECT COUNT(DISTINCT sector) FROM hk_stock_info WHERE sector IS NOT NULL"
            )
            stats['sectors'] = self.cursor.fetchone()[0]
            
            # 最新更新时间
            self.cursor.execute(
                "SELECT MAX(updated_at) FROM hk_stock_info"
            )
            latest_update = self.cursor.fetchone()[0]
            stats['latest_update'] = latest_update
            
            return stats
        except Exception as e:
            print(f"获取统计信息时出错: {e}")
            return {}
    
    def run(self, json_path=None, update_existing=True, verify=True):
        """
        执行完整的导入流程
        
        Args:
            json_path: JSON文件路径
            update_existing: 是否更新已存在的记录
            verify: 是否验证数据
        """
        print("="*60)
        print("港股股票信息导入程序")
        print(f"时区: 新加坡时间 (UTC+8)")
        print("="*60)
        
        # 1. 连接数据库
        if not self.connect():
            return False
        
        try:
            # 2. 创建表
            if not self.create_table():
                return False
            
            # 3. 加载数据
            stocks = self.load_stock_data(json_path)
            if not stocks:
                print("没有数据可导入")
                return False
            
            # 4. 导入数据
            print(f"\n开始导入数据...")
            success, fail, update = self.import_data(stocks, update_existing)
            print(f"\n导入完成!")
            print(f"  新增: {success} 条")
            print(f"  更新: {update} 条")
            print(f"  失败: {fail} 条")
            
            # 5. 验证数据
            if verify:
                self.verify_data()
            
            # 6. 显示统计信息
            stats = self.get_statistics()
            if stats:
                print(f"\n统计信息:")
                print(f"  总股票数: {stats.get('total', 0)}")
                print(f"  活跃股票: {stats.get('active', 0)}")
                print(f"  行业数量: {stats.get('sectors', 0)}")
                if stats.get('latest_update'):
                    print(f"  最新更新: {stats.get('latest_update')}")
            
            return True
            
        except Exception as e:
            print(f"导入过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # 7. 断开连接
            self.disconnect()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='导入港股股票信息到数据库')
    parser.add_argument(
        '--json', 
        help='股票列表JSON文件路径（默认为 Config/stock_list.json）'
    )
    parser.add_argument(
        '--no-update', 
        action='store_true',
        help='不更新已存在的记录'
    )
    parser.add_argument(
        '--no-verify', 
        action='store_true',
        help='不验证数据'
    )
    parser.add_argument(
        '--db', 
        help='数据库路径（默认为 SQLiteDB/HK_Stock.db）'
    )
    
    args = parser.parse_args()
    
    # 创建导入器
    importer = HKStockInfoImporter(db_path=args.db)
    
    # 执行导入
    json_path = args.json
    if json_path:
        json_path = Path(json_path)
    
    success = importer.run(
        json_path=json_path,
        update_existing=not args.no_update,
        verify=not args.no_verify
    )
    
    if success:
        print("\n✓ 股票信息导入成功！")
        sys.exit(0)
    else:
        print("\n✗ 股票信息导入失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
