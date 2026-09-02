#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
顺序执行月线股票分析程序
项目路径: C:\Users\Quansheng\Documents\projects\TA_Workflow
脚本路径: core\Monthly

使用方法：
cd C:\Users\Quansheng\Documents\projects\TA_Workflow
python Monthly_TA_report.py

"""

import subprocess
import sys
import os
from datetime import datetime
import platform
import io
import logging
from logging.handlers import RotatingFileHandler

# ==================== 编码设置 ====================
# 设置主程序控制台编码为UTF-8
if platform.system() == 'Windows':
    # 设置控制台代码页
    try:
        os.system('chcp 65001 > nul')
    except:
        pass
    
    # 重新包装stdout/stderr
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 设置环境变量
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# ==================== 路径配置 ====================
PROJECT_ROOT = r"C:\Users\Quansheng\Documents\projects\TA_Workflow"
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "Core", "Monthly")
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv")
LAUNCHER_PATH = os.path.join(PROJECT_ROOT,"Core", "Utl", "stock_analysis_utl.py")

# 日志文件路径配置
LOG_DIR = os.path.join(PROJECT_ROOT, "Log")
LOG_FILE = os.path.join(LOG_DIR, "Monthly_TA_report.log")

# ==================== 日志设置 ====================
class TeeLogger:
    """同时将输出写入日志文件和控制台的类"""
    def __init__(self, log_file_path, console_output=True):
        self.console_output = console_output
        self.log_file_path = log_file_path
        self.log_file = None
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志系统"""
        # 创建日志目录
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
        
        # 设置logger
        self.logger = logging.getLogger('Monthly_TA_Report')
        self.logger.setLevel(logging.INFO)
        
        # 移除已有的处理器
        self.logger.handlers.clear()
        
        # 文件处理器 - 直接覆盖模式
        file_handler = logging.FileHandler(  # 改用 FileHandler
            self.log_file_path,
            mode='w',  # 'w' 表示覆盖写入
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        
        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # 控制台处理器（可选）
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter('%(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def write(self, message, level='info'):
        """写入日志"""
        if not message or message.strip() == '':
            return
        
        # 移除多余的换行符
        message = message.rstrip('\n')
        
        if level == 'info':
            self.logger.info(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'debug':
            self.logger.debug(message)
        else:
            self.logger.info(message)
    
    def info(self, message):
        self.write(message, 'info')
    
    def warning(self, message):
        self.write(message, 'warning')
    
    def error(self, message):
        self.write(message, 'error')
    
    def debug(self, message):
        self.write(message, 'debug')
    
    def close(self):
        """关闭日志"""
        for handler in self.logger.handlers:
            handler.close()
        self.logger.handlers.clear()
        
# 全局logger实例
tee_logger = None

# ==================== 重定向输出函数 ====================
class OutputRedirector:
    """重定向stdout/stderr到日志的类"""
    def __init__(self, tee_logger, original_stream, stream_type='stdout'):
        self.tee_logger = tee_logger
        self.original_stream = original_stream
        self.stream_type = stream_type
        self.buffer = []
    
    def write(self, text):
        """写入方法"""
        if text and text.strip():
            # 写入日志
            if self.stream_type == 'stderr':
                self.tee_logger.error(text.strip())
            else:
                self.tee_logger.info(text.strip())
        
        # 同时输出到原始流
        if self.original_stream:
            self.original_stream.write(text)
    
    def flush(self):
        """刷新方法"""
        if self.original_stream:
            self.original_stream.flush()
    
    def isatty(self):
        """判断是否为终端"""
        return False if self.original_stream is None else self.original_stream.isatty()

def setup_global_logger(console_output=True):
    """设置全局logger"""
    global tee_logger
    tee_logger = TeeLogger(LOG_FILE, console_output)
    return tee_logger

def redirect_output_to_log():
    """重定向标准输出和错误输出到日志"""
    global tee_logger
    
    if tee_logger is None:
        setup_global_logger()
    
    # 保存原始流
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # 重定向stdout
    sys.stdout = OutputRedirector(tee_logger, original_stdout, 'stdout')
    
    # 重定向stderr
    sys.stderr = OutputRedirector(tee_logger, original_stderr, 'stderr')

def restore_output():
    """恢复标准输出和错误输出"""
    if hasattr(sys.stdout, 'original_stream'):
        sys.stdout = sys.stdout.original_stream
    if hasattr(sys.stderr, 'original_stream'):
        sys.stderr = sys.stderr.original_stream

def get_venv_python():
    """获取虚拟环境中的Python解释器路径"""
    system = platform.system()
    
    if system == 'Windows':
        venv_python = os.path.join(VENV_DIR, 'Scripts', 'python.exe')
    else:  # Linux/Mac
        venv_python = os.path.join(VENV_DIR, 'bin', 'python')
    
    # 检查虚拟环境是否存在
    if os.path.exists(venv_python):
        return venv_python
    else:
        tee_logger.warning(f"警告: 未找到虚拟环境 {venv_python}")
        tee_logger.warning("使用系统Python")
        return sys.executable

def check_launcher():
    """检查启动器是否存在，如果不存在则创建"""
    if not os.path.exists(LAUNCHER_PATH):
        tee_logger.warning(f"警告: 启动器不存在: {LAUNCHER_PATH}")
        tee_logger.warning("请先创建 stock_analysis_utl.py 文件")
        return False
    return True

def change_to_scripts_dir():
    """切换到脚本目录"""
    if os.path.exists(SCRIPTS_DIR):
        os.chdir(SCRIPTS_DIR)
        tee_logger.info(f"切换到脚本目录: {SCRIPTS_DIR}")
        return True
    else:
        tee_logger.error(f"错误: 脚本目录不存在: {SCRIPTS_DIR}")
        return False

def filter_error_output(stderr_text):
    """过滤错误输出，去掉logging错误堆栈"""
    if not stderr_text:
        return ""
    
    lines = stderr_text.split('\n')
    filtered_lines = []
    skip = False
    skip_patterns = [
        '--- Logging error ---',
        'Call stack:',
        'Message:',
        'Arguments:',
        'UnicodeEncodeError',
        'charmap codec'
    ]
    
    for line in lines:
        # 检查是否应该跳过这一行
        should_skip = False
        for pattern in skip_patterns:
            if pattern in line:
                should_skip = True
                break
        
        # 如果当前行是空行且处于跳过状态，继续跳过
        if skip and not line.strip():
            continue
        
        # 如果当前行是空行，重置跳过状态
        if not line.strip():
            skip = False
            continue
        
        # 如果应该跳过，设置跳过标记
        if should_skip:
            skip = True
            continue
        
        # 如果处于跳过状态，继续跳过
        if skip:
            continue
        
        # 不跳过文件路径行
        if line.strip().startswith('  File'):
            continue
        
        # 添加有意义的行
        if line.strip():
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)

def run_script(script_name, python_executable, is_final_script=False):
    """执行单个Python脚本
    
    Args:
        script_name: 脚本名称
        python_executable: Python解释器路径
        is_final_script: 是否为最后一个脚本（合并PDF）
    """
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    
    tee_logger.info(f"\n{'='*70}")
    tee_logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行: {script_name}")
    tee_logger.info(f"脚本路径: {script_path}")
    if is_final_script:
        tee_logger.info("⚠️  这是最后一个脚本（合并PDF），执行完成后将自动退出")
    tee_logger.info(f"{'='*70}")
    
    # 检查脚本是否存在
    if not os.path.exists(script_path):
        tee_logger.error(f"[FAIL] 脚本文件不存在: {script_path}")
        return False
    
    # 检查启动器是否存在
    if not check_launcher():
        tee_logger.error("[FAIL] 启动器不存在，无法执行脚本")
        return False
    
    try:
        # 创建环境变量
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        env['PYTHONHASHSEED'] = '0'  # 可选，用于可重现性
        
        # 使用启动器执行脚本
        cmd = [
            python_executable,
            LAUNCHER_PATH,
            script_path
        ]
        
        # 执行脚本
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=SCRIPTS_DIR,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        
        # 打印标准输出
        if result.stdout:
            try:
                tee_logger.info(result.stdout)
            except UnicodeEncodeError:
                tee_logger.info(result.stdout.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
        
        # 打印错误输出（过滤后）
        if result.stderr:
            filtered_error = filter_error_output(result.stderr)
            if filtered_error:
                tee_logger.error(f"错误输出:\n{filtered_error}")
        
        # 检查执行结果
        if result.returncode == 0:
            tee_logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SUCCESS] {script_name} 执行成功")
            return True
        else:
            tee_logger.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [FAIL] {script_name} 执行失败 (返回码: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        tee_logger.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] {script_name} 执行超时")
        return False
    except Exception as e:
        tee_logger.error(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] 执行 {script_name} 时发生异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_environment(python_exe):
    """检查环境"""
    tee_logger.info("\n" + "="*70)
    tee_logger.info("环境检查")
    tee_logger.info("="*70)
    
    # 检查项目根目录
    if os.path.exists(PROJECT_ROOT):
        tee_logger.info(f"[OK] 项目根目录: {PROJECT_ROOT}")
    else:
        tee_logger.error(f"[FAIL] 项目根目录不存在: {PROJECT_ROOT}")
        return False
    
    # 检查脚本目录
    if os.path.exists(SCRIPTS_DIR):
        tee_logger.info(f"[OK] 脚本目录: {SCRIPTS_DIR}")
    else:
        tee_logger.error(f"[FAIL] 脚本目录不存在: {SCRIPTS_DIR}")
        return False
    
    # 检查启动器
    if os.path.exists(LAUNCHER_PATH):
        tee_logger.info(f"[OK] UTF-8启动器: {LAUNCHER_PATH}")
    else:
        tee_logger.error(f"[FAIL] UTF-8启动器不存在: {LAUNCHER_PATH}")
        tee_logger.error("请创建 stock_analysis_utl.py 文件")
        return False
    
    # 检查Python版本
    try:
        result = subprocess.run(
            [python_exe, '--version'],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        tee_logger.info(f"[OK] Python版本: {result.stdout.strip()}")
    except Exception as e:
        tee_logger.error(f"[FAIL] 无法获取Python版本信息: {e}")
        return False
    
    # 检查Python是否支持UTF-8
    try:
        result = subprocess.run(
            [python_exe, '-c', 'import sys; print(sys.stdout.encoding)'],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )
        encoding = result.stdout.strip()
        tee_logger.info(f"[OK] Python输出编码: {encoding}")
        if encoding.lower() != 'utf-8':
            tee_logger.warning(f"[WARN] 建议使用UTF-8编码，当前为: {encoding}")
    except Exception as e:
        tee_logger.warning(f"[WARN] 无法获取Python编码信息: {e}")
    
    # 列出脚本目录中的文件
    try:
        files = os.listdir(SCRIPTS_DIR)
        py_files = [f for f in files if f.endswith('.py')]
        tee_logger.info(f"[OK] 找到 {len(py_files)} 个Python文件")
        
        # 显示前5个文件
        if py_files:
            tee_logger.info(f"   示例文件: {', '.join(py_files[:5])}")
    except Exception as e:
        tee_logger.error(f"[FAIL] 无法读取脚本目录: {e}")
    
    tee_logger.info("="*70 + "\n")
    return True

def display_summary(success_count, total_count, failed_scripts, start_time):
    """显示执行摘要"""
    tee_logger.info(f"\n{'='*70}")
    tee_logger.info("执行摘要")
    tee_logger.info(f"{'='*70}")
    tee_logger.info(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    tee_logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    tee_logger.info(f"执行时长: {str(datetime.now() - start_time).split('.')[0]}")
    tee_logger.info(f"成功: {success_count}/{total_count}")
    
    if failed_scripts:
        tee_logger.info(f"\n失败的脚本 ({len(failed_scripts)}个):")
        for i, script in enumerate(failed_scripts, 1):
            tee_logger.info(f"  {i}. [FAIL] {script}")
        tee_logger.info(f"\n建议:")
        tee_logger.info(f"  1. 检查失败的脚本是否有语法错误")
        tee_logger.info(f"  2. 确认数据文件是否存在")
        tee_logger.info(f"  3. 查看错误输出获取详细信息")
        tee_logger.info(f"  4. 单独运行失败的脚本进行调试")
    else:
        tee_logger.info("\n[SUCCESS] 所有脚本执行成功！")
        tee_logger.info("✅ 月线技术分析报告已生成并合并完成")
    
    tee_logger.info(f"{'='*70}")

def main():
    """主函数"""
    start_time = datetime.now()
    
    # 设置全局logger
    global tee_logger
    tee_logger = setup_global_logger(console_output=True)
    
    # 重定向输出到日志
    redirect_output_to_log()
    
    # 记录启动信息
    tee_logger.info("="*70)
    tee_logger.info(f"程序启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    tee_logger.info(f"日志文件: {LOG_FILE}")
    tee_logger.info("="*70)
    
    try:
        # 获取虚拟环境的Python解释器
        python_exe = get_venv_python()
        tee_logger.info(f"使用Python解释器: {python_exe}")
        
        # 切换到脚本目录
        if not change_to_scripts_dir():
            tee_logger.error("无法切换到脚本目录，程序退出")
            return 1
        
        # 检查环境
        if not check_environment(python_exe):
            tee_logger.warning("\n环境检查失败，是否继续？(y/n): ")
            # 由于输出被重定向，这里使用input从控制台读取
            response = input().strip().lower()
            if response != 'y':
                tee_logger.info("程序退出")
                return 1
        
        # 要执行的脚本列表（按顺序）- 月线技术分析工作流
        scripts = [
            "Monthly_TA2A_Aggregate_Indicators_akshare.py",
            "Monthly_TA2B_Calculate_indicators.py",
            "Monthly_TA3_Analyze_Indicators_Plot.py",
            "Monthly_TA4A_Aggregate_MoneyFlow.py",
            "Monthly_TA4B_Analyze_MoneyFlow.py",
            "Monthly_TA5_MergePDF.py"  # 最后一个脚本 - 合并PDF
        ]
        
        tee_logger.info(f"\n{'='*70}")
        tee_logger.info(f"开始顺序执行 {len(scripts)} 个月线分析脚本")
        tee_logger.info(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        tee_logger.info(f"工作目录: {os.getcwd()}")
        tee_logger.info(f"Python解释器: {python_exe}")
        tee_logger.info(f"月线分析工作流包括:")
        for idx, script in enumerate(scripts, 1):
            if idx == len(scripts):
                tee_logger.info(f"  {idx}. {script} 📄 (合并PDF - 执行完成后自动退出)")
            else:
                tee_logger.info(f"  {idx}. {script}")
        tee_logger.info(f"{'='*70}")
        
        # 记录执行结果
        failed_scripts = []
        success_count = 0
        
        for i, script in enumerate(scripts, 1):
            # 判断是否为最后一个脚本（合并PDF）
            is_final = (i == len(scripts))
            
            tee_logger.info(f"\n>>> 进度: {i}/{len(scripts)} <<<")
            
            # 执行脚本
            if run_script(script, python_exe, is_final):
                success_count += 1
                
                # 如果是最后一个脚本且执行成功，自动退出
                if is_final:
                    tee_logger.info("\n" + "="*70)
                    tee_logger.info("✅ 所有月线分析脚本执行完成，PDF报告已合并")
                    tee_logger.info("🔄 程序将自动退出...")
                    tee_logger.info("="*70)
                    break
            else:
                failed_scripts.append(script)
                
                # 如果是最后一个脚本失败，直接退出
                if is_final:
                    tee_logger.error("\n" + "="*70)
                    tee_logger.error("❌ PDF合并脚本执行失败，程序将退出")
                    tee_logger.error("="*70)
                    break
                
                # 对于非最后一个脚本，询问是否继续
                if i < len(scripts):
                    tee_logger.info("\n是否继续执行下一个脚本？(y/n): ")
                    response = input().strip().lower()
                    if response != 'y':
                        tee_logger.info("用户中断执行")
                        break
        
        # 显示执行摘要（如果还没有显示完成信息）
        if success_count < len(scripts) or failed_scripts:
            display_summary(success_count, len(scripts), failed_scripts, start_time)
        
        # 记录完成信息
        tee_logger.info(f"\n程序完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        tee_logger.info(f"日志已保存到: {LOG_FILE}")
        tee_logger.info("="*70)
        
        # 返回失败数量作为退出码
        return len(failed_scripts)
    
    finally:
        # 恢复输出
        restore_output()
        # 关闭日志
        if tee_logger:
            tee_logger.close()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        # 记录中断信息到日志
        if tee_logger:
            tee_logger.warning("程序被用户中断")
            tee_logger.close()
        sys.exit(1)
    except Exception as e:
        print(f"\n程序发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        # 记录错误信息到日志
        if tee_logger:
            tee_logger.error(f"程序发生未预期的错误: {e}")
            tee_logger.error(traceback.format_exc())
            tee_logger.close()
        sys.exit(1)
        