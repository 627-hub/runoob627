from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, Float, DateTime, Index, Boolean, Date
from datetime import datetime

Base = declarative_base()


class Stock(Base):
    __tablename__ = 'stocks'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, unique=True)
    name = Column(String(50))
    market = Column(String(10))
    is_mainboard = Column(Boolean, default=True)
    listing_date = Column(String(10))
    market_cap = Column(Float)
    sectors = Column(String(500))
    
    __table_args__ = (
        Index("ix_stock_code", "code", unique=True),
    )


class StockMetrics(Base):
    __tablename__ = 'stock_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False)
    trade_date = Column(String(10), nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    amount = Column(Float)
    pct_change = Column(Float)
    momentum = Column(Float)
    attack = Column(Float)
    pullback = Column(Float)
    opening = Column(Float)
    support = Column(Float)
    volume_div = Column(Float)
    score = Column(Float)
    avg_score_8d = Column(Float)
    created_at = Column(String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    __table_args__ = (
        Index("ix_stock_date", "stock_code", "trade_date", unique=True),
    )


class StockFormula(Base):
    __tablename__ = 'stock_formulas'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False)
    formula_name = Column(String(100), nullable=False)
    trade_date = Column(String(10), nullable=False)
    created_at = Column(String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    __table_args__ = (
        Index("ix_formula_stock_date", "stock_code", "formula_name", "trade_date", unique=True),
    )


class UserFilter(Base):
    __tablename__ = 'user_filters'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    config = Column(String(1000))
    is_active = Column(Boolean, default=False)
    created_at = Column(String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class UserFormula(Base):
    __tablename__ = 'user_formulas'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    formula = Column(String(1000))
    category = Column(String(50))
    formula_arg = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at = Column(String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class StockSector(Base):
    """股票板块关联表（规范化存储，支持按类型筛选）"""
    __tablename__ = 'stock_sectors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, index=True)
    block_code = Column(String(20))
    block_name = Column(String(100), nullable=False)
    block_type = Column(String(20))  # 行业/概念/地区/风格/指数
    trade_date = Column(String(10))

    __table_args__ = (
        Index("ix_sector_stock_type", "stock_code", "block_type"),
        Index("ix_sector_name", "block_name"),
    )


class RefreshLog(Base):
    __tablename__ = 'refresh_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100))
    status = Column(String(20))
    details = Column(String(500))
    started_at = Column(String(30))
    created_at = Column(String(30), default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))