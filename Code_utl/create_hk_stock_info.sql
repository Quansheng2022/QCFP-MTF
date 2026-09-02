-- create_hk_stock_info.sql
-- 创建港股股票信息表

CREATE TABLE IF NOT EXISTS hk_stock_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL UNIQUE,
    stock_name TEXT NOT NULL,
    sector TEXT,
    market TEXT DEFAULT 'HKEX',
    stock_type TEXT DEFAULT 'stock',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_hk_stock_info_code ON hk_stock_info(stock_code);
CREATE INDEX IF NOT EXISTS idx_hk_stock_info_sector ON hk_stock_info(sector);

-- 添加注释（SQLite不支持COMMENT，这里仅作文档说明）
-- 表说明：存储港股股票基本信息
-- code: 股票代码
-- name: 股票名称
-- sector: 行业板块
-- market: 交易市场
-- stock_type: 股票类型（stock/ETF等）
-- is_active: 是否活跃（1:活跃，0:停牌/退市）
