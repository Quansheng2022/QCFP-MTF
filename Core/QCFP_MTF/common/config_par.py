# coding: utf-8
"""stock_data_analysis.par 读取（含 [QCFP_MTF] 节）"""

import configparser
from pathlib import Path

from .paths import get_project_root


def _par_path() -> Path:
    return get_project_root() / "Config" / "stock_data_analysis.par"


def load_par_config() -> dict:
    """读取 stock_data_analysis.par，扁平化返回 dict"""
    path = _par_path()
    cp = configparser.ConfigParser()
    cp.read(str(path), encoding="utf-8")
    out = {}
    for section in cp.sections():
        for key, value in cp.items(section):
            out[f"{section}.{key}"] = value
    return out


def load_qcfp_par_section() -> dict:
    """读取 [QCFP_MTF] 节（不存在时返回空 dict）"""
    path = _par_path()
    cp = configparser.ConfigParser()
    cp.read(str(path), encoding="utf-8")
    if not cp.has_section("QCFP_MTF"):
        return {}
    return {k: v for k, v in cp.items("QCFP_MTF")}
