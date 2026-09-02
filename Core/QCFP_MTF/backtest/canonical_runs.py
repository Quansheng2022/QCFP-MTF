# coding: utf-8
"""Canonical-Only Research Runs（QCFP-MTF 2.8：新 8 号）

正式 OOS / Ablation / Stress 全部必须 canonical-only：
    build_evidence_timeline() → canonical_replay() → run_backtest()

正式 API：
    run_canonical_backtest()
    run_canonical_oos()
    run_canonical_ablation()
    run_canonical_stress()

历史比较（永远 SHADOW_ONLY / NON_CERTIFIABLE）：
    run_legacy_shadow_comparator()

验收标准：任何正式研究产物必须带
    engine=canonical / decision_provenance / feature_manifest_hash /
    strategy_version / data_snapshot_id，否则 RESEARCH_ONLY / INVALID。
"""

import hashlib
import json

import pandas as pd

from ..decision.versions import MODEL_VERSION, feature_manifest_hash
from .canonical import canonical_replay
from .data_pipeline import assert_evidence_no_decision_authority, \
    build_evidence_timeline, build_signal_timeline
from .engine import run_backtest


def _provenance(run_id, data_snapshot_id="") -> dict:
    return {
        "engine": "canonical",
        "decision_provenance": "canonical_replay->evaluate",
        "feature_manifest_hash": feature_manifest_hash(),
        "strategy_version": MODEL_VERSION,
        "data_snapshot_id": data_snapshot_id,
    }


def _evidence_to_canonical(structural, monthly, weekly, chip, idx_df,
                           settings, stocks=None, weekly_kl=None,
                           daily=None, run_id="") -> tuple:
    """正式证据链：evidence-only → canonical_replay → DecisionSnapshot。"""
    signals = build_evidence_timeline(
        structural, monthly, weekly, chip, idx_df, settings,
        stocks=stocks, weekly_kl=weekly_kl, daily=daily)
    assert_evidence_no_decision_authority(signals)
    df, snap_objs = canonical_replay(
        signals, settings, run_id=run_id, daily=daily,
        return_snapshots=True)
    return df, snap_objs


def run_canonical_backtest(structural, monthly, weekly, chip, idx_df,
                           settings, stocks=None, weekly_kl=None,
                           daily=None, start=None, end=None,
                           run_id="canonical_bt", data_snapshot_id="") -> dict:
    """正式回测：evidence → canonical_replay → run_backtest。"""
    df, snap_objs = _evidence_to_canonical(
        structural, monthly, weekly, chip, idx_df, settings,
        stocks=stocks, weekly_kl=weekly_kl, daily=daily, run_id=run_id)
    bt = run_backtest(df, weekly_kl, settings, start=start, end=end)
    return {"backtest": bt, "signals": df, "snapshots": snap_objs,
            "provenance": _provenance(run_id, data_snapshot_id)}


def run_canonical_oos(structural, monthly, weekly, chip, idx_df, settings,
                      train_end, test_start, test_end,
                      stocks=None, weekly_kl=None, daily=None,
                      run_id="canonical_oos", data_snapshot_id="") -> dict:
    """正式 OOS Walk-forward：train 段外样本验证。"""
    df, snap_objs = _evidence_to_canonical(
        structural, monthly, weekly, chip, idx_df, settings,
        stocks=stocks, weekly_kl=weekly_kl, daily=daily, run_id=run_id)
    df_train = df[df["decision_date"] <= train_end] \
        if train_end else df.iloc[0:0]
    df_oos = df[df["decision_date"] >= test_start]
    bt_train = run_backtest(df_train, weekly_kl, settings,
                            start=None, end=train_end)
    bt_oos = run_backtest(df_oos, weekly_kl, settings,
                          start=test_start, end=test_end)
    return {"train_backtest": bt_train, "oos_backtest": bt_oos,
            "snapshots": snap_objs,
            "provenance": _provenance(run_id, data_snapshot_id)}


def run_canonical_ablation(structural, monthly, weekly, chip, idx_df,
                           settings, ablations=None, stocks=None,
                           weekly_kl=None, daily=None,
                           run_id="canonical_ablation",
                           data_snapshot_id="") -> dict:
    """正式 Ablation：每个变体只改一个模块，全部 canonical-only。"""
    ablations = ablations or [{"label": "FULL", "settings": settings}]
    results = {}
    for variant in ablations:
        label = variant["label"]
        s = variant["settings"]
        df, snap_objs = _evidence_to_canonical(
            structural, monthly, weekly, chip, idx_df, s,
            stocks=stocks, weekly_kl=weekly_kl, daily=daily,
            run_id=f"{run_id}_{label}")
        bt = run_backtest(df, weekly_kl, s)
        results[label] = {"backtest": bt, "snapshots": snap_objs}
    return {"variants": results,
            "provenance": _provenance(run_id, data_snapshot_id)}


def run_canonical_stress(structural, monthly, weekly, chip, idx_df,
                         settings, stress_settings=None, stocks=None,
                         weekly_kl=None, daily=None,
                         run_id="canonical_stress",
                         data_snapshot_id="") -> dict:
    """正式 Stress：成本/流动性/缺口等压力情景，全部 canonical-only。"""
    scenarios = stress_settings or [{"label": "BASE", "settings": settings}]
    results = {}
    for scenario in scenarios:
        label = scenario["label"]
        s = scenario["settings"]
        df, snap_objs = _evidence_to_canonical(
            structural, monthly, weekly, chip, idx_df, s,
            stocks=stocks, weekly_kl=weekly_kl, daily=daily,
            run_id=f"{run_id}_{label}")
        bt = run_backtest(df, weekly_kl, s)
        results[label] = {"backtest": bt, "snapshots": snap_objs}
    return {"scenarios": results,
            "provenance": _provenance(run_id, data_snapshot_id)}


def run_legacy_shadow_comparator(structural, monthly, weekly, chip,
                                 idx_df, settings, stocks=None,
                                 weekly_kl=None, daily=None,
                                 run_id="legacy_shadow") -> dict:
    """Legacy Shadow Comparator：永远 SHADOW_ONLY / NON_CERTIFIABLE。"""
    signals = build_signal_timeline(
        structural, monthly, weekly, chip, idx_df, settings,
        stocks=stocks, weekly_kl=weekly_kl, daily=daily)
    assert_evidence_no_decision_authority(signals)
    bt = run_backtest(signals, weekly_kl, settings)
    return {
        "backtest": bt,
        "signals": signals,
        "authority": "SHADOW_ONLY",
        "non_certifiable": True,
        "note": "Legacy 仅供历史对照，非正式结果来源",
        "provenance": {
            "engine": "legacy_comparator",
            "decision_provenance": "build_signal_timeline->run_backtest",
            "certifiable": False,
        },
    }
