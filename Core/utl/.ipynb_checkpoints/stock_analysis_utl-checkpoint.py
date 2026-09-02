#!/usr/bin/env python
# coding: utf-8

# In[57]:


import re
import sys
import os
import io
import traceback
from datetime import datetime, timedelta
from pathlib import Path



# In[58]:


# config_loader.py
import os
import sys
import traceback
from pathlib import Path
import configparser

class GlobalConfig:
    """全局配置类，用于存储路径信息"""
    full_data_dir = None
    full_report_dir = None
    full_log_dir = None
    full_temp_dir = None

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

def load_config(config_path, project_dir):
    """
    加载配置文件参数，合并相对路径与项目目录
    
    参数:
        config_path: 配置文件路径
        project_dir: 项目根目录
    
    返回:
        config: 包含所有配置参数的字典
    """
    config_path = str(config_path)
    project_dir = str(project_dir)
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件未找到: {config_path}")
    
    config = {}
    config_parser = configparser.ConfigParser()
    
    try:
        # 尝试多种编码格式
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'latin1', 'cp1252', 'utf-16']
        used_encoding = None
        
        for encoding in encodings:
            try:
                with open(config_path, 'r', encoding=encoding) as f:
                    config_parser.read_file(f)
                used_encoding = encoding
                break
            except (UnicodeDecodeError, LookupError):
                continue
        
        if used_encoding is None:
            raise UnicodeDecodeError("无法使用可用编码解码配置文件")
        
        # === 处理 FOLDERS 部分 ===
        if config_parser.has_section('FOLDERS'):
            for key in config_parser.options('FOLDERS'):
                value = config_parser.get('FOLDERS', key)
                value = value.strip().strip("'").strip('"')
                config[key] = value
        
        # === 处理 ANALYSIS_PERIOD 部分 ===
        if config_parser.has_section('ANALYSIS_PERIOD'):
            for key in config_parser.options('ANALYSIS_PERIOD'):
                value = config_parser.get('ANALYSIS_PERIOD', key)
                value = value.strip().strip("'").strip('"')
                config[key] = value
        
        # === 处理 TICKERS 部分 ===
        if config_parser.has_section('TICKERS'):
            for key in config_parser.options('TICKERS'):
                value = config_parser.get('TICKERS', key)
                value = value.strip().strip("'").strip('"')
                
                # 智能解析列表
                if value.startswith('[') and value.endswith(']'):
                    try:
                        parsed_value = ast.literal_eval(value)
                        if isinstance(parsed_value, list):
                            config[key] = parsed_value
                        else:
                            config[key] = [item.strip() for item in value.strip('[]').split(',')]
                    except (SyntaxError, ValueError):
                        config[key] = [item.strip() for item in value.strip('[]').split(',')]
                else:
                    if ',' in value:
                        config[key] = [item.strip() for item in value.split(',')]
                    else:
                        config[key] = [value]
                
                # 清理股票代码
                config[key] = [code.strip("'").strip('"') for code in config[key]]
        
        # === 处理 PROCESS_SWITCHES 部分 ===
        if config_parser.has_section('PROCESS_SWITCHES'):
            for key in config_parser.options('PROCESS_SWITCHES'):
                value = config_parser.get('PROCESS_SWITCHES', key)
                value = value.strip().strip("'").strip('"').lower()
                config[key] = value in ['yes', 'true', '1', 'y']
        
        # === 合并相对路径与项目目录 ===
        # 处理数据目录
        data_rel = config.get('data_dir', 'data')
        config['full_data_dir'] = os.path.join(project_dir, data_rel)
        GlobalConfig.full_data_dir = config['full_data_dir']

        # 处理报告目录
        report_rel = config.get('report_dir', 'report')
        config['full_report_dir'] = os.path.join(project_dir, report_rel)
        GlobalConfig.full_report_dir = config['full_report_dir']

        # 处理日志目录
        log_rel = config.get('log_dir', 'log')
        config['full_log_dir'] = os.path.join(project_dir, log_rel)
        GlobalConfig.full_log_dir = config['full_log_dir']

        # 处理临时目录
        temp_rel = config.get('temp_dir', 'temp')
        config['full_temp_dir'] = os.path.join(project_dir, temp_rel)
        GlobalConfig.full_temp_dir = config['full_temp_dir']
        
        # 处理转换脚本目录
        scripts_rel = config.get('converted_scripts_dir', 'scripts')
        config['full_converted_scripts_dir'] = os.path.join(project_dir, scripts_rel)
        
        # 验证和创建目录
        for path_key in ['full_data_dir', 'full_report_dir', 'full_log_dir', 'full_temp_dir', 'full_converted_scripts_dir']:
            path = config.get(path_key)
            if path and not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
        
        # tickers列表处理
        if 'tickers' not in config:
            config['tickers'] = []
        
        if isinstance(config['tickers'], str):
            config['tickers'] = [ticker.strip() for ticker in config['tickers'].split(',') if ticker.strip()]
        
        # 股票代码列表去重
        if isinstance(config['tickers'], (list, tuple)):
            if config['tickers']:
                config['tickers'] = list(dict.fromkeys(config['tickers']))
        else:
            config['tickers'] = []
        
        # 为新增参数设置默认值
        if 'download_trading_data' not in config:
            config['download_trading_data'] = False
            
        if 'convert_money_flow' not in config:
            config['convert_money_flow'] = False

        if 'auto_open_pdf' not in config:
            config['auto_open_pdf'] = False
            
        return config
    
    except configparser.Error as e:
        raise RuntimeError(f"配置文件解析错误: {str(e)}") from e
    except UnicodeDecodeError as e:
        raise RuntimeError(f"配置文件编码错误: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"处理配置文件时发生错误: {str(e)}") from e

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
        
        return config
    except Exception as e:
        print(f"统一配置加载错误: {str(e)}")
        traceback.print_exc()
        return {}

if __name__ == "__main__":
    # 测试配置加载
    try:
        config = load_unified_config()
        print("\n=== 加载的配置 ===")
        for key, value in config.items():
            print(f"{key}: {value}")
    except Exception as e:
        print(f"配置加载失败: {str(e)}")
        traceback.print_exc()


# In[59]:


from datetime import datetime, timedelta
import re

def get_validated_dates(config, project_dir):
    """
    验证开始日期和结束日期
    
    参数:
    config (dict): 从 load_config 函数加载的配置字典
    project_dir (str): 项目目录路径
    
    返回:
    tuple: (start_date, end_date) 作为 datetime.date 对象
    """
    try:
        # 获取日期配置
        start_date_str = config.get('start_date', '').strip()
        end_date_str = config.get('end_date', '').strip()

        print(f"start_date_str is {start_date_str} ")
        print(f"start_date_str is {end_date_str} ")
        
        # 当前日期作为参考
        today = datetime.now().date()
        
        # 情况1: 两个日期都为空或 "None"
        # if ( not start_date_str or start_date_str.lower() == "none" ) and \
        #    ( not end_date_str or end_date_str.lower() == "none" ):
        if ( not start_date_str and not start_date_str ):
            # 设置为最近6个月
            end_date = today
            start_date = end_date - timedelta(days=180)  # 近似6个月
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
            
            # # 设置end_date为start_date + 6个月
            # end_date = start_date + timedelta(days=180)  # 近似6个月
            
            # # 确保不超过今天
            # if end_date > today:
            #     end_date = today

            # 设置end_date为今天
            end_date = today
            
            print(f"⚙️ 未指定结束日期，设置为开始日期后6个月: {end_date.strftime('%Y-%m-%d')}")
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
            
            # 设置start_date为end_date - 6个月
            start_date = end_date - timedelta(days=180)  # 近似6个月
            
            # 确保不早于最小日期
            min_date = datetime(2000, 1, 1).date()
            if start_date < min_date:
                start_date = min_date
                print(f"⚠️ 警告: 自动计算的开始日期早于2000年，调整为2000-01-01")
            
            print(f"⚙️ 未指定开始日期，设置为结束日期前6个月: {start_date.strftime('%Y-%m-%d')}")
            return start_date, end_date
    
    except ValueError as e:
        raise ValueError(f"日期验证失败: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"处理日期范围时发生错误: {str(e)}") from e


# In[60]:


from datetime import datetime, timedelta
import re
from dateutil.relativedelta import relativedelta

def get_validated_dates_by_week(config, project_dir):
    """
    验证开始日期和结束日期
    
    参数:
    config (dict): 从 load_config 函数加载的配置字典
    project_dir (str): 项目目录路径
    
    返回:
    tuple: (start_date, end_date) 作为 datetime.date 对象
    """
    try:
        # 获取日期配置
        start_date_str = config.get('start_date', '').strip()
        end_date_str = config.get('end_date', '').strip()
        
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
            end_date = start_date + relativedelta(months=24)  # 近似24个月
            
            # 确保不超过今天
            if end_date > today:
                end_date = today
            
            print(f"⚙️ 未指定结束日期，设置为开始日期后6个月: {end_date.strftime('%Y-%m-%d')}")
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
            start_date = end_date - relativedelta(months=24)  # 近似24个月
            
            # 确保不早于最小日期
            min_date = datetime(2000, 1, 1).date()
            if start_date < min_date:
                start_date = min_date
                print(f"⚠️ 警告: 自动计算的开始日期早于2000年，调整为2000-01-01")
            
            print(f"⚙️ 未指定开始日期，设置为结束日期前6个月: {start_date.strftime('%Y-%m-%d')}")
            return start_date, end_date
    
    except ValueError as e:
        raise ValueError(f"日期验证失败: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"处理日期范围时发生错误: {str(e)}") from e


# In[61]:


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


# In[62]:


def setup_windows_encoding():
    """解决Windows环境的中文编码问题"""
    if sys.platform == "win32":  # 现在可以正常访问 sys 了
        try:
            os.system("chcp 65001 > nul")
        except Exception as e:
            print(f"设置控制台代码页失败: {e}")


# In[63]:


class GlobalConfig:
    full_data_dir = None
    full_report_dir = None
    full_log_dir = None
    full_temp_dir = None
    
    @classmethod
    def update_paths(cls, config, project_dir):
        """更新全局路径配置"""
        # 使用fix_path_escapes处理路径
        cls.full_data_dir = fix_path_escapes(os.path.join(project_dir, config.get("data_dir", "data")))
        cls.full_report_dir = fix_path_escapes(os.path.join(project_dir, config.get("report_dir", "report")))
        cls.full_log_dir = fix_path_escapes(os.path.join(project_dir, config.get("log_dir", "log")))
        cls.full_temp_dir = fix_path_escapes(os.path.join(project_dir, config.get("temp_dir", "temp")))
        
        # 确保目录存在
        os.makedirs(cls.full_data_dir, exist_ok=True)
        os.makedirs(cls.full_report_dir, exist_ok=True)
        os.makedirs(cls.full_log_dir, exist_ok=True)
        os.makedirs(cls.full_temp_dir, exist_ok=True)
    

