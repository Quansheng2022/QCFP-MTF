# Code_utl/Import_HK_Stock_Info_Simple.py
"""
简化版的港股股票信息导入脚本
直接运行即可导入数据
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from Code_utl.Import_HK_Stock_Info import HKStockInfoImporter


def main():
    """主函数"""
    print("开始导入港股股票信息...")
    
    # 创建导入器
    importer = HKStockInfoImporter()
    
    # 执行导入
    success = importer.run()
    
    if success:
        print("\n✓ 港股股票信息导入完成！")
    else:
        print("\n✗ 港股股票信息导入失败！")


if __name__ == "__main__":
    main()
	