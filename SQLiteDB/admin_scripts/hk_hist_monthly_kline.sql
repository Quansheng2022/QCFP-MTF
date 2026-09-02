BEGIN;

-- 创建新表
CREATE TABLE hk_hist_monthly_kline_new (
    id             INTEGER,
    stock_code     TEXT    NOT NULL,
    stock_name     TEXT    NOT NULL,
    date           TEXT    NOT NULL,
    open           REAL,
    high           REAL,
    low            REAL,
    close          REAL,
    volume         REAL,
    amount         REAL,
    turnover_rate  REAL,
    amplitude      REAL,
    change_amount  REAL,
    change_percent REAL,
    ema5           REAL,
    ema10          REAL,
    ema20          REAL,
    ema50          REAL,
    ema100         REAL,
    ema200         REAL,
    macd_dif       REAL,
    macd_signal    REAL,
    macd_histogram REAL,
    PRIMARY KEY (id)
);

-- 复制数据
INSERT INTO hk_hist_monthly_kline_new (
    id, stock_code, stock_name, date, open, high, low, close,
    volume, amount, turnover_rate, amplitude, change_amount,
    change_percent, ema5, ema10, ema20, ema50, ema100, ema200,
    macd_dif, macd_signal, macd_histogram
)
SELECT 
    id, stock_code, stock_name, date, Open, High, Low, Close,
    Volume, Amount, Turnover_Rate, Amplitude, Change_Amount,
    Change_Percent, EMA5, EMA10, EMA20, EMA50, EMA100, EMA200,
    MACD_DIF, MACD_Signal, MACD_Histogram
FROM hk_hist_monthly_kline;

-- 删除旧表
DROP TABLE hk_hist_monthly_kline;

-- 重命名新表
ALTER TABLE hk_hist_monthly_kline_new RENAME TO hk_hist_monthly_kline;

COMMIT;

-- 5. 创建索引
CREATE INDEX idx_hk_hist_monthly_kline ON hk_hist_monthly_kline(stock_code, date);