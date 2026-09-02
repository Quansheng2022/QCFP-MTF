#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TA_Workflow 多时间框架分析测试程序
按顺序执行 P1-P8 引擎，包括决策报告、回测可视化报告、L4 日线战术层与 2.2 决策链审计
"""

import os
import sys
import subprocess
import time
import argparse
from pathlib import Path
from datetime import datetime

class TAWorkflowTester:
    """TA工作流测试器"""
    
    def __init__(self, project_root):
        """
        初始化测试器
        
        Args:
            project_root: 项目根目录路径
        """
        self.project_root = Path(project_root)
        self.results = []
        self.start_time = None
        
    def print_header(self, title):
        """打印标题"""
        print("\n" + "="*80)
        print(f"  {title}")
        print("="*80)
        
    def print_section(self, section_name):
        """打印章节标题"""
        print(f"\n{'─'*80}")
        print(f"  {section_name}")
        print(f"{'─'*80}")
        
    def run_command(self, cmd, description, timeout=300):
        """
        运行单个命令
        
        Args:
            cmd: 命令列表
            description: 命令描述
            timeout: 超时时间（秒）
        
        Returns:
            bool: 是否成功
        """
        self.print_section(description)
        print(f"执行命令: {' '.join(cmd)}")
        print(f"工作目录: {self.project_root}")
        print("-" * 80)
        
        start_time = time.time()
        
        try:
            # 运行命令
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=timeout
            )
            
            elapsed_time = time.time() - start_time
            
            # 打印输出
            if result.stdout:
                print("标准输出:")
                print(result.stdout)
            
            if result.stderr:
                print("标准错误:")
                print(result.stderr)
            
            # 判断执行结果
            success = result.returncode == 0
            
            # 记录结果
            self.results.append({
                'description': description,
                'command': ' '.join(cmd),
                'success': success,
                'returncode': result.returncode,
                'elapsed_time': elapsed_time,
                'stdout': result.stdout,
                'stderr': result.stderr
            })
            
            if success:
                print(f"\n✅ 执行成功 (耗时: {elapsed_time:.2f}秒)")
            else:
                print(f"\n❌ 执行失败 (返回码: {result.returncode}, 耗时: {elapsed_time:.2f}秒)")
            
            return success
            
        except subprocess.TimeoutExpired:
            print(f"\n⏱️  执行超时 (超过{timeout}秒)")
            self.results.append({
                'description': description,
                'command': ' '.join(cmd),
                'success': False,
                'returncode': -1,
                'elapsed_time': time.time() - start_time,
                'stdout': '',
                'stderr': 'Timeout'
            })
            return False
            
        except Exception as e:
            print(f"\n❌ 执行异常: {str(e)}")
            self.results.append({
                'description': description,
                'command': ' '.join(cmd),
                'success': False,
                'returncode': -1,
                'elapsed_time': time.time() - start_time,
                'stdout': '',
                'stderr': str(e)
            })
            return False
    
    def run_all_engines(self, stock_code, skip_backtest=False, skip_reports=False):
        """
        运行所有引擎
        
        Args:
            stock_code: 股票代码
            skip_backtest: 是否跳过回测
            skip_reports: 是否跳过报告生成
        """
        self.start_time = time.time()
        
        # 定义引擎配置
        engines = [
            {
                'name': 'P1 季线结构行情分析引擎',
                'script': 'Core\\QCFP_MTF\\scripts\\structural_engine.py',
                'description': '季线结构行情分析',
                'timeout': 300
            },
            {
                'name': 'P2 月线市场行为分析引擎',
                'script': 'Core\\QCFP_MTF\\scripts\\monthly_behavior_engine.py',
                'description': '月线市场行为分析',
                'timeout': 300
            },
            {
                'name': 'P3 周线战术分析引擎',
                'script': 'Core\\QCFP_MTF\\scripts\\weekly_tactical_engine.py',
                'description': '周线战术分析',
                'timeout': 300
            },
            {
                'name': 'P3.5 日线战术引擎（L4）',
                'script': 'Core\\QCFP_MTF\\scripts\\daily_tactical_engine.py',
                'description': '日线战术状态（DAILY_*，供 DSS 日线层与散户 FSM 使用）',
                'timeout': 300
            },
            {
                'name': 'P4 融合引擎',
                'script': 'Core\\QCFP_MTF\\scripts\\mtf_fusion_engine.py',
                'description': '多时间框架融合',
                'timeout': 300
            },
            {
                'name': 'P5a 决策引擎',
                'script': 'Core\\QCFP_MTF\\scripts\\decision_engine.py',
                'description': '决策分析',
                'timeout': 300
            }
        ]
        
        # 添加MD格式决策报告（如果不跳过报告）
        if not skip_reports:
            engines.append({
                'name': 'P5b MD格式决策报告',
                'script': 'Core\\QCFP_MTF\\scripts\\dss_report.py',
                'description': '生成Markdown格式决策报告',
                'timeout': 120
            })
        
        # 添加回测引擎（如果不跳过回测）
        if not skip_backtest:
            engines.append({
                'name': 'P6a 回测引擎',
                'script': 'Core\\QCFP_MTF\\scripts\\backtest_runner.py',
                'description': '回测验证',
                'timeout': 600,
                'extra_args': ['--dry-run']
            })
        
        # 添加回测可视化报告（如果不跳过报告）
        if not skip_backtest and not skip_reports:
            engines.append({
                'name': 'P6b 回测可视化报告',
                'script': 'Core\\QCFP_MTF\\scripts\\html_report.py',
                'description': '生成HTML回测报告（净值曲线/分年度/市场分层）',
                'timeout': 180
            })

        # 添加 All-in-One 一体化报告（如果不跳过报告）
        if not skip_reports:
            engines.append({
                'name': 'P7 All-in-One 一体化报告',
                'script': 'Core\\QCFP_MTF\\scripts\\all_in_one_report.py',
                'description': '生成MD+HTML一体化分析报告（含状态快照/决策/回测汇总）',
                'timeout': 180
            })
        # 添加 2.2 决策链审计（Stateful Shadow，仅计算不写库；不跳过报告时运行）
        if not skip_reports:
            engines.append({
                'name': 'P8 2.2 决策链审计（Stateful Shadow）',
                'script': 'Core\\QCFP_MTF\\scripts\\shadow_mode.py',
                'description': '全历史滚动重放：Institutional→Setup→FSM→Sizing→Target（审计链）',
                'timeout': 300
            })
        
        # 打印开始信息
        self.print_header(f"TA_Workflow 多时间框架分析测试")
        print(f"股票代码: {stock_code}")
        print(f"项目根目录: {self.project_root}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"引擎数量: {len(engines)}")
        print(f"跳过回测: {skip_backtest}")
        print(f"跳过报告: {skip_reports}")
        
        # 依次运行每个引擎
        total_engines = len(engines)
        successful_engines = 0
        
        for idx, engine in enumerate(engines, 1):
            print(f"\n{'#'*80}")
            print(f"  引擎 {idx}/{total_engines}: {engine['name']}")
            print(f"{'#'*80}")
            
            # 构建命令
            cmd = ['python.exe', engine['script'], '--stock', stock_code]
            
            # 添加额外参数
            if 'extra_args' in engine:
                cmd.extend(engine['extra_args'])
            
            # 运行命令
            success = self.run_command(
                cmd, 
                engine['description'], 
                timeout=engine.get('timeout', 300)
            )
            
            if success:
                successful_engines += 1
            
            # 如果某个引擎失败，询问是否继续
            if not success and idx < total_engines:
                print("\n⚠️  引擎执行失败，是否继续执行下一个引擎?")
                response = input("继续? (y/n): ").strip().lower()
                if response != 'y':
                    print("用户中断执行")
                    break
        
        # 打印总结报告
        self.print_summary(stock_code, total_engines, successful_engines)
    
    def run_single_engine(self, stock_code, engine_id, skip_backtest=False, skip_reports=False):
        """
        运行单个引擎
        
        Args:
            stock_code: 股票代码
            engine_id: 引擎标识 (P1-P6)
            skip_backtest: 是否跳过回测
            skip_reports: 是否跳过报告
        """
        # 定义引擎映射
        engine_map = {
            'P1': {
                'script': 'Core\\QCFP_MTF\\scripts\\structural_engine.py',
                'desc': '季线结构行情分析',
                'timeout': 300
            },
            'P2': {
                'script': 'Core\\QCFP_MTF\\scripts\\monthly_behavior_engine.py',
                'desc': '月线市场行为分析',
                'timeout': 300
            },
            'P3': {
                'script': 'Core\\QCFP_MTF\\scripts\\weekly_tactical_engine.py',
                'desc': '周线战术分析',
                'timeout': 300
            },
            'P3.5': {
                'script': 'Core\\QCFP_MTF\\scripts\\daily_tactical_engine.py',
                'desc': '日线战术引擎（L4）',
                'timeout': 300
            },
            'P4': {
                'script': 'Core\\QCFP_MTF\\scripts\\mtf_fusion_engine.py',
                'desc': '融合分析',
                'timeout': 300
            },
            'P5': {
                'script': 'Core\\QCFP_MTF\\scripts\\decision_engine.py',
                'desc': '决策分析',
                'timeout': 300
            },
            'P5R': {
                'script': 'Core\\QCFP_MTF\\scripts\\dss_report.py',
                'desc': 'MD格式决策报告',
                'timeout': 120
            },
            'P6': {
                'script': 'Core\\QCFP_MTF\\scripts\\backtest_runner.py',
                'desc': '回测验证',
                'timeout': 600,
                'extra_args': ['--dry-run']
            },
            'P6R': {
                'script': 'Core\\QCFP_MTF\\scripts\\html_report.py',
                'desc': 'HTML回测可视化报告',
                'timeout': 180
            },
            'P7': {
                'script': 'Core\\QCFP_MTF\\scripts\\all_in_one_report.py',
                'desc': 'All-in-One 一体化报告（MD+HTML）',
                'timeout': 180
            },
            'P8': {
                'script': 'Core\\QCFP_MTF\\scripts\\shadow_mode.py',
                'desc': '2.2 决策链审计（Stateful Shadow）',
                'timeout': 300
            }
        }
        
        engine_id_upper = engine_id.upper()
        
        if engine_id_upper not in engine_map:
            print(f"❌ 无效的引擎标识: {engine_id}")
            print(f"可用的引擎: P1, P2, P3, P3.5, P4, P5, P5R, P6, P6R, P7, P8")
            return False
        
        # 检查是否因跳过选项而跳过
        if engine_id_upper in ['P6', 'P6R'] and skip_backtest:
            print(f"⚠️  回测已被跳过，不执行 {engine_id}")
            return True
        
        if engine_id_upper in ['P5R', 'P6R', 'P7', 'P8'] and skip_reports:
            print(f"⚠️  报告已被跳过，不执行 {engine_id}")
            return True
        
        engine = engine_map[engine_id_upper]
        
        self.print_header(f"运行单个引擎: {engine_id}")
        
        # 构建命令
        cmd = ['python.exe', engine['script'], '--stock', stock_code]
        
        # 添加额外参数
        if 'extra_args' in engine:
            cmd.extend(engine['extra_args'])
        
        # 运行命令
        success = self.run_command(
            cmd, 
            engine['desc'], 
            timeout=engine.get('timeout', 300)
        )
        
        return success
    
    def print_summary(self, stock_code, total_engines, successful_engines):
        """打印执行总结"""
        elapsed_time = time.time() - self.start_time
        
        self.print_header("执行总结报告")
        print(f"股票代码: {stock_code}")
        print(f"总引擎数: {total_engines}")
        print(f"成功引擎: {successful_engines}")
        print(f"失败引擎: {total_engines - successful_engines}")
        print(f"总耗时: {elapsed_time:.2f}秒")
        print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\n详细结果:")
        print("-" * 80)
        for idx, result in enumerate(self.results, 1):
            status = "✅ 成功" if result['success'] else "❌ 失败"
            print(f"{idx}. {result['description']}: {status}")
            print(f"   命令: {result['command']}")
            print(f"   耗时: {result['elapsed_time']:.2f}秒")
            if not result['success'] and result['stderr']:
                # 截取错误信息的前200个字符
                error_msg = result['stderr'][:200]
                if len(result['stderr']) > 200:
                    error_msg += "..."
                print(f"   错误: {error_msg}")
            print()
        
        print("=" * 80)
        if successful_engines == total_engines:
            print("🎉 所有引擎执行成功!")
        else:
            print(f"⚠️  部分引擎执行失败 ({total_engines - successful_engines}/{total_engines})")
        print("=" * 80)
        
        # 保存结果到文件
        self.save_results(stock_code)
    
    def save_results(self, stock_code):
        """保存执行结果到文件"""
        log_dir = self.project_root / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'test_run_{stock_code}_{timestamp}.txt'
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"TA_Workflow 测试执行报告\n")
                f.write(f"{'='*80}\n")
                f.write(f"股票代码: {stock_code}\n")
                f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*80}\n\n")
                
                for idx, result in enumerate(self.results, 1):
                    f.write(f"引擎 {idx}: {result['description']}\n")
                    f.write(f"  命令: {result['command']}\n")
                    f.write(f"  状态: {'成功' if result['success'] else '失败'}\n")
                    f.write(f"  耗时: {result['elapsed_time']:.2f}秒\n")
                    if result['stdout']:
                        f.write(f"  输出:\n{result['stdout']}\n")
                    if result['stderr']:
                        f.write(f"  错误:\n{result['stderr']}\n")
                    f.write(f"{'-'*80}\n")
            
            print(f"\n📝 执行结果已保存到: {log_file}")
            
        except Exception as e:
            print(f"\n⚠️  保存结果文件失败: {str(e)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='TA_Workflow 多时间框架测试程序',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行所有引擎（含报告）
  python test_workflow.py --stock 01093
  
  # 运行所有引擎，跳过回测和报告
  python test_workflow.py --stock 01093 --skip-backtest --skip-reports
  
  # 只运行决策引擎
  python test_workflow.py --stock 01093 --single P5
  
  # 只运行 L4 日线战术引擎
  python test_workflow.py --stock 01093 --single P3.5
  
  # 只运行 2.2 决策链审计
  python test_workflow.py --stock 01093 --single P8
  
  # 只生成决策报告
  python test_workflow.py --stock 01093 --single P5R
  
  # 只运行回测（含可视化报告）
  python test_workflow.py --stock 01093 --single P6
  
  # 只生成回测可视化报告
  python test_workflow.py --stock 01093 --single P6R
  
  # 自定义项目路径
  python test_workflow.py --stock 01093 --project-root "C:\\MyProject"
        """
    )
    
    parser.add_argument(
        '--stock',
        required=True,
        help='股票代码 (例如: 01093)'
    )
    parser.add_argument(
        '--project-root',
        default='C:\\Users\\Quansheng\\Documents\\projects\\TA_Workflow',
        help='项目根目录路径'
    )
    parser.add_argument(
        '--skip-backtest',
        action='store_true',
        help='跳过回测引擎 (P6a) 和回测报告 (P6b)'
    )
    parser.add_argument(
        '--skip-reports',
        action='store_true',
        help='跳过所有报告生成 (P5b MD报告, P6b HTML报告)'
    )
    parser.add_argument(
        '--single',
        choices=['P1', 'P2', 'P3', 'P3.5', 'P4', 'P5', 'P5R', 'P6', 'P6R', 'P7', 'P8'],
        help='只运行指定的引擎 (P1-P4, P3.5=日线L4, P5=决策, P5R=决策报告, P6=回测, P6R=回测报告, P7=一体化, P8=2.2审计)'
    )
    parser.add_argument(
        '--no-interactive',
        action='store_true',
        help='非交互模式，出错时自动继续执行'
    )
    
    args = parser.parse_args()
    
    # 创建测试器实例
    tester = TAWorkflowTester(args.project_root)
    
    # 检查项目根目录是否存在
    if not tester.project_root.exists():
        print(f"❌ 项目根目录不存在: {tester.project_root}")
        sys.exit(1)
    
    # 如果指定了单个引擎
    if args.single:
        success = tester.run_single_engine(
            args.stock, 
            args.single, 
            args.skip_backtest,
            args.skip_reports
        )
        sys.exit(0 if success else 1)
    else:
        # 运行所有引擎
        tester.run_all_engines(
            args.stock, 
            args.skip_backtest,
            args.skip_reports
        )
        
        # 统计成功/失败
        if tester.results:
            total = len(tester.results)
            success = sum(1 for r in tester.results if r['success'])
            sys.exit(0 if success == total else 1)

if __name__ == "__main__":
    main()
