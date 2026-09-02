# coding: utf-8
"""项目路径解析工具（QCFP-MTF 专用）"""

import os
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录（TA_Workflow）

    优先级：
    1. 环境变量 PROJECT_ROOT
    2. 从本文件位置向上查找（Core/QCFP_MTF/common/paths.py -> 项目根）
    3. 从当前工作目录向上查找
    """
    env_dir = os.environ.get("PROJECT_ROOT")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)

    # 从本文件位置向上查找
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "Config" / "stock_data_analysis.par").exists() \
                and (parent / "SQLiteDB").exists() \
                and (parent / "Core").exists():
            return parent

    # 兜底：从 cwd 向上查找
    cwd = Path.cwd().resolve()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "Config").exists() and (parent / "Core").exists():
            return parent
    return p.parents[3]


def get_db_path() -> Path:
    """数据库完整路径"""
    return get_project_root() / "SQLiteDB" / "HK_Stock.db"


def get_config_dir() -> Path:
    """Config 目录"""
    return get_project_root() / "Config"


def get_qcfp_dir() -> Path:
    """QCFP_MTF 模块根目录"""
    return get_project_root() / "Core" / "QCFP_MTF"


def get_report_root() -> Path:
    """QCFP 输出根目录（Report/QCFP_MTF）"""
    return get_project_root() / "Report" / "QCFP_MTF"


def get_log_dir() -> Path:
    """日志目录（与项目一致，取配置中的 log_dir；默认 Log）"""
    from .config_par import load_par_config
    cfg = load_par_config()
    log_rel = cfg.get("log_dir", "Log")
    return get_project_root() / log_rel
