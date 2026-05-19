import os

# backend 目录：E:\py_work\tdxplugins\backend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 项目根目录（tdxplugins）：E:\py_work\tdxplugins
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# 日志目录（项目根目录下的 logs 文件夹）
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# 数据库文件应放在 backend 的数据目录下
DATA_DIR = os.path.join(BASE_DIR, "data")

DB_PATH = os.path.join(DATA_DIR, "stock_data.db")

# 通达信插件路径
TDX_PLUGIN_PATH = os.environ.get("TDX_PLUGIN_PATH", "")

# CORS 允许的来源（生产环境应设置为前端域名）
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# 简单认证 token（可选，设置后需要带 X-API-Token 头）
API_TOKEN = os.environ.get("API_TOKEN", "")

TDX_CONFIG = {
    "limit_up_block": "JZZT",
    "multi_board_sector": "880785.SH",
}

REFRESH_INTERVAL_MINUTES = 10

FILTER_DEFAULT = {
    "min_pct_change": None,
    "max_pct_change": None,
    "min_amount": None,
    "min_volume": None,
    "min_score": None,
    "market": ["SH", "SZ"],
    "exclude_sectors": [],
    "include_sectors": [],
    "min_listing_days": 0,
    "is_mainboard_only": True,
    "exclude_st": True,
    "min_market_cap": 2000000000,
}

FORMULA_CATEGORIES = {
    "涨停类": [
        "5板以上",
        "4进5",
        "3进4",
        "2进3",
        "炸板反包",
    ],
    "跌停类": ["曾跌停", "跌停反转"],
    "趋势类": ["权重趋势"],
    "形态类": ["短庄起爆牛"],
    "其他": ["龙头股炸板"],
}

DEFAULT_ACTIVE_FORMULAS = ["3进4", "2进3", "5板以上", "4进5"]

FORMULA_COMBINE_MODES = ["or", "and"]
DEFAULT_COMBINE_MODE = "or"
