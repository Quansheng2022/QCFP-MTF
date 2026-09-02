#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ==================================================
# Gen_Stock_Review_Prompt.py -- 合并日度、周度数据与模板，生成完整个股复盘Prompt
# 功能：读取已生成的日度和周度个股Prompt文件，结合模板文件，输出综合复盘分析提问
# 依赖：需要事先运行 Gen_Daily_Prompt.py 和 Gen_Weekly_Prompt.py 生成对应文件
# 输入：模板文件（个股review_复盘模板超级Prompt.txt），日度Prompt文件，周度Prompt文件
# 输出：PROJECT ROOT\prompt\review\Prompt_个股复盘_[stock_code]_[stock_name].txt
# ==================================================

import os
from datetime import datetime
from pathlib import Path
import logging
import json

# ==================== 项目根目录与输出路径 ====================
def get_project_root():
    """返回项目根目录（TA_Workflow2）"""
    return Path(__file__).resolve().parent.parent

def get_work_root():
    """返回当前脚本所在目录（用于查找 stock_list.json）"""
    return Path(__file__).resolve().parent

def get_prompt_dir():
    """返回prompt输出目录，并确保该目录存在"""
    root = get_project_root()
    prompt_dir = root / 'prompt'
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return prompt_dir

def get_review_prompt_dir():
    """返回review输出目录（PROJECT ROOT\prompt\review），并确保该目录存在"""
    root = get_project_root()
    review_dir = root / 'prompt' / 'review'
    review_dir.mkdir(parents=True, exist_ok=True)
    return review_dir

def get_code_prompt_dir():
    """返回code_prompt目录，并确保该目录存在"""
    root = get_project_root()
    code_prompt_dir = root / 'code_prompt'
    code_prompt_dir.mkdir(parents=True, exist_ok=True)
    return code_prompt_dir

# ==================== 加载股票列表 ====================
def load_stock_list():
    """
    从当前工作目录（脚本所在目录）的 stock_list.json 文件中读取股票列表
    返回列表，每个元素为字典，包含 'stock_code' 和 'stock_name'
    """
    work_dir = get_work_root()
    json_path = work_dir / 'stock_list.json'
    if not json_path.exists():
        logger.error(f"股票列表文件不存在: {json_path}")
        raise FileNotFoundError(f"请确保 {json_path} 存在且格式正确")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        stocks = data.get('stocks', [])
        if not stocks:
            logger.warning("股票列表为空")
        for s in stocks:
            if 'stock_code' not in s or 'stock_name' not in s:
                raise ValueError(f"股票条目缺少 'stock_code' 或 'stock_name' 字段: {s}")
        logger.info(f"成功加载 {len(stocks)} 只股票")
        return stocks
    except json.JSONDecodeError as e:
        logger.error(f"解析 JSON 文件失败: {e}")
        raise
    except Exception as e:
        logger.error(f"加载股票列表时出错: {e}")
        raise

# ==================== 辅助函数 ====================
def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def get_individual_filepath(stock_code, stock_name, prefix):
    """
    返回某个前缀的个股文件路径
    prefix: 'Daily' 或 'Weekly'
    这些文件位于 PROJECT ROOT\prompt 目录下
    """
    safe_name = stock_name.replace(' ', '_')
    filename = f"Prompt_{prefix}_{stock_code}_{safe_name}.txt"
    return get_prompt_dir() / filename

def read_file_content(filepath):
    """读取文件内容，若文件不存在返回None"""
    if not filepath.exists():
        logger.warning(f"文件不存在: {filepath}")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取文件失败 {filepath}: {e}")
        return None

def write_file_content(filepath, content):
    """写入内容到文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"已生成: {filepath}")
        return True
    except Exception as e:
        logger.error(f"写入文件失败 {filepath}: {e}")
        return False

def generate_header(stock_code, stock_name):
    """
    生成文件开头的指定文本
    格式：请作为一家国际资产管理公司(QS财富方舟)的AI投资委员会，对以下港股 [stock_code]_[stock_name]进行机构级每日复盘，[TODAY YYYY-MM-DD]。
    """
    today = datetime.now().strftime('%Y-%m-%d')
    header = f"请作为一家国际资产管理公司(QS财富方舟)的AI投资委员会，对以下港股 {stock_code}_{stock_name}进行机构级每日复盘，{today}。\n\n"
    return header

# ==================== 主流程 ====================
def main():
    prompt_dir = get_prompt_dir()
    logger.info(f"Prompt 目录: {prompt_dir}")
    
    review_dir = get_review_prompt_dir()
    logger.info(f"Review 输出目录: {review_dir}")
    
    code_prompt_dir = get_code_prompt_dir()
    logger.info(f"Code Prompt 目录: {code_prompt_dir}")

    # 1. 加载股票列表
    try:
        stock_list = load_stock_list()
    except Exception as e:
        print(f"加载股票列表失败: {e}")
        return

    # 2. 定位模板文件（在 code_prompt 目录下）
    template_path = code_prompt_dir / '个股review_复盘模板超级Prompt.txt'
    if not template_path.exists():
        logger.error(f"模板文件不存在: {template_path}")
        print(f"错误: 模板文件不存在，请将 '个股review_复盘模板超级Prompt.txt' 放在 {code_prompt_dir} 目录下")
        return

    template_content = read_file_content(template_path)
    if template_content is None:
        return

    success_count = 0
    fail_count = 0
    missing_files = []

    for stock in stock_list:
        code = stock["stock_code"]
        name = stock["stock_name"]
        logger.info(f"处理 {name} ({code}) ...")

        # 构建日度和周度文件路径（从 prompt 目录读取）
        daily_path = get_individual_filepath(code, name, "Daily")
        weekly_path = get_individual_filepath(code, name, "Weekly")

        # 检查文件是否存在
        daily_content = read_file_content(daily_path)
        weekly_content = read_file_content(weekly_path)

        if daily_content is None or weekly_content is None:
            missing_files.append(f"{code} ({name}) - 缺少日度或周度文件")
            fail_count += 1
            continue

        # 生成文件头部
        header = generate_header(code, name)
        
        # 合并内容：头部 + 模板 + 分隔线 + 日度数据 + 分隔线 + 周度数据
        merged_content = header
        
        # 模板内容
        merged_content += template_content + "\n\n"
        
        # 日度数据
        merged_content += "=" * 80 + "\n"
        merged_content += "【日度走势数据】\n"
        merged_content += "=" * 80 + "\n\n"
        merged_content += daily_content + "\n\n"

        # 周度数据
        merged_content += "=" * 80 + "\n"
        merged_content += "【周度走势数据】\n"
        merged_content += "=" * 80 + "\n\n"
        merged_content += weekly_content + "\n\n"

        # 添加生成时间
        merged_content += "-" * 80 + "\n"
        merged_content += f"合并生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        # 写入输出文件到 review 目录
        safe_name = name.replace(' ', '_')
        output_path = review_dir / f"Prompt_个股复盘_{code}_{safe_name}.txt"
        if write_file_content(output_path, merged_content):
            success_count += 1
        else:
            fail_count += 1

    # 统计报告
    print(f"\n处理完成: 成功 {success_count} 只，失败 {fail_count} 只")
    if missing_files:
        print("缺失文件的股票:")
        for item in missing_files:
            print(f"  {item}")
    logger.info(f"程序执行完成: 成功 {success_count}, 失败 {fail_count}")

if __name__ == "__main__":
    main()