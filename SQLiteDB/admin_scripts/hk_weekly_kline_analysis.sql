BEGIN;

-- 创建新表
CREATE TABLE hk_weekly_kline_analysis_new (
    id                 INTEGER,
    stock_code         TEXT    NOT NULL,
    stock_name         TEXT    NOT NULL,
    date               TEXT    NOT NULL,
    open               REAL,
    high               REAL,
    low                REAL,
    close              REAL,
    volume             REAL,
    amount             REAL,
    turnover_rate      REAL,
    amplitude          REAL,
    change_percent     REAL,
    change_amount      REAL,
    ema5               REAL,
    ema10              REAL,
    ema20              REAL,
    ema50              REAL,
    ema100             REAL,
    ema200             REAL,
    macd_dif           REAL,
    macd_signal        REAL,
    macd_histogram     REAL,
    ema5_10_status     TEXT,
    ema5_10_streak     INTEGER,
    ema5_20_status     TEXT,
    ema5_20_streak     INTEGER,
    ema10_50_status    TEXT,
    ema10_50_streak    INTEGER,
    ema20_50_status    TEXT,
    ema20_50_streak    INTEGER,
    golden_triangle    INTEGER,
    death_triangle     INTEGER,
    macd_cross         REAL,
    macd_status        REAL,
    macd_golden_streak REAL,
    macd_death_streak  REAL,
    kdj_k              REAL,
    kdj_d              REAL,
    kdj_j              REAL,
    vol_ema5           REAL,
    volume_ratio       REAL,
    gain               REAL,
    loss               REAL,
    avg_gain           REAL,
    avg_loss           REAL,
    rs                 REAL,
    rsi14              REAL,
    PRIMARY KEY (id)
);

-- 复制数据
INSERT INTO hk_weekly_kline_analysis_new (
    id, stock_code, stock_name, date, open, high, low, close,
    volume, amount, turnover_rate, amplitude, change_percent, change_amount,
    ema5, ema10, ema20, ema50, ema100, ema200,
    macd_dif, macd_signal, macd_histogram,
    ema5_10_status, ema5_10_streak,
    ema5_20_status, ema5_20_streak,
    ema10_50_status, ema10_50_streak,
    ema20_50_status, ema20_50_streak,
    golden_triangle, death_triangle,
    macd_cross, macd_status, macd_golden_streak, macd_death_streak,
    kdj_k, kdj_d, kdj_j,
    vol_ema5, volume_ratio,
    gain, loss, avg_gain, avg_loss, rs, rsi14
)
SELECT 
    id, stock_code, stock_name, date, Open, High, Low, Close,
    Volume, Amount, Turnover_Rate, Amplitude, Change_Percent, Change_Amount,
    EMA5, EMA10, EMA20, EMA50, EMA100, EMA200,
    MACD_DIF, MACD_Signal, MACD_Histogram,
    EMA5_10_Status, EMA5_10_Streak,
    EMA5_20_Status, EMA5_20_Streak,
    EMA10_50_Status, EMA10_50_Streak,
    EMA20_50_Status, EMA20_50_Streak,
    Golden_Triangle, Death_Triangle,
    MACD_Cross, MACD_Status, MACD_Golden_Streak, MACD_Death_Streak,
    KDJ_K, KDJ_D, KDJ_J,
    VOL_EMA5, Volume_Ratio,
    Gain, Loss, AvgGain, AvgLoss, RS, RSI14
FROM hk_weekly_kline_analysis;

-- 删除旧表
DROP TABLE hk_weekly_kline_analysis;

-- 重命名新表
ALTER TABLE hk_weekly_kline_analysis_new RENAME TO hk_weekly_kline_analysis;

COMMIT;
-- 5. 创建索引
CREATE INDEX idx_hk_weekly_kline_analysis ON hk_weekly_kline_analysis(stock_code, date);