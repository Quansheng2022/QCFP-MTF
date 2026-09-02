# coding: utf-8
"""日志工具：与项目现有脚本一致的 文件+控制台 双输出"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str,
                 log_dir: Path = None,
                 log_file: str = None,
                 console: bool = True,
                 mode: str = "a",
                 level: int = logging.INFO) -> logging.Logger:
    """创建（或重置）一个 logger

    Args:
        name: logger 名称（也作为默认日志文件名）
        log_dir: 日志目录，None 时自动用 Log/
        log_file: 日志文件名；None 时用 {name}.log
        console: 是否同时输出到控制台
        mode: 'a' 追加 / 'w' 覆盖（项目多数步骤脚本用 'w' 覆盖）
        level: 日志级别
    """
    if log_dir is None:
        from .config_par import load_par_config
        from .paths import get_project_root
        cfg = load_par_config()
        log_rel = cfg.get("FOLDERS.log_dir", "Log")
        log_dir = get_project_root() / log_rel
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_file or f"{name}.log"

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_dir / log_file, mode=mode, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)
    return logger
