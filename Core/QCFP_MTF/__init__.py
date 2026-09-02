# coding: utf-8
"""
QCFP-MTF 2.5.0 —— 季度筹码-资金-价格 三维多时间周期框架 股票分析系统
（版本唯一来源：QCFP_MTF.decision.versions）

Quarter Chip-Flow-Price - Multi-Timeframe

目录结构：
    common/      共享工具（路径/日志/数据库/日历/标准化）
    config/      配置加载
    data/        数据加载、数据质量、证据等级
    structural/  季度结构引擎（P1）
    behavioral/  月线行为引擎（P2）
    tactical/    周线战术引擎（P3）
    fusion/      多周期融合层（P4）
    decision/    DSS 决策层（P5）
    backtest/    回测与校准（P6）
    scripts/     P0 可执行步骤脚本
    tests/       单元测试
"""

__version__ = "2.5.0"
MODEL_VERSION = "QCFP-MTF-2.5.0"
