#!/usr/bin/env python
# coding: utf-8

"""
Step 13: Merge daily analysis report with buy/sell signal reports 
Source code: Daily_TA7_Merge_Analysis_Report_Workflow.py
Function:
合并每只股票的多份 PDF 报告（视文件存在情况动态处理）：
- {ticker}_daily_analysis_report.pdf
- {ticker}_weekly_analysis_report.pdf
- {ticker}_buy_signal_analysis_sum.pdf   （可选，缺失时自动插入提示页）
- {ticker}_sell_signal_analysis_sum.pdf  （可选，缺失时自动插入提示页）

输出：{ticker}_analysis_report.pdf 保存在配置的报告目录中 ..\report\
"""

import os
import sys
import time
import io
import subprocess
import tempfile
import traceback
import logging
from pathlib import Path
from datetime import datetime
import PyPDF2

# 尝试导入 reportlab，用于生成占位 PDF 页面
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ reportlab 未安装，买入/卖出信号缺失时将直接跳过，不会插入提示页。"
          "可通过 pip install reportlab 安装以获得完整提示。")

# ==================== 注册中文字体（内置宋体） ====================
import platform

# ==================== 中文字体自动搜索与注册 ====================
CHINESE_FONT_NAME = None   # 最终注册成功的字体名

def _find_system_chinese_font():
    """根据操作系统查找常见的中文字体文件路径"""
    system = platform.system()
    common_fonts = []
    if system == "Windows":
        win_dir = os.environ.get("WINDIR", "C:\\Windows")
        common_fonts = [
            os.path.join(win_dir, "Fonts", "simsun.ttc"),
            os.path.join(win_dir, "Fonts", "msyh.ttc"),
            os.path.join(win_dir, "Fonts", "msyhbd.ttc"),
            os.path.join(win_dir, "Fonts", "simhei.ttf"),
        ]
    elif system == "Darwin":  # macOS
        common_fonts = [
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ]
    else:  # Linux
        common_fonts = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/arphic/ukai.ttc",
        ]
    # 追加项目本地字体（如有特殊需求可在此添加相对路径）
    # 注意：此时 project_dir 尚未定义，稍后在 main 中再检查本地字体
    return common_fonts

def register_chinese_font():
    """多级尝试注册中文字体：CID -> 系统字体 -> 降级英文"""
    global CHINESE_FONT_NAME
    if not REPORTLAB_AVAILABLE:
        return False

    # 第一级：尝试内置 CID 字体
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        try:
            pdfmetrics.getFont('STSong-Light')
            CHINESE_FONT_NAME = 'STSong-Light'
            print("📝 已使用内置CID字体：STSong-Light")
            return True
        except Exception:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            CHINESE_FONT_NAME = 'STSong-Light'
            print("📝 已注册内置CID字体：STSong-Light")
            return True
    except Exception as e:
        print(f"⚠️ CID字体注册失败：{e}，尝试系统字体...")

    # 第二级：尝试加载系统中的 TTF/TTC 字体
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        # 获取系统字体列表
        font_paths = _find_system_chinese_font()
        # 如果 project_dir 已定义，添加本地字体
        try:
            local_font = project_dir / "fonts" / "simsun.ttf"
            if local_font.exists():
                font_paths.insert(0, str(local_font))
        except NameError:
            pass  # project_dir 尚未定义
            
        for font_path in font_paths:
            if os.path.exists(font_path):
                font_name = os.path.splitext(os.path.basename(font_path))[0]
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    CHINESE_FONT_NAME = font_name
                    print(f"📝 已注册系统字体：{font_name} ({font_path})")
                    return True
                except Exception as e:
                    print(f"⚠️ 注册系统字体失败：{e}")
                    continue
        else:
            print("⚠️ 未找到系统中文字体文件")
    except ImportError:
        print("⚠️ 无法导入 ttfonts，系统字体不可用")

    # 降级：中文不可用，使用英文
    print("⚠️ 所有中文字体不可用，将使用英文提示")
    return False


def setup_logging(log_dir, log_filename="Daily_TA7_Merge_Analysis_Report_Workflow.log"):
    """
    配置日志系统，同时输出到控制台和日志文件
    
    参数:
    log_dir (str): 日志文件目录
    log_filename (str): 日志文件名
    """
    # 确保日志目录存在
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_filepath = os.path.join(log_dir, log_filename)
    else:
        log_filepath = log_filename
    
    # 清除现有的handler，避免重复
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 配置日志格式
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 设置根日志记录器
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # 文件处理器 - 写入日志文件
            logging.FileHandler(log_filepath, encoding='utf-8'),
            # 控制台处理器 - 输出到控制台
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # 重定向print到logging
    # 创建一个自定义的print函数
    global print
    original_print = print
    
    def logging_print(*args, **kwargs):
        """自定义print函数，将输出重定向到logging"""
        # 将args转换为字符串
        message = ' '.join(str(arg) for arg in args)
        # 如果有sep参数，使用它
        if 'sep' in kwargs:
            message = kwargs['sep'].join(str(arg) for arg in args)
        # 记录到日志
        logging.info(message)
    
    print = logging_print
    
    logging.info(f"日志系统初始化完成，日志文件: {log_filepath}")
    return log_filepath


# ==================== 生成提示 PDF ====================
def create_no_signal_pdf(ticker, signal_type, temp_dir):
    """
    在指定临时目录生成一个单页 PDF，提示该股票最近 3 周无买入/卖出信号

    参数:
        ticker (str): 股票代码
        signal_type (str): 'buy' 或 'sell'
        temp_dir (Path or str): 临时文件存放目录 (如 project_dir / "temp")

    返回:
        Path: 生成的临时 PDF 完整路径

    依赖:
        - reportlab 库 (全局变量 REPORTLAB_AVAILABLE 需已定义)
        - 全局变量 CHINESE_FONT_NAME (通常由 register_chinese_font() 设置)
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab 不可用，无法生成提示 PDF")

    # 确保临时目录存在
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 根据中文字体可用性选择文本和字体
    if CHINESE_FONT_NAME:
        signal_cn = "买入" if signal_type == "buy" else "卖出"
        text = f"{ticker} 在最近3周内没有{signal_cn}信号。"
        font_name = CHINESE_FONT_NAME
    else:
        signal_en = "buy" if signal_type == "buy" else "sell"
        text = f"{ticker} has no {signal_en} signal in the last 3 weeks."
        font_name = "Helvetica"

    # 创建临时文件（保留文件句柄以便 context manager 清理，这里用 os.close 关闭 fd）
    fd, tmp_path = tempfile.mkstemp(
        suffix=".pdf",
        prefix=f"{ticker}_{signal_type}_placeholder_",
        dir=str(temp_dir)
    )
    os.close(fd)
    tmp_path = Path(tmp_path)

    # 使用 reportlab 绘制 PDF 页面
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas

    c = rl_canvas.Canvas(str(tmp_path), pagesize=A4)
    width, height = A4
    c.setFont(font_name, 12)
    c.drawCentredString(width / 2, height / 2, text)
    c.save()

    # 调试输出（显示完整临时文件路径）
    if CHINESE_FONT_NAME:
        signal_cn = "买入" if signal_type == "buy" else "卖出"
        logging.info(f"  ℹ️  {signal_cn}信号摘要缺失，已生成提示页：{tmp_path}")
    else:
        logging.info(f"  ℹ️  Signal summary missing, generated placeholder: {tmp_path}")

    return tmp_path


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


# ==================== PDF 合并函数 ====================
def merge_pdfs(pdf_inputs, pdf_output):
    """
    将多个 PDF 文件合并为一个 PDF 文件

    参数:
        pdf_inputs (list): 包含多个 PDF 文件路径的列表（均已存在）
        pdf_output (str or Path): 合并后的输出文件路径

    返回:
        int: 成功合并的文件数
        list: 缺失的文件列表
    """
    merger = PyPDF2.PdfMerger()
    merged_count = 0
    missing_files = []

    try:
        for pdf in pdf_inputs:
            # 此时传入的文件均已确认存在（调用方已处理）
            if not os.path.exists(pdf):
                logging.warning(f"  ⚠️ 文件不存在: {pdf}")
                missing_files.append(str(pdf))
                continue
                
            try:
                with open(pdf, 'rb') as f:
                    merger.append(f)
                merged_count += 1
                logging.info(f"  ✅ 成功添加PDF: {pdf}")
            except Exception as e:
                logging.error(f"  ❌ 处理文件 {pdf} 时出错：{e}")
                raise

        if merged_count > 0:
            with open(pdf_output, 'wb') as out_file:
                merger.write(out_file)
            logging.info(f"  ✅ 成功合并 {merged_count} 个 PDF → {pdf_output}")
        else:
            logging.warning("  ❌ 没有有效的 PDF 文件可供合并")
    except Exception as e:
        logging.error(f"  ❌ 合并失败：{e}")
        raise
    finally:
        merger.close()

    return merged_count, missing_files


# ==================== 辅助函数：用系统默认程序打开 PDF ====================
def open_pdf(path):
    """使用系统默认的 PDF 阅读器打开文件"""
    path = str(path)
    if sys.platform == 'win32':
        os.startfile(path)
    elif sys.platform == 'darwin':
        subprocess.run(['open', path])
    else:
        subprocess.run(['xdg-open', path])


# ==================== 主程序 ====================
def main():
    try:
        # ----- 1. 加载配置文件 -----
        config_path = project_dir / "config" / "stock_data_analysis.par"
        CONFIG = load_config(config_path, project_dir)
        logging.info(f"配置文件加载成功：{config_path}")

        # ----- 2. 更新全局路径 -----
        GlobalConfig.update_paths(CONFIG, project_dir)

        # ----- 3. 初始化日志系统 -----
        # 在更新路径后初始化日志系统
        log_filepath = setup_logging(
            GlobalConfig.full_log_dir, 
            "Daily_TA7_Merge_Analysis_Report_Workflow.log"
        )

        # ----- 4. 注册中文字体 -----
        if REPORTLAB_AVAILABLE:
            register_chinese_font()

        # ----- 5. 显示配置概览 -----
        logging.info("=" * 50)
        logging.info(f"项目目录：{project_dir}")
        logging.info(f"配置文件位置：{config_path}")
        logging.info(f"报告目录：{GlobalConfig.full_report_dir}")
        logging.info(f"临时目录：{GlobalConfig.full_temp_dir}")
        logging.info(f"日志目录：{GlobalConfig.full_log_dir}")
        logging.info(f"日志文件：{log_filepath}")

        # ----- 6. 获取股票列表 -----
        tickers = CONFIG.get('tickers')
        if not tickers:
            DEFAULT_TICKERS = [
                "00788", "00371", "02202", "00354", "00357", "03800",
                "00020", "00268", "01093", "06060", "01951", "01177", "03033"
            ]
            tickers = DEFAULT_TICKERS
            logging.warning(f"配置文件中未找到股票代码，使用默认列表：{tickers}")
        else:
            logging.info(f"从配置加载了 {len(tickers)} 只股票代码")
            if len(tickers) > 5:
                logging.info(f"前5个股票代码: {tickers[:5]}... 等")
            else:
                logging.info(f"股票代码: {tickers}")

        # ----- 7. 是否自动打开合并后的 PDF -----
        auto_open = CONFIG.get('auto_open_pdf', False)
        if auto_open:
            logging.info("🔓 自动打开 PDF 功能已启用")

        # ----- 8. 逐只股票合并报告 -----
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.info(f"{current_time} 开始合并分析报告！")
        
        success_count = 0
        for ticker in tickers:
            logging.info(f"\n📄 正在处理 {ticker}...")

            # 固定存在的两份报告
            daily_pdf = Path(GlobalConfig.full_report_dir) / f"{ticker}_daily_analysis_report.pdf"
            weekly_pdf = Path(GlobalConfig.full_report_dir) / f"{ticker}_weekly_analysis_report.pdf"

            # 可能缺失的买卖信号摘要
            buy_signal_pdf = Path(GlobalConfig.full_report_dir) / f"{ticker}_buy_signal_analysis_sum.pdf"
            sell_signal_pdf = Path(GlobalConfig.full_report_dir) / f"{ticker}_sell_signal_analysis_sum.pdf"

            # 构建实际要合并的文件列表（动态处理缺失项）
            input_files = []
            temp_files = []  # 用于记录生成的临时文件，稍后清理
            missing_files = []

            # 日线报告（必须存在，否则跳过该股票？可根据业务调整，此处仅给出警告）
            if daily_pdf.exists():
                input_files.append(daily_pdf)
                logging.info(f"  ✅ 找到日线报告: {daily_pdf.name}")
            else:
                logging.warning(f"  ⚠️ {daily_pdf.name} 不存在，将跳过")
                missing_files.append(str(daily_pdf))

            if weekly_pdf.exists():
                input_files.append(weekly_pdf)
                logging.info(f"  ✅ 找到周线报告: {weekly_pdf.name}")
            else:
                logging.warning(f"  ⚠️ {weekly_pdf.name} 不存在，将跳过")
                missing_files.append(str(weekly_pdf))

            # 处理买入信号摘要
            if buy_signal_pdf.exists():
                input_files.append(buy_signal_pdf)
                logging.info(f"  ✅ 找到买入信号摘要: {buy_signal_pdf.name}")
            else:
                logging.warning(f"  ⚠️ {buy_signal_pdf.name} 不存在", end="")
                if REPORTLAB_AVAILABLE:
                    try:
                        placeholder = create_no_signal_pdf(ticker, "buy", GlobalConfig.full_temp_dir)
                        input_files.append(placeholder)
                        temp_files.append(placeholder)
                        logging.info(f"  ✅ 已生成买入信号提示页")
                    except Exception as e:
                        logging.error(f"，且生成提示页失败：{e}")
                else:
                    logging.warning("，且未安装 reportlab，无法生成提示页")

            # 处理卖出信号摘要
            if sell_signal_pdf.exists():
                input_files.append(sell_signal_pdf)
                logging.info(f"  ✅ 找到卖出信号摘要: {sell_signal_pdf.name}")
            else:
                logging.warning(f"  ⚠️ {sell_signal_pdf.name} 不存在", end="")
                if REPORTLAB_AVAILABLE:
                    try:
                        placeholder = create_no_signal_pdf(ticker, "sell", GlobalConfig.full_temp_dir)
                        input_files.append(placeholder)
                        temp_files.append(placeholder)
                        logging.info(f"  ✅ 已生成卖出信号提示页")
                    except Exception as e:
                        logging.error(f"，且生成提示页失败：{e}")
                else:
                    logging.warning("，且未安装 reportlab，无法生成提示页")

            # 合并
            output_pdf = Path(GlobalConfig.full_report_dir) / f"{ticker}_analysis_report.pdf"
            merged, missing_files = merge_pdfs(input_files, output_pdf)

            # 记录合并结果
            if missing_files:
                logging.warning(f"股票 {ticker} 缺失 {len(missing_files)} 个PDF文件")
                for missing_file in missing_files:
                    logging.warning(f"  缺失文件: {missing_file}")

            if merged > 0:
                success_count += 1
                logging.info(f"股票 {ticker} 合并完成，成功合并 {merged} 个文件")
                if auto_open:
                    try:
                        open_pdf(output_pdf)
                        time.sleep(1)
                        logging.info(f"  📂 已打开 PDF：{output_pdf}")
                    except Exception as e:
                        logging.error(f"  ⚠️ 无法打开 PDF：{e}")
            else:
                logging.error(f"  ❌ {ticker} 合并失败——没有有效的输入文件")

            # 清理临时文件
            for tmp in temp_files:
                try:
                    tmp.unlink()
                    logging.info(f"  🗑️ 已清理临时文件: {tmp}")
                except Exception as e:
                    logging.warning(f"  ⚠️ 清理临时文件失败: {tmp}, 错误: {e}")

        # ----- 9. 汇总 -----
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.info("=" * 50)
        logging.info(f"{current_time} ✅ 完成！成功合并 {success_count} / {len(tickers)} 只股票的报告")
        if not REPORTLAB_AVAILABLE:
            logging.info("💡 提示：安装 reportlab 可在信号摘要缺失时自动插入提示页。")

    except Exception as e:
        logging.error(f"发生未知错误: {type(e).__name__}: {e}")
        logging.error(traceback.format_exc())

        if 'get_ipython' not in globals():
            sys.exit(1)
        else:
            logging.info("在 Jupyter 环境中运行，程序继续但可能无法正常工作")


# ==================== 程序入口 ====================
if __name__ == "__main__":
    # 执行Windows编码设置
    setup_windows_encoding()
    main()