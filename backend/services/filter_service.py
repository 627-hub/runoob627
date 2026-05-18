# -*- coding: utf-8 -*-
"""
筛选服务
"""

import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from models import Stock, StockMetrics, UserFilter
import config


def get_all_filters(session: Session) -> List[Dict]:
    """获取所有筛选配置"""
    filters = session.query(UserFilter).order_by(UserFilter.id.desc()).all()
    result = []
    for f in filters:
        result.append(
            {
                "id": f.id,
                "name": f.name,
                "config": json.loads(f.config) if f.config else {},
                "is_active": f.is_active,
                "created_at": f.created_at,
                "updated_at": f.updated_at,
            }
        )
    return result


def create_filter(session: Session, name: str, filter_config: Dict) -> Dict:
    """创建筛选配置"""
    filter_obj = UserFilter(
        name=name,
        config=json.dumps(filter_config, ensure_ascii=False),
        is_active=True,
    )
    session.add(filter_obj)
    session.commit()
    session.refresh(filter_obj)
    return {
        "id": filter_obj.id,
        "name": filter_obj.name,
        "config": filter_config,
        "is_active": filter_obj.is_active,
    }


def update_filter(
    session: Session, filter_id: int, name: str = None, config: Dict = None
) -> Optional[Dict]:
    """更新筛选配置"""
    filter_obj = session.query(UserFilter).filter(UserFilter.id == filter_id).first()
    if not filter_obj:
        return None

    if name is not None:
        filter_obj.name = name
    if config is not None:
        filter_obj.config = json.dumps(config, ensure_ascii=False)

    filter_obj.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session.commit()

    return {
        "id": filter_obj.id,
        "name": filter_obj.name,
        "config": json.loads(filter_obj.config),
        "is_active": filter_obj.is_active,
    }


def delete_filter(session: Session, filter_id: int) -> bool:
    """删除筛选配置"""
    filter_obj = session.query(UserFilter).filter(UserFilter.id == filter_id).first()
    if not filter_obj:
        return False
    session.delete(filter_obj)
    session.commit()
    return True


def set_active_filter(session: Session, filter_id: int) -> bool:
    """设置激活的筛选配置"""
    session.query(UserFilter).update({"is_active": False})
    filter_obj = session.query(UserFilter).filter(UserFilter.id == filter_id).first()
    if filter_obj:
        filter_obj.is_active = True
        session.commit()
        return True
    return False


def apply_filter(stocks: List[Dict], filter_config: Dict) -> List[Dict]:
    """应用筛选条件"""
    if not filter_config:
        return stocks

    result = stocks

    if (
        "min_pct_change" in filter_config
        and filter_config["min_pct_change"] is not None
    ):
        min_val = filter_config["min_pct_change"]
        result = [s for s in result if s.get("pct_change", 0) >= min_val]

    if (
        "max_pct_change" in filter_config
        and filter_config["max_pct_change"] is not None
    ):
        max_val = filter_config["max_pct_change"]
        result = [s for s in result if s.get("pct_change", 0) <= max_val]

    if "min_amount" in filter_config and filter_config["min_amount"] is not None:
        min_val = filter_config["min_amount"]
        result = [s for s in result if s.get("amount", 0) >= min_val]

    if "min_volume" in filter_config and filter_config["min_volume"] is not None:
        min_val = filter_config["min_volume"]
        result = [s for s in result if s.get("volume", 0) >= min_val]

    if "min_score" in filter_config and filter_config["min_score"] is not None:
        min_val = filter_config["min_score"]
        result = [s for s in result if (s.get("score") or 0) >= min_val]

    if "market" in filter_config and filter_config["market"]:
        markets = filter_config["market"]
        result = [s for s in result if s.get("market") in markets]

    if "is_mainboard_only" in filter_config and filter_config["is_mainboard_only"]:
        result = [s for s in result if s.get("is_mainboard", False)]

    # 过滤 ST 股票（前端需要时的默认行为）
    if filter_config.get("exclude_st"):
        new_result = []
        for s in result:
            name = str(s.get("name", "")).upper()
            if (
                name.startswith("ST") or
                name.startswith("*ST") or
                " ST " in name or
                name.startswith("S.T")
            ):  # 简易判断
                continue
            new_result.append(s)
        result = new_result

    # 过滤流通市值（若数据可用）
    if filter_config.get("min_market_cap") is not None:
        min_cap = filter_config.get("min_market_cap")
        new_result = []
        for s in result:
            cap = s.get("market_cap")
            if cap is None:
                # 若没有市值数据，保留该股票，避免大面积筛空
                new_result.append(s)
            else:
                try:
                    if cap >= min_cap:
                        new_result.append(s)
                except Exception:
                    new_result.append(s)
        result = new_result

    if "min_listing_days" in filter_config and filter_config["min_listing_days"]:
        import time

        min_days = filter_config["min_listing_days"]
        now = time.time()
        result = [s for s in result if s.get("listing_date")]
        filtered = []
        for s in result:
            ld = s.get("listing_date", "")
            if ld and len(ld) == 8:
                try:
                    listing_ts = time.mktime(time.strptime(ld, "%Y%m%d"))
                    days = (now - listing_ts) / 86400
                    if days >= min_days:
                        filtered.append(s)
                except:
                    continue
        result = filtered

    return result

def get_active_filter(session: Session) -> Optional[Dict]:
    """获取当前激活的筛选配置。返回 dict 形式 {name, config}，若无激活配置返回 FILTER_DEFAULT。"""
    # Get all active filters
    all_active = session.query(UserFilter).filter(UserFilter.is_active == True).all()
    # Find the first non-system filter
    filter_obj = None
    for f in all_active:
        if f.name and not f.name.startswith("__"):
            filter_obj = f
            break
    # If no user filter found, return default config
    if not filter_obj:
        import config
        return {"name": "默认筛选", "config": config.FILTER_DEFAULT}
    try:
        import json
        cfg = json.loads(filter_obj.config) if filter_obj.config else {}
        return {"name": filter_obj.name, "config": cfg}
    except Exception:
        return {"name": filter_obj.name, "config": {}}


from datetime import datetime
