# -*- coding: utf-8 -*-
"""
系统API路由
"""

from fastapi import APIRouter
from pydantic import BaseModel

from services.refresh_service import (
    get_refresh_status,
    trigger_manual_refresh,
    trigger_formula_refresh,
)
from services.tdx_service import TDXService
from services.refresh_service import start_scheduler as _start_scheduler
from services.refresh_service import stop_scheduler as _stop_scheduler
from models import Stock, StockMetrics, StockFormula, RefreshLog
from database import get_session

router = APIRouter(prefix="/api", tags=["system"])


class RefreshResponse(BaseModel):
    status: str
    stock_count: int = 0
    error: str = None


@router.get("/health")
async def health_check():
    """健康检查"""
    tdx_ok = TDXService._initialized
    return {
        "status": "ok",
        "tdx_connected": tdx_ok,
    }


@router.get("/refresh/status")
async def get_refresh_status_endpoint():
    """获取刷新状态"""
    return get_refresh_status()


@router.post("/refresh/trigger")
async def trigger_refresh_endpoint():
    """手动触发完整刷新（获取数据+计算指标+公式选股）"""
    return trigger_manual_refresh()


@router.post("/refresh/formula-trigger")
async def trigger_formula_refresh_endpoint():
    """手动触发轻量级刷新（只更新公式选股结果，不重新获取行情数据）"""
    return await trigger_formula_refresh()


@router.post("/refresh/scheduler/start")
async def start_scheduler_endpoint():
    """启动定时刷新任务"""
    try:
        _start_scheduler()
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh/scheduler/stop")
async def stop_scheduler_endpoint():
    """停止定时刷新任务"""
    try:
        _stop_scheduler()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/refresh/scheduler/status")
async def get_scheduler_status():
    """获取定时刷新任务状态"""
    # 简单直观状态：是否正在运行
    return {"running": last_refresh_status.get("running", False)}

@router.get("/tdx/test")
async def test_tdx_connection():
    """测试通达信连接"""
    if not TDXService._initialized:
        TDXService.initialize()

    limit_up = TDXService.get_limit_up_stocks()
    multi_board = TDXService.get_multi_board_stocks()

    return {
        "connected": TDXService._initialized,
        "limit_up_count": len(limit_up),
        "multi_board_count": len(multi_board),
    }


@router.get("/debug/db-status")
async def db_status():
    """调试：返回数据库中各表的记录数，帮助排查数据是否已写入"""
    session = get_session()
    try:
        return {
            "stocks": session.query(Stock).count(),
            "stock_metrics": session.query(StockMetrics).count(),
            "stock_formulas": session.query(StockFormula).count(),
            "refresh_logs": session.query(RefreshLog).count(),
        }
    finally:
        session.close()
