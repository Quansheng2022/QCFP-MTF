#!/usr/bin/env python
# coding: utf-8

"""
stock_list_loader.py
股票列表加载工具 - 从配置文件加载股票列表

功能:
  1. 从 Config/stock_list.json 加载股票列表
  2. 提供股票列表的各种映射和查询功能
  3. 如果配置文件不存在，创建示例配置文件
  4. 支持保存股票列表到配置文件

路径: TA_Workflow2/Core/Utl/stock_list_loader.py
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime

# =====================================================
# 1. 路径设置
# =====================================================

def get_project_dir() -> Path:
    """
    获取项目根目录 (TA_Workflow2)
    脚本位于 TA_Workflow2/Core/Utl/ 目录下
    """
    try:
        # 尝试从环境变量获取
        env_dir = os.environ.get('PROJECT_ROOT')
        if env_dir and Path(env_dir).exists():
            return Path(env_dir)

        # 从当前脚本路径推断项目根目录
        script_path = Path(__file__).resolve()
        
        # Core/Utl 目录的父目录的父目录就是项目根目录
        # 路径: .../TA_Workflow2/Core/Utl/stock_list_loader.py
        # 项目根目录: .../TA_Workflow2
        project_dir = script_path.parent.parent.parent
        
        # 验证是否真的是项目根目录（检查是否存在 Config 目录）
        if (project_dir / 'Config').exists():
            return project_dir
        
        # 如果找不到 Config，尝试其他方式
        # 检查是否在 Core/Utl 目录中
        if script_path.parent.parent.name == 'Core' and script_path.parent.name == 'Utl':
            return script_path.parent.parent.parent
        
        # 尝试从当前工作目录向上查找
        cwd = Path(os.getcwd()).resolve()
        for parent in [cwd] + list(cwd.parents):
            if (parent / 'Config').exists() and (parent / 'Core').exists():
                return parent
        
        return cwd.parent.parent if cwd.name == 'Utl' else cwd
        
    except Exception as e:
        print(f"[ERROR] 获取项目目录错误: {str(e)}")
        return Path(__file__).resolve().parent.parent.parent

# =====================================================
# 2. 核心功能函数
# =====================================================

def get_sample_stock_list() -> List[Dict[str, str]]:
    """
    获取示例股票列表（仅用于创建示例配置文件）
    
    Returns:
        示例股票列表
    """
    return [
        {'code': '00020', 'name': '商汤科技', 'sector': '信息技术', 'market': 'HKEX'},
        {'code': '00268', 'name': '金蝶国际', 'sector': '信息技术', 'market': 'HKEX'},
        {'code': '00354', 'name': '中软国际', 'sector': '信息技术', 'market': 'HKEX'},
        {'code': '00357', 'name': '美兰空港', 'sector': '交通运输', 'market': 'HKEX'},
        {'code': '00371', 'name': '北控水务', 'sector': '公用事业', 'market': 'HKEX'},
        {'code': '00579', 'name': '京能清洁能源', 'sector': '公用事业', 'market': 'HKEX'},
        {'code': '00788', 'name': '中国铁塔', 'sector': '电信服务', 'market': 'HKEX'},
        {'code': '01093', 'name': '石药集团', 'sector': '医疗保健', 'market': 'HKEX'},
        {'code': '01177', 'name': '中生制药', 'sector': '医疗保健', 'market': 'HKEX'},
        {'code': '01951', 'name': '锦鑫生殖', 'sector': '医疗保健', 'market': 'HKEX'},
        {'code': '02202', 'name': '港股万科企业', 'sector': '房地产', 'market': 'HKEX'},
        {'code': '02602', 'name': '港股万物云', 'sector': '信息技术', 'market': 'HKEX'},
        {'code': '02611', 'name': '国泰海通', 'sector': '金融', 'market': 'HKEX'},
        {'code': '03800', 'name': '协鑫科技', 'sector': '新能源', 'market': 'HKEX'},
        {'code': '06060', 'name': '众安在线', 'sector': '金融', 'market': 'HKEX'},
        {'code': '00700', 'name': '腾讯控股', 'sector': '信息技术', 'market': 'HKEX'},
    ]

def create_sample_config(config_dir: Path) -> bool:
    """
    创建示例配置文件
    
    Args:
        config_dir: 配置目录路径
        
    Returns:
        是否创建成功
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    stock_list_path = config_dir / 'stock_list.json'
    
    # 如果文件已存在，不覆盖
    if stock_list_path.exists():
        print(f"[INFO] 配置文件已存在: {stock_list_path}")
        return True
    
    sample_list = get_sample_stock_list()
    
    data = {
        'stocks': sample_list,
        'metadata': {
            'version': '1.0',
            'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'description': '港股股票列表，用于数据导入和验证',
            'total_stocks': len(sample_list),
            'note': '请根据实际需要修改此文件'
        }
    }
    
    try:
        with open(stock_list_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 已创建示例配置文件: {stock_list_path}")
        print(f"[INFO] 共包含 {len(sample_list)} 只示例股票")
        print(f"[INFO] 请根据实际需要修改此文件")
        return True
    except Exception as e:
        print(f"[ERROR] 创建示例配置文件失败: {e}")
        return False

def load_stock_list(config_dir: Optional[Path] = None) -> List[Dict[str, str]]:
    """
    从配置文件加载股票列表
    
    Args:
        config_dir: 配置目录路径，如果为None则自动查找
        
    Returns:
        股票列表，每个元素包含 code, name, sector, market 字段
        
    Raises:
        FileNotFoundError: 如果配置文件不存在且无法创建
        ValueError: 如果配置文件格式不正确
        
    Examples:
        >>> stocks = load_stock_list()
        >>> print(f"加载了 {len(stocks)} 只股票")
    """
    if config_dir is None:
        project_dir = get_project_dir()
        config_dir = project_dir / 'Config'
    
    stock_list_path = config_dir / 'stock_list.json'
    
    # 如果配置文件不存在，创建示例文件
    if not stock_list_path.exists():
        print(f"[WARN] 股票列表文件不存在: {stock_list_path}")
        print("[INFO] 正在创建示例配置文件...")
        if not create_sample_config(config_dir):
            raise FileNotFoundError(f"无法创建配置文件: {stock_list_path}")
        # 重新加载
        return load_stock_list(config_dir)
    
    try:
        with open(stock_list_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 支持两种格式：直接数组或包含stocks键的对象
        if isinstance(data, list):
            stocks = data
        elif isinstance(data, dict) and 'stocks' in data:
            stocks = data['stocks']
        else:
            raise ValueError(f"股票列表文件格式不正确: {stock_list_path}")
        
        if not stocks:
            raise ValueError(f"股票列表为空: {stock_list_path}")
        
        # 验证每个股票记录的必填字段
        required_fields = ['code', 'name']
        valid_stocks = []
        invalid_count = 0
        
        for stock in stocks:
            if all(field in stock for field in required_fields):
                # 确保有 sector 和 market 字段（如果没有，设置默认值）
                if 'sector' not in stock:
                    stock['sector'] = 'N/A'
                if 'market' not in stock:
                    stock['market'] = 'HKEX'
                valid_stocks.append(stock)
            else:
                invalid_count += 1
                print(f"[WARN] 跳过无效的股票记录: {stock}")
        
        if invalid_count > 0:
            print(f"[WARN] 跳过了 {invalid_count} 条无效记录")
        
        if not valid_stocks:
            raise ValueError("没有有效的股票记录")
        
        print(f"[INFO] 成功加载 {len(valid_stocks)} 只股票")
        return valid_stocks
        
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败: {e}")
    except Exception as e:
        raise ValueError(f"加载股票列表失败: {e}")

def save_stock_list(stock_list: List[Dict[str, str]], config_dir: Optional[Path] = None) -> bool:
    """
    保存股票列表到配置文件
    
    Args:
        stock_list: 股票列表
        config_dir: 配置目录路径
        
    Returns:
        是否保存成功
        
    Examples:
        >>> stocks = load_stock_list()
        >>> # 修改 stocks...
        >>> save_stock_list(stocks)
    """
    if config_dir is None:
        project_dir = get_project_dir()
        config_dir = project_dir / 'Config'
    
    config_dir.mkdir(parents=True, exist_ok=True)
    stock_list_path = config_dir / 'stock_list.json'
    
    # 构建数据对象
    data = {
        'stocks': stock_list,
        'metadata': {
            'version': '1.0',
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'description': '港股股票列表，用于数据导入和验证',
            'total_stocks': len(stock_list)
        }
    }
    
    try:
        with open(stock_list_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 股票列表已保存: {stock_list_path}")
        print(f"[INFO] 共保存 {len(stock_list)} 只股票")
        return True
    except Exception as e:
        print(f"[ERROR] 保存股票列表失败: {e}")
        return False

def get_stock_map(stock_list: Optional[List[Dict[str, str]]] = None) -> Dict[str, Dict[str, str]]:
    """
    将股票列表转换为以代码为键的字典
    
    Args:
        stock_list: 股票列表，如果为None则自动加载
        
    Returns:
        代码到股票信息的映射字典
        
    Examples:
        >>> stock_map = get_stock_map()
        >>> print(stock_map['01951']['name'])
        锦鑫生殖
    """
    if stock_list is None:
        stock_list = load_stock_list()
    
    return {item['code']: item for item in stock_list}

def get_stock_name_map(stock_list: Optional[List[Dict[str, str]]] = None) -> Dict[str, str]:
    """
    获取股票代码到名称的映射
    
    Args:
        stock_list: 股票列表，如果为None则自动加载
        
    Returns:
        代码到名称的映射字典
        
    Examples:
        >>> name_map = get_stock_name_map()
        >>> print(name_map['01951'])
        锦鑫生殖
    """
    if stock_list is None:
        stock_list = load_stock_list()
    
    return {item['code']: item['name'] for item in stock_list}

def get_stock_by_code(code: str, stock_list: Optional[List[Dict[str, str]]] = None) -> Optional[Dict[str, str]]:
    """
    根据股票代码获取股票信息
    
    Args:
        code: 股票代码
        stock_list: 股票列表，如果为None则自动加载
        
    Returns:
        股票信息字典，如果不存在则返回None
        
    Examples:
        >>> stock = get_stock_by_code('01951')
        >>> print(stock['name'])
        锦鑫生殖
    """
    if stock_list is None:
        stock_list = load_stock_list()
    
    stock_map = get_stock_map(stock_list)
    return stock_map.get(code)

def get_stocks_by_sector(sector: str, stock_list: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
    """
    根据行业获取股票列表
    
    Args:
        sector: 行业名称
        stock_list: 股票列表，如果为None则自动加载
        
    Returns:
        指定行业的股票列表
        
    Examples:
        >>> tech_stocks = get_stocks_by_sector('信息技术')
        >>> print(f"信息技术行业有 {len(tech_stocks)} 只股票")
    """
    if stock_list is None:
        stock_list = load_stock_list()
    
    return [stock for stock in stock_list if stock.get('sector') == sector]

def get_all_sectors(stock_list: Optional[List[Dict[str, str]]] = None) -> List[str]:
    """
    获取所有行业列表
    
    Args:
        stock_list: 股票列表，如果为None则自动加载
        
    Returns:
        行业列表（去重并排序）
        
    Examples:
        >>> sectors = get_all_sectors()
        >>> print(sectors)
        ['公用事业', '医疗保健', '新能源', ...]
    """
    if stock_list is None:
        stock_list = load_stock_list()
    
    sectors = set()
    for stock in stock_list:
        sector = stock.get('sector', 'N/A')
        if sector != 'N/A':
            sectors.add(sector)
    
    return sorted(sectors)

def get_stock_codes(stock_list: Optional[List[Dict[str, str]]] = None) -> List[str]:
    """
    获取所有股票代码列表
    
    Args:
        stock_list: 股票列表，如果为None则自动加载
        
    Returns:
        股票代码列表（排序）
        
    Examples:
        >>> codes = get_stock_codes()
        >>> print(codes[:5])
        ['00020', '00268', '00354', '00357', '00371']
    """
    if stock_list is None:
        stock_list = load_stock_list()
    
    return sorted([stock['code'] for stock in stock_list])

def validate_stock_list(stock_list: List[Dict[str, str]]) -> Tuple[bool, List[str]]:
    """
    验证股票列表的有效性
    
    Args:
        stock_list: 股票列表
        
    Returns:
        (是否有效, 错误信息列表)
        
    Examples:
        >>> stocks = load_stock_list()
        >>> valid, errors = validate_stock_list(stocks)
        >>> if valid:
        ...     print("股票列表有效")
        ... else:
        ...     print("错误:", errors)
    """
    errors = []
    required_fields = ['code', 'name']
    
    # 检查每个股票记录
    for i, stock in enumerate(stock_list):
        # 检查必填字段
        for field in required_fields:
            if field not in stock or not stock[field]:
                errors.append(f"记录 {i+1}: 缺少必填字段 '{field}'")
        
        # 检查代码格式（5位数字）
        if 'code' in stock and stock['code']:
            code = stock['code']
            if not code.isdigit() or len(code) != 5:
                errors.append(f"记录 {i+1}: 代码 '{code}' 格式不正确（应为5位数字）")
    
    # 检查重复代码
    codes = [stock.get('code') for stock in stock_list if stock.get('code')]
    if len(codes) != len(set(codes)):
        duplicate_codes = [code for code in set(codes) if codes.count(code) > 1]
        errors.append(f"发现重复的股票代码: {duplicate_codes}")
    
    return len(errors) == 0, errors

def print_stock_list_summary(stock_list: Optional[List[Dict[str, str]]] = None):
    """
    打印股票列表摘要信息
    
    Args:
        stock_list: 股票列表，如果为None则自动加载
        
    Examples:
        >>> print_stock_list_summary()
    """
    if stock_list is None:
        stock_list = load_stock_list()
    
    print("\n" + "=" * 60)
    print("股票列表摘要")
    print("=" * 60)
    print(f"总股票数: {len(stock_list)}")
    
    # 按行业统计
    sectors = {}
    for stock in stock_list:
        sector = stock.get('sector', 'N/A')
        sectors[sector] = sectors.get(sector, 0) + 1
    
    print("\n按行业统计:")
    for sector, count in sorted(sectors.items()):
        print(f"  {sector}: {count} 只")
    
    # 按市场统计
    markets = {}
    for stock in stock_list:
        market = stock.get('market', 'N/A')
        markets[market] = markets.get(market, 0) + 1
    
    print("\n按市场统计:")
    for market, count in sorted(markets.items()):
        print(f"  {market}: {count} 只")
    
    # 前10只股票
    print("\n前10只股票:")
    for i, stock in enumerate(stock_list[:10], 1):
        print(f"  {i:2d}. {stock['code']} - {stock['name']} ({stock.get('sector', 'N/A')})")
    
    if len(stock_list) > 10:
        print(f"  ... 还有 {len(stock_list) - 10} 只股票")
    
    print("=" * 60)

# =====================================================
# 3. 主函数（测试用）
# =====================================================

def main():
    """测试函数"""
    print("=" * 60)
    print("股票列表加载工具 - 测试")
    print("=" * 60)
    
    try:
        # 1. 加载股票列表
        print("\n1. 加载股票列表...")
        stock_list = load_stock_list()
        print(f"   加载了 {len(stock_list)} 只股票")
        
        # 2. 验证股票列表
        print("\n2. 验证股票列表...")
        valid, errors = validate_stock_list(stock_list)
        if valid:
            print("   ✅ 股票列表有效")
        else:
            print("   ❌ 发现错误:")
            for error in errors:
                print(f"      - {error}")
        
        # 3. 测试各种映射
        print("\n3. 测试映射功能...")
        name_map = get_stock_name_map(stock_list)
        print(f"   股票名称映射: {len(name_map)} 条")
        
        stock_map = get_stock_map(stock_list)
        print(f"   股票信息映射: {len(stock_map)} 条")
        
        # 4. 测试查询功能
        print("\n4. 测试查询功能...")
        test_code = '01951'
        stock = get_stock_by_code(test_code, stock_list)
        if stock:
            print(f"   查询 {test_code}: {stock['name']} ({stock.get('sector', 'N/A')})")
        
        # 5. 获取所有行业
        print("\n5. 获取所有行业...")
        sectors = get_all_sectors(stock_list)
        print(f"   行业列表: {sectors}")
        
        # 6. 获取行业股票
        if sectors:
            test_sector = sectors[0]
            sector_stocks = get_stocks_by_sector(test_sector, stock_list)
            print(f"\n6. 查询行业 '{test_sector}' 的股票...")
            print(f"   {len(sector_stocks)} 只股票:")
            for stock in sector_stocks[:5]:
                print(f"      - {stock['code']} {stock['name']}")
            if len(sector_stocks) > 5:
                print(f"      ... 还有 {len(sector_stocks) - 5} 只")
        
        # 7. 打印摘要
        print_stock_list_summary(stock_list)
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()