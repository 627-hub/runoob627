# -*- coding: utf-8 -*-
import os
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
import config
import logging

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        db_path = config.DB_PATH
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_db():
    """初始化数据库表并执行迁移"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    # 执行迁移
    _migrate_add_avg_score_8d()
    _migrate_add_sectors()


def _migrate_add_avg_score_8d():
    """迁移：为 stock_metrics 表添加 avg_score_8d 列"""
    try:
        db_path = config.DB_PATH
        if not db_path or not os.path.exists(db_path):
            return
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(stock_metrics)")
        cols = [r[1] for r in cur.fetchall()]
        if 'avg_score_8d' not in cols:
            cur.execute("ALTER TABLE stock_metrics ADD COLUMN avg_score_8d REAL")
            conn.commit()
            logger.info("迁移完成：已添加 avg_score_8d 列到 stock_metrics 表")
        conn.close()
    except Exception as e:
        logger.debug(f"迁移 avg_score_8d 失败: {e}")


def _migrate_add_sectors():
    """迁移：为 stocks 表添加 sectors 列"""
    try:
        db_path = config.DB_PATH
        if not db_path or not os.path.exists(db_path):
            return
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(stocks)")
        cols = [r[1] for r in cur.fetchall()]
        if 'sectors' not in cols:
            cur.execute("ALTER TABLE stocks ADD COLUMN sectors TEXT")
            conn.commit()
            logger.info("迁移完成：已添加 sectors 列到 stocks 表")
        conn.close()
    except Exception as e:
        logger.debug(f"迁移 sectors 失败: {e}")


def get_db():
    """FastAPI依赖注入用的数据库会话"""
    session = get_session()
    try:
        yield session
    finally:
        session.close()
