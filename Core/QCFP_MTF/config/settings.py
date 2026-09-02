# coding: utf-8
"""QCFP-MTF 配置加载

优先级：内置默认值 < Config/qcfp_settings.yaml < stock_data_analysis.par [QCFP_MTF] 节
"""

from pathlib import Path
from typing import Any, Dict

from ..common.config_par import load_qcfp_par_section
from ..common.paths import get_config_dir

try:
    import yaml
    _HAS_YAML = True
except ImportError:  # 无 PyYAML 环境使用内置简化解析器兜底
    yaml = None
    _HAS_YAML = False


DEFAULT_SETTINGS: Dict[str, Any] = {
        "model": {
        "version": "QCFP-MTF-2.5.0",
    },
    # 2.7 Regime-aware 参数（不同市场环境不同阈值/上限）
    "regime_params": {
        "Bull": {"risk_cap": 1.0, "entry": 1.0, "holding": 1.0},
        "Sideway": {"risk_cap": 0.8, "entry": 1.0, "holding": 0.8},
        "Bear": {"risk_cap": 0.5, "entry": 1.0, "holding": 0.6},
        "HighVolatility": {"risk_cap": 0.6, "entry": 1.0, "holding": 0.5},
        "Crisis": {"risk_cap": 0.2, "entry": 1.0, "holding": 0.3},
    },
    "enabled": True,
    "data_quality": {
        "missing_threshold_b": 0.05,   # 核心字段缺失率 <= 5% 视为 A/B 边界
        "missing_threshold_c": 0.20,   # 核心字段缺失率 > 20% 视为 C/D 边界
        "anomaly_checks": ["negative_price", "non_positive_volume", "turnover_out_of_range"],
    },
    "institutional": {
        "disclosure_lag_days": 45,     # 机构持股披露滞后天数（推算 available_date 用）
        "available_date_mode": "estimated",
        "permission": {
            "enabled": True,
            "persistence_min_quarters": 2,
            "downgrade": {
                "divergence": True,
                "low_confidence": True,
                "poor_data_quality": True,
            },
        },
    },
    "cbi_weights": {
        "turnover_stability": 0.30,
        "turnover_pctl_inverse": 0.30,
        "volume_stability": 0.25,
        "amplitude_stability": 0.15,
    },
    "chip_confidence_weights": {
        "quarterly_chip": 0.60,
        "cbi": 0.40,
    },
    "thresholds": {
        "turnover_z": {"t1": -1.5, "t2": -0.5, "t3": 0.5, "t4": 1.5},
        "turnover_pctl": {"t1": 0.10, "t2": 0.30, "t3": 0.70, "t4": 0.90},
        "weekly_volume_breakout": 1.8,
        "weekly_volume_shrink": 0.5,
        "weekly_turnover_spike": 2.0,
        "cbi": {"locked": 70, "stable": 50, "active": 30},
        "quarterly_return_window": 1,
        "trend_score_window": "end_of_quarter",
    },
    "structural": {
        "direction_thresholds": {
            "c_pp_threshold": 0.5,       # holder_pct_qoq_pp（百分点）
            "f_z_threshold": 0.5,
            "p_return_threshold": 2.0,   # %
            "p_flat_return": 1.0,        # %
        },
        "trend_score_weights": {
            "return_pctl": 0.30,
            "ma_alignment": 0.25,
            "macd_state": 0.15,
            "position_52w": 0.20,
            "vwap_deviation": 0.10,
        },
        "divergence": {
            "z_threshold": 1.0,
        },
        "score_mapping": {
            "STRUCTURAL_BULLISH": 85,
            "STRUCTURAL_ACCUMULATION": 70,
            "STRUCTURAL_DIVERGENCE": 55,
            "STRUCTURAL_DISTRIBUTION": 35,
            "STRUCTURAL_DECLINE": 20,
            "STRUCTURAL_BOTTOM_CANDIDATE": 45,
        },
        "fallback": {
            "allow_f_missing_with_cp": True,
        },
    },
    "behavioral": {
        "turnover": {
            "window": 12,
            "min_history": 5,
            "pctl_min_history": 6,
            "z_bands": [-1.5, -0.5, 0.5, 1.5],
            "pctl_bands": [0.10, 0.30, 0.70, 0.90],
        },
        "volume": {
            "ma_window": 6,
            "accel_lag": 3,
            "up_ratio": 1.10,
            "down_ratio": 0.90,
            "strong_ratio": 1.50,
        },
        "price_direction": {
            "up_threshold": 1.5,
            "down_threshold": 1.5,
        },
        "cost_position": {
            "neutral_pct": 2.0,
        },
    },
    "tactical": {
        "volume": {
            "ma_window": 20,
            "breakout_ratio": 1.8,
            "shrink_ratio": 0.5,
        },
        "turnover": {
            "quarter_window": 13,
            "spike_ma_window": 8,
            "spike_ratio": 2.0,
        },
        "ma": {
            "slope_lag": 2,
            "slope_threshold_pct": 0.5,
        },
        "breakout": {
            "lookback": 20,
        },
    },
    "daily": {
        "tactical": {
            "breakout_lookback": 20,
            "breakout_volume_ratio": 1.5,
            "stall_volume_ratio": 1.2,
            "near_high_ratio": 0.98,
            "accum_flow_z": 0.2,
            "flow_z_window": 60,
        },
        "timing": {
            "enabled": False,       # Model B 默认关闭：增量测试未过验收，保持诊断层
            "distribution_reduce": 0.5,
            "breakout_add_ratio": 1.25,
        },
    },
    "fusion": {
        "chip_confidence": {
            "quarterly_chip_weight": 0.60,
            "cbi_weight": 0.40,
            "high_threshold": 70,
            "medium_threshold": 50,
        },
        "anti_inference": {
            "mode": "warn",
        },
        "market_context": {
            "hsi_return_window": 60,
            "vhsi_risk_off": 25,
        },
        "score_mapping": {
            "BULLISH_CONFIRMED": 85,
            "BULLISH_STABLE": 75,
            "BULLISH_WARNING": 55,
            "BEARISH_RECOVERY_CANDIDATE": 40,
            "BEARISH_CONFIRMED": 20,
        },
    },
    "decision": {
        "action_mapping": {
            "BULLISH_CONFIRMED": "BUY",
            "BULLISH_STABLE": "HOLD",
            "BULLISH_WARNING": "REDUCE",
            "BEARISH_RECOVERY_CANDIDATE": "WAIT",
            "BEARISH_CONFIRMED": "EXIT",
            "DATA_INSUFFICIENT": "WAIT",
        },
        "risk": {
            "base": {
                "BULLISH_CONFIRMED": 1,
                "BULLISH_STABLE": 1,
                "BULLISH_WARNING": 2,
                "BEARISH_RECOVERY_CANDIDATE": 3,
                "BEARISH_CONFIRMED": 3,
                "DATA_INSUFFICIENT": 4,
            },
            "add_divergence": 1,
            "add_risk_off": 1,
            "add_dq_c": 1,
            "add_dq_d": 2,
            "add_low_confidence": 1,
        },
        "position_advice": {
            "BULLISH_CONFIRMED": "80%~100%",
            "BULLISH_STABLE": "50%~80%",
            "BULLISH_WARNING": "20%~50%",
            "BEARISH_RECOVERY_CANDIDATE": "0%~20%",
            "BEARISH_CONFIRMED": "0%",
            "DATA_INSUFFICIENT": "0%",
        },
        "base_position": {
            "BULLISH_CONFIRMED": 1.0,
            "BULLISH_STABLE": 0.75,
            "BULLISH_WARNING": 0.5,
            "BEARISH_RECOVERY_CANDIDATE": 0.2,
            "BEARISH_CONFIRMED": 0.0,
            "DATA_INSUFFICIENT": 0.0,
        },
        "position_cap": {
            "Low": 1.0,
            "Medium": 0.8,
            "High": 0.5,
            "Extreme": 0.2,
        },
        "tactical_override": {
            "enabled": True,
            "max_52w_position": 0.15,
            "min_trigger": ["Breakout", "Pullback", "Consolidation"],
        },
        "catalyst_quality": {
            "position_high": 0.35,
            "position_mid": 0.20,
            "position_low": 0.05,
            "time_stop_high": None,
            "time_stop_mid": None,   # 中性偏强改用移动止损（trailing_stop）
            "time_stop_low": 2,
        },
        "trailing_stop": {
            "enabled": True,
        },
        "stop_loss_policy": {
            "type": "entry_week_low",  # 唯一止损来源（P0-3）：entry_week_low / quarterly_vwap
            "buffer_pct": 0.02,
        },
        "downside_risk": {
            "enabled": True,           # 下行风险层（V18）：DES + 风险下限 + 滞后解除 + 单调性
            "breakdown_risk_floor": "Extreme",
            "release_weeks": 2,
            "exit_at_score": 7,
            "weights": {
                "breakdown": 2, "breakdown_streak": 1, "below_ma20": 1,
                "ma5_lt_ma10": 1, "ma20_slope_neg": 1, "flow_neg": 1,
                "flow_neg2": 1, "daily_decline": 2, "cqs_neg": 1,
                "ret5w_neg": 1, "ret13w_neg": 1, "dd52_neg": 1,
            },
        },
        "retail": {
            "position_bands": {
                "Extreme": "0%",
                "High": "0%~20%",
                "Low_recovery": "30%~50%",
                "BULLISH_STABLE": "50%~70%",
                "BULLISH_CONFIRMED": "60%~80%",
                "strong_risk_on": "80%~100%",
                "REDUCE": "20%~40%",
                "Zero": "0%",
            },
            "fsm": {
                "cooldown_weeks": 2,
                "chase_52w": 0.6,     # 突破但 52W 位置>0.6 → 禁止追高（改等回踩）
                "position": {
                    "test": 0.10,
                    "build_step": 0.10,
                    "trim_step": 0.15,
                    "max_position": 0.70,
                },
            },
            # 2.4 Participation Budget（四层架构中间层）：
            # 权限回答"最多承担多少风险"，预算回答"当前允许拿多少钱参与探索"
            "participation_budget": {
                "observe": 0.05,   # WATCH + Setup + 低/中风险 → 观察仓上限
                "test": 0.10,
                "allow": 0.50,
                "strong": 0.70,
                # 2.5：Market Context 真正生效（risk_on 全预算；neutral 0.6；risk_off 0.3）
                "market_scale": {
                    "risk_on": 1.0,
                    "neutral": 0.6,
                    "risk_off": 0.3,
                },
            },
            # 2.4 趋势存活权：确认趋势（HOLDING）持仓在波动中享有更宽存活缓冲
            "trend_survival": {
                "enabled": True,
                "buffer_pct": 0.05,
                "min_state": "HOLDING",
            },
            # 2.5：允许交易 ≠ 值得交易（TQS 低于门槛 → 压仓为 0）
            "trade_quality": {
                "min_tradable": 40,
            },
        },
        "hard_exit": {
            "enabled": True,
            "des_threshold": 7,
        },
        "stop_loss": {
            "BULLISH_WARNING": "周线放量跌破季VWAP×0.95",
            "BEARISH_RECOVERY_CANDIDATE": "跌破建仓成本-5%",
            "BEARISH_CONFIRMED": "空仓观望",
        },
    },
    "backtest": {
        "mode": "research",   # research | production（production 强制 PIT 股票池）
        # 2.5 回测引擎源：canonical=唯一决策引擎（正式结果）；
        # legacy 仅作 Shadow Comparator（--engine legacy 显式选择，非正式来源）
        "engine_source": "canonical",
        "cost": {
            "commission_rate": 0.0025,
            "stamp_rate": 0.001,
            "slippage_rate": 0.001,
        },
        "liquidity": {
            "min_weekly_amount": 0.0,
        },
        "position_target": {
            "BUY": 1.0,
            "ADD": 1.0,
            "HOLD": 1.0,
            "REDUCE": 0.5,
            "EXIT": 0.0,
            "WAIT": 0.0,
        },
        # 2.5 组合层暴露约束（target 层生效，T+1 前）
        "portfolio_constraints": {
            "enabled": False,
            "max_single_stock": 0.30,
            "max_sector": 0.50,
            "max_total_exposure": 1.0,
            # 2.7 组合级治理
            "min_cash": 0.10,
            "total_risk_budget": 0.06,
            "high_corr_cap": 0.30,
        },
        "risk_free": 0.0,
        "annual_periods": 52,
    },
    "output": {
        "report_dir": "Report/QCFP_MTF",
        "audit_subdir": "audit",
    },
}


# ---------------- 内置简化 YAML 解析器（无 PyYAML 时兜底） ----------------

def _parse_scalar(raw: str):
    v = raw.strip()
    if v == "" or v.lower() in ("null", "none", "~"):
        return None
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(x) for x in inner.split(",")]
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    low = v.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _parse_simple_yaml(text: str) -> dict:
    """解析本系统 qcfp_settings.yaml 使用的 YAML 子集：
    支持注释、层级缩进（任意层）、标量、内联列表。
    """
    root: dict = {}
    stack = []  # [(indent, node_dict)]
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if " #" in line:
            line = line[: line.index(" #")].rstrip()
        indent = len(raw) - len(raw.lstrip(" "))
        if line.endswith(":"):
            key = line[:-1].strip()
            node: dict = {}
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1] if stack else root
            parent[key] = node
            stack.append((indent, node))
        elif ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1] if stack else root
            parent[key] = _parse_scalar(val)
    return root


# ---------------- 加载与合并 ----------------

def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_qcfp_settings(settings_file: Path = None) -> Dict[str, Any]:
    """加载 QCFP-MTF 配置（默认值 + YAML + par 节合并）"""
    path = Path(settings_file) if settings_file else get_config_dir() / "qcfp_settings.yaml"
    data: dict = {}
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if _HAS_YAML:
            loaded = yaml.safe_load(text) or {}
        else:
            loaded = _parse_simple_yaml(text)
        data = loaded if isinstance(loaded, dict) else {}

    merged = _deep_merge(DEFAULT_SETTINGS, data)

    # par [QCFP_MTF] 节覆盖（项目主配置优先）
    par = load_qcfp_par_section()
    if par:
        par_map = {
            "model_version": ("model", "version"),
            "enabled": ("enabled",),
            "report_dir": ("output", "report_dir"),
            "settings_file": ("settings_file",),
            "disclosure_lag_days": ("institutional", "disclosure_lag_days"),
        }
        for key, target in par_map.items():
            if key not in par:
                continue
            val = par[key]
            if key == "enabled":
                val = str(val).lower() in ("yes", "true", "on", "1")
            if key == "disclosure_lag_days":
                try:
                    val = int(val)
                except ValueError:
                    continue
            node = merged
            for part in target[:-1]:
                node = node.setdefault(part, {})
            node[target[-1]] = val
    return merged


def get(settings: dict, dotted_key: str, default=None):
    """按 a.b.c 路径取配置值"""
    node = settings
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def retail_settings(settings) -> dict:
    """retail 配置实际位于 decision.retail（兼容历史顶层 retail 读取）"""
    s = settings or {}
    return (s.get("decision", {}).get("retail", {})
            or s.get("retail", {}) or {})
