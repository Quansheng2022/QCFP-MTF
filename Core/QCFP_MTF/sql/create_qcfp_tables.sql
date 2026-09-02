-- create_qcfp_tables.sql
-- QCFP-MTF 2.1.1 核心表（5 张结果表 + 1 张审计快照表）
-- 说明：日期统一 YYYY-MM-DD；stock_code 统一 5 位数字字符串；
--      model_version 保证历史结果可复现；data_quality 为 A/B/C/D。

-- 1. 季度结构表（FSM-1 输出）
CREATE TABLE IF NOT EXISTS qcfp_quarterly_structural (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    period_end TEXT NOT NULL,
    available_date TEXT,
    inst_ownership_pct_chg REAL,
    holder_quantity_chg_pct REAL,
    inst_participation_chg REAL,
    q_inst_flow_raw REAL,
    q_inst_flow_z REAL,
    q_ifa_zscore REAL,
    q_return REAL,
    q_trend_score REAL,
    q_position_52w REAL,
    c_state TEXT,
    f_state TEXT,
    p_state TEXT,
    structural_regime TEXT,
    core_score REAL,
    resolve_method TEXT,
    source_period TEXT,
    model_version TEXT,
    data_quality TEXT,
    update_time TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_qs_code_period
    ON qcfp_quarterly_structural(stock_code, period_end);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_qs_code_period_version
    ON qcfp_quarterly_structural(stock_code, period_end, model_version);
CREATE INDEX IF NOT EXISTS idx_qcfp_qs_available ON qcfp_quarterly_structural(available_date);
CREATE INDEX IF NOT EXISTS idx_qcfp_qs_version ON qcfp_quarterly_structural(model_version);

-- 2. 月线行为表（P2 输出）
CREATE TABLE IF NOT EXISTS qcfp_monthly_behavior (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    month_end TEXT NOT NULL,
    m_turnover_zscore REAL,
    m_turnover_pctl REAL,
    m_turnover_ma_ratio REAL,
    m_volume_ma_ratio REAL,
    m_volume_accel REAL,
    m_vwap_deviation REAL,
    m_turnover_efficiency REAL,
    m_vp_regime TEXT,
    turnover_liquidity_regime TEXT,
    monthly_behavior_state TEXT,
    cbi_score REAL,
    cbi_state TEXT,
    cost_position TEXT,
    cost_vs_weekly_vwap REAL,
    cost_vs_monthly_vwap REAL,
    cost_vs_quarterly_vwap REAL,
    model_version TEXT,
    data_quality TEXT,
    update_time TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_mb_code_month
    ON qcfp_monthly_behavior(stock_code, month_end);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_mb_code_month_version
    ON qcfp_monthly_behavior(stock_code, month_end, model_version);
CREATE INDEX IF NOT EXISTS idx_qcfp_mb_version ON qcfp_monthly_behavior(model_version);

-- 3. 周线战术表（P3 输出）
CREATE TABLE IF NOT EXISTS qcfp_weekly_tactical (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    week_end TEXT NOT NULL,
    w_turnover_deviation REAL,
    w_turnover_spike INTEGER DEFAULT 0,
    w_volume_breakout INTEGER DEFAULT 0,
    w_volume_shrink INTEGER DEFAULT 0,
    w_vwap_deviation REAL,
    w_ma_slope TEXT,
    w_breakout INTEGER DEFAULT 0,
    w_breakdown INTEGER DEFAULT 0,
    tactical_signal TEXT,
    model_version TEXT,
    data_quality TEXT,
    update_time TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_wt_code_week
    ON qcfp_weekly_tactical(stock_code, week_end);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_wt_code_week_version
    ON qcfp_weekly_tactical(stock_code, week_end, model_version);
CREATE INDEX IF NOT EXISTS idx_qcfp_wt_version ON qcfp_weekly_tactical(model_version);

-- 4. 多周期决策表（P4/P5 输出）
CREATE TABLE IF NOT EXISTS qcfp_mtf_decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    decision_date TEXT NOT NULL,
    structural_regime TEXT,
    monthly_behavior_state TEXT,
    tactical_signal TEXT,
    cbi_score REAL,
    cost_position TEXT,
    chip_stability_confidence TEXT,
    mtf_regime TEXT,
    qcfp_score REAL,
    structure_behavior_alignment TEXT,
    action_signal TEXT,
    risk_level TEXT,
    market_context TEXT,
    evidence_summary TEXT,
    align_method TEXT,
    alignment_override INTEGER DEFAULT 0,
    base_action TEXT,
    final_action TEXT,
    base_target REAL,
    final_target REAL,
    risk_override_active INTEGER DEFAULT 0,
    catalyst_score REAL,
    catalyst_type TEXT,
    des_score INTEGER,
    des_band TEXT,
    model_version TEXT,
    data_quality TEXT,
    update_time TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_mtf_code_date
    ON qcfp_mtf_decision(stock_code, decision_date);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_mtf_code_date_version
    ON qcfp_mtf_decision(stock_code, decision_date, model_version);
CREATE INDEX IF NOT EXISTS idx_qcfp_mtf_version ON qcfp_mtf_decision(model_version);

-- 5. 回测结果表（P6 输出）
CREATE TABLE IF NOT EXISTS qcfp_backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    signal_date TEXT,
    action_signal TEXT,
    position REAL,
    pnl REAL,
    mtf_regime TEXT,
    market_regime TEXT,
    model_version TEXT,
    run_id TEXT,
    update_time TEXT
);
CREATE INDEX IF NOT EXISTS idx_qcfp_bt_code_date
    ON qcfp_backtest_results(stock_code, signal_date);
CREATE INDEX IF NOT EXISTS idx_qcfp_bt_run ON qcfp_backtest_results(run_id);

-- 6. 数据质量审计快照表（P0 输出，保留每次审计历史）
CREATE TABLE IF NOT EXISTS qcfp_data_quality_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    data_type TEXT NOT NULL,
    grade TEXT NOT NULL,
    rows INTEGER DEFAULT 0,
    first_date TEXT,
    last_date TEXT,
    core_missing_rate REAL,
    anomalies INTEGER DEFAULT 0,
    reasons TEXT,
    model_version TEXT,
    audit_date TEXT,
    update_time TEXT
);
CREATE INDEX IF NOT EXISTS idx_qcfp_dq_code ON qcfp_data_quality_audit(stock_code);
CREATE INDEX IF NOT EXISTS idx_qcfp_dq_audit_date ON qcfp_data_quality_audit(audit_date);

-- 7. 日线战术层表（L4 · Tactical Timing，V14 新增）
-- 定位：Q/M/W 决定战略方向，Daily 只负责交易时机；F+P 为主、C 不使用。
CREATE TABLE IF NOT EXISTS qcfp_daily_tactical (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    trade_date TEXT NOT NULL,
    daily_state TEXT,
    d_breakout INTEGER DEFAULT 0,
    d_distribution INTEGER DEFAULT 0,
    d_pullback INTEGER DEFAULT 0,
    d_accumulation INTEGER DEFAULT 0,
    d_decline INTEGER DEFAULT 0,
    d_trend_score REAL,
    d_vol_ratio REAL,
    d_near_high REAL,
    d_inst_flow REAL,
    d_flow_z REAL,
    d_flow_slope REAL,
    model_version TEXT,
    data_quality TEXT,
    update_time TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_dt_code_date
    ON qcfp_daily_tactical(stock_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_qcfp_dt_version ON qcfp_daily_tactical(model_version);

-- 8. 决策台账表（2.3 Decision Governance：唯一决策事实源）
-- 任何报告/审计只允许读取 Ledger；禁止报告自行重算决策。
CREATE TABLE IF NOT EXISTS qcfp_decision_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    stock_code TEXT NOT NULL,
    decision_date TEXT NOT NULL,
    input_fingerprint TEXT,
    data_snapshot_id TEXT,
    data_version TEXT,
    settings_hash TEXT,
    model_version TEXT,
    rule_version TEXT,
    schema_version TEXT,
    institutional_state TEXT,
    institutional_pressure INTEGER,
    institutional_persistence INTEGER,
    institutional_permission TEXT,
    permission_cap TEXT,
    institutional_reasons TEXT,
    setup_type TEXT,
    daily_trigger TEXT,
    exit_event TEXT,
    exit_reason TEXT,
    previous_fsm_state TEXT,
    next_fsm_state TEXT,
    base_fsm_state TEXT,
    previous_position REAL,
    raw_target REAL,
    final_target REAL,
    permission_constraint_applied INTEGER DEFAULT 0,
    override_rule_ids TEXT,
    decision_path TEXT,
    primary_reason TEXT,
    secondary_reasons TEXT,
    participation_mode TEXT,
    participation_cap REAL,
    position_class TEXT,
    exit_severity INTEGER DEFAULT 0,
    feature_manifest_hash TEXT,
    trade_quality REAL,
    trade_quality_band TEXT,
    pit_grade TEXT,
    data_quality TEXT,
    evidence_grade TEXT,
    context TEXT,
    status TEXT DEFAULT 'ACTIVE',
    superseded_by TEXT,
    created_at TEXT
);
-- 2.3：七元审计身份（含 input_fingerprint + schema_version）
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_dl_identity
    ON qcfp_decision_ledger(decision_id, run_id, input_fingerprint,
                            data_snapshot_id, data_version, settings_hash,
                            model_version, rule_version, schema_version);
CREATE INDEX IF NOT EXISTS idx_qcfp_dl_code_date
    ON qcfp_decision_ledger(stock_code, decision_date);
CREATE INDEX IF NOT EXISTS idx_qcfp_dl_settings
    ON qcfp_decision_ledger(settings_hash);

-- 9. 模型注册表（2.5 Model Registry：settings_hash → 完整配置可复现）
CREATE TABLE IF NOT EXISTS qcfp_model_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_version TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    feature_manifest_hash TEXT,
    settings_hash TEXT NOT NULL,
    settings_blob TEXT,
    code_commit TEXT,
    python_version TEXT,
    dependency_hash TEXT,
    created_at TEXT,
    status TEXT DEFAULT 'ACTIVE'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_mr_identity
    ON qcfp_model_registry(settings_hash, model_version, rule_version,
                           schema_version);

-- 10. 策略生命周期表（2.7：Development→…→Production→Retired）
CREATE TABLE IF NOT EXISTS qcfp_strategy_lifecycle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    data_version TEXT,
    feature_version TEXT,
    rule_version TEXT,
    parameter_version TEXT,
    approval_status TEXT DEFAULT 'development',
    effective_date TEXT,
    retirement_date TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_qcfp_sl_version
    ON qcfp_strategy_lifecycle(version);

-- 11. 运行时事件台账（Runtime Evidence Wiring：第 8 项）
-- 唯一真实运行事件事实源；event_seq 作为链顺序，Hash 覆盖全部事实字段。
CREATE TABLE IF NOT EXISTS qcfp_runtime_event_ledger (
    event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE,
    event_type TEXT, event_time TEXT,
    decision_id TEXT, release_id TEXT, certificate_id TEXT,
    execution_mode TEXT, account_id TEXT, stock_code TEXT,
    order_intent_id TEXT, broker_order_id TEXT,
    side TEXT, requested_qty REAL, filled_qty REAL, fill_price REAL,
    commission REAL, stamp_duty REAL, exchange_fee REAL, other_fee REAL,
    internal_position REAL, broker_position REAL,
    reconciliation_status TEXT, incident_id TEXT,
    payload TEXT, payload_hash TEXT,
    previous_event_hash TEXT, current_event_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_qcfp_rel_event_seq
    ON qcfp_runtime_event_ledger(event_seq);
CREATE INDEX IF NOT EXISTS idx_qcfp_rel_decision
    ON qcfp_runtime_event_ledger(decision_id);

-- 12. 决策证书表（Runtime Evidence Wiring：第 2 项 identity cross-bind）
CREATE TABLE IF NOT EXISTS qcfp_decision_certificate (
    certificate_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL,
    release_id TEXT,
    snapshot_hash TEXT,
    evidence_pack_hash TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_qcfp_cert_decision
    ON qcfp_decision_certificate(decision_id);

-- 13. 研究 Outcome 表（Runtime Evidence Wiring：第 4 项）
-- Outcome 与 Decision 物理分离：future_aware=1 / research_only=1，
-- 只允许异步追加，绝不允许 UPDATE Decision Row。
CREATE TABLE IF NOT EXISTS qcfp_research_outcome (
    outcome_id TEXT PRIMARY KEY,
    decision_id TEXT, release_id TEXT, stock_code TEXT, decision_date TEXT,
    evaluation_time TEXT, horizon TEXT, horizon_end TEXT,
    entry_reference_price REAL, exit_reference_price REAL,
    future_return REAL, mfe REAL, mae REAL, mfe_date TEXT, mae_date TEXT,
    wave_peak_return REAL, wave_capture REAL, outcome_type TEXT,
    missed_opportunity INTEGER, false_participation INTEGER,
    future_aware INTEGER, research_only INTEGER,
    source_data_snapshot_id TEXT, outcome_hash TEXT, created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_qcfp_oc_decision
    ON qcfp_research_outcome(decision_id);
CREATE INDEX IF NOT EXISTS idx_qcfp_oc_horizon
    ON qcfp_research_outcome(horizon_end);

-- 14. Shadow 全 Universe 终态事实表（Runtime Evidence Wiring：Closure 4）
-- ABSTAIN / SAFE_MODE / HALTED 也必须是 Ledger Fact（不允许只存在于
-- Coverage JSON）；CERTIFIED / NO_TRADE 走 qcfp_decision_ledger。
CREATE TABLE IF NOT EXISTS qcfp_shadow_decision_fact (
    fact_id TEXT PRIMARY KEY,
    stock_code TEXT NOT NULL,
    decision_date TEXT NOT NULL,
    terminal_state TEXT NOT NULL,
    reason TEXT,
    run_id TEXT,
    release_id TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_qcfp_sf_code_date
    ON qcfp_shadow_decision_fact(stock_code, decision_date);
CREATE INDEX IF NOT EXISTS idx_qcfp_sf_state
    ON qcfp_shadow_decision_fact(terminal_state);

-- 15. 每日 Runtime Evidence 投影表（P0-2：Rolling Evidence Store）
-- 只存 Evidence projection，不成为任何决策 Authority；
-- 唯一键 (release_id, execution_mode, trade_date)，同一天重跑 revision+1。
CREATE TABLE IF NOT EXISTS qcfp_runtime_evidence_daily (
    evidence_id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    run_id TEXT,
    revision_no INTEGER NOT NULL DEFAULT 1,
    supersedes_evidence_id TEXT,
    universe_count INTEGER,
    actual_decisions INTEGER,
    coverage REAL,
    certified_count INTEGER,
    no_trade_count INTEGER,
    abstain_count INTEGER,
    safe_mode_count INTEGER,
    halted_count INTEGER,
    permission_violations INTEGER,
    pit_violations INTEGER,
    uncertified_executions INTEGER,
    replay_eligible INTEGER,
    replay_exact INTEGER,
    critical_replay_mismatch INTEGER,
    incident_count INTEGER,
    unresolved_unknown INTEGER,
    unresolved_mismatch INTEGER,
    evidence_hash TEXT,
    verdict TEXT,
    evidence_freeze_id TEXT,
    feature_manifest_hash TEXT,
    config_hash TEXT,
    universe_hash TEXT,
    decision_duplicate_count INTEGER,
    outcome_count INTEGER,
    outcome_coverage REAL,
    outcome_maturity_5d INTEGER,
    outcome_maturity_20d INTEGER,
    outcome_maturity_60d INTEGER,
    decision_flip_rate REAL,
    daily_evidence_state TEXT,
    qualification_eligible INTEGER,
    invalidated INTEGER DEFAULT 0,
    invalidation_reason TEXT,
    created_at TEXT,
    UNIQUE (release_id, execution_mode, trade_date, revision_no)
);
CREATE INDEX IF NOT EXISTS idx_qcfp_red_release_date
    ON qcfp_runtime_evidence_daily(release_id, execution_mode, trade_date);
