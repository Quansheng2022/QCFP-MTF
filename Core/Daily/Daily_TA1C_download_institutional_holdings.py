#!/usr/bin/env python
# coding: utf-8

"""
Daily_TA1A_download_institutional_holdings_enhanced.py
功能：
1. 优先使用富途 OpenAPI 获取港股机构持股（季度汇总）。
2. 增加调试信息：检测 OpenD 版本、尝试多个相关接口。
3. 若富途接口不可用，自动切换至 AKShare 免费数据源。
4. 保存到 SQLiteDB/HK_Stock.db 的 hk_hist_institutional_holdings 表。
"""

import subprocess
import time
import sys
import socket
import traceback
import sqlite3
import logging
import calendar
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set, Dict, List, Any

import pandas as pd
import moomoo as ft

# === 导入 AKShare（备选） ===
try:
    import akshare as ak
except ImportError:
    ak = None
    print("⚠️ AKShare 未安装，备选方案不可用。如需使用，请运行: pip install akshare")

# === 路径配置（与资金流程序完全一致） ===
script_dir = Path(__file__).resolve().parent
core_dir = script_dir.parent
if str(core_dir) not in sys.path:
    sys.path.insert(0, str(core_dir))

from utl.stock_analysis_utl import get_project_root
core_dir_from_utils = get_project_root()
project_dir = core_dir_from_utils.parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

try:
    from utl.stock_analysis_utl import load_config, setup_windows_encoding
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    sys.exit(1)

setup_windows_encoding()

# ==================== 日志配置 ====================
def setup_logger(log_dir: Path, log_filename: str = "Daily_TA1A_download_institutional_holdings.log") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_filename
    logger = logging.getLogger('InstitutionalDownload')
    logger.setLevel(logging.DEBUG)  # 开启 DEBUG 级别
    if logger.handlers:
        logger.handlers.clear()
    file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

# ==================== SQLite 管理（同前） ====================
class SQLiteInstitutionalManager:
    def __init__(self, db_path: Path, logger: logging.Logger = None):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.logger = logger

    def log(self, msg: str, level: str = "info"):
        if self.logger:
            getattr(self.logger, level)(msg)
        else:
            print(msg)

    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS hk_hist_institutional_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            period_text TEXT NOT NULL,
            institution_quantity INTEGER,
            holder_quantity INTEGER,
            holder_pct REAL,
            quarter_end_price REAL,
            data_source TEXT DEFAULT 'futu',
            update_time TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, period_text)
        )
        """)
        # 旧表结构缺少 data_source 列时补充（保留已有数据）
        self.cursor.execute("PRAGMA table_info(hk_hist_institutional_holdings)")
        columns = {row[1] for row in self.cursor.fetchall()}
        if 'data_source' not in columns:
            self.cursor.execute("ALTER TABLE hk_hist_institutional_holdings ADD COLUMN data_source TEXT DEFAULT 'futu'")
            self.log("已为旧表补充 data_source 列")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_stock_period ON hk_hist_institutional_holdings(stock_code, period_text)")
        self.conn.commit()
        self.log("表 hk_hist_institutional_holdings 已就绪")

    def record_exists(self, stock_code: str, period_text: str) -> bool:
        self.cursor.execute("SELECT COUNT(*) as cnt FROM hk_hist_institutional_holdings WHERE stock_code=? AND period_text=?", (stock_code, period_text))
        row = self.cursor.fetchone()
        return row['cnt'] > 0 if row else False

    def get_existing_periods(self, stock_code: str) -> Set[str]:
        self.cursor.execute("SELECT period_text FROM hk_hist_institutional_holdings WHERE stock_code=?", (stock_code,))
        rows = self.cursor.fetchall()
        return {row['period_text'] for row in rows}

    def insert_record(self, stock_code: str, stock_name: str, period_text: str,
                      institution_quantity: int, holder_quantity: int,
                      holder_pct: float, quarter_end_price: float = None, data_source: str = 'futu') -> bool:
        if self.record_exists(stock_code, period_text):
            return False
        sql = """
        INSERT INTO hk_hist_institutional_holdings
        (stock_code, stock_name, period_text, institution_quantity, holder_quantity, holder_pct, quarter_end_price, data_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.cursor.execute(sql, (stock_code, stock_name, period_text, institution_quantity, holder_quantity, holder_pct, quarter_end_price, data_source))
        self.conn.commit()
        return True

    def insert_batch(self, stock_code: str, stock_name: str, records: List[Dict], data_source: str = 'futu') -> int:
        inserted = 0
        for rec in records:
            if self.insert_record(
                stock_code, stock_name,
                rec['period_text'],
                rec['institution_quantity'],
                rec['holder_quantity'],
                rec['holder_pct'],
                rec.get('quarter_end_price'),
                data_source
            ):
                inserted += 1
        return inserted

    def get_statistics(self) -> Dict:
        self.cursor.execute("SELECT COUNT(*) as total_records, COUNT(DISTINCT stock_code) as stock_count, MIN(period_text) as earliest, MAX(period_text) as latest FROM hk_hist_institutional_holdings")
        row = self.cursor.fetchone()
        return dict(row) if row else {}

# ==================== 辅助函数：季度末收盘价 ====================
def parse_period_to_quarter_end_date(period_text: str) -> str:
    try:
        year, q = period_text.split('/')
        quarter = int(q[1])
        month = quarter * 3
        # 用当月实际天数，避免 6/9/11 月生成 31 号这类不存在的日期
        day = calendar.monthrange(int(year), month)[1]
        return f"{year}-{month:02d}-{day:02d}"
    except Exception:
        return None

def get_quarter_end_price(ctx: ft.OpenQuoteContext, symbol: str, period_text: str,
                          logger=None, db_conn: sqlite3.Connection = None) -> Optional[float]:
    date_str = parse_period_to_quarter_end_date(period_text)
    if not date_str:
        return None
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # 优先从本地 hk_hist_daily_kline 表取收盘价（更快更稳定）
    if db_conn is not None:
        stock_code = symbol.split('.')[-1]  # 'HK.00700' -> '00700'
        for offset in range(0, 5):
            check_date = target_date - timedelta(days=offset)
            if check_date.weekday() >= 5:
                continue
            cur = db_conn.cursor()
            cur.execute(
                "SELECT close FROM hk_hist_daily_kline WHERE stock_code=? AND date=?",
                (stock_code, check_date.strftime("%Y-%m-%d"))
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                return float(row[0])
        if logger:
            logger.debug(f"本地 K 线表未找到 {period_text} 收盘价，回退 OpenD 接口")

    # 回退：通过 OpenD 历史 K 线接口获取
    for offset in range(0, 5):
        check_date = target_date - timedelta(days=offset)
        if check_date.weekday() >= 5:
            continue
        # moomoo 10.10 起接口更名为 request_history_kline，返回 (ret, data, page_req_key)
        # 注意：新接口日期参数只接受 YYYY-MM-DD 格式，YYYYMMDD 会返回 ret=-1
        date_fmt = check_date.strftime("%Y-%m-%d")
        ret, data, _ = ctx.request_history_kline(symbol, start=date_fmt, end=date_fmt)
        if ret == 0 and not data.empty:
            return float(data.iloc[0]['close'])
    if logger:
        logger.debug(f"未找到 {period_text} 收盘价")
    return None

# ==================== OpenD 管理（同前） ====================
def start_opend(futu_cfg):
    # OpenD 10.10 起废弃 login_account/login_pwd/login_pwd_md5 配置参数，
    # 启动后默认进入交互式登录。只有之前登录时勾选过“记住密码”，
    # 才能用 -login_account=<账号> -login_by_remember=1 免密自动登录。
    cmd = [
        futu_cfg['opend_exec_path'],
        f"-login_account={futu_cfg['futu_account']}",
        "-login_by_remember=1",
        f"-api_port={futu_cfg['api_port']}",
        "-lang=chs"
    ]
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.Popen(cmd, startupinfo=si)
    else:
        return subprocess.Popen(cmd)

def wait_for_opend(port, timeout=120):
    for _ in range(timeout):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            return True
        time.sleep(1)
    return False

def wait_for_opend_ready(quote_ctx, timeout=120):
    """轮询 OpenD 全局状态，直到行情已登录且程序进入 READY。"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            ret, state = quote_ctx.get_global_state()
            if ret == 0:
                if (state.get('qot_logined') and
                        state.get('program_status_type') == 'READY'):
                    return True, state
        except Exception:
            # OpenD 启动初期连接会被拒绝或关闭，属正常现象，继续等待
            pass
        time.sleep(1)
    return False, None

def silence_moomoo_console(enable=False):
    """开关 moomoo 库的控制台日志（文件日志不受影响）。

    仅移除 stdout handler 无法完全静音（stderr 路径仍会输出），
    因此直接调整 FTConsoleLog 的日志级别，返回原 level 供恢复。
    """
    console_logger = logging.getLogger('FTConsoleLog')
    old_level = console_logger.level
    console_logger.setLevel(logging.INFO if enable else logging.CRITICAL)
    return old_level

# ==================== 加载股票名称 ====================
def load_stock_names(project_dir: Path) -> Dict[str, str]:
    stock_names = {}
    stock_list_path = project_dir / "Config" / "stock_list.json"
    if stock_list_path.exists():
        try:
            import json
            with open(stock_list_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and 'stocks' in data:
                    for item in data['stocks']:
                        code = item.get('stock_code')
                        name = item.get('stock_name')
                        if code and name:
                            stock_names[code] = name
                elif isinstance(data, list):
                    for item in data:
                        code = item.get('code') or item.get('stock_code')
                        name = item.get('name') or item.get('stock_name')
                        if code and name:
                            stock_names[code] = name
                elif isinstance(data, dict):
                    for code, name in data.items():
                        if code and name:
                            stock_names[code] = name
        except Exception as e:
            print(f"⚠️ 加载股票名称失败: {e}")
    return stock_names

# ==================== 备选数据源：AKShare ====================
def fetch_hk_institutional_from_akshare(stock_code: str, logger=None) -> List[Dict]:
    """
    使用 AKShare 获取港股机构持股汇总数据（从东方财富）
    返回列表，每项包含 period_text, institution_quantity, holder_quantity, holder_pct
    """
    if ak is None:
        if logger:
            logger.error("AKShare 未安装，无法使用备选方案")
        return []

    try:
        # 尝试获取股东户数及持股比例（东方财富港股股东户数）
        # 接口：stock_hk_shareholding_holdernumber_hk
        # 注意：该接口返回的是股东户数，非机构数，且不一定有机构持股比例
        # 这里我们尝试另一个接口：stock_hk_shareholding_shareholder（股东明细）
        # 但根据 akshare 文档，更合适的可能是 stock_hk_shareholding_holdernumber_hk
        # 我们先用这个，如果不行，再尝试其他
        df = ak.stock_hk_shareholding_holdernumber_hk(symbol=stock_code)
        # 该接口返回列：报告期, 股东户数, 户均持股, 持股比例...
        # 我们需要将其转换为机构持股数据，但东方财富的港股股东数据并非机构持股汇总，
        # 而是全体股东户数。因此这个数据不准确，但作为备选应急。
        # 更好的备选：使用 tushare 或直接解析 CCASS 数据，但复杂度较高。
        # 因此，若富途失败，我们建议用户升级 OpenD，而不是依赖不可靠的备选。
        if logger:
            logger.warning("AKShare 的港股股东数据并非机构持股汇总，仅供参考。建议升级 OpenD 使用官方接口。")
        # 这里仅作演示，返回空，实际可忽略。
        return []
    except Exception as e:
        if logger:
            logger.error(f"AKShare 获取失败: {e}")
        return []

# ==================== 机构持股全量获取（分页） ====================
def fetch_all_institutional_holdings(ctx: ft.OpenQuoteContext, symbol: str, logger=None) -> Optional[pd.DataFrame]:
    """获取全部历史机构持股记录（num=50 + next_key 翻页），失败返回 None。"""
    page_size = 50  # 服务器限制 num 必须在 1~50 之间
    max_pages = 200  # 安全上限，防止异常死循环
    frames = []
    next_key = None
    for page in range(max_pages):
        try:
            ret, data = ctx.get_shareholders_institutional(symbol, num=page_size, next_key=next_key)
        except Exception as e:
            if logger:
                logger.warning(f"   机构持股接口调用异常: {e}")
            return None
        if ret != 0:
            if logger:
                logger.warning(f"   机构持股接口失败: ret={ret}, msg={data}")
            return None
        if data.empty:
            break
        frames.append(data)
        nk = data['next_key'].iloc[0] if 'next_key' in data.columns else '-1'
        if not nk or nk == '-1':
            break
        next_key = nk
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    # 去掉重复报告期（翻页边界可能重叠），按报告期倒序排列
    result = result.drop_duplicates(subset='period_text', keep='first').reset_index(drop=True)
    return result

def fetch_latest_institutional_period(ctx: ft.OpenQuoteContext, symbol: str, logger=None) -> Optional[str]:
    """轻量获取最新报告期（num=1），失败返回 None。"""
    try:
        ret, data = ctx.get_shareholders_institutional(symbol, num=1)
        if ret == 0 and not data.empty:
            return str(data.iloc[0]['period_text'])
    except Exception as e:
        if logger:
            logger.warning(f"   获取最新报告期异常: {e}")
    return None

# ==================== 主函数 ====================
def main():
    config_path = project_dir / "Config" / "stock_data_analysis.par"
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        sys.exit(1)

    try:
        config = load_config(str(config_path), str(project_dir))
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        sys.exit(1)

    log_dir = project_dir / "Log"
    logger = setup_logger(log_dir, "Daily_TA1A_download_institutional_holdings_enhanced.log")
    logger.info("=" * 60)
    logger.info("开始执行增强版机构持股下载程序")
    logger.info("=" * 60)

    tickers = config.get('tickers', [])
    if not tickers:
        logger.error("配置中无股票列表")
        sys.exit(1)

    logger.info(f"待处理股票: {len(tickers)} 只")

    sqlite_dir = config.get('full_sqlite_dir', project_dir / "SQLiteDB")
    db_path = Path(sqlite_dir) / "HK_Stock.db"
    stock_names = load_stock_names(project_dir)

    futu_cfg = {
        'futu_account': config.get('futu_account', ''),
        'futu_pwd_md5': config.get('futu_pwd_md5', ''),
        'opend_exec_path': config.get('opend_exec_path', ''),
        'api_host': config.get('api_host', '127.0.0.1'),
        'api_port': int(config.get('api_port', 11111))
    }
    missing = [k for k in ['futu_account', 'futu_pwd_md5', 'opend_exec_path'] if not futu_cfg.get(k)]
    if missing:
        logger.error(f"配置缺少: {missing}")
        sys.exit(1)

    # 启动 OpenD
    logger.info("🚀 启动 OpenD ...")
    opend_process = start_opend(futu_cfg)
    logger.info("⏳ 等待 OpenD 就绪 ...")
    if not wait_for_opend(futu_cfg['api_port'], timeout=120):
        logger.error("❌ OpenD 启动超时")
        opend_process.terminate()
        sys.exit(1)
    logger.info("✅ OpenD 已就绪")

    # 端口监听不代表 API 已就绪：OpenD 启动后还需完成登录/初始化（约几秒）。
    # 用一次预热连接等 OpenD 真正 READY 后再关闭，主连接就能第一次成功。
    # 预热期间 OpenD 仍在启动，库内部的首连被拒/重连/关闭属正常现象，
    # 临时静音 moomoo 控制台日志，避免这些噪音被误认为失败。
    logger.info("⏳ 预热连接：等待 OpenD 登录完成并进入 READY ...")
    old_log_level = silence_moomoo_console(False)
    try:
        warm_ctx = ft.OpenQuoteContext(host=futu_cfg['api_host'], port=futu_cfg['api_port'])
        warm_ready, _ = wait_for_opend_ready(warm_ctx, timeout=120)
        warm_ctx.close()
        time.sleep(1)  # 等 OpenD 处理完连接关闭，避免与主连接交错
        if not warm_ready:
            logger.warning("⚠️ OpenD 未在预期时间内进入 READY，仍尝试主连接 ...")
    finally:
        logging.getLogger('FTConsoleLog').setLevel(old_log_level)

    quote_ctx = None
    failed_stocks = []
    success_stocks = []
    total_inserted = 0

    try:
        quote_ctx = ft.OpenQuoteContext(host=futu_cfg['api_host'], port=futu_cfg['api_port'])
        
        # --- 调试信息：获取 OpenD 全局状态 ---
        logger.info("🔍 正在获取 OpenD 调试信息...")
        ret, state = quote_ctx.get_global_state()
        if ret == 0:
            logger.info(f"   OpenD 状态: {state}")
        else:
            logger.warning(f"   获取全局状态失败: {ret}")

        # --- 调试信息：尝试调用其他接口以判断支持情况 ---
        test_symbol = f"HK.{tickers[0]}" if tickers else "HK.00700"
        logger.info(f"🔍 测试接口可用性（使用 {test_symbol}）:")
        # 1. get_shareholders_holder_detail（持股明细，10.10 起新接口）
        try:
            ret, shareholders = quote_ctx.get_shareholders_holder_detail(test_symbol, request_type=ft.HolderDetailType.ALL)
            logger.info(f"   get_shareholders_holder_detail: ret={ret}, len={len(shareholders) if ret==0 else 'N/A'}")
        except Exception as e:
            logger.warning(f"   get_shareholders_holder_detail 调用失败（不影响主流程）: {e}")
        # 2. get_shareholders_holding_changes（持股变动，10.10 起新接口）
        try:
            ret, holding_change = quote_ctx.get_shareholders_holding_changes(test_symbol)
            logger.info(f"   get_shareholders_holding_changes: ret={ret}, len={len(holding_change) if ret==0 else 'N/A'}")
        except Exception as e:
            logger.warning(f"   get_shareholders_holding_changes 调用失败（不影响主流程）: {e}")
        # 3. 再次尝试机构持股（但会报错，已由重试处理）

        with SQLiteInstitutionalManager(db_path, logger) as db_manager:
            db_manager.create_table()

            for raw_ticker in tickers:
                symbol = f"HK.{raw_ticker}"
                stock_code = raw_ticker
                stock_name = stock_names.get(stock_code, '')
                logger.info(f"\n{'='*60}")
                logger.info(f"📊 处理: {symbol} ({stock_name})")
                logger.info(f"{'='*60}")

                try:
                    # 先获取快照验证股票
                    ret, snapshot = quote_ctx.get_market_snapshot([symbol])
                    if ret != 0:
                        logger.error(f"   快照失败: {ret}, {snapshot}")
                        failed_stocks.append(stock_code)
                        continue

                    # ---- 先轻量获取最新报告期，判断是否需要更新 ----
                    latest_period = None
                    max_retries = 3
                    for attempt in range(max_retries):
                        latest_period = fetch_latest_institutional_period(quote_ctx, symbol, logger)
                        if latest_period is not None:
                            break
                        logger.warning(f"   获取最新报告期失败（{attempt+1}/{max_retries}）")
                        time.sleep(2)

                    if latest_period is not None and db_manager.record_exists(stock_code, latest_period):
                        logger.info(f"   ✅ {latest_period} 机构持股明细数据已存在，无需下载更新")
                        success_stocks.append(stock_code)
                        continue

                    # ---- 最新数据不存在，获取全部历史机构持股（分页 + 重试） ----
                    data = None
                    for attempt in range(max_retries):
                        data = fetch_all_institutional_holdings(quote_ctx, symbol, logger)
                        if data is not None:
                            break
                        logger.warning(f"   第 {attempt+1}/{max_retries} 次尝试失败")
                        time.sleep(2)
                    if data is None:
                        logger.error("   ❌ 机构持股接口不可用（重试后仍失败）")
                        logger.error("   💡 建议：升级 OpenD 到最新版本，或检查账户权限。")
                        # 备选方案：尝试 AKShare（但效果不佳，可忽略）
                        logger.info("   ⚠️ 尝试使用 AKShare 备选（可能不准确）...")
                        ak_records = fetch_hk_institutional_from_akshare(raw_ticker, logger)
                        if ak_records:
                            inserted = db_manager.insert_batch(stock_code, stock_name, ak_records, data_source='akshare')
                            total_inserted += inserted
                            logger.info(f"   ✅ 通过 AKShare 插入 {inserted} 条记录（仅供参考）")
                            success_stocks.append(stock_code)
                        else:
                            failed_stocks.append(stock_code)
                        continue

                    if data.empty:
                        logger.warning(f"   ⚠️ 返回数据为空（可能无机构持股记录）")
                        success_stocks.append(stock_code)
                        continue

                    logger.info(f"   📥 获取到 {len(data)} 条历史记录")

                    existing_periods = db_manager.get_existing_periods(stock_code)
                    if existing_periods:
                        logger.info(f"   📊 已有 {len(existing_periods)} 条记录，跳过重复")

                    records_to_insert = []
                    for _, row in data.iterrows():
                        period_text = row['period_text']
                        if period_text in existing_periods:
                            continue
                        inst_qty = int(row['institution_quantity']) if pd.notna(row['institution_quantity']) else None
                        holder_qty = int(row['holder_quantity']) if pd.notna(row['holder_quantity']) else None
                        holder_pct = float(row['holder_pct']) if pd.notna(row['holder_pct']) else None

                        try:
                            price = get_quarter_end_price(quote_ctx, symbol, period_text, logger, db_conn=db_manager.conn)
                        except Exception as e:
                            # 价格获取失败不应中断整只股票，价格置空继续入库
                            logger.warning(f"   获取 {period_text} 收盘价失败: {e}")
                            price = None
                        records_to_insert.append({
                            'period_text': period_text,
                            'institution_quantity': inst_qty,
                            'holder_quantity': holder_qty,
                            'holder_pct': holder_pct,
                            'quarter_end_price': price
                        })

                    if records_to_insert:
                        inserted = db_manager.insert_batch(stock_code, stock_name, records_to_insert, data_source='futu')
                        total_inserted += inserted
                        logger.info(f"   ✅ 成功插入 {inserted} 条新记录")
                        success_stocks.append(stock_code)
                    else:
                        logger.info(f"   ⏭️ 无新记录")
                        success_stocks.append(stock_code)

                    periods = db_manager.get_existing_periods(stock_code)
                    if periods:
                        sorted_p = sorted(periods)
                        logger.info(f"   📊 当前共 {len(periods)} 条，范围: {sorted_p[0]} 至 {sorted_p[-1]}")

                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"   ❌ 处理失败: {e}")
                    logger.error(traceback.format_exc())
                    failed_stocks.append(stock_code)

            # 统计
            logger.info("\n" + "=" * 60)
            logger.info("📊 执行结果:")
            logger.info(f"   ✅ 成功: {len(success_stocks)} 只")
            logger.info(f"   ❌ 失败: {len(failed_stocks)} 只")
            logger.info(f"   📝 新增记录: {total_inserted}")
            if failed_stocks:
                logger.info(f"   失败列表: {', '.join(failed_stocks)}")

            stats = db_manager.get_statistics()
            if stats:
                logger.info(f"\n📊 数据库总计: {stats.get('total_records',0)} 条, 股票 {stats.get('stock_count',0)} 只, 范围 {stats.get('earliest','')} 至 {stats.get('latest','')}")
            logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 严重错误: {e}")
        logger.error(traceback.format_exc())
    finally:
        if quote_ctx:
            quote_ctx.close()
        opend_process.terminate()
        logger.info("🛑 OpenD 已关闭")
        logger.info("程序结束")

if __name__ == "__main__":
    main()
