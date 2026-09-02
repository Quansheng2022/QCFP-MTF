-- 1. 创建新表，列名全部改为小写
CREATE TABLE hk_hist_daily_kline_new (
    id             INTEGER,
    stock_code     TEXT,
    stock_name     TEXT,
    date           TEXT,
    open           REAL,
    high           REAL,
    low            REAL,
    close          REAL,
    volume         REAL,
    amount         REAL,
    amplitude      REAL,
    change_percent REAL,
    change_amount  REAL,
    turnover_rate  REAL,
    previous_close REAL,
    PRIMARY KEY (id)
);

-- 2. 复制数据到新表（注意列名映射）
INSERT INTO hk_hist_daily_kline_new (
    id,
    stock_code,
    stock_name,
    date,
    open,
    high,
    low,
    close,
    volume,
    amount,
    amplitude,
    change_percent,
    change_amount,
    turnover_rate,
    previous_close
)
SELECT 
    id,
    stock_code,
    stock_name,
    date,
    Open,
    High,
    Low,
    Close,
    Volume,
    Amount,
    Amplitude,
    Change_Percent,
    Change_Amount,
    Turnover_Rate,
    Previous_Close
FROM hk_hist_daily_kline;

-- 3. 删除旧表
DROP TABLE hk_hist_daily_kline;

-- 4. 重命名新表
ALTER TABLE hk_hist_daily_kline_new RENAME TO hk_hist_daily_kline;

-- 5. 创建索引
CREATE INDEX idx_hk_hist_daily_kline ON hk_hist_weekly_kline(stock_code, date);