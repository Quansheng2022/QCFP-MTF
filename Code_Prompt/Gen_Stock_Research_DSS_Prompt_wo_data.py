#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =======================================================================
# Gen_Stock_Research_DSS_Prompt.py -- 个股研究与投资决策支持系统报告提示词。
# 功能：从机构与牛散视角研究个股，并提供辅助投资决策的报告。
# 依赖：无。可直接提问。
# 输入：PROJECT ROOT\code_prompt\个股_research_DSS_超级Prompt_V7.md, 
# 输出：PROJECT ROOT\prompt\research_DSS\Prompt_Research_DSS_[stock_code]_[stock_name].md
# =======================================================================

import os
from datetime import datetime
from pathlib import Path
import logging
import json
import re

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
    prompt_dir = root / 'prompt' / 'research_DSS'
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return prompt_dir

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

def create_yaml_front_matter(stock_code, stock_name):
    """
    创建YAML front matter
    """
    today = datetime.now().strftime('%Y-%m-%d')
    return f"""请采用以下牛散实战分析框架，生成 {stock_code}_{stock_name} 研究与投资决策报告"""

def extract_prompt_content(content):
    """
    提取模板中的核心提示词内容（去掉可能的YAML front matter）
    """
    if not content:
        return content
    
    # 如果内容以 --- 开头，移除YAML front matter
    if content.strip().startswith('---'):
        # 查找第二个 ---
        parts = content.split('---', 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content

def replace_stock_placeholders(content, stock_code, stock_name):
    """
    替换模板中的股票代码和名称占位符
    支持 [stock_code] 和 [stock_name] 两种占位符格式
    """
    content = content.replace('[stock_code]', stock_code)
    content = content.replace('[stock_name]', stock_name)
    content = content.replace('{stock_code}', stock_code)
    content = content.replace('{stock_name}', stock_name)
    return content

# ==================== 主流程 ====================
def main():
    prompt_dir = get_prompt_dir()
    logger.info(f"Prompt 输出目录: {prompt_dir}")

    # 1. 加载股票列表
    try:
        stock_list = load_stock_list()
    except Exception as e:
        print(f"加载股票列表失败: {e}")
        return

    # 2. 定位模板文件（从 code_prompt 目录读取）
    template_path = get_project_root() / 'code_prompt' / '个股_research_DSS_超级Prompt_V7.md'
    if not template_path.exists():
        logger.error(f"模板文件不存在: {template_path}")
        print(f"错误: 模板文件不存在，请将 '个股_research_DSS_超级Prompt_V7.md' 放在 code_prompt 目录下")
        return

    template_content = read_file_content(template_path)
    if template_content is None:
        return

    # 提取模板核心内容（去除可能的YAML front matter）
    template_prompt = extract_prompt_content(template_content)

    success_count = 0
    fail_count = 0

    for stock in stock_list:
        code = stock["stock_code"]
        name = stock["stock_name"]
        logger.info(f"处理 {name} ({code}) ...")

        try:
            # 替换模板中的股票占位符
            prompt_content = replace_stock_placeholders(template_prompt, code, name)

            # 创建YAML front matter
            yaml_header = create_yaml_front_matter(code, name)

            # 构建完整内容：YAML + 模板提示词
            merged_content = yaml_header + "\n"
            merged_content += prompt_content + "\n\n"

            # 添加生成时间
            merged_content += "-" * 80 + "\n"
            merged_content += f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

            # 写入输出文件（.md格式）
            safe_name = name.replace(' ', '_')
            output_path = prompt_dir / f"Prompt_Research_DSS_{code}_{safe_name}.md"
            if write_file_content(output_path, merged_content):
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logger.error(f"处理 {code} ({name}) 时出错: {e}")
            fail_count += 1

    # 统计报告
    print(f"\n处理完成: 成功 {success_count} 只，失败 {fail_count} 只")
    logger.info(f"程序执行完成: 成功 {success_count}, 失败 {fail_count}")

if __name__ == "__main__":
    main()