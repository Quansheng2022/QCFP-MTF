#!/usr/bin/env python
# coding: utf-8

# stock_analysis_utl.py

import re
import sys
import os
import io
import sqlite3
import platform
import runpy
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set, Dict, List, Any, Tuple
import configparser


class GlobalConfig:
    full_data_dir = None
    full_report_dir = None
    full_log_dir = None
    full_temp_dir = None
    full_sqlite_dir = None      # 新增：SQLite数据库目录
    db_name = None               # 新增：数据库名称
    full_db_path = None          # 新增：完整数据库路径

    # 新增：多进程控制变量
    use_multiprocessing = False   # 是否启用多进程
    max_workers = 4               # 最大进程数

    @classmethod
    def update_paths(cls, config, project_dir):
        """更新全局路径配置"""
        cls.full_data_dir = fix_path_escapes(os.path.join(project_dir, config.get("data_dir", "data")))
        cls.full_report_dir = fix_path_escapes(os.path.join(project_dir, config.get("report_dir", "report")))
        cls.full_log_dir = fix_path_escapes(os.path.join(project_dir, config.get("log_dir", "log")))
        cls.full_temp_dir = fix_path_escapes(os.path.join(project_dir, config.get("temp_dir", "temp")))
        
        # 新增：SQLite相关路径
        cls.full_sqlite_dir = fix_path_escapes(os.path.join(project_dir, config.get("sqlite_dir", "SQLiteDB")))
        cls.db_name = config.get("db_name", "HK_Stock.db")
        cls.full_db_path = fix_path_escapes(os.path.join(cls.full_sqlite_dir, cls.db_name))

        # 确保目录存在
        os.makedirs(cls.full_data_dir, exist_ok=True)
        os.makedirs(cls.full_report_dir, exist_ok=True)
        os.makedirs(cls.full_log_dir, exist_ok=True)
        os.makedirs(cls.full_temp_dir, exist_ok=True)
        os.makedirs(cls.full_sqlite_dir, exist_ok=True)  # 新增：确保SQLite目录存在

    @classmethod
    def get_db_path(cls):
        """获取数据库完整路径（便捷方法）"""
        if cls.full_db_path is None:
            raise ValueError("数据库路径未初始化，请先调用 update_paths()")
        return cls.full_db_path

    @classmethod
    def get_sqlite_dir(cls):
        """获取SQLite目录路径（便捷方法）"""
        if cls.full_sqlite_dir is None:
            raise ValueError("SQLite目录未初始化，请先调用 update_paths()")
        return cls.full_sqlite_dir

    @classmethod
    def update_multiprocessing_config(cls, use_mp, workers):
        """更新多进程配置（从配置文件读取后调用）"""
        cls.use_multiprocessing = use_mp
        cls.max_workers = workers


def get_project_dir():
    """获取项目根目录"""
    try:
        # 尝试从环境变量获取
        env_dir = os.environ.get('PROJECT_ROOT')
        if env_dir and Path(env_dir).exists():
            return Path(env_dir)

        # 尝试 Python 脚本环境
        try:
            return Path(__file__).resolve().parent.parent
        except NameError:
            pass

        # Jupyter Notebook 环境
        cwd = Path(os.getcwd())
        if "notebook_scripts" in str(cwd):
            return cwd.parent
        return cwd
    except Exception as e:
        print(f"获取项目目录错误: {str(e)}")
        return Path.cwd()


def convert_config_value(value: str) -> Any:
    """
    转换配置值的类型
    - 数字字符串 -> int/float
    - 布尔字符串 -> bool
    - 其他保持字符串
    """
    if not isinstance(value, str):
        return value
    
    value = value.strip()
    
    # 空字符串返回 None
    if value == '':
        return None
    
    # 1. 尝试转换为布尔值
    true_values = ['true', 'yes', 'on', '1', 'y', 't']
    false_values = ['false', 'no', 'off', '0', 'n', 'f']
    
    if value.lower() in true_values:
        return True
    if value.lower() in false_values:
        return False
    
    # 2. 尝试转换为整数
    try:
        # 检查是否是整数（包括负数）
        if re.match(r'^-?\d+$', value):
            return int(value)
    except (ValueError, TypeError):
        pass
    
    # 3. 尝试转换为浮点数
    try:
        # 检查是否是浮点数（包括负数和小数）
        if re.match(r'^-?\d+\.\d+$', value):
            return float(value)
    except (ValueError, TypeError):
        pass
    
    # 4. 如果都不是，保持字符串
    return value


def load_config(config_path, project_dir):
    """
    加载配置文件（完整版）
    
    支持的段落：
    - [FOLDERS]: 目录配置
    - [DATABASE]: 数据库配置
    - [TICKERS]: 股票列表
    - [FREDAPI]: FRED API配置
    - [FUTU_MOOMOO]: 富途配置
    - [PROCESS_SWITCHES]: 处理开关
    - [MULTI_PROCESSING]: 多进程配置
    - [ANALYSIS_PERIOD]: 分析周期配置
    - [DATA_DOWNLOAD]: 数据下载配置
    - [HK_MACRO_DATA]: 香港宏观数据配置
    """
    config = {}
    cp = configparser.ConfigParser()
    cp.read(config_path, encoding='utf-8')
    
    # 1. 读取 FOLDERS 段
    if cp.has_section('FOLDERS'):
        for key in cp.options('FOLDERS'):
            value = cp.get('FOLDERS', key).strip().strip("'").strip('"')
            config[key] = value
    
    # 2. 读取 DATABASE 段
    if cp.has_section('DATABASE'):
        config['db_name'] = cp.get('DATABASE', 'db_name', fallback='HK_Stock.db').strip()
    else:
        config['db_name'] = 'HK_Stock.db'
    
    # 3. 读取 [TICKERS] 段落 - 这是关键修复！
    if cp.has_section('TICKERS'):
        tickers_str = cp.get('TICKERS', 'tickers', fallback='').strip()
        if tickers_str:
            # 按逗号分割，去除空白，过滤空字符串
            tickers_list = [t.strip() for t in tickers_str.split(',') if t.strip()]
            config['tickers'] = tickers_list
            print(f"[INFO] 已读取股票列表: {len(tickers_list)} 只股票")
            print(f"[INFO] 股票列表: {', '.join(tickers_list[:5])}{'...' if len(tickers_list) > 5 else ''}")
        else:
            config['tickers'] = []
            print("[WARN] [TICKERS] 段落中未找到 tickers 配置")
    else:
        config['tickers'] = []
        print("[WARN] 配置文件中没有 [TICKERS] 段落")
    
    # 4. 读取 [FREDAPI] 段落
    if cp.has_section('FREDAPI'):
        config['FRED_API_KEY'] = cp.get('FREDAPI', 'FRED_API_KEY', fallback='').strip()
        print(f"[INFO] 已读取 FRED_API_KEY: {'已配置' if config['FRED_API_KEY'] else '未配置'}")
    else:
        config['FRED_API_KEY'] = ''
        print("[WARN] 配置文件中没有 [FREDAPI] 段落")
    
    # 5. 读取 FUTU_MOOMOO 段
    if cp.has_section('FUTU_MOOMOO'):
        config['futu_account'] = cp.get('FUTU_MOOMOO', 'futu_account', fallback='')
        config['futu_pwd_md5'] = cp.get('FUTU_MOOMOO', 'futu_pwd_md5', fallback='')
        config['opend_exec_path'] = cp.get('FUTU_MOOMOO', 'opend_exec_path', fallback='')
        config['api_host'] = cp.get('FUTU_MOOMOO', 'api_host', fallback='127.0.0.1')
        port_str = cp.get('FUTU_MOOMOO', 'api_port', fallback='11111')
        try:
            config['api_port'] = int(port_str)
        except ValueError:
            config['api_port'] = 11111
        
        # 验证必要的配置
        if not config['futu_account']:
            print("[WARN] FUTU_MOOMOO: futu_account 未配置")
        if not config['futu_pwd_md5']:
            print("[WARN] FUTU_MOOMOO: futu_pwd_md5 未配置")
        if not config['opend_exec_path']:
            print("[WARN] FUTU_MOOMOO: opend_exec_path 未配置")
    else:
        config['futu_account'] = ''
        config['futu_pwd_md5'] = ''
        config['opend_exec_path'] = ''
        config['api_host'] = '127.0.0.1'
        config['api_port'] = 11111
        print("[WARN] 配置文件中没有 [FUTU_MOOMOO] 段落")
    
    # 6. 读取 [PROCESS_SWITCHES] 段落
    if cp.has_section('PROCESS_SWITCHES'):
        for key in cp.options('PROCESS_SWITCHES'):
            value = cp.get('PROCESS_SWITCHES', key).strip().strip("'").strip('"')
            # 转换布尔值
            if value.lower() in ['yes', 'true', 'on', '1']:
                config[key] = True
            elif value.lower() in ['no', 'false', 'off', '0']:
                config[key] = False
            else:
                config[key] = value
    
    # 7. 读取 [MULTI_PROCESSING] 段落
    if cp.has_section('MULTI_PROCESSING'):
        use_mp_str = cp.get('MULTI_PROCESSING', 'use_multiprocessing', fallback='No')
        config['use_multiprocessing'] = use_mp_str.lower() in ['yes', 'true', 'on', '1']
        
        max_workers_str = cp.get('MULTI_PROCESSING', 'max_workers', fallback='4')
        try:
            config['max_workers'] = int(max_workers_str)
        except ValueError:
            config['max_workers'] = 4
    
    # 8. 读取 [HK_MACRO_DATA] 段落
    if cp.has_section('HK_MACRO_DATA'):
        for key in cp.options('HK_MACRO_DATA'):
            value = cp.get('HK_MACRO_DATA', key).strip().strip("'").strip('"')
            if value:
                config[key] = value
    
    # 9. 读取 [ANALYSIS_PERIOD] 段落
    if cp.has_section('ANALYSIS_PERIOD'):
        for key in cp.options('ANALYSIS_PERIOD'):
            value = cp.get('ANALYSIS_PERIOD', key).strip().strip("'").strip('"')
            if value:
                config[key] = value
    
    # 10. 读取 [DATA_DOWNLOAD] 段落
    if cp.has_section('DATA_DOWNLOAD'):
        for key in cp.options('DATA_DOWNLOAD'):
            value = cp.get('DATA_DOWNLOAD', key).strip().strip("'").strip('"')
            if value:
                config[key] = value
    
    # 构建完整路径
    data_rel = config.get('data_dir', 'data')
    config['full_data_dir'] = os.path.join(str(project_dir), data_rel)
    
    report_rel = config.get('report_dir', 'report')
    config['full_report_dir'] = os.path.join(str(project_dir), report_rel)
    
    log_rel = config.get('log_dir', 'log')
    config['full_log_dir'] = os.path.join(str(project_dir), log_rel)
    
    temp_rel = config.get('temp_dir', 'temp')
    config['full_temp_dir'] = os.path.join(str(project_dir), temp_rel)
    
    sqlite_rel = config.get('sqlite_dir', 'SQLiteDB')
    config['full_sqlite_dir'] = os.path.join(str(project_dir), sqlite_rel)
    
    db_name = config.get('db_name', 'HK_Stock.db')
    config['full_db_path'] = os.path.join(config['full_sqlite_dir'], db_name)
    
    # 确保目录存在
    for path_key in ['full_data_dir', 'full_report_dir', 'full_log_dir', 
                    'full_temp_dir', 'full_sqlite_dir']:
        path = config.get(path_key)
        if path and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
    
    return config


def load_unified_config():
    """加载统一配置"""
    try:
        # 获取项目目录
        project_dir = get_project_dir()
        print(f"项目目录: {project_dir}")

        # 配置文件路径
        config_path = project_dir / 'config' / 'stock_data_analysis.par'
        print(f"配置文件路径: {config_path}")

        # 验证配置文件存在
        if not config_path.exists():
            # 尝试其他可能的路径
            alt_path = project_dir.parent / 'config' / 'stock_data_analysis.par'
            if alt_path.exists():
                config_path = alt_path
                print(f"使用备用配置文件路径: {config_path}")
            else:
                raise FileNotFoundError(f"配置文件不存在: {config_path}")

        # 加载配置
        config = load_config(str(config_path), str(project_dir))

        # 打印关键配置项
        print("\n=== 关键配置验证 ===")
        print(f"download_trading_data: {config.get('download_trading_data', '未找到')}")
        print(f"calculate_ta_indicators: {config.get('calculate_ta_indicators', '未找到')}")
        print(f"sqlite_dir: {config.get('sqlite_dir', '未找到')}")
        print(f"db_name: {config.get('db_name', '未找到')}")
        print(f"full_db_path: {config.get('full_db_path', '未找到')}")
        print(f"tickers count: {len(config.get('tickers', []))}")

        return config
    except Exception as e:
        print(f"统一配置加载错误: {str(e)}")
        traceback.print_exc()
        return {}


def get_validated_dates(config, project_dir):
    """
    获取并验证日期范围
    
    参数:
    config: 配置字典
    project_dir: 项目目录
    
    返回:
    start_date, end_date: 验证后的日期对象
    """
    try:
        # 获取配置中的日期字符串，处理 None 值
        start_date_str = config.get('start_date')
        end_date_str = config.get('end_date')
        
        # 如果配置项不存在或为 None，使用默认值
        if start_date_str is None or start_date_str == '':
            # 默认使用30天前
            start_date = datetime.now() - timedelta(days=30)
            print(f"⚠️ 未配置 start_date，使用默认值: {start_date.strftime('%Y-%m-%d')}")
        else:
            start_date_str = start_date_str.strip()
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        
        if end_date_str is None or end_date_str == '':
            # 默认使用今天
            end_date = datetime.now()
            print(f"⚠️ 未配置 end_date，使用默认值: {end_date.strftime('%Y-%m-%d')}")
        else:
            end_date_str = end_date_str.strip()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # 转换为日期对象（只保留日期部分）
        start_date = start_date.date()
        end_date = end_date.date()
        
        # 验证日期范围
        if start_date > end_date:
            raise ValueError(f"开始日期 {start_date} 不能晚于结束日期 {end_date}")
        
        # 如果结束日期是未来日期，调整为今天
        today = datetime.now().date()
        if end_date > today:
            print(f"⚠️ 结束日期 {end_date} 是未来日期，调整为今天 {today}")
            end_date = today
        
        # 如果开始日期也是未来日期，调整为30天前
        if start_date > today:
            start_date = today - timedelta(days=30)
            print(f"⚠️ 开始日期是未来日期，调整为 {start_date}")
        
        print(f"✅ 日期验证通过: {start_date} 至 {end_date}")
        return start_date, end_date
        
    except ValueError as e:
        print(f"❌ 日期格式错误: {e}")
        # 使用默认日期
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        print(f"⚠️ 使用默认日期范围: {start_date} 到 {end_date}")
        return start_date, end_date
    except Exception as e:
        print(f"❌ 处理日期范围时发生错误: {str(e)}")
        # 使用默认日期
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        print(f"⚠️ 使用默认日期范围: {start_date} 到 {end_date}")
        return start_date, end_date


def get_validated_dates_by_week(config, project_dir):
    """
    验证开始日期和结束日期（按周分析）

    参数:
    config (dict): 从 load_config 函数加载的配置字典
    project_dir (str): 项目目录路径

    返回:
    tuple: (start_date, end_date) 作为 datetime.date 对象
    """
    from dateutil.relativedelta import relativedelta
    
    try:
        # 获取日期配置
        start_date_str = config.get('start_date_week', '').strip()
        end_date_str = config.get('end_date_week', '').strip()

        # 当前日期作为参考
        today = datetime.now().date()

        # 情况1: 两个日期都为空或 "None"
        if not start_date_str or start_date_str.lower() == "none" or \
           not end_date_str or end_date_str.lower() == "none":
            # 设置为最近24个月
            end_date = today
            start_date = end_date - relativedelta(months=24)

            print(f"⚙️ 未指定日期范围，使用默认范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
            return start_date, end_date

        # 验证日期格式的正则表达式
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'  # YYYY-MM-DD

        # 情况2: 两个日期都非空且不为 "None"
        if start_date_str and end_date_str and \
           start_date_str.lower() != "none" and end_date_str.lower() != "none":
            # 验证格式
            if not re.match(date_pattern, start_date_str):
                raise ValueError(f"无效的 start_date 格式: {start_date_str} (应为 YYYY-MM-DD)")

            if not re.match(date_pattern, end_date_str):
                raise ValueError(f"无效的 end_date 格式: {end_date_str} (应为 YYYY-MM-DD)")

            # 转换为日期对象
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError as e:
                raise ValueError(f"日期转换失败: {str(e)}")

            # 验证日期范围
            if start_date > end_date:
                raise ValueError(f"开始日期 {start_date_str} 不能晚于结束日期 {end_date_str}")

            if start_date > today:
                raise ValueError(f"开始日期 {start_date_str} 不能晚于当前日期")

            if end_date > today:
                raise ValueError(f"结束日期 {end_date_str} 不能晚于当前日期")

            return start_date, end_date

        # 情况3: start_date非空且不为 "None"，end_date为空或 "None"
        if start_date_str and start_date_str.lower() != "none" and \
           (not end_date_str or end_date_str.lower() == "none"):
            # 验证格式
            if not re.match(date_pattern, start_date_str):
                raise ValueError(f"无效的 start_date 格式: {start_date_str} (应为 YYYY-MM-DD)")

            # 转换为日期对象
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError as e:
                raise ValueError(f"开始日期转换失败: {str(e)}")

            # 验证日期
            if start_date > today:
                raise ValueError(f"开始日期 {start_date_str} 不能晚于当前日期")

            # 设置end_date为start_date + 24个月
            end_date = start_date + relativedelta(months=24)

            # 确保不超过今天
            if end_date > today:
                end_date = today

            print(f"⚙️ 未指定结束日期，设置为开始日期后24个月: {end_date.strftime('%Y-%m-%d')}")
            return start_date, end_date

        # 情况4: end_date非空且不为 "None"，start_date为空或 "None"
        if end_date_str and end_date_str.lower() != "none" and \
           (not start_date_str or start_date_str.lower() == "none"):
            # 验证格式
            if not re.match(date_pattern, end_date_str):
                raise ValueError(f"无效的 end_date 格式: {end_date_str} (应为 YYYY-MM-DD)")

            # 转换为日期对象
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError as e:
                raise ValueError(f"结束日期转换失败: {str(e)}")

            # 验证日期
            if end_date > today:
                raise ValueError(f"结束日期 {end_date_str} 不能晚于当前日期")

            # 设置start_date为end_date - 24个月
            start_date = end_date - relativedelta(months=24)

            # 确保不早于最小日期
            min_date = datetime(2000, 1, 1).date()
            if start_date < min_date:
                start_date = min_date
                print(f"⚠️ 警告: 自动计算的开始日期早于2000年，调整为2000-01-01")

            print(f"⚙️ 未指定开始日期，设置为结束日期前24个月: {start_date.strftime('%Y-%m-%d')}")
            return start_date, end_date

    except ValueError as e:
        raise ValueError(f"日期验证失败: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"处理日期范围时发生错误: {str(e)}") from e


def fix_path_escapes(text):
    """
    自动修复Windows路径转义问题
    将单反斜杠替换为双反斜杠或正斜杠
    """
    # 使用正则表达式匹配Windows路径模式
    pattern = r'(?:[a-zA-Z]:\\)(?:[^\\\s]+\\)*[^\\\s]*'
    matches = re.findall(pattern, text)

    # 为每个匹配的路径创建修复版
    for match in matches:
        # 创建三种可能的修复版本
        raw_path = 'r"' + match.replace('\\', '\\\\') + '"'  # 原始字符串表示法
        double_slash_path = '"' + match.replace('\\', '\\\\') + '"'  # 双反斜杠
        forward_slash_path = '"' + match.replace('\\', '/') + '"'  # 正斜杠

        # 尝试使用最安全的正斜杠版本
        text = text.replace(f"'{match}'", forward_slash_path)
        text = text.replace(f'"{match}"', forward_slash_path)

    # 额外全局替换未转义的单个反斜杠
    text = re.sub(r'(?<!\\)\$?!\$', r'\\\\', text)

    return text


def setup_windows_encoding():
    """解决Windows环境的中文编码问题"""
    if sys.platform == "win32":
        try:
            os.system("chcp 65001 > nul")
        except Exception as e:
            print(f"设置控制台代码页失败: {e}")


# ==================== 股票信息查询（原 stock_info_utils.py） ====================

class StockInfoQuery:
    """股票信息查询类"""

    def __init__(self, db_path=None):
        """初始化查询工具"""
        if db_path is None:
            # 默认数据库路径
            project_root = Path(__file__).resolve().parent.parent.parent
            db_path = project_root / 'SQLiteDB' / 'HK_Stock.db'
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接数据库"""
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.conn:
            self.conn.close()

    def get_stock_info(self, code: str) -> Optional[Dict]:
        """获取单个股票信息

        Args:
            code: 股票代码

        Returns:
            Dict: 股票信息，如果不存在返回None
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM hk_stock_info WHERE code = ?",
                (code,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"查询股票信息失败: {e}")
            return None

    def get_stocks_by_sector(self, sector: str) -> List[Dict]:
        """获取指定行业的股票列表

        Args:
            sector: 行业名称

        Returns:
            List[Dict]: 股票列表
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM hk_stock_info WHERE sector = ? AND is_active = 1",
                (sector,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"查询行业股票失败: {e}")
            return []

    def get_all_sectors(self) -> List[str]:
        """获取所有行业列表

        Returns:
            List[str]: 行业列表
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT DISTINCT sector FROM hk_stock_info WHERE sector IS NOT NULL ORDER BY sector"
            )
            rows = cursor.fetchall()
            return [row['sector'] for row in rows]
        except Exception as e:
            print(f"查询行业列表失败: {e}")
            return []

    def get_all_stocks(self, active_only: bool = True) -> List[Dict]:
        """获取所有股票信息

        Args:
            active_only: 是否只返回活跃股票

        Returns:
            List[Dict]: 股票列表
        """
        try:
            cursor = self.conn.cursor()
            if active_only:
                cursor.execute(
                    "SELECT * FROM hk_stock_info WHERE is_active = 1 ORDER BY code"
                )
            else:
                cursor.execute("SELECT * FROM hk_stock_info ORDER BY code")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"查询所有股票失败: {e}")
            return []

    def search_stocks(self, keyword: str) -> List[Dict]:
        """搜索股票（按代码或名称）

        Args:
            keyword: 搜索关键词

        Returns:
            List[Dict]: 匹配的股票列表
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT * FROM hk_stock_info
                WHERE code LIKE ? OR name LIKE ?
                AND is_active = 1
                ORDER BY code
                """,
                (f'%{keyword}%', f'%{keyword}%')
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"搜索股票失败: {e}")
            return []

    def get_statistics(self) -> Dict:
        """获取统计信息

        Returns:
            Dict: 统计信息
        """
        try:
            cursor = self.conn.cursor()

            # 总记录数
            cursor.execute("SELECT COUNT(*) as total FROM hk_stock_info")
            total = cursor.fetchone()['total']

            # 活跃股票数
            cursor.execute(
                "SELECT COUNT(*) as active FROM hk_stock_info WHERE is_active = 1"
            )
            active = cursor.fetchone()['active']

            # 行业数量
            cursor.execute(
                "SELECT COUNT(DISTINCT sector) as sectors FROM hk_stock_info WHERE sector IS NOT NULL"
            )
            sectors = cursor.fetchone()['sectors']

            # 各行业股票数量
            cursor.execute(
                """
                SELECT sector, COUNT(*) as count
                FROM hk_stock_info
                WHERE sector IS NOT NULL
                GROUP BY sector
                ORDER BY count DESC
                """
            )
            sector_counts = cursor.fetchall()

            return {
                'total': total,
                'active': active,
                'sectors': sectors,
                'sector_distribution': [dict(row) for row in sector_counts]
            }
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {}

    def get_stock_codes(self, active_only: bool = True) -> List[str]:
        """获取所有股票代码

        Args:
            active_only: 是否只返回活跃股票

        Returns:
            List[str]: 股票代码列表
        """
        try:
            cursor = self.conn.cursor()
            if active_only:
                cursor.execute(
                    "SELECT code FROM hk_stock_info WHERE is_active = 1 ORDER BY code"
                )
            else:
                cursor.execute("SELECT code FROM hk_stock_info ORDER BY code")
            rows = cursor.fetchall()
            return [row['code'] for row in rows]
        except Exception as e:
            print(f"获取股票代码失败: {e}")
            return []

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()


# ==================== 路径工具（原 path_utils.py） ====================

def get_project_root():
    """
    返回 Core 目录（TA_Workflow/Core 的绝对路径）。
    该函数向上回溯两级（从 utl 目录出发），因为本文件位于 TA_Workflow/Core/utl/ 中。
    """
    return Path(__file__).resolve().parent.parent


# ==================== UTF-8 启动器（原 run_with_utf8.py） ====================

def setup_utf8():
    """设置UTF-8编码环境"""
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

    # 重新包装stdout/stderr
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    # Windows下设置控制台代码页
    if platform.system() == 'Windows':
        try:
            os.system('chcp 65001 > nul')
        except Exception:
            pass


def run_script_with_utf8(script_path, script_args=None):
    """以 UTF-8 环境执行指定 Python 脚本（run_with_utf8.py 的核心逻辑）"""
    if script_args is None:
        script_args = []
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"脚本不存在 - {script_path}")

    # 将参数添加到sys.argv
    sys.argv = [script_path] + list(script_args)

    # 将脚本目录添加到sys.path
    script_dir = os.path.dirname(os.path.abspath(script_path))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    # 使用runpy执行
    runpy.run_path(script_path, run_name="__main__")


def main_utf8_launcher(argv=None):
    """UTF-8 启动器命令行入口（供 run_with_utf8.py 兼容调用）"""
    argv = list(sys.argv if argv is None else argv)

    # 设置UTF-8编码
    setup_utf8()

    # 获取要执行的脚本路径
    if len(argv) < 2:
        print("用法: python stock_analysis_utl.py <脚本路径> [参数...]")
        print("示例: python Core/utl/stock_analysis_utl.py Core/Daily/Daily_TA1B_download_data_moomoo.py")
        return 1

    script_path = argv[1]
    script_args = argv[2:]

    # 检查脚本是否存在
    if not os.path.exists(script_path):
        print(f"错误: 脚本不存在 - {script_path}")
        return 1

    try:
        run_script_with_utf8(script_path, script_args)
    except SystemExit as e:
        # 脚本正常退出
        return e.code if e.code is not None else 0
    except Exception as e:
        print(f"执行脚本时发生错误: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    # 若带命令行参数，则作为 UTF-8 启动器使用：
    # python Core/utl/stock_analysis_utl.py <脚本路径> [参数...]
    if len(sys.argv) > 1:
        sys.exit(main_utf8_launcher())

    # 测试配置加载
    try:
        config = load_unified_config()
        print("\n=== 加载的配置 ===")
        for key, value in config.items():
            if 'pwd' in key.lower() or 'password' in key.lower():
                print(f"{key}: ******")
            else:
                print(f"{key}: {value}")
        
        # 验证关键配置
        print("\n=== 配置验证 ===")
        if config.get('tickers'):
            print(f"✅ 股票列表: {len(config['tickers'])} 只")
            print(f"   前5只: {', '.join(config['tickers'][:5])}")
        else:
            print("❌ 未找到股票列表")
        
        if config.get('FRED_API_KEY'):
            print(f"✅ FRED API Key: 已配置")
        else:
            print("❌ FRED API Key: 未配置")
            
        if config.get('futu_account'):
            print(f"✅ 富途账号: 已配置")
        else:
            print("❌ 富途账号: 未配置")
            
    except Exception as e:
        print(f"配置加载失败: {str(e)}")
        traceback.print_exc()
