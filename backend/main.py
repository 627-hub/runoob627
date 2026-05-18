# -*- coding: utf-8 -*-
import sys
import os

"""
股票选股监控系统 - FastAPI后端
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config

sys.path.append(config.TDX_PLUGIN_PATH)

from database import init_db
from routers import stocks_router, filters_router, system_router, formulas_router
from services.refresh_service import refresh_stock_data
from services.tdx_service import TDXService

# 配置日志
LOG_DIR = config.LOGS_DIR
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "backend.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("系统启动中...")

    init_db()
    logger.info("数据库初始化完成")

    TDXService.initialize()

    # 启动时立即执行一次全量公式刷新
    logger.info("启动时执行全量公式刷新...")
    try:
        import asyncio
        asyncio.create_task(refresh_stock_data())
    except Exception as e:
        logger.warning(f"启动刷新失败: {e}")

    scheduler.add_job(
        refresh_stock_data,
        "interval",
        minutes=10,
        id="data_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("定时刷新任务已启动")

    yield

    logger.info("系统关闭中...")
    scheduler.shutdown()
    logger.info("定时任务已停止")


app = FastAPI(
    title="股票选股监控系统",
    description="基于通达信数据源的股票选股监控系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 导入认证模块
from auth import verify_token, get_auth_dependencies

# 根据是否配置 token 决定是否启用认证
auth_deps = get_auth_dependencies()

app.include_router(stocks_router)
app.include_router(filters_router)
app.include_router(system_router, dependencies=auth_deps)
app.include_router(formulas_router, dependencies=auth_deps)


@app.get("/")
async def root():
    return {
        "message": "股票选股监控系统 API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
