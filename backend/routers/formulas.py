# -*- coding: utf-8 -*-
"""
公式API路由
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
import config
from services.formulas_service import (
    get_user_formulas,
    save_user_formulas,
    update_formula_active,
    get_combine_mode,
    set_combine_mode,
    get_active_formulas,
)

router = APIRouter(prefix="/api/formulas", tags=["formulas"])


class FormulaSaveRequest(BaseModel):
    formulas: List[str]
    combine_mode: str = "or"


@router.get("/categories")
async def get_formula_categories():
    """获取公式分类列表"""
    return config.FORMULA_CATEGORIES


@router.get("/combine-modes")
async def get_combine_modes():
    """获取组合模式选项"""
    return {
        "modes": config.FORMULA_COMBINE_MODES,
        "default": config.DEFAULT_COMBINE_MODE,
    }


@router.get("/user")
async def get_user_formulas_endpoint(db: Session = Depends(get_db)):
    """获取用户配置的公式"""
    formulas = get_user_formulas(db)
    mode = get_combine_mode(db)
    active_list = get_active_formulas(db)
    active_names = [f["name"] for f in active_list]

    return {
        "formulas": formulas,
        "active_formulas": active_names,
        "combine_mode": mode,
    }


@router.post("/user")
async def save_user_formulas_endpoint(
    request: FormulaSaveRequest, db: Session = Depends(get_db)
):
    """保存用户选择的公式"""
    try:
        save_user_formulas(db, request.formulas, config.FORMULA_CATEGORIES)
        set_combine_mode(db, request.combine_mode)
        return {"status": "success", "message": "保存成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{formula_id}/toggle")
async def toggle_formula(
    formula_id: int, is_active: bool, db: Session = Depends(get_db)
):
    """切换公式启用状态"""
    success = update_formula_active(db, formula_id, is_active)
    if not success:
        raise HTTPException(status_code=404, detail="公式不存在")
    return {"status": "success"}


@router.get("/test/{formula_name}")
async def test_formula(formula_name: str):
    """测试单个公式"""
    from services.tdx_service import TDXService

    result = TDXService.run_xg_formula(formula_name)
    count = len(result) if result else 0

    return {
        "formula_name": formula_name,
        "stock_count": count,
        "stocks": list(result.keys())[:20] if result else [],
    }
