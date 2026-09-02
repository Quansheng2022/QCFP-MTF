# coding: utf-8
"""配置加载测试（含无 PyYAML 的简化解析器）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import (_parse_simple_yaml, get,
                                      load_qcfp_settings)


def test_load_defaults():
    s = load_qcfp_settings()
    assert get(s, "model.version") == "QCFP-MTF-2.5.0"
    assert get(s, "cbi_weights.turnover_stability") == 0.30
    assert get(s, "chip_confidence_weights.quarterly_chip") == 0.60


def test_get_default():
    assert get({}, "a.b.c", 42) == 42


def test_simple_yaml_parser():
    text = """
model:
  version: QCFP-MTF-2.5.0
data_quality:
  missing_threshold_b: 0.05
  anomaly_checks: [negative_price, zero_volume]
enabled: true
"""
    data = _parse_simple_yaml(text)
    assert data["model"]["version"] == "QCFP-MTF-2.5.0"
    assert data["data_quality"]["missing_threshold_b"] == 0.05
    assert data["data_quality"]["anomaly_checks"] == ["negative_price", "zero_volume"]
    assert data["enabled"] is True


def test_parser_matches_real_file():
    # 解析真实配置，验证兜底解析器与文件结构一致
    text = (PROJECT_ROOT / "Config" / "qcfp_settings.yaml").read_text(encoding="utf-8")
    data = _parse_simple_yaml(text)
    assert data["model"]["version"] == "QCFP-MTF-2.5.0"
    assert "cbi_weights" in data and "thresholds" in data


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_settings 全部通过 ✅")
