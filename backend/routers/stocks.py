# -*- coding: utf-8 -*-
# Startup migration: ensure market_cap column exists using sqlite3 (no engine dependency)
import logging
import sqlite3
import os
import config
logger = logging.getLogger(__name__)

def _ensure_market_cap_startup():
    try:
        db_path = getattr(config, 'DB_PATH', None)
        if not db_path or not os.path.exists(db_path):
            return
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(stocks)")
        cols = [r[1] for r in cur.fetchall()]
        if 'market_cap' not in cols:
            cur.execute("ALTER TABLE stocks ADD COLUMN market_cap REAL")
            conn.commit()
            logger.info("market_cap column added to stocks table (startup sqlite3 migration)")
        conn.close()
    except Exception as e:
        logger.debug(f"Startup sqlite3 market_cap migration failed: {e}")

_ensure_market_cap_startup()

"""
股票API路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import config
from models import Stock, StockMetrics, StockFormula, StockSector
from services.filter_service import apply_filter, get_active_filter

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/")
async def get_stocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    sort_by: str = Query("score", pattern="^(code|score|pct_change|amount|volume)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    min_pct_change: Optional[float] = None,
    max_pct_change: Optional[float] = None,
    min_amount: Optional[float] = None,
    min_score: Optional[float] = None,
    market: Optional[str] = None,
    is_mainboard: Optional[bool] = None,
    search: Optional[str] = None,
    formulas: Optional[str] = Query(None, description="按公式筛选（逗号分隔，OR 逻辑）"),
    sector: Optional[str] = None,
    block_type: Optional[str] = Query(None, description="按板块类型筛选（行业/概念/地区/风格/指数）"),
    db: Session = Depends(get_db),
):
    """获取股票列表（支持分页/排序/筛选）"""

    query = db.query(Stock).join(StockMetrics, Stock.code == StockMetrics.stock_code)

    if min_pct_change is not None:
        query = query.filter(StockMetrics.pct_change >= min_pct_change)

    if max_pct_change is not None:
        query = query.filter(StockMetrics.pct_change <= max_pct_change)

    if min_amount is not None:
        query = query.filter(StockMetrics.amount >= min_amount)

    if min_score is not None:
        query = query.filter(StockMetrics.score >= min_score)

    if market:
        query = query.filter(Stock.market == market)

    if is_mainboard is not None:
        query = query.filter(Stock.is_mainboard == is_mainboard)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Stock.code.like(search_pattern)) | (Stock.name.like(search_pattern))
        )

    # 按公式筛选（逗号分隔，OR 逻辑：任一公式匹配即返回）
    if formulas:
        formula_list = [f.strip() for f in formulas.split(",") if f.strip()]
        if formula_list:
            subquery = (
                db.query(StockFormula.stock_code)
                .filter(StockFormula.formula_name.in_(formula_list))
                .distinct()
                .subquery()
            )
            query = query.filter(Stock.code.in_(subquery))

    # 按板块名称筛选（兼容旧版 sectors 字段 LIKE 查询）
    if sector:
        query = query.filter(Stock.sectors.like(f"%{sector}%"))

    # 按板块类型筛选（从 stock_sectors 表查询）
    if block_type:
        type_subquery = (
            db.query(StockSector.stock_code)
            .filter(StockSector.block_type == block_type)
            .distinct()
            .subquery()
        )
        query = query.filter(Stock.code.in_(type_subquery))

    order_col = getattr(StockMetrics, sort_by, StockMetrics.score)
    if sort_order == "desc":
        query = query.order_by(order_col.desc())
    else:
        query = query.order_by(order_col.asc())

    total = query.count()
    offset = (page - 1) * page_size
    stocks = query.offset(offset).limit(page_size).all()

    result = []
    for s in stocks:
        metrics = (
            db.query(StockMetrics)
            .filter(StockMetrics.stock_code == s.code)
            .order_by(StockMetrics.trade_date.desc())
            .first()
        )

        # 获取公式来源
        # 只按当天筛选，确保显示最新的公式选股结果
        from common import get_today_str
        today = get_today_str()
        
        formulas = (
            db.query(StockFormula.formula_name)
            .filter(StockFormula.stock_code == s.code)
            .filter(StockFormula.trade_date == today)
            .distinct()
            .all()
        )
        formula_list = [f[0] for f in formulas]

        # 获取板块数据（按类型分组）
        sector_rows = (
            db.query(StockSector.block_name, StockSector.block_type)
            .filter(StockSector.stock_code == s.code)
            .all()
        )
        sectors_by_type = {}
        block_types = []
        for name, typ in sector_rows:
            if typ:
                if typ not in block_types:
                    block_types.append(typ)
                if typ not in sectors_by_type:
                    sectors_by_type[typ] = []
                if name not in sectors_by_type[typ]:
                    sectors_by_type[typ].append(name)

        result.append(
            {
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "market": s.market,
                "is_mainboard": s.is_mainboard,
                "listing_date": s.listing_date,
                "market_cap": getattr(s, 'market_cap', None),
                "sectors": getattr(s, 'sectors', None),
                "block_types": block_types,
                "sectors_by_type": sectors_by_type,
                "open": metrics.open if metrics else None,
                "high": metrics.high if metrics else None,
                "low": metrics.low if metrics else None,
                "close": metrics.close if metrics else None,
                "volume": metrics.volume if metrics else None,
                "amount": metrics.amount if metrics else None,
                "pct_change": metrics.pct_change if metrics else None,
                "momentum": metrics.momentum if metrics else None,
                "attack": metrics.attack if metrics else None,
                "pullback": metrics.pullback if metrics else None,
                "opening": metrics.opening if metrics else None,
                "support": metrics.support if metrics else None,
                "volume_div": metrics.volume_div if metrics else None,
                "score": metrics.score if metrics else None,
                "avg_score_8d": getattr(metrics, 'avg_score_8d', None) if metrics else None,
                "trade_date": metrics.trade_date if metrics else None,
                "formulas": formula_list,
            }
        )

    # Apply active filter on the in-memory results for direct dashboard control
    active_filter = get_active_filter(db)
    # Determine effective config: if active_filter contains {name, config}, use config; else use as-is
    effective_config = None
    if isinstance(active_filter, dict) and 'config' in active_filter:
        effective_config = active_filter['config']
        # Optionally use name for display later
        effective_name = active_filter.get('name')
    elif isinstance(active_filter, dict):
        effective_config = active_filter
        effective_name = active_filter.get('name', None)
    else:
        effective_config = config.FILTER_DEFAULT
        effective_name = None

    # 如果没有激活筛选，则使用默认筛选
    if not effective_config:
        effective_config = config.FILTER_DEFAULT
    filtered_result = apply_filter(result, effective_config)
    total_filtered = len(filtered_result)
    page_offset = (page - 1) * page_size
    data_page = filtered_result[page_offset: page_offset + page_size]

    return {
        "total": total_filtered,
        "page": page,
        "page_size": page_size,
        "data": data_page,
    }


@router.get("/{stock_code}")
async def get_stock(stock_code: str, db: Session = Depends(get_db)):
    """获取股票详情"""

    stock = db.query(Stock).filter(Stock.code == stock_code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")

    metrics_list = (
        db.query(StockMetrics)
        .filter(StockMetrics.stock_code == stock_code)
        .order_by(StockMetrics.trade_date.desc())
        .limit(30)
        .all()
    )

    return {
        "stock": {
            "id": stock.id,
            "code": stock.code,
            "name": stock.name,
            "market": stock.market,
            "is_mainboard": stock.is_mainboard,
            "listing_date": stock.listing_date,
            "sectors": getattr(stock, 'sectors', None),
            "block_types": [t[0] for t in db.query(StockSector.block_type).filter(StockSector.stock_code == stock_code).distinct().all() if t[0]],
        },
        "metrics": [
            {
                "trade_date": m.trade_date,
                "open": m.open,
                "high": m.high,
                "low": m.low,
                "close": m.close,
                "volume": m.volume,
                "amount": m.amount,
                "pct_change": m.pct_change,
                "momentum": m.momentum,
                "attack": m.attack,
                "pullback": m.pullback,
                "opening": m.opening,
                "support": m.support,
                "volume_div": m.volume_div,
                "score": m.score,
                "avg_score_8d": getattr(m, 'avg_score_8d', None),
            }
            for m in metrics_list
        ],
    }


@router.get("/filter-options/options")
async def get_filter_options(db: Session = Depends(get_db)):
    """获取筛选选项"""

    markets = db.query(Stock.market).distinct().all()
    market_list = [m[0] for m in markets if m[0]]

    score_stats = (
        db.query(StockMetrics.score).filter(StockMetrics.score.isnot(None)).all()
    )
    scores = [s[0] for s in score_stats if s[0]]
    score_max = max(scores) if scores else 100
    score_min = min(scores) if scores else 0

    amount_stats = (
        db.query(StockMetrics.amount).filter(StockMetrics.amount.isnot(None)).all()
    )
    amounts = [a[0] for a in amount_stats if a[0]]
    amount_max = max(amounts) if amounts else 1000000000

    return {
        "markets": market_list,
        "score_range": {"min": score_min, "max": score_max},
        "amount_range": {"min": 0, "max": amount_max},
    }


@router.get("/sectors/list")
async def get_sectors_list(db: Session = Depends(get_db)):
    """获取所有板块列表（按类型分组）"""
    # 从 stock_sectors 表查询所有板块名称和类型
    rows = db.query(StockSector.block_name, StockSector.block_type).distinct().all()

    # 按类型分组
    by_type = {}
    all_names = set()
    for name, typ in rows:
        if name:
            all_names.add(name)
            if typ:
                if typ not in by_type:
                    by_type[typ] = []
                if name not in by_type[typ]:
                    by_type[typ].append(name)

    # 额外兼容：从旧 sectors 字段提取（覆盖未被 stock_sectors 收录的）
    old_rows = db.query(Stock.sectors).filter(Stock.sectors.isnot(None)).all()
    for r in old_rows:
        if r[0]:
            for sector in r[0].split(','):
                s = sector.strip()
                if s and s not in all_names:
                    all_names.add(s)
                    if "其他" not in by_type:
                        by_type["其他"] = []
                    by_type["其他"].append(s)

    sorted_by_type = {k: sorted(v) for k, v in sorted(by_type.items())}
    all_flat = sorted(all_names)

    return {
        "sectors": all_flat,
        "by_type": sorted_by_type,
        "types": list(sorted(by_type.keys())),
    }


@router.get("/stats/summary")
async def get_stock_stats(db: Session = Depends(get_db)):
    """获取股票统计信息"""

    total_stocks = db.query(Stock).count()
    stocks_with_metrics = db.query(StockMetrics.stock_code).distinct().count()

    latest_date = (
        db.query(StockMetrics.trade_date)
        .order_by(StockMetrics.trade_date.desc())
        .first()
    )

    up_count = 0
    limit_up_count = 0
    if latest_date:
        up_count = (
            db.query(StockMetrics)
            .filter(
                StockMetrics.trade_date == latest_date[0], StockMetrics.pct_change > 0
            )
            .count()
        )
        limit_up_count = (
            db.query(StockMetrics)
            .filter(
                StockMetrics.trade_date == latest_date[0],
                StockMetrics.pct_change >= 9.9,
            )
            .count()
        )

    return {
        "total_stocks": total_stocks,
        "stocks_with_metrics": stocks_with_metrics,
        "latest_date": latest_date[0] if latest_date else None,
        "up_count": up_count,
        "limit_up_count": limit_up_count,
    }
