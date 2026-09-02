#!/usr/bin/env python
# coding: utf-8

"""
Name: Quarterly_TA4E_Analyze_chip_report.py
Function:
生成季度筹码结构分析报告（Markdown）。

报告定位：“机构参与度 + 筹码集中/扩散 + 持仓迁移 + 价格验证”的季度结构报告，
不回答“哪家机构在买/卖、机构成本、机构真实盈亏”等问题（当前无机构持股明细）。

筹码周期判断方法（状态机）：
- 9 阶段：01分散 → 02筑底 → 03吸筹 → 04集中 → 05蓄势 → 06主升 → 07派发 → 08扩散 → 09退潮
- 三维评分：Chip Score / Flow Score / Price Score（0-100）
- 判定流程：单季度规则 → Candidate Regime → 连续确认（≥2季度）→ Confirmed Regime
- 同时输出：持续时间、上一状态、状态转换、转换评分、置信度

数据来源：
- hk_quarterly_institutional_holdings_analysis（筹码因子，TA4C 产出）
- hk_quarterly_chip_analysis（Chip × Flow × Price 联合，TA4D 产出）
- hk_quarterly_kline_analysis（价格/量能/均线，TA2B 产出）
- hk_quarterly_moneyflow_analysis（资金流 5 季均线，TA4B 产出）

输出：Report/{ticker}_quarterly_chip_report.md
"""

# ==================== 标准库导入 ====================
import os
import sys
import io
import re
import argparse
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
import traceback

# ==================== 第三方库导入 ====================
import numpy as np
import pandas as pd


def setup_logging(log_dir: Path) -> logging.Logger:
    """设置日志记录器（覆盖模式）"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'Quarterly_TA4E_Analyze_chip_report.log'

    logger = logging.getLogger('Quarterly_TA4E_Analyze_chip_report')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def check_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """检查表是否存在"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


# ==================== 格式化辅助 ====================
def fmt_int(v):
    if v is None or pd.isna(v):
        return 'N/A'
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return 'N/A'


def fmt_pct(v, digits=2):
    if v is None or pd.isna(v):
        return 'N/A'
    try:
        return f"{float(v):+.{digits}f}%"
    except (TypeError, ValueError):
        return 'N/A'


def fmt_pp(v, digits=2):
    if v is None or pd.isna(v):
        return 'N/A'
    try:
        return f"{float(v):+.{digits}f}pp"
    except (TypeError, ValueError):
        return 'N/A'


def fmt_num(v, digits=2):
    if v is None or pd.isna(v):
        return 'N/A'
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return 'N/A'


def fmt_score(v):
    if v is None or pd.isna(v):
        return 'N/A'
    try:
        return f"{float(v):.0f}"
    except (TypeError, ValueError):
        return 'N/A'


def _clip(value, lo=0.0, hi=100.0):
    if value is None or pd.isna(value):
        return None
    return float(min(hi, max(lo, value)))


def normalize_quarter(q):
    m = re.match(r'^\s*(\d{4})\s*/?\s*-?\s*[Qq]([1-4])\s*$', str(q).strip()) if q else None
    if not m:
        return None
    return f"{int(m.group(1))}/Q{int(m.group(2))}"


def migration_band(score):
    if score is None or pd.isna(score):
        return 'N/A'
    s = float(score) * 100.0
    if s >= 80:
        return '强集中'
    if s >= 40:
        return '集中'
    if s > -40:
        return '中性'
    if s > -80:
        return '扩散'
    return '强扩散'


def trend_text(t):
    if t is None or pd.isna(t):
        return 'N/A'
    t = int(t)
    return {2: '强烈上升', 1: '上升', 0: '稳定', -1: '下降', -2: '强烈下降'}.get(t, 'N/A')


def direction_text(d):
    if d is None or pd.isna(d):
        return 'N/A'
    d = int(d)
    return {1: '偏多/上行', -1: '偏空/下行', 0: '中性/震荡'}.get(d, 'N/A')


# ==================== 筹码周期状态机 ====================
# 阶段 -> (编号, 大周期)
STAGE_INFO = {
    '分散': ('01', '底部周期'),
    '筑底': ('02', '底部周期'),
    '吸筹': ('03', '吸筹周期'),
    '集中': ('04', '吸筹周期'),
    '蓄势': ('05', '上涨前夜'),
    '主升': ('06', '上涨周期'),
    '派发': ('07', '顶部周期'),
    '扩散': ('08', '顶部周期'),
    '退潮': ('09', '下跌周期'),
    '中性观察': ('--', '观察期'),
}

STAGE_NUM = {k: v[0] for k, v in STAGE_INFO.items()}

# 状态转换含义（顺向为主，逆向为辅）
TRANSITION_MEANING = {
    '01→02': '下跌趋缓，结构开始稳定',
    '02→03': '潜在吸筹启动',
    '03→04': '筹码改善得到确认',
    '04→05': '进入蓄势',
    '05→06': '突破进入主升',
    '06→07': '顶部风险预警',
    '07→08': '派发得到确认',
    '08→09': '进入退潮',
    '09→01': '进入新一轮分散/筑底',
    '02→01': '筑底失败，重新分散',
    '03→02': '吸筹未延续，回落筑底',
    '04→03': '集中未确认，回退吸筹',
    '05→04': '蓄势未突破，回退集中',
    '06→05': '主升受阻，回退蓄势',
    '07→06': '派发后重新走强',
    '08→07': '扩散缓解，回到派发观察',
    '09→08': '退潮减缓，筹码松动收窄',
}


def flow_score(fbi, inst_5ma, ind_5ma):
    """资金流评分（0-100）：FBI 主导 + 5 季均线结构"""
    s = 50.0
    if fbi is not None and pd.notna(fbi):
        s += 40.0 * np.tanh(float(fbi) / 0.3)
    if (inst_5ma is not None and pd.notna(inst_5ma)
            and ind_5ma is not None and pd.notna(ind_5ma)):
        if float(inst_5ma) > float(ind_5ma):
            s += 10.0
        elif float(inst_5ma) < float(ind_5ma):
            s -= 10.0
    return _clip(s)


def price_score(chg, macd_dif, rsi, ema5, ema20, ema50):
    """价格评分（0-100）：季度收益 + MACD + RSI + 均线排列"""
    s = 50.0
    if chg is not None and pd.notna(chg):
        s += 50.0 * np.tanh(float(chg) / 12.0)
    if macd_dif is not None and pd.notna(macd_dif):
        s += 12.0 if float(macd_dif) > 0 else -12.0
    if rsi is not None and pd.notna(rsi):
        s += (float(rsi) - 50.0) * 0.3
    if (ema5 is not None and pd.notna(ema5)
            and ema20 is not None and pd.notna(ema20)
            and ema50 is not None and pd.notna(ema50)):
        if ema5 > ema20 > ema50:
            s += 8.0
        elif ema5 < ema20 < ema50:
            s -= 8.0
    return _clip(s)


def enter_conditions(stage, chip_s, flow_s, price_s, r):
    """
    每个阶段的进入条件（文档 §21）。
    返回 (是否满足, 条件说明)。
    """
    pct_t = int(r.get('holder_pct_trend') or 0) if r.get('holder_pct_trend') is not None else 0
    if stage == '吸筹':
        ok = chip_s is not None and chip_s > 55 and flow_s is not None and flow_s > 50 \
            and price_s is not None and price_s < 55
        return ok, 'Chip>55、Flow>50、Price<55（结构改善领先价格）'
    if stage == '蓄势':
        ok = chip_s is not None and chip_s > 70 and flow_s is not None and flow_s > 60 \
            and price_s is not None and 40 <= price_s <= 60
        return ok, 'Chip>70、Flow>60、Price 40~60（筹码好、价格未启动）'
    if stage == '主升':
        ok = price_s is not None and price_s > 70 and flow_s is not None and flow_s > 65 \
            and chip_s is not None and chip_s > 60
        return ok, 'Price>70、Flow>65、Chip>60（三维正反馈）'
    if stage == '集中':
        ok = chip_s is not None and chip_s >= 60 and pct_t >= 0
        return ok, 'Chip≥60 且持股比例趋势非负（筹码改善已形成趋势）'
    if stage == '派发':
        ok = chip_s is not None and chip_s < 50
        return ok, 'Chip<50（筹码方向转弱，价格仍强）'
    if stage in ('扩散', '分散', '退潮'):
        ok = chip_s is not None and chip_s < 55
        return ok, 'Chip<55（筹码结构走弱）'
    if stage == '筑底':
        ok = price_s is not None and price_s < 55 and flow_s is not None and flow_s >= 45
        return ok, 'Price<55 且 Flow≥45（下跌趋缓、资金未恶化）'
    return True, '中性观察，无强制进入条件'


def candidate_stage(chip_s, flow_s, price_s, fl_known, r):
    """
    基于三维评分（Chip/Flow/Price）判定 Candidate Regime（文档 §21/§23）。
    资金流缺失（fl_known=False）时不阻止依赖资金条件的正向结构判定。
    返回 (候选阶段, 是否满足进入条件, 条件说明)。
    """
    if chip_s is None or pd.isna(chip_s):
        chip_s = 50.0
    if flow_s is None or pd.isna(flow_s):
        flow_s = 50.0
    if price_s is None or pd.isna(price_s):
        price_s = 50.0
    chip_s, flow_s, price_s = float(chip_s), float(flow_s), float(price_s)

    # 优先级：退潮 > 主升 > 派发 > 扩散 > 分散 > 蓄势 > 集中 > 吸筹 > 筑底
    if chip_s < 45 and price_s < 45 and (not fl_known or flow_s < 50):
        cand = '退潮'
    elif price_s >= 70 and chip_s >= 60 and (not fl_known or flow_s >= 65):
        cand = '主升'
    elif chip_s < 50 and price_s >= 55:
        cand = '派发'
    elif chip_s < 50 and price_s < 55 and (not fl_known or flow_s < 50):
        cand = '扩散'
    elif chip_s < 45 and price_s < 50:
        cand = '分散'
    elif chip_s >= 70 and price_s < 60 and (not fl_known or flow_s >= 60):
        cand = '蓄势'
    elif chip_s >= 60 and price_s < 70 and (not fl_known or flow_s >= 50):
        cand = '集中'
    elif chip_s >= 55 and price_s < 55 and (not fl_known or flow_s >= 50):
        cand = '吸筹'
    elif 45 <= chip_s < 60 and price_s < 55 and (not fl_known or flow_s >= 45):
        cand = '筑底'
    else:
        cand = '中性观察'
    ok, detail = enter_conditions(cand, chip_s, flow_s, price_s, r)
    return cand, ok, detail


def run_regime_state_machine(df):
    """
    对单只股票的历史序列运行状态机：
    Candidate（单季度）→ 连续 2 季度确认 → Confirmed Regime。
    输出：_candidate / confirmed_regime / regime_duration / previous_regime /
          regime_transition / regime_transition_score / regime_confidence
    """
    df = df.copy()
    candidates, confirmed, durations = [], [], []
    previous, transitions, trans_scores, confidences = [], [], [], []

    prev_candidate = None
    prev_confirmed = None
    prev_dur = 0

    for i, (_, r) in enumerate(df.iterrows()):
        cand = r.get('_candidate') or '中性观察'
        if i == 0:
            conf = cand
            dur = 1
        elif cand == '中性观察':
            # 中性观察不作为确认状态：保持上一确认阶段，等待明确信号
            conf = prev_confirmed if prev_confirmed else cand
            dur = prev_dur + 1 if conf == prev_confirmed else 1
        elif cand == prev_candidate:
            # 连续 2 季度同一候选 → 确认为新状态
            conf = cand
            dur = prev_dur + 1 if conf == prev_confirmed else 1
        elif bool(r.get('_enter_ok')) and (r.get('_base_confidence') or 0) >= 70.0:
            # 强证据单季度确认：进入条件满足且阶段特异性置信度很高（避免单季度噪音）
            conf = cand
            dur = prev_dur + 1 if conf == prev_confirmed else 1
        else:
            # 单季度变化 → 保持原确认状态（滞后确认，降低噪声）
            conf = prev_confirmed if prev_confirmed else cand
            dur = prev_dur + 1 if conf == prev_confirmed else 1

        prev_regime = prev_confirmed
        transition = None
        trans_score = None
        if prev_confirmed is not None and conf != prev_confirmed:
            transition = f"{STAGE_NUM.get(prev_confirmed, '--')}→{STAGE_NUM.get(conf, '--')}"
            trans_score = r.get('_base_confidence')

        base_conf = r.get('_base_confidence') or 50.0
        persist_bonus = 10.0 if cand == prev_candidate else 0.0
        dur_bonus = min(10.0, max(0.0, (dur - 1)) * 3.0)
        conf_val = _clip(base_conf + persist_bonus + dur_bonus)

        candidates.append(cand)
        confirmed.append(conf)
        durations.append(dur)
        previous.append(prev_regime)
        transitions.append(transition)
        trans_scores.append(trans_score)
        confidences.append(conf_val)

        prev_candidate = cand
        prev_confirmed = conf
        prev_dur = dur

    df['_candidate'] = candidates
    df['confirmed_regime'] = confirmed
    df['regime_duration'] = durations
    df['previous_regime'] = previous
    df['regime_transition'] = transitions
    df['regime_transition_score'] = trans_scores
    df['regime_confidence'] = confidences
    return df


def build_radar(chip_s, flow_s, price_s):
    """筹码周期雷达（ASCII）"""
    def bar(v):
        if v is None or pd.isna(v):
            return ''
        return '█' * int(round(float(v) / 10.0))
    return (f"筹码 {fmt_score(chip_s):>3}  {bar(chip_s)}\n"
            f"资金 {fmt_score(flow_s):>3}  {bar(flow_s)}\n"
            f"价格 {fmt_score(price_s):>3}  {bar(price_s)}")


def stage_specific_confidence(cand, chip_s, flow_s, price_s):
    """
    阶段特异性置信度（0-100）：
    - 正向阶段（蓄势/集中/吸筹/筑底/主升）：评分越高置信度越高；
    - 负向阶段（退潮/扩散/分散/派发）：反向评分越高置信度越高。
    """
    c = float(chip_s) if chip_s is not None and pd.notna(chip_s) else 50.0
    f = float(flow_s) if flow_s is not None and pd.notna(flow_s) else 50.0
    p = float(price_s) if price_s is not None and pd.notna(price_s) else 50.0
    if cand in ('退潮', '扩散', '分散', '派发'):
        return _clip(0.35 * (100.0 - c) + 0.35 * (100.0 - f) + 0.30 * (100.0 - p))
    return _clip(0.35 * c + 0.35 * f + 0.30 * p)


def stage_evidence(r):
    """当前季度判定证据摘要"""
    items = []
    items.append(f"机构数量趋势 {trend_text(r.get('institution_trend'))}"
                 f"（QoQ {fmt_pct(r.get('institution_quantity_qoq_pct'))}）")
    items.append(f"持股数量趋势 {trend_text(r.get('holder_trend'))}"
                 f"（QoQ {fmt_pct(r.get('holder_quantity_qoq_pct'))}）")
    items.append(f"持股比例趋势 {trend_text(r.get('holder_pct_trend'))}"
                 f"（QoQ {fmt_pp(r.get('holder_pct_qoq_pp'))}）")
    fbi = r.get('fbi')
    if fbi is not None and pd.notna(fbi):
        bias = '机构净流入' if float(fbi) > 0.1 else ('机构净流出' if float(fbi) < -0.1 else '均衡')
        items.append(f"FBI {float(fbi):+.2f}（{bias}）")
    chg = r.get('change_percent')
    if chg is not None and pd.notna(chg):
        items.append(f"季度涨跌 {float(chg):+.1f}%")
    return '；'.join(items)


def cp_relation(chip_d, price_d):
    """筹码—价格关系判定"""
    if chip_d == 1 and price_d == 1:
        return '正向确认', '筹码改善与价格上涨同步，结构得到价格验证'
    if chip_d == 1 and price_d == 0:
        return '吸筹/蓄势候选', '筹码改善但价格尚未启动，可能是吸筹/蓄势阶段'
    if chip_d == 1 and price_d == -1:
        return '逆势集中', '筹码改善但价格下跌，需验证是底部吸筹还是被动集中'
    if chip_d == -1 and price_d == 1:
        return '上涨背离', '筹码恶化但价格上涨，上涨缺乏筹码结构支撑（风险信号）'
    if chip_d == -1 and price_d == 0:
        return '筹码走弱观察', '筹码恶化而价格横盘，警惕后续补跌'
    if chip_d == 0 and price_d == 1:
        return '价格独立走强', '价格走强但筹码未见改善，独立性存疑'
    if chip_d == 0 and price_d == -1:
        return '价格独立走弱', '价格走弱但筹码未见恶化，观察资金面'
    return '中性', '筹码与价格均无明显方向'


def price_new_high_flag(kline_closes, cur_close):
    if cur_close is None or pd.isna(cur_close) or len(kline_closes) < 2:
        return False
    prior = [c for c in kline_closes[:-1] if c is not None and pd.notna(c)]
    if not prior:
        return False
    return float(cur_close) >= max(prior)


def compute_forward_returns(kline_df, chip_df):
    """计算每个筹码季度对应的未来 Q+1/Q+2/Q+4 收益（基于季线收盘价）"""
    rows = []
    if kline_df.empty or chip_df.empty:
        return pd.DataFrame(rows)
    kline = kline_df.sort_values('date')
    for stock_code, g in chip_df.groupby('stock_code'):
        k = kline[kline['stock_code'] == stock_code]
        if k.empty:
            continue
        dates = k['date'].tolist()
        closes = pd.to_numeric(k['close'], errors='coerce').tolist()
        date_to_idx = {d: i for i, d in enumerate(dates)}
        for _, r in g.iterrows():
            qed = r['quarter_end_date']
            if qed not in date_to_idx:
                continue
            i = date_to_idx[qed]
            base = closes[i]
            if base is None or pd.isna(base) or base == 0:
                continue
            fwd = {}
            for horizon, offset in [('fwd_1q', 1), ('fwd_2q', 2), ('fwd_4q', 4)]:
                j = i + offset
                if j < len(closes) and closes[j] is not None and pd.notna(closes[j]):
                    fwd[horizon] = (closes[j] - base) / base * 100.0
                else:
                    fwd[horizon] = None
            rows.append({
                'stock_code': stock_code,
                'quarter': r['quarter'],
                'quarter_end_date': qed,
                'chip_structure_score': r.get('chip_structure_score'),
                **fwd,
            })
    return pd.DataFrame(rows)


def score_band(score):
    if score is None or pd.isna(score):
        return None
    s = float(score)
    if s < 20:
        return '0-20'
    if s < 40:
        return '20-40'
    if s < 60:
        return '40-60'
    if s < 80:
        return '60-80'
    return '80-100'


def build_forward_return_table(fwd_df):
    if fwd_df is None or fwd_df.empty:
        return []
    fwd_df = fwd_df.copy()
    fwd_df['band'] = fwd_df['chip_structure_score'].apply(score_band)
    fwd_df = fwd_df.dropna(subset=['band'])
    if fwd_df.empty:
        return []
    table = []
    for band in ['0-20', '20-40', '40-60', '60-80', '80-100']:
        sub = fwd_df[fwd_df['band'] == band]
        if sub.empty:
            table.append((band, 0, 'N/A', 'N/A', 'N/A'))
            continue
        table.append((
            band,
            len(sub),
            f"{sub['fwd_1q'].mean():+.2f}%" if sub['fwd_1q'].notna().any() else 'N/A',
            f"{sub['fwd_2q'].mean():+.2f}%" if sub['fwd_2q'].notna().any() else 'N/A',
            f"{sub['fwd_4q'].mean():+.2f}%" if sub['fwd_4q'].notna().any() else 'N/A',
        ))
    return table


# ==================== 报告生成 ====================
def build_report(stock_code, stock_name, target_quarter, chip_df, integrated_df,
                 kline_df, flow_df, fwd_df, logger):
    """生成单只股票的季度筹码结构分析报告（Markdown 文本）。"""
    hist = chip_df[chip_df['stock_code'] == stock_code].sort_values('quarter').reset_index(drop=True)
    if hist.empty:
        logger.warning(f"{stock_code} 无筹码分析数据，跳过")
        return None

    # ---- 数据拼接：筹码因子 + 联合分析 + 季线 + 资金流 ----
    hist2 = hist.copy()
    if not integrated_df.empty:
        integ_cols = ['stock_code', 'quarter',
                      'chip_direction', 'flow_direction', 'price_direction',
                      'chip_flow_alignment', 'chip_price_alignment', 'flow_price_alignment',
                      'chip_flow_price_regime', 'integrated_score',
                      'institutional_flow', 'individual_flow', 'idr', 'fbi', 'flow_bias',
                      'close', 'change_percent', 'macd_status', 'ema5_10_status', 'rsi14',
                      'price_trend', 'signal_summary']
        sub = integrated_df[integrated_df['stock_code'] == stock_code][integ_cols]
        hist2 = hist2.merge(sub, on=['stock_code', 'quarter'], how='left')
    else:
        for col in ['chip_direction', 'flow_direction', 'price_direction',
                    'chip_flow_alignment', 'chip_price_alignment', 'flow_price_alignment',
                    'chip_flow_price_regime', 'integrated_score',
                    'institutional_flow', 'individual_flow', 'idr', 'fbi', 'flow_bias',
                    'close', 'change_percent', 'macd_status', 'ema5_10_status', 'rsi14',
                    'price_trend', 'signal_summary']:
            hist2[col] = None

    if not kline_df.empty:
        k_cols = ['stock_code', 'date', 'macd_dif', 'ema5', 'ema20', 'ema50', 'volume_ratio']
        ksub = kline_df[kline_df['stock_code'] == stock_code][k_cols]
        ksub = ksub.drop_duplicates(subset=['stock_code', 'date'])
        hist2 = hist2.merge(
            ksub.rename(columns={'date': 'quarter_end_date'}),
            on=['stock_code', 'quarter_end_date'], how='left'
        )
    else:
        for col in ['macd_dif', 'ema5', 'ema20', 'ema50', 'volume_ratio']:
            hist2[col] = None

    if not flow_df.empty:
        f_cols = ['stock_code', 'date', 'inst_5ma', 'ind_5ma']
        fsub = flow_df[flow_df['stock_code'] == stock_code][f_cols]
        fsub = fsub.drop_duplicates(subset=['stock_code', 'date'])
        hist2 = hist2.merge(
            fsub.rename(columns={'date': 'quarter_end_date'}),
            on=['stock_code', 'quarter_end_date'], how='left'
        )
    else:
        hist2['inst_5ma'] = None
        hist2['ind_5ma'] = None

    # ---- 三维评分 + 候选状态 ----
    base_confs = []
    flow_scores = []
    price_scores = []
    candidates = []
    enter_oks = []
    enter_details = []
    for _, r in hist2.iterrows():
        fs = flow_score(r.get('fbi'), r.get('inst_5ma'), r.get('ind_5ma'))
        ps = price_score(r.get('change_percent'), r.get('macd_dif'),
                         r.get('rsi14'), r.get('ema5'), r.get('ema20'), r.get('ema50'))
        cs = r.get('chip_structure_score')
        fl_known = r.get('fbi') is not None and pd.notna(r.get('fbi'))
        cand, ok, detail = candidate_stage(cs, fs, ps, fl_known, r)
        base_conf = stage_specific_confidence(cand, cs, fs, ps)
        base_confs.append(base_conf)
        flow_scores.append(fs)
        price_scores.append(ps)
        candidates.append(cand)
        enter_oks.append(ok)
        enter_details.append(detail)

    hist2['_flow_score'] = flow_scores
    hist2['_price_score'] = price_scores
    hist2['_candidate'] = candidates
    hist2['_enter_ok'] = enter_oks
    hist2['_enter_detail'] = enter_details
    hist2['_base_confidence'] = base_confs

    # ---- 状态机（候选 → 连续确认）----
    hist2 = run_regime_state_machine(hist2)

    # ---- 目标季度 ----
    target_rows = hist2[hist2['quarter'] == target_quarter]
    if target_rows.empty:
        logger.warning(f"{stock_code} 目标季度 {target_quarter} 无数据，跳过")
        return None
    cur = target_rows.iloc[-1]

    kline_close = []
    if not kline_df.empty:
        kline_close = kline_df.loc[kline_df['stock_code'] == stock_code, 'close'].tolist()

    price_percentile = None
    closes = [c for c in kline_close if c is not None and pd.notna(c)]
    if closes:
        last = closes[-1]
        price_percentile = sum(1 for c in closes if c <= last) / len(closes) * 100.0

    chip_d = int(cur.get('chip_direction') or 0)
    price_d = int(cur.get('price_direction') or 0)
    flow_d = int(cur.get('flow_direction') or 0)
    confirmed = cur.get('confirmed_regime') or '中性观察'
    candidate = cur.get('_candidate') or '中性观察'
    prev_regime = cur.get('previous_regime')
    transition = cur.get('regime_transition')
    transition_meaning = TRANSITION_MEANING.get(transition, '') if transition else ''
    duration = int(cur.get('regime_duration') or 1)
    confidence = cur.get('regime_confidence')
    enter_ok = bool(cur.get('_enter_ok'))
    enter_detail = cur.get('_enter_detail') or ''
    chip_score = cur.get('chip_structure_score')
    flow_score_v = cur.get('_flow_score')
    price_score_v = cur.get('_price_score')
    big_cycle = STAGE_INFO.get(confirmed, ('--', '观察期'))[1]

    rel, rel_reason = cp_relation(chip_d, price_d)
    new_high = price_new_high_flag(kline_close, cur.get('close'))
    top_warning = new_high and chip_d == -1

    lines = []
    add = lines.append

    # ===== 标题 =====
    add(f"# {stock_name}（{stock_code}）")
    add(f"## 季度筹码结构分析报告")
    add(f"### {target_quarter}\n")
    add("---\n")

    # ===== 1 执行摘要 =====
    add("## 1. 执行摘要\n")
    inst_t = int(cur.get('institution_trend') or 0)
    pct_t = int(cur.get('holder_pct_trend') or 0)
    add(f"- 筹码状态：{trend_text(pct_t)}（持股比例）")
    add(f"- 机构参与度：{trend_text(inst_t)}，参与度评分 {fmt_score(cur.get('institution_participation_score'))} / 100")
    add(f"- 持股比例：{fmt_num(cur.get('holder_pct'))}%（QoQ {fmt_pp(cur.get('holder_pct_qoq_pp'))}）")
    add(f"- 持股数量：{fmt_int(cur.get('holder_quantity'))}（QoQ {fmt_int(cur.get('holder_quantity_qoq'))}）")
    add(f"- 筹码迁移：{migration_band(cur.get('chip_migration_score'))}（状态 {cur.get('chip_migration_status') or 'N/A'}）")
    add(f"- **筹码周期：{STAGE_NUM.get(confirmed, '--')} {confirmed}**（大周期：{big_cycle}，已持续 {duration} 个季度）")
    if prev_regime and transition:
        add(f"- 状态转换：{STAGE_NUM.get(prev_regime, '--')} {prev_regime} → {STAGE_NUM.get(confirmed, '--')} {confirmed}"
            f"（{transition}：{transition_meaning or '状态迁移'}）")
    add(f"- 周期置信度：{fmt_score(confidence)} / 100")
    add(f"- 周期雷达：Chip {fmt_score(chip_score)} / Flow {fmt_score(flow_score_v)} / Price {fmt_score(price_score_v)}")
    add(f"- 筹码—价格关系：{rel}（{rel_reason}）")
    if top_warning:
        add("- ⚠️ 顶部结构预警：价格创近8个季度新高，但筹码方向为负，形成背离（风险信号，非确定性预测）")
    add("")
    add(f"**核心结论**：{stock_name}在{target_quarter}的筹码周期为**{STAGE_NUM.get(confirmed, '--')} {confirmed}**"
        f"（Chip Score {fmt_score(chip_score)}/100，置信度 {fmt_score(confidence)}）。"
        f"机构参与度{trend_text(inst_t)}、持股比例{trend_text(pct_t)}。"
        f"上述结论基于季度汇总数据（证据等级 A/B），**不构成对具体机构买卖行为的推断**。")
    add("")
    add("---\n")

    # ===== 2 数据质量与边界 =====
    add("## 2. 数据质量与分析边界\n")
    add(f"- 数据来源：{cur.get('data_source') or 'N/A'}（hk_hist_institutional_holdings 季度汇总）")
    add(f"- 数据截止：{target_quarter}（{cur.get('quarter_end_date')}）")
    add(f"- 历史长度：{len(hist2)} 个季度（{hist2['quarter'].iloc[0]} ~ {hist2['quarter'].iloc[-1]}）")
    add("")
    add("**本报告基于季度机构持股汇总数据，不包含单一机构持股明细，因此无法识别机构名称、机构成本、"
        "机构增减持行为及机构内部集中度。**")
    add("")
    add("**可以分析**：机构数量、持股数量、持股比例、季度/年度变化、筹码集中/扩散趋势、"
        "机构参与度、筹码迁移、与价格/资金流的关系。")
    add("")
    add("**不能直接分析**：哪家机构增持/减持、机构平均成本、Top10 机构集中度、HHI、"
        "单一机构锁仓、机构波段操作、机构真实盈亏。")
    add("")
    add("**证据等级**：A=直接观察；B=高可信推断；C=假设；D=不可验证。")
    risks = []
    if int(cur.get('corporate_action_flag') or 0) == 1:
        risks.append("持股数量环比变动≥25%，存在 IPO/配股/拆分/并购等股本结构变化风险，QoQ 指标可能被污染")
    if int(cur.get('data_quality_flag') or 1) == 0:
        risks.append("原始字段存在缺失（data_quality_flag=0），部分指标不可靠")
    if cur.get('quarter_end_price') is None or pd.isna(cur.get('quarter_end_price')):
        risks.append("该季度无季末价格数据，筹码—价格关系缺少价格锚点")
    if not risks:
        risks.append("当前记录未触发明显数据质量提示")
    add(f"- 数据质量风险：{'；'.join(risks)}")
    add("")
    add("---\n")

    # ===== 3 筹码存量 =====
    add("## 3. 筹码存量状态\n")
    add(f"- 机构数量：{fmt_int(cur.get('institution_quantity'))} [A]")
    add(f"- 持股数量：{fmt_int(cur.get('holder_quantity'))} [A]")
    add(f"- 持股比例：{fmt_num(cur.get('holder_pct'))}% [A]")
    add(f"- 季末价格：{fmt_num(cur.get('quarter_end_price'), 4)} [A]")
    add("")
    add("| 变化维度 | 机构数量 | 持股数量 | 持股比例 |")
    add("|----------|----------|----------|----------|")
    add(f"| QoQ | {fmt_int(cur.get('institution_quantity_qoq'))} ({fmt_pct(cur.get('institution_quantity_qoq_pct'))}) "
        f"| {fmt_int(cur.get('holder_quantity_qoq'))} ({fmt_pct(cur.get('holder_quantity_qoq_pct'))}) "
        f"| {fmt_pp(cur.get('holder_pct_qoq_pp'))} |")
    add(f"| YoY | {fmt_pct(cur.get('institution_quantity_yoy_pct'))} "
        f"| {fmt_pct(cur.get('holder_quantity_yoy_pct'))} "
        f"| {fmt_pp(cur.get('holder_pct_yoy_pp'))} |")
    add(f"| 4Q累计 | {fmt_int(cur.get('institution_quantity_4q_change'))} "
        f"| {fmt_int(cur.get('holder_quantity_4q_change'))} "
        f"| {fmt_pp(cur.get('holder_pct_4q_change_pp'))} |")
    add("")
    add(f"解读：机构数量环比 {fmt_pct(cur.get('institution_quantity_qoq_pct'))}、"
        f"持股数量环比 {fmt_pct(cur.get('holder_quantity_qoq_pct'))}、"
        f"持股比例环比 {fmt_pp(cur.get('holder_pct_qoq_pp'))}。"
        f"（注：持股比例变化应以百分点计，而非百分比。）")
    add("")
    add("---\n")

    # ===== 4 机构参与度 =====
    add("## 4. 机构参与度\n")
    recent = hist2.tail(5)
    q_str = ' → '.join(recent['quarter'].tolist())
    inst_str = ' → '.join(fmt_int(x) for x in recent['institution_quantity'].tolist())
    add(f"- 机构数量（近5个季度）：{q_str}")
    add(f"- 机构数量：{inst_str} [A]")
    add(f"- 参与度评分：{fmt_score(cur.get('institution_participation_score'))} / 100 [B]")
    add(f"- 机构数量趋势：{trend_text(cur.get('institution_trend'))}（QoQ {fmt_pct(cur.get('institution_quantity_qoq_pct'))}）")
    add("")
    inst_qoq = cur.get('institution_quantity_qoq')
    if inst_qoq is not None and pd.notna(inst_qoq) and float(inst_qoq) > 0:
        add("解读：机构参与广度扩大（机构数量增加）。[B]")
    elif inst_qoq is not None and pd.notna(inst_qoq) and float(inst_qoq) < 0:
        add("解读：机构参与广度收缩（机构数量减少）。[B]")
    else:
        add("解读：机构参与数量环比基本持平。[B]")
    if int(inst_t) > 0 and int(pct_t) <= 0:
        add("注意：机构数量上升但持股比例未同步提升，说明平均/整体持股强度未同步提高，不能直接定义为吸筹。[B]")
    elif int(inst_t) <= 0 and int(pct_t) > 0:
        add("注意：机构数量下降但持股比例上升，可能是“筹码集中代理信号”，而非机构锁仓证据。[C]")
    add("")
    add("---\n")

    # ===== 5 持股结构 =====
    add("## 5. 持有人结构变化\n")
    add(f"- 持股数量：{fmt_int(cur.get('holder_quantity'))} [A]")
    add(f"  - QoQ：{fmt_int(cur.get('holder_quantity_qoq'))}（{fmt_pct(cur.get('holder_quantity_qoq_pct'))}）")
    add(f"  - 4Q累计变化：{fmt_int(cur.get('holder_quantity_4q_change'))}")
    add(f"- 持股比例：{fmt_num(cur.get('holder_pct'))}% [A]")
    add(f"  - QoQ：{fmt_pp(cur.get('holder_pct_qoq_pp'))}")
    add(f"  - YoY：{fmt_pp(cur.get('holder_pct_yoy_pp'))}")
    add(f"  - 4Q累计：{fmt_pp(cur.get('holder_pct_4q_change_pp'))}")
    add(f"- 持股数量趋势：{trend_text(cur.get('holder_trend'))}")
    add(f"- 持股比例趋势：{trend_text(cur.get('holder_pct_trend'))}")
    add("")
    add("解读：持股比例变化使用百分点口径，避免与百分比变化混淆。"
        f"持股比例环比 {fmt_pp(cur.get('holder_pct_qoq_pp'))}、"
        f"过去4个季度累计 {fmt_pp(cur.get('holder_pct_4q_change_pp'))}。")
    add("")
    add("---\n")

    # ===== 6 筹码集中/扩散 =====
    add("## 6. 筹码集中/扩散分析\n")
    a_t = int(inst_t)
    b_t = int(cur.get('holder_trend') or 0)
    c_t = int(pct_t)
    add("三个观察变量（A=机构数量，B=持股数量，C=持股比例）：")
    add(f"- A（机构数量）方向：{trend_text(a_t)}")
    add(f"- B（持股数量）方向：{trend_text(b_t)}")
    add(f"- C（持股比例）方向：{trend_text(c_t)}")
    add("")
    if a_t > 0 and b_t > 0 and c_t > 0:
        state = "情况①：强集中（最积极结构）"
        explain = "机构参与扩大，持股数量与持股比例同步提高。"
    elif a_t > 0 and b_t > 0 and c_t == 0:
        state = "情况②：温和改善"
        explain = "机构参与扩大，持股数量增加，但持股比例尚未明显提升。"
    elif a_t > 0 and c_t < 0:
        state = "情况③：参与扩张但筹码强度下降"
        explain = "机构数量增加但持股比例下降，参与广度与筹码强度背离，需谨慎。"
    elif a_t < 0 and b_t < 0 and c_t < 0:
        state = "情况④：明显扩散/退出"
        explain = "机构数量、持股数量、持股比例同步下降，为较明确的负面结构。"
    elif a_t < 0 and b_t > 0 and c_t > 0:
        state = "情况⑤：潜在集中"
        explain = "参与机构数量减少，但整体持股进一步集中；这是“集中代理信号”，不能证明少数大型机构吸收了筹码。"
    else:
        state = "中性/其他组合"
        explain = "各变量方向未形成典型组合，建议结合迁移评分与资金面综合判断。"
    add(f"**{state}**")
    add(f"解释：{explain}")
    add("")
    mig_v = cur.get('chip_migration_score')
    mig_display = 'N/A'
    if mig_v is not None and pd.notna(mig_v):
        mig_display = f"{float(mig_v):+.2f}（-100~+100 口径 {float(mig_v) * 100:+.0f}）"
    add(f"- 筹码迁移评分：{mig_display}")
    if mig_v is not None and pd.notna(mig_v):
        add(f"- 迁移分段：{migration_band(mig_v)}")
    add(f"- 迁移状态：{cur.get('chip_migration_status') or 'N/A'}")
    add("")
    add("**重要边界**：以上均为“集中/扩散代理信号”，而非机构锁仓或具体机构行为的证据。[C]")
    add("")
    add("---\n")

    # ===== 7 筹码—价格关系 =====
    add("## 7. 筹码—价格关系\n")
    add(f"- Chip 方向：{direction_text(chip_d)}")
    add(f"- Price 方向：{direction_text(price_d)}")
    add(f"- 季度涨跌幅：{fmt_pct(cur.get('change_percent'))}")
    add(f"- 关系判定：**{rel}**（{rel_reason}）")
    if top_warning:
        add("")
        add("⚠️ **顶部结构预警**：价格创近8个季度新高而筹码方向为负。"
            "背离是风险信号而非确定性预测，需结合资金流与成交量验证。")
    add("")
    add("---\n")

    # ===== 8 历史周期 =====
    add("## 8. 历史周期复盘（近12个季度）\n")
    add("| 季度 | 机构数量 | 持股比例% | Chip Score | 周期阶段 | 季度涨跌% |")
    add("|------|----------|-----------|------------|----------|-----------|")
    kline_date_map = {}
    if not kline_df.empty:
        ksub = kline_df[kline_df['stock_code'] == stock_code]
        kline_date_map = dict(zip(ksub['date'], ksub['change_percent']))
    for _, r in hist2.tail(12).iterrows():
        chg = kline_date_map.get(r['quarter_end_date'])
        chg_str = fmt_pct(chg) if chg is not None and pd.notna(chg) else 'N/A'
        stg = r.get('confirmed_regime') or 'N/A'
        stg_str = f"{STAGE_NUM.get(stg, '--')} {stg}"
        if r.get('regime_transition'):
            stg_str += f"（←{r['regime_transition']}）"
        add(f"| {r['quarter']} | {fmt_int(r.get('institution_quantity'))} | "
            f"{fmt_num(r.get('holder_pct'))} | {fmt_score(r.get('chip_structure_score'))} | "
            f"{stg_str} | {chg_str} |")
    add("")
    add("历史拐点提示：结合上表可观察筹码阶段（状态机确认）与价格涨跌的先后关系；"
        "单季度波动可能存在噪音，状态机采用连续2季度确认以降低误判。")
    add("")
    add("---\n")

    # ===== 9 当前筹码状态（状态机） =====
    add("## 9. 当前筹码状态（筹码周期状态机）\n")
    add(f"- **确认状态：{STAGE_NUM.get(confirmed, '--')} {confirmed}**（大周期：{big_cycle}）")
    add(f"- 候选状态：{candidate}（{'已连续确认' if candidate == confirmed else '待连续确认'}）")
    add(f"- 状态持续：{duration} 个季度")
    if prev_regime:
        suffix = '（维持）' if prev_regime == confirmed else ''
        add(f"- 上一状态：{STAGE_NUM.get(prev_regime, '--')} {prev_regime}{suffix}")
    if candidate != confirmed:
        add(f"- 潜在方向：{STAGE_NUM.get(candidate, '--')} {candidate}"
            f"（当前为候选，需连续 2 季度同向确认）")
    if transition:
        add(f"- 状态转换：{transition}（{transition_meaning or '状态迁移'}）")
        if cur.get('regime_transition_score') is not None:
            add(f"- 转换评分：{fmt_score(cur.get('regime_transition_score'))} / 100")
    add(f"- 周期置信度：{fmt_score(confidence)} / 100"
        f"（持续季度加成 + 连续确认加成，范围 0-100）")
    add("")
    add("**筹码周期雷达**：")
    add("```")
    add(build_radar(chip_score, flow_score_v, price_score_v))
    add("```")
    add("")
    add(f"- Chip Score：{fmt_score(chip_score)} / 100")
    add(f"- Flow Score：{fmt_score(flow_score_v)} / 100（FBI {fmt_num(cur.get('fbi'))}，{cur.get('flow_bias') or 'N/A'}）")
    add(f"- Price Score：{fmt_score(price_score_v)} / 100（季度涨跌 {fmt_pct(cur.get('change_percent'))}）")
    add("")
    add(f"- 判定证据：{stage_evidence(cur)}")
    add(f"- 进入条件：{'满足' if enter_ok else '未完全满足'}（{enter_detail}）")
    add("")
    add("**状态机说明**：单季度变化先进入 Candidate，连续 2 个季度同向才确认为 Confirmed Regime；"
        "允许相邻状态双向转换（如 02↔01、05↔04），市场可以失败、反转、重新蓄势。")
    add("")
    add("**下一季度观察条件**：")
    add(f"- {transition_meaning or '保持当前状态'}："
        f"{STAGE_OBSERVE.get(confirmed, '持续跟踪三维评分与证据一致性')}")
    add("")
    add("（筹码周期九态：01 分散 / 02 筑底 / 03 吸筹 / 04 集中 / 05 蓄势 / "
        "06 主升 / 07 派发 / 08 扩散 / 09 退潮）")
    add("")
    add("---\n")

    # ===== 10 风险 =====
    add("## 10. 风险\n")
    add("- **数据口径风险**：季度汇总数据不含机构明细，集中度与迁移均为代理指标。")
    if int(cur.get('corporate_action_flag') or 0) == 1:
        add("- **股本变化风险**：corporate_action_flag=1，持股数量大幅变动，QoQ 可能受 IPO/配股/拆分等影响。")
    else:
        add("- **股本变化风险**：当前季度未触发股本大幅变动提示（corporate_action_flag=0）。")
    add("- **筹码解释风险**：不能将代理信号等同于机构锁仓/吸筹等具体行为。")
    if chip_d == -1 and price_d == 1:
        add("- **价格背离风险**：价格上涨但筹码恶化（上涨背离），若资金流不能持续，回落风险上升。")
    elif chip_d == 1 and price_d == -1:
        add("- **逆势集中风险**：筹码改善但价格下跌，需验证是底部吸筹还是基本面恶化的被动集中。")
    else:
        add("- **价格背离风险**：需持续跟踪筹码与价格的同步性。")
    if transition == '06→07':
        add("- **顶部周期风险**：状态转换显示 06 主升 → 07 派发，属顶部风险预警。")
    if transition == '08→09':
        add("- **下跌周期风险**：状态转换显示 08 扩散 → 09 退潮，警惕全面走弱。")
    add("")
    add("---\n")

    # ===== 11 QCFP联合验证 =====
    add("## 11. QCFP 联合验证（筹码 × 资金 × 价格）\n")
    add(f"- Chip：{direction_text(chip_d)}（评分 {fmt_score(chip_score)}）")
    add(f"- Flow：{direction_text(flow_d)}（FBI {fmt_num(cur.get('fbi'))}，{cur.get('flow_bias') or 'N/A'}）")
    add(f"- Price：{direction_text(price_d)}（季度涨跌 {fmt_pct(cur.get('change_percent'))}）")
    add(f"- 筹码×资金：{cur.get('chip_flow_alignment') or 'N/A'}")
    add(f"- 筹码×价格：{cur.get('chip_price_alignment') or 'N/A'}")
    add(f"- 资金×价格：{cur.get('flow_price_alignment') or 'N/A'}")
    add(f"- **三维状态：{cur.get('chip_flow_price_regime') or 'N/A'}**")
    add(f"- 综合评分：{fmt_score(cur.get('integrated_score'))} / 100")
    if cur.get('signal_summary'):
        add(f"- 信号摘要：{cur.get('signal_summary')}")
    add("")
    if chip_d == 1 and flow_d == 1 and price_d == 1:
        add("**🟢 强确认**：筹码、资金、价格三者一致向好。")
    elif (chip_d == 1 and flow_d == -1) or (chip_d == -1 and flow_d == 1):
        add("**🟡 结构背离**：筹码与资金方向相反，结构一致性不足。")
    elif chip_d == -1 and flow_d == 1 and price_d == -1:
        add("**🟡 潜在底部转折**：筹码偏弱但资金逆势流入，关注是否出现底部转折。")
    else:
        add("三维方向未形成典型共振/背离，建议持续跟踪。")
    add("")
    add("---\n")

    # ===== 12 投资含义 =====
    add("## 12. 投资含义\n")
    add(f"- 机构参与：{trend_text(inst_t)}（参与度 {fmt_score(cur.get('institution_participation_score'))}/100）")
    add(f"- 筹码方向：{migration_band(cur.get('chip_migration_score'))}（迁移状态 {cur.get('chip_migration_status') or 'N/A'}）")
    add(f"- 筹码趋势：{trend_text(pct_t)}（持股比例）")
    add(f"- 筹码周期：{STAGE_NUM.get(confirmed, '--')} {confirmed}（{big_cycle}，持续 {duration} 季度）")
    add(f"- QCFP 状态：{cur.get('chip_flow_price_regime') or 'N/A'}")
    add(f"- 潜在催化：筹码结构与价格/资金形成共振时，可作为中期关注信号（见历史有效性检验）")
    add(f"- 主要风险：数据口径限制 + {('股本变动' if int(cur.get('corporate_action_flag') or 0) == 1 else '价格背离')}")
    add("")
    add("---\n")

    # ===== 13 结论 =====
    add("## 13. 结论\n")
    add(f"- 当前状态：{STAGE_NUM.get(confirmed, '--')} {confirmed}"
        f"（置信度 {fmt_score(confidence)}/100，持续 {duration} 季度）")
    add(f"- 状态转换：{transition or '无（维持原状态）'}（{transition_meaning or '—'}）")
    add(f"- 证据强度：原始数据（机构数量/持股数量/持股比例）为 A 级直接观察；"
        "集中度、迁移、参与度为 B/C 级推断；本报告不包含 D 级不可验证表述。")
    add(f"- 未来重点观察：① 机构数量与持股比例是否连续 2 个季度同向；"
        "② 筹码迁移评分能否进入 +40 以上区间并持续；"
        "③ 价格是否对筹码改善形成正向确认；"
        "④ 资金流（FBI/IDR）与筹码方向的一致性；"
        f"⑤ {STAGE_OBSERVE.get(confirmed, '持续跟踪三维评分与证据一致性')}。")
    add("")

    # ===== 附录：历史有效性 =====
    add("---\n")
    add("## 附录：历史有效性检验（全市场）\n")
    table = build_forward_return_table(fwd_df)
    if table:
        add("| Chip Score 分段 | N | Q+1平均收益 | Q+2平均收益 | Q+4平均收益 |")
        add("|-----------------|---|-------------|-------------|-------------|")
        for band, n, r1, r2, r4 in table:
            add(f"| {band} | {n} | {r1} | {r2} | {r4} |")
        add("")
        add("说明：未来收益基于季线收盘价计算；样本不足的区间请谨慎解读。"
            "该检验回答“筹码指标是否有预测价值”，不构成对未来收益的承诺。")
    else:
        add("当前样本不足，无法完成历史有效性检验。")
    add("")

    return '\n'.join(lines)


# 各阶段下一季度观察条件（供第 9/13 节引用）
STAGE_OBSERVE = {
    '分散': '观察机构数量/持股比例是否止跌企稳、价格是否不再创新低（→筑底）',
    '筑底': '观察持股比例是否连续上升、机构数量止跌、资金是否开始净流入（→吸筹）',
    '吸筹': '观察筹码/资金改善是否延续 2 个季度且价格不破前低（→集中确认）',
    '集中': '观察价格是否放量突破、资金是否持续流入（→蓄势/主升）',
    '蓄势': '观察价格突破 + 资金流确认（→主升）',
    '主升': '观察价格/资金/筹码是否持续正反馈（否则 →派发预警）',
    '派发': '观察筹码是否进一步恶化、价格是否开始走弱（→扩散）',
    '扩散': '观察资金与价格是否全面走弱（→退潮）',
    '退潮': '观察价格是否企稳、筹码是否止跌（→筑底/分散）',
    '中性观察': '持续跟踪三维评分与证据一致性',
}


# === 添加UTL路径到系统路径 ===
script_dir = Path(__file__).resolve().parent
core_dir = script_dir.parent
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

try:
    from utl.stock_analysis_utl import (
        load_config,
        setup_windows_encoding,
        GlobalConfig
    )
except ImportError as e:
    print("=" * 60)
    print("❌ 严重错误：无法导入 utl.stock_analysis_utl 模块")
    print(f"   详细错误: {e}")
    print("=" * 60)
    sys.exit(1)

# === 强制UTF-8编码输出 ===
if 'get_ipython' not in globals():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
else:
    import ipykernel
    if ipykernel:
        sys.stdout.encoding = 'utf-8'
        sys.stderr.encoding = 'utf-8'

setup_windows_encoding()


def main():
    """主函数，程序的入口点"""
    logger = None
    try:
        parser = argparse.ArgumentParser(description="季度筹码结构分析报告生成器")
        parser.add_argument("--quarter", default=None,
                            help="目标季度（如 2026/Q2 或 2026Q2），缺省为最新季度")
        parser.add_argument("--ticker", default=None,
                            help="股票代码（5位，如 00700），缺省为全部股票")
        args = parser.parse_args()

        project_dir = core_dir.parent
        config_path = project_dir / 'config' / 'stock_data_analysis.par'
        CONFIG = load_config(str(config_path), project_dir)
        print(f"配置文件加载成功: {config_path}")

        GlobalConfig.update_paths(CONFIG, project_dir)

        log_dir = Path(GlobalConfig.full_log_dir)
        logger = setup_logging(log_dir)

        logger.info("=" * 70)
        logger.info("Quarterly_TA4E_Analyze_chip_report 启动（筹码周期状态机版）")
        logger.info("=" * 70)
        logger.info(f"项目目录: {project_dir}")
        logger.info(f"数据库路径: {GlobalConfig.full_db_path}")
        logger.info(f"报告目录: {GlobalConfig.full_report_dir}")

        report_dir = Path(GlobalConfig.full_report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)

        db_path = Path(GlobalConfig.full_db_path)
        if not db_path.exists():
            logger.error(f"数据库文件不存在: {db_path}")
            return

        conn = get_db_connection(db_path)
        try:
            if not check_table_exists(conn, 'hk_quarterly_institutional_holdings_analysis'):
                logger.error("hk_quarterly_institutional_holdings_analysis 不存在，"
                             "请先运行 Quarterly_TA4C_Analyze_institutional_holdings.py")
                return

            # 筹码因子（TA4C）
            df_chip = pd.read_sql_query(
                """
                SELECT stock_code, stock_name, quarter, quarter_end_date,
                       institution_quantity, holder_quantity, holder_pct, quarter_end_price,
                       institution_quantity_qoq, institution_quantity_qoq_pct,
                       holder_quantity_qoq, holder_quantity_qoq_pct, holder_pct_qoq_pp,
                       institution_quantity_yoy_pct, holder_quantity_yoy_pct, holder_pct_yoy_pp,
                       institution_quantity_4q_change, holder_quantity_4q_change,
                       holder_pct_4q_change_pp,
                       institution_trend, holder_trend, holder_pct_trend,
                       chip_migration_score, chip_migration_status,
                       institution_participation_score, institutional_concentration_score,
                       chip_structure_score, chip_regime,
                       data_quality_flag, corporate_action_flag, data_source
                FROM hk_quarterly_institutional_holdings_analysis
                """,
                conn
            )
            logger.info(f"筹码因子数据: {len(df_chip)} 行")

            # 联合分析（TA4D）
            if check_table_exists(conn, 'hk_quarterly_chip_analysis'):
                df_integ = pd.read_sql_query(
                    """
                    SELECT stock_code, quarter, quarter_end_date,
                           chip_direction, flow_direction, price_direction,
                           chip_flow_alignment, chip_price_alignment, flow_price_alignment,
                           chip_flow_price_regime, integrated_score,
                           institutional_flow, individual_flow, idr, fbi, flow_bias,
                           close, change_percent, macd_status, ema5_10_status, rsi14,
                           price_trend, signal_summary
                    FROM hk_quarterly_chip_analysis
                    """,
                    conn
                )
            else:
                df_integ = pd.DataFrame()
            logger.info(f"联合分析数据: {len(df_integ)} 行")

            # 季线（TA2B）
            if check_table_exists(conn, 'hk_quarterly_kline_analysis'):
                df_kline = pd.read_sql_query(
                    """
                    SELECT stock_code, date, close, change_percent,
                           volume_ratio, macd_status, ema5_10_status, rsi14,
                           macd_dif, ema5, ema20, ema50
                    FROM hk_quarterly_kline_analysis
                    """,
                    conn
                )
            else:
                df_kline = pd.DataFrame()
            logger.info(f"季线分析数据: {len(df_kline)} 行")

            # 季度资金流 5 季均线（TA4B）
            if check_table_exists(conn, 'hk_quarterly_moneyflow_analysis'):
                df_flow = pd.read_sql_query(
                    """
                    SELECT stock_code, date, inst_5ma, ind_5ma
                    FROM hk_quarterly_moneyflow_analysis
                    """,
                    conn
                )
            else:
                df_flow = pd.DataFrame()
            logger.info(f"季度资金流均线数据: {len(df_flow)} 行")

            if df_chip.empty:
                logger.warning("⚠️ 无筹码因子数据，程序退出")
                return

            latest_quarter = df_chip.sort_values('quarter_end_date')['quarter'].iloc[-1]
            target_quarter = normalize_quarter(args.quarter) or latest_quarter
            logger.info(f"目标季度: {target_quarter}")

            fwd_df = compute_forward_returns(df_kline, df_chip)
            logger.info(f"历史有效性样本: {len(fwd_df)} 条")

            if args.ticker:
                tickers = [str(args.ticker).zfill(5)]
            else:
                tickers = sorted(df_chip['stock_code'].unique())
            logger.info(f"待生成报告股票数: {len(tickers)}")

            success = 0
            for stock_code in tickers:
                stock_name = df_chip.loc[df_chip['stock_code'] == stock_code, 'stock_name']
                stock_name = stock_name.dropna().iloc[0] if not stock_name.empty else stock_code
                logger.info(f"\n生成 {stock_code} ({stock_name}) 筹码报告...")
                report_text = build_report(
                    stock_code, stock_name, target_quarter,
                    df_chip, df_integ, df_kline, df_flow, fwd_df, logger
                )
                if not report_text:
                    continue
                out_path = report_dir / f"{stock_code}_quarterly_chip_report.md"
                out_path.write_text(report_text, encoding='utf-8')
                logger.info(f"✅ 报告已生成: {out_path}")
                success += 1

            logger.info("=" * 70)
            logger.info(f"✅ 季度筹码结构分析报告生成完成：成功 {success}/{len(tickers)} 份")
            logger.info("=" * 70)
        finally:
            conn.close()
    except Exception as e:
        if logger:
            logger.error(f"发生未知错误: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
        else:
            print(f"发生未知错误: {type(e).__name__}: {e}")
            print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
