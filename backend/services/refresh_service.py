# -*- coding: utf-8 -*-
"""
数据刷新服务 - 使用选股公式
"""

import logging
import os
import json
import traceback
import threading
from datetime import datetime
from typing import Optional, List, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import get_session
from models import Stock, StockMetrics, RefreshLog, StockFormula, StockSector
from services.tdx_service import (
    TDXService,
    process_market_data,
)
from services.formulas_service import (
    get_active_formulas,
    get_combine_mode,
    save_stock_formula,
    init_default_formulas,
    get_all_available_formulas,
)
from common import is_mainboard_stock, get_today_str
import config

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

REFRESH_JOB_ID = "data_refresh"


def _save_sectors(session, stock_code, trade_date):
    """保存板块数据到 stock_sectors 表（先查，查到再删旧插新，查不到保留原数据）"""
    try:
        sectors_list = TDXService.get_stock_sectors(stock_code)
        if not sectors_list:
            return
        # 查到有效数据后，再删旧插新
        session.query(StockSector).filter(StockSector.stock_code == stock_code).delete()
        for s in sectors_list:
            record = StockSector(
                stock_code=stock_code,
                block_code=str(s.get("BlockCode", "")),
                block_name=s.get("BlockName", ""),
                block_type=s.get("BlockType", ""),
                trade_date=trade_date,
            )
            session.add(record)
        sectors_str = ",".join([s.get("BlockName", "") for s in sectors_list if s.get("BlockName")])
        stock_obj = session.query(Stock).filter(Stock.code == stock_code).first()
        if stock_obj:
            stock_obj.sectors = sectors_str
    except Exception as e:
        logger.debug(f"保存板块数据失败 {stock_code}: {e}")


last_refresh_status = {
    "running": False,
    "last_run": None,
    "last_status": None,
    "stock_count": 0,
    "formulas_count": 0,
    "formulas_used": [],
    "error": None,
}
# 添加线程锁防止并发调用
_refresh_lock = threading.Lock()


async def refresh_stock_data():
    """刷新股票数据 - 使用选股公式"""
    global last_refresh_status

    if last_refresh_status["running"]:
        logger.warning("数据刷新正在进行中，跳过本次刷新")
        return {"status": "skipped", "reason": "refresh_in_progress"}

    last_refresh_status["running"] = True
    last_refresh_status["last_run"] = datetime.now().isoformat()
    last_refresh_status["error"] = None

    session = get_session()
    started_at = datetime.now().isoformat()

    # 1) Ensure market_cap column exists using sqlite3 migration (avoid engine dependency)
    def _ensure_market_cap_column():
        try:
            import sqlite3
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
                logger.info("market_cap column added to stocks table (sqlite3 migration)")
            conn.close()
        except Exception as _e:
            logger.debug(f"Market cap column migration failed: {_e}")
    _ensure_market_cap_column()

    # 检查数据库是否已是最新交易日，避免重复刷新
    trade_date = get_today_str()
    try:
        # 先查 StockMetrics 表
        latest_metrics = session.query(StockMetrics.trade_date).order_by(StockMetrics.trade_date.desc()).first()
        latest_db_date = latest_metrics[0] if latest_metrics else None
        # 如果 StockMetrics 没有数据，再查 StockFormula 表（可能上次刷新中途失败）
        if latest_db_date is None:
            latest_formula = session.query(StockFormula.trade_date).order_by(StockFormula.trade_date.desc()).first()
            formula_date = latest_formula[0] if latest_formula else None
            if formula_date:
                logger.warning(f"交易日检查：StockMetrics 无数据，但 StockFormula 最新日期={formula_date}（上次刷新可能中途失败）")
        logger.info(f"交易日检查：DB 最新日期={latest_db_date}, 今日={trade_date}")
        if latest_db_date:
            sh_dates = TDXService.get_trading_dates(market="SH", count=1)
            sz_dates = TDXService.get_trading_dates(market="SZ", count=1)
            logger.info(f"交易日检查：通达信 SH={sh_dates}, SZ={sz_dates}")
            all_latest = [d for d in (sh_dates or []) + (sz_dates or []) if d]
            if all_latest:
                latest_tdx_date = max(all_latest)
                logger.info(f"交易日检查：最新 TDX 交易日={latest_tdx_date}")
                if latest_db_date >= latest_tdx_date:
                    logger.info(f"数据库交易日 {latest_db_date} >= 最新交易日 {latest_tdx_date}，跳过刷新")
                    last_refresh_status["last_status"] = "skipped"
                    last_refresh_status["last_run"] = datetime.now().isoformat()
                    last_refresh_status["running"] = False
                    return {"status": "skipped", "reason": f"数据已是最新交易日 {latest_db_date}"}
            else:
                logger.info("交易日检查：通达信未返回交易日数据，跳过检查继续刷新")
        else:
            logger.info("交易日检查：DB 无历史数据，跳过检查继续刷新")
    except Exception as e:
        logger.warning(f"交易日检查失败，继续刷新: {e}")

    # 2) 增量更新：只清除当天的指标数据和公式标注，保留历史
    try:
        # 只删除当天的公式标注和指标数据，实现增量更新
        formula_deleted = session.query(StockFormula).filter(StockFormula.trade_date == trade_date).delete(synchronize_session=False)
        metrics_deleted = session.query(StockMetrics).filter(StockMetrics.trade_date == trade_date).delete(synchronize_session=False)
        session.commit()
        logger.info(f"已清除 {trade_date} 的旧数据（StockFormula={formula_deleted}行，StockMetrics={metrics_deleted}行），准备增量更新")
    except Exception as e:
        logger.warning(f"清除旧数据失败: {e}")
        session.rollback()

    # Remove: 不再每次刷新时重置公式，使用用户保存的公式配置
    # init_default_formulas(session)

    log = RefreshLog(started_at=started_at, status="running")
    session.add(log)
    session.commit()
    log_id = log.id

    try:
        # 清除历史中的 UPn 筛股数据，确保每次刷新只保留当前激活的公式结果
        session.query(StockFormula).filter(StockFormula.formula_name == "UPN").delete(synchronize_session=False)
        session.commit()
        
        # 开始主刷新事务
        logger.info("=" * 30)
        logger.info("开始刷新股票数据...")
        logger.info("=" * 30)

        # 1. 获取所有可用公式（全量刷新，确保所有公式数据在 DB 中）
        all_formulas = get_all_available_formulas()
        # 同时保留原 get_active_formulas 用于记录哪些公式被用户激活（仍写 stock_formulas）
        user_active_formulas = get_active_formulas(session)
        combine_mode = get_combine_mode(session)
        logger.info(f"全量公式数: {len(all_formulas)}, 用户激活数: {len(user_active_formulas)}")
        logger.info(f"TDXService._initialized: {TDXService._initialized}")

        # 2. 使用全量公式选股获取候选股票
        candidate_stocks = {}

        logger.info("正在使用全量公式选股...")
        formula_result = TDXService.run_multiple_formulas(all_formulas, combine_mode="or")
        logger.info(f"全量公式选股结果: {formula_result.get('total', 0)} 只")

        stocks_result = formula_result.get("stocks", {})
        if stocks_result:
            for code, formulas_list in stocks_result.items():
                candidate_stocks[code] = formulas_list
            logger.info(f"全量公式选股获取候选股票: {len(candidate_stocks)} 只")

        # 备选：如果公式选股失败，使用涨停股板块
        if not candidate_stocks:
            logger.warning("公式选股无结果，尝试使用涨停股板块作为备选")
            limit_up_stocks = TDXService.get_limit_up_stocks()
            if limit_up_stocks:
                for s in limit_up_stocks:
                    code = s.get("Code", "")
                    if code and code not in candidate_stocks:
                        candidate_stocks[code] = ["JZZT"]
                logger.info(f"涨停股板块获取成功: {len(candidate_stocks)} 只")

        if not candidate_stocks:
            raise Exception("公式选股失败，无候选股票")

        stock_codes = list(candidate_stocks.keys())
        logger.info(f"候选股票: {len(stock_codes)} 只")

        if len(stock_codes) > 200:
            stock_codes = stock_codes[:200]
            logger.info(f"限制为前200只股票")

        # 3. 获取市场数据（获取20天数据以计算8日平均评分）
        logger.info("正在获取市场数据...")
        data = TDXService.get_market_data(stock_codes, days=20)
        logger.info(
            f"市场数据返回: {type(data)}, keys: {list(data.keys()) if data else 'None'}"
        )

        if not data:
            raise Exception("获取行情数据失败")

        # 4. 计算指标（使用8天计算8日平均评分）
        logger.info("正在计算指标...")
        metrics_dict = process_market_data(data, stock_codes, days=8)
        logger.info(f"计算指标完成: {len(metrics_dict)} 只")

        stocks_updated = 0
        metrics_updated = 0
        trade_date = get_today_str()

        # 5. 存储数据 - 只存储有指标数据的股票
        stocks_to_save = [s for s in stock_codes if s in metrics_dict]
        logger.info(f"有指标数据的股票: {len(stocks_to_save)} 只")

        for stock_code in stocks_to_save:
            stock_code = stock_code.strip()
            formulas_list = candidate_stocks.get(stock_code, ["JZZT"])
            metrics = metrics_dict.get(stock_code, {})

            # 5.1 存储股票基本信息
            existing_stock = (
                session.query(Stock).filter(Stock.code == stock_code).first()
            )

            if not existing_stock:
                market = "SH" if stock_code.endswith(".SH") else "SZ"
                listing_date = None
                stock_info = TDXService.get_stock_info(stock_code)
                if stock_info:
                    listing_date = stock_info.get("J_start", "")
                
                # Get market_cap using TDX get_gb_info
                stock_cap_value = None
                try:
                    import sqlite3, os
                    db_path = getattr(config, 'DB_PATH', None)
                    if db_path and os.path.exists(db_path):
                        conn = sqlite3.connect(db_path)
                        cur = conn.cursor()
                        cur.execute("PRAGMA table_info(stocks)")
                        cols = [r[1] for r in cur.fetchall()]
                        if 'market_cap' in cols:
                            market_cap = TDXService.get_market_cap(stock_code)
                            if market_cap and market_cap > 0:
                                stock_cap_value = market_cap
                        conn.close()
                except Exception:
                    pass
                
                new_stock = Stock(
                    code=stock_code,
                    name=stock_info.get("Name", "") if stock_info else "",
                    market=market,
                    is_mainboard=is_mainboard_stock(stock_code),
                    listing_date=listing_date,
                    sectors="",
                )
                if stock_cap_value is not None:
                    try:
                        new_stock.market_cap = stock_cap_value
                    except Exception:
                        pass
                session.add(new_stock)
                session.flush()
                # 写入板块数据（此时 stock 行已存在，_save_sectors 能更新 stock.sectors）
                _save_sectors(session, stock_code, trade_date)
                stocks_updated += 1
            else:
                if not existing_stock.name and not existing_stock.listing_date:
                    stock_info = TDXService.get_stock_info(stock_code)
                    if stock_info:
                        existing_stock.name = stock_info.get("Name", "")
                        existing_stock.listing_date = stock_info.get("J_start", "")
                
                # 更新板块信息到 stock_sectors 表（每次刷新都更新）
                _save_sectors(session, stock_code, trade_date)

            # 5.2 存储指标数据
            close = metrics.get("close") or metrics.get("momentum")
            high = metrics.get("high") or metrics.get("attack")
            low = metrics.get("low") or metrics.get("pullback")
            open_price = metrics.get("open") or metrics.get("opening")

            existing_metrics = (
                session.query(StockMetrics)
                .filter(
                    StockMetrics.stock_code == stock_code,
                    StockMetrics.trade_date == trade_date,
                )
                .first()
            )

            if existing_metrics:
                existing_metrics.open = open_price
                existing_metrics.high = high
                existing_metrics.low = low
                existing_metrics.close = close
                existing_metrics.volume = metrics.get("volume")
                existing_metrics.amount = metrics.get("amount")
                existing_metrics.pct_change = metrics.get("pct_change") if metrics.get("pct_change") is not None else None
                existing_metrics.momentum = metrics.get("momentum")
                existing_metrics.attack = metrics.get("attack")
                existing_metrics.pullback = metrics.get("pullback")
                existing_metrics.opening = metrics.get("opening")
                existing_metrics.support = metrics.get("support")
                existing_metrics.volume_div = metrics.get("volume_div")
                existing_metrics.score = metrics.get("score")
                existing_metrics.avg_score_8d = metrics.get("avg_score_8d")
            else:
                new_metrics = StockMetrics(
                    stock_code=stock_code,
                    trade_date=trade_date,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=metrics.get("volume"),
                    amount=metrics.get("amount"),
                    pct_change=metrics.get("pct_change") if metrics.get("pct_change") is not None else None,
                    momentum=metrics.get("momentum"),
                    attack=metrics.get("attack"),
                    pullback=metrics.get("pullback"),
                    opening=metrics.get("opening"),
                    support=metrics.get("support"),
                    volume_div=metrics.get("volume_div"),
                    score=metrics.get("score"),
                    avg_score_8d=metrics.get("avg_score_8d"),
                )
                session.add(new_metrics)

            metrics_updated += 1

            # 5.3 存储公式来源
            for formula_name in formulas_list:
                save_stock_formula(session, stock_code, formula_name, trade_date)

        session.commit()

        # 6) 从 DB 查询历史评分，滚动计算 avg_score_8d
        from sqlalchemy import func
        avg_updated = 0
        for stock_code in stocks_to_save:
            past_scores = session.query(StockMetrics.score).filter(
                StockMetrics.stock_code == stock_code,
                StockMetrics.trade_date < trade_date,
                StockMetrics.score.isnot(None),
            ).order_by(StockMetrics.trade_date.desc()).limit(8).all()
            valid = [s[0] for s in past_scores if s[0] is not None]
            if valid:
                avg = round(sum(valid) / len(valid), 2)
                session.query(StockMetrics).filter(
                    StockMetrics.stock_code == stock_code,
                    StockMetrics.trade_date == trade_date,
                ).update({"avg_score_8d": avg}, synchronize_session=False)
                avg_updated += 1
        if avg_updated:
            session.commit()
            logger.info(f"DB 历史评分滚动平均完成: {avg_updated} 只")

        log_obj = session.query(RefreshLog).filter(RefreshLog.id == log_id).first()
        if log_obj:
            log_obj.completed_at = datetime.now().isoformat()
            log_obj.stock_count = metrics_updated
            log_obj.status = "success"
            session.commit()

        last_refresh_status["last_status"] = "success"
        last_refresh_status["stock_count"] = metrics_updated
        last_refresh_status["formulas_count"] = len(all_formulas)
        last_refresh_status["formulas_used"] = [f["name"] for f in all_formulas]
        last_refresh_status["running"] = False

        logger.info(
            f"数据刷新完成: {metrics_updated} 只股票, 使用 {len(all_formulas)} 个公式"
        )

        return {
            "status": "success",
            "stock_count": metrics_updated,
            "formulas_count": len(all_formulas),
            "formulas_used": [f["name"] for f in all_formulas],
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
        }

    except Exception as e:
        import traceback

        logger.error(f"数据刷新失败: {e}")
        logger.error(traceback.format_exc())
        logger.error(f"TDXService._initialized = {TDXService._initialized}")

        # 回滚事务
        try:
            session.rollback()
        except Exception as rollback_err:
            logger.error(f"回滚事务失败: {rollback_err}")

        log_obj = session.query(RefreshLog).filter(RefreshLog.id == log_id).first()
        if log_obj:
            log_obj.completed_at = datetime.now().isoformat()
            log_obj.status = "failed"
            log_obj.error_message = str(e)
            try:
                session.commit()
            except Exception:
                pass

        last_refresh_status["last_status"] = "failed"
        last_refresh_status["error"] = str(e)
        last_refresh_status["running"] = False

        return {
            "status": "failed",
            "error": str(e),
        }
    finally:
        session.close()


def start_scheduler():
    """启动定时任务"""
    scheduler.add_job(
        refresh_stock_data,
        "interval",
        minutes=config.REFRESH_INTERVAL_MINUTES,
        id=REFRESH_JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"定时刷新任务已启动，每 {config.REFRESH_INTERVAL_MINUTES} 分钟执行一次"
    )


def stop_scheduler():
    """停止定时任务"""
    scheduler.shutdown()
    logger.info("定时刷新任务已停止")


def get_refresh_status() -> Dict:
    """获取刷新状态"""
    return last_refresh_status.copy()


def trigger_manual_refresh():
    """手动触发刷新（带线程锁防止并发）"""
    import asyncio

    # 使用线程锁防止并发调用
    if not _refresh_lock.acquire(blocking=False):
        logger.warning("数据刷新正在进行中，跳过本次刷新")
        return {"status": "skipped", "reason": "refresh_in_progress"}

    try:
        result = asyncio.run(refresh_stock_data())
        return result
    except Exception as e:
        # 重新抛出异常，让调用者处理
        raise e
    finally:
        _refresh_lock.release()


async def refresh_formula_selections_only():
    """轻量级刷新：公式选股 + 获取行情数据 + 计算指标（包括8日评分）+ 保存板块"""
    global last_refresh_status

    if last_refresh_status["running"]:
        logger.warning("数据刷新正在进行中，跳过本次刷新")
        return {"status": "skipped", "reason": "refresh_in_progress"}

    last_refresh_status["running"] = True
    last_refresh_status["last_run"] = datetime.now().isoformat()
    last_refresh_status["error"] = None

    session = get_session()
    started_at = datetime.now().isoformat()

    log = RefreshLog(started_at=started_at, status="running")
    session.add(log)
    session.commit()
    log_id = log.id

    try:
        logger.info("=" * 30)
        logger.info("开始轻量级刷新：公式选股 + 行情数据 + 指标计算")
        logger.info("=" * 30)

        # 1. 获取用户启用的公式
        active_formulas = get_active_formulas(session)
        combine_mode = get_combine_mode(session)
        logger.info(f"active_formulas: {active_formulas}")
        logger.info(f"combine_mode: {combine_mode}")

        if not active_formulas:
            raise Exception("没有激活的公式")

        # 2. 使用公式选股
        logger.info("正在使用公式选股...")
        formula_result = TDXService.run_multiple_formulas(active_formulas, combine_mode)
        logger.info(f"公式选股结果: {formula_result.get('total', 0)} 只")

        stocks_result = formula_result.get("stocks", {})
        if not stocks_result:
            raise Exception("公式选股失败，无候选股票")

        stock_codes = list(stocks_result.keys())
        logger.info(f"候选股票: {len(stock_codes)} 只")

        # 3. 获取市场数据（获取10天数据以计算8日平均评分）
        logger.info("正在获取市场数据...")
        data = TDXService.get_market_data(stock_codes, days=10)
        logger.info(f"市场数据返回: {type(data)}, keys: {list(data.keys()) if data else 'None'}")

        if not data:
            raise Exception("获取行情数据失败")

        # 4. 计算指标（使用8天计算8日平均评分）
        logger.info("正在计算指标...")
        metrics_dict = process_market_data(data, stock_codes, days=8)
        logger.info(f"计算指标完成: {len(metrics_dict)} 只")

        trade_date = get_today_str()

        # 5. 清除当天的公式标注和指标数据
        session.query(StockFormula).filter(StockFormula.trade_date == trade_date).delete(synchronize_session=False)
        session.query(StockMetrics).filter(StockMetrics.trade_date == trade_date).delete(synchronize_session=False)
        session.commit()
        logger.info(f"已清除 {trade_date} 的旧数据")

        # 6. 存储数据
        stocks_updated = 0
        metrics_updated = 0

        for stock_code in stock_codes:
            stock_code = stock_code.strip()
            formulas_list = stocks_result.get(stock_code, [])
            metrics = metrics_dict.get(stock_code, {})

            # 6.1 存储股票基本信息（如果不存在则创建，并更新板块）
            existing_stock = session.query(Stock).filter(Stock.code == stock_code).first()

            if not existing_stock:
                market = "SH" if stock_code.endswith(".SH") else "SZ"
                listing_date = None
                stock_info = TDXService.get_stock_info(stock_code)
                if stock_info:
                    listing_date = stock_info.get("J_start", "")

                # 获取板块信息写入 stock_sectors 表
                _save_sectors(session, stock_code, trade_date)

                new_stock = Stock(
                    code=stock_code,
                    name=stock_info.get("Name", "") if stock_info else "",
                    market=market,
                    is_mainboard=is_mainboard_stock(stock_code),
                    listing_date=listing_date,
                    sectors="",
                )
                session.add(new_stock)
                session.flush()
                # 写入板块数据（此时 stock 行已存在）
                _save_sectors(session, stock_code, trade_date)
                stocks_updated += 1
            else:
                # 每次刷新都更新板块信息
                _save_sectors(session, stock_code, trade_date)

            # 6.2 存储指标数据（如果有）
            if metrics:
                close = metrics.get("close") or metrics.get("momentum")
                high = metrics.get("high") or metrics.get("attack")
                low = metrics.get("low") or metrics.get("pullback")
                open_price = metrics.get("open") or metrics.get("opening")

                existing_metrics = (
                    session.query(StockMetrics)
                    .filter(
                        StockMetrics.stock_code == stock_code,
                        StockMetrics.trade_date == trade_date,
                    )
                    .first()
                )

                if existing_metrics:
                    existing_metrics.open = open_price
                    existing_metrics.high = high
                    existing_metrics.low = low
                    existing_metrics.close = close
                    existing_metrics.volume = metrics.get("volume")
                    existing_metrics.amount = metrics.get("amount")
                    existing_metrics.pct_change = metrics.get("pct_change") if metrics.get("pct_change") is not None else None
                    existing_metrics.momentum = metrics.get("momentum")
                    existing_metrics.attack = metrics.get("attack")
                    existing_metrics.pullback = metrics.get("pullback")
                    existing_metrics.opening = metrics.get("opening")
                    existing_metrics.support = metrics.get("support")
                    existing_metrics.volume_div = metrics.get("volume_div")
                    existing_metrics.score = metrics.get("score")
                    existing_metrics.avg_score_8d = metrics.get("avg_score_8d")
                else:
                    new_metrics = StockMetrics(
                        stock_code=stock_code,
                        trade_date=trade_date,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=metrics.get("volume"),
                        amount=metrics.get("amount"),
                        pct_change=metrics.get("pct_change") if metrics.get("pct_change") is not None else None,
                        momentum=metrics.get("momentum"),
                        attack=metrics.get("attack"),
                        pullback=metrics.get("pullback"),
                        opening=metrics.get("opening"),
                        support=metrics.get("support"),
                        volume_div=metrics.get("volume_div"),
                        score=metrics.get("score"),
                        avg_score_8d=metrics.get("avg_score_8d"),
                    )
                    session.add(new_metrics)

                metrics_updated += 1

            # 6.3 存储公式来源
            for formula_name in formulas_list:
                save_stock_formula(session, stock_code, formula_name, trade_date)

        session.commit()

        # 7. 更新日志
        log_obj = session.query(RefreshLog).filter(RefreshLog.id == log_id).first()
        if log_obj:
            log_obj.completed_at = datetime.now().isoformat()
            log_obj.stock_count = metrics_updated
            log_obj.status = "success"
            session.commit()

        last_refresh_status["last_status"] = "success"
        last_refresh_status["stock_count"] = metrics_updated
        last_refresh_status["formulas_count"] = len(active_formulas)
        last_refresh_status["formulas_used"] = [f["name"] for f in active_formulas]
        last_refresh_status["running"] = False

        logger.info(f"轻量级刷新完成: {metrics_updated} 只股票, 使用 {len(active_formulas)} 个公式")

        return {
            "status": "success",
            "stock_count": metrics_updated,
            "formulas_count": len(active_formulas),
            "formulas_used": [f["name"] for f in active_formulas],
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
            "mode": "formula_with_data",
        }

    except Exception as e:
        logger.error(f"轻量级刷新失败: {e}")
        logger.error(traceback.format_exc())

        log_obj = session.query(RefreshLog).filter(RefreshLog.id == log_id).first()
        if log_obj:
            log_obj.completed_at = datetime.now().isoformat()
            log_obj.status = "failed"
            log_obj.error_message = str(e)
            session.commit()

        last_refresh_status["last_status"] = "failed"
        last_refresh_status["error"] = str(e)
        last_refresh_status["running"] = False

        return {
            "status": "failed",
            "error": str(e),
        }
    finally:
        session.close()


async def trigger_formula_refresh():
    """只刷新公式选股结果，不重新获取行情数据（外部调用接口，异步）"""
    if not _refresh_lock.acquire(blocking=False):
        logger.warning("数据刷新正在进行中，跳过本次刷新")
        return {"status": "skipped", "reason": "refresh_in_progress"}

    try:
        result = await refresh_formula_selections_only()
        return result
    except Exception as e:
        raise e
    finally:
        _refresh_lock.release()


import config
