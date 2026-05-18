# -*- coding: utf-8 -*-
"""
筛选配置API路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services.filter_service import (
    get_all_filters,
    create_filter,
    update_filter,
    delete_filter,
    set_active_filter,
)
import config

router = APIRouter(prefix="/api/filters", tags=["filters"])


class FilterCreate(BaseModel):
    name: str
    config: dict
    activate: bool = True


class FilterUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None


@router.get("/")
async def list_filters(db: Session = Depends(get_db)):
    """获取筛选配置列表"""
    return get_all_filters(db)


@router.post("/")
async def create_filter_endpoint(
    filter_data: FilterCreate, db: Session = Depends(get_db)
):
    """创建筛选配置（可选同时激活）"""
    result = create_filter(db, filter_data.name, filter_data.config)
    if filter_data.activate:
        # 将新建筛选配置设为激活状态
        try:
            set_active_filter(db, result["id"])
            result["is_active"] = True
        except Exception:
            pass
    return result


@router.put("/{filter_id}")
async def update_filter_endpoint(
    filter_id: int, filter_data: FilterUpdate, db: Session = Depends(get_db)
):
    """更新筛选配置"""
    result = update_filter(
        db,
        filter_id,
        name=filter_data.name,
        config=filter_data.config,
    )
    if not result:
        raise HTTPException(status_code=404, detail="筛选配置不存在")
    return result


@router.delete("/{filter_id}")
async def delete_filter_endpoint(filter_id: int, db: Session = Depends(get_db)):
    """删除筛选配置"""
    success = delete_filter(db, filter_id)
    if not success:
        raise HTTPException(status_code=404, detail="筛选配置不存在")
    return {"status": "deleted", "id": filter_id}


@router.post("/{filter_id}/activate")
async def activate_filter(filter_id: int, db: Session = Depends(get_db)):
    """激活筛选配置"""
    success = set_active_filter(db, filter_id)
    if not success:
        raise HTTPException(status_code=404, detail="筛选配置不存在")
    return {"status": "activated", "id": filter_id}


@router.get("/default")
async def get_default_config():
    """获取默认筛选配置"""
    return config.FILTER_DEFAULT


@router.get("/active")
async def get_active_filter_endpoint(db: Session = Depends(get_db)):
    """获取当前激活的筛选配置（用于前端直接读取并展示）"""
    from services.filter_service import get_active_filter
    active = get_active_filter(db)
    return active or config.FILTER_DEFAULT
