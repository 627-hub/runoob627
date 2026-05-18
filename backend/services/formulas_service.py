# -*- coding: utf-8 -*-
"""
公式服务 - 管理用户配置的选股公式
"""

import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from models import UserFormula, StockFormula
from database import get_session
import config


def get_user_formulas(session: Session) -> List[Dict]:
    """获取用户配置的公式"""
    formulas = session.query(UserFormula).order_by(UserFormula.id.desc()).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "category": f.category,
            "formula_arg": f.formula_arg,
            "is_active": f.is_active,
            "created_at": f.created_at,
            "updated_at": f.updated_at,
        }
        for f in formulas
    ]


def get_active_formulas(session: Session) -> List[Dict]:
    """获取用户启用的公式列表（过滤掉无用的 UPN 公式）"""
    formulas = session.query(UserFormula).filter(UserFormula.is_active == True).all()
    filtered = [f for f in formulas if f.name != "UPN"]
    return [
        {
            "name": f.name,
            "arg": f.formula_arg or "",
            "category": f.category,
        }
        for f in filtered
    ]


FORMULA_DEFAULT_ARGS = {
    "1进2": "10",
    "2进3": "10",
    "3进4": "10",
    "4进5": "10",
    "5板以上": "10",
    "断板": "10",
}


def save_user_formulas(
    session: Session, formulas: List[str], categories: Dict[str, List[str]]
) -> bool:
    """保存用户选择的公式

    Args:
        formulas: 选中的公式名称列表
        categories: 公式分类 {"涨停类": ["涨停试盘", "曾涨停"], ...}
    """
    # 先清空所有公式
    session.query(UserFormula).delete()

    # 查找公式对应的分类
    category_map = {}
    for cat, names in categories.items():
        for name in names:
            category_map[name] = cat

    # 逐个添加
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for name in formulas:
        formula_arg = FORMULA_DEFAULT_ARGS.get(name, "")
        formula = UserFormula(
            name=name,
            category=category_map.get(name, "其他"),
            formula_arg=formula_arg,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(formula)

    session.commit()
    return True


def update_formula_active(session: Session, formula_id: int, is_active: bool) -> bool:
    """更新公式启用状态"""
    formula = session.query(UserFormula).filter(UserFormula.id == formula_id).first()
    if not formula:
        return False

    formula.is_active = is_active
    from datetime import datetime

    formula.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session.commit()
    return True


def get_combine_mode(session: Session) -> str:
    """获取组合模式"""
    from models import UserFilter

    filter_obj = (
        session.query(UserFilter)
        .filter(UserFilter.name == "__formula_combine_mode__")
        .first()
    )
    if filter_obj:
        try:
            config_data = json.loads(filter_obj.config)
            return config_data.get("mode", "or")
        except:
            pass
    return "or"


def set_combine_mode(session: Session, mode: str) -> bool:
    """设置组合模式"""
    from models import UserFilter

    filter_obj = (
        session.query(UserFilter)
        .filter(UserFilter.name == "__formula_combine_mode__")
        .first()
    )

    if filter_obj:
        filter_obj.config = json.dumps({"mode": mode})
    else:
        filter_obj = UserFilter(
            name="__formula_combine_mode__",
            config=json.dumps({"mode": mode}),
            is_active=True,
        )
        session.add(filter_obj)

    session.commit()
    return True


def save_stock_formula(
    session: Session, stock_code: str, formula_name: str, trade_date: str
) -> bool:
    """保存股票-公式关联（幂等操作，重复不会报错）"""
    from datetime import datetime

    # 检查是否已存在，避免重复插入
    existing = (
        session.query(StockFormula)
        .filter(
            StockFormula.stock_code == stock_code,
            StockFormula.formula_name == formula_name,
            StockFormula.trade_date == trade_date,
        )
        .first()
    )

    if existing:
        return True  # 已存在，直接返回

    record = StockFormula(
        stock_code=stock_code,
        formula_name=formula_name,
        trade_date=trade_date,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    session.add(record)
    session.commit()
    return True


def get_stock_formulas(
    session: Session, stock_code: str, trade_date: str = None
) -> List[str]:
    """获取股票的公式来源"""
    query = session.query(StockFormula).filter(StockFormula.stock_code == stock_code)

    if trade_date:
        query = query.filter(StockFormula.trade_date == trade_date)

    records = query.all()
    return list(set([r.formula_name for r in records]))


def get_all_available_formulas() -> List[Dict]:
    """获取配置中所有可用的公式（用于全量刷新）"""
    all_formulas = []
    for cat, names in config.FORMULA_CATEGORIES.items():
        for name in names:
            formula_arg = FORMULA_DEFAULT_ARGS.get(name, "")
            all_formulas.append({
                "name": name,
                "arg": formula_arg,
                "category": cat,
            })
    return all_formulas


def init_default_formulas(session: Session) -> None:
    """初始化默认公式配置"""
    # 总是重新初始化，确保参数正确，并排除无效的 UPN 公式
    sanitized = [f for f in config.DEFAULT_ACTIVE_FORMULAS if f != "UPN"]
    save_user_formulas(
        session, sanitized, config.FORMULA_CATEGORIES
    )
    logger.info(f"已初始化默认公式: {sanitized}")


import logging

logger = logging.getLogger(__name__)
