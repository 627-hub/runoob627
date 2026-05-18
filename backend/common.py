# -*- coding: utf-8 -*-
"""
common.py - 项目共享工具函数
被后端服务复用
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np


WEIGHTS = {
    "momentum": 0.35,
    "attack": 0.25,
    "pullback": 0.10,
    "opening": 0.10,
    "support": 0.10,
    "volume_div": 0.10,
}


def get_today_str() -> str:
    return datetime.now().strftime("%Y%m%d")


def ensure_data_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_json(filepath: str, default: Any = None) -> Any:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(filepath: str, data: Any) -> None:
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_daily_limit(stock_code: str) -> float:
    """根据股票代码返回每日涨跌幅限制（%）"""
    code = stock_code.split(".")[0]
    if stock_code.endswith(".SZ") and code.startswith("30"):
        return 20.0
    if stock_code.endswith(".SH") and code.startswith("688"):
        return 20.0
    return 10.0


def get_limit_up_price(last_close: float, stock_code: str) -> float:
    """计算涨停价"""
    limit = get_daily_limit(stock_code) / 100
    raw = last_close * (1 + limit)
    return round(raw + 0.005, 2)


def is_mainboard_stock(stock_code: str) -> bool:
    """判断是否为沪深主板股票"""
    code = stock_code.split(".")[0]
    if stock_code.endswith(".SH") and code.startswith(("600", "601", "603", "605")):
        return True
    if stock_code.endswith(".SZ") and code.startswith(("000", "001", "002", "003")):
        return True
    return False


def _safe_pct_change(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    """安全计算涨跌幅，prev<=0 返回 None"""
    if prev is None or prev <= 0:
        return None
    return (curr - prev) / prev * 100


def compute_stock_metrics(
    stock_code: str,
    close: List,
    high: List,
    low: List,
    open_: List,
    volume: List,
    days: int,
) -> Optional[Dict]:
    """
    计算单只股票最近 days 个交易日的 6 个指标
    动量/攻击波/回撤/竞价 按每日涨跌幅限制归一化
    """
    need = days + 1
    if len(close) < need:
        return None

    limit = get_daily_limit(stock_code)

    momentums, attacks, pullbacks, openings, supports, volume_divs = (
        [],
        [],
        [],
        [],
        [],
        [],
    )

    for i in range(-days, 0):
        prev_close = close[i - 1]
        if prev_close is None or prev_close <= 0:
            continue

        c = close[i]
        if c is not None:
            momentums.append(_safe_pct_change(c, prev_close) / limit)

        h = high[i] if i < len(high) else None
        if h is not None:
            attacks.append(_safe_pct_change(h, prev_close) / limit)

        l = low[i] if i < len(low) else None
        if l is not None:
            pullbacks.append(_safe_pct_change(l, prev_close) / limit)

        o = open_[i] if i < len(open_) else None
        if o is not None:
            openings.append(_safe_pct_change(o, prev_close) / limit)

        if c is not None and o is not None and o > 0:
            supports.append((c - o) / o * 100)

        v = volume[i] if i < len(volume) else None
        prev_v = volume[i - 1] if (i - 1) < len(volume) else None
        if v is not None and prev_v is not None and prev_v > 0:
            volume_divs.append(_safe_pct_change(v, prev_v))

    if not momentums:
        return None

    def _mean_safe(lst: List) -> Optional[float]:
        valid = [x for x in lst if x is not None]
        return float(np.mean(valid)) if valid else None

    return {
        "momentum": _mean_safe(momentums),
        "attack": max([x for x in attacks if x is not None], default=None),
        "pullback": min([x for x in pullbacks if x is not None], default=None),
        "opening": _mean_safe(openings),
        "support": _mean_safe(supports),
        "volume_div": _mean_safe(volume_divs),
    }


def percentile_rank(values: List, ascending: bool = True) -> List:
    """将值列表转换为百分位排名 (0-100)"""
    n = len(values)
    if n == 0:
        return []
    sorted_idx = sorted(range(n), key=lambda i: values[i], reverse=not ascending)
    ranks = [0.0] * n
    for rank, idx in enumerate(sorted_idx):
        ranks[idx] = (rank + 1) / n * 100
    return ranks


def calculate_composite_score(metrics: Dict) -> Optional[float]:
    """根据指标计算综合评分"""
    if not metrics:
        return None

    keys = ["momentum", "attack", "pullback", "opening", "support", "volume_div"]
    valid_keys = [k for k in keys if metrics.get(k) is not None]

    if not valid_keys:
        return None

    values = [metrics[k] for k in valid_keys]
    ascending = {
        "momentum": True,
        "attack": True,
        "pullback": True,
        "opening": True,
        "support": True,
        "volume_div": False,
    }

    ranks = percentile_rank(values, ascending=ascending[valid_keys[0]])

    score = sum(ranks[i] * WEIGHTS[valid_keys[i]] for i in range(len(valid_keys)))
    return round(score, 2)


def compute_tdx_metrics(
    stock_code: str,
    close: List,
    high: List,
    low: List,
    open_: List,
    volume: List,
    days: int = 13,
    n: int = 5,
) -> Dict:
    """按照通达信公式逻辑计算 TDX 指标和评分"""
    import logging

    _log = logging.getLogger(__name__ + ".compute_tdx_metrics")
    _log.setLevel(logging.DEBUG)

    # 自动转换数据格式（支持 DataFrame/Series/列表）
    def to_list(data):
        """通用字段解析函数（支持嵌套 dict → 按日期排序的列表）"""
        if data is None:
            return []
        # 处理嵌套 dict（key 为日期，value 为数值）
        if isinstance(data, dict) and not isinstance(data, (list, tuple)):
            return [data[key] for key in sorted(data.keys())]
        # 如果是 DataFrame（单列）
        if hasattr(data, 'iloc') and hasattr(data, 'columns'):
            if len(data.columns) == 1:
                return data.iloc[:, 0].tolist()
            return data.iloc[:, 0].tolist()
        # 如果是 Series
        if hasattr(data, 'tolist') and callable(data.tolist):
            return data.tolist()
        # 如果是列表或元组
        if isinstance(data, (list, tuple)):
            return list(data)
        return list(data) if data is not None else []

    close = to_list(close)
    high = to_list(high)
    low = to_list(low)
    open_ = to_list(open_)
    volume = to_list(volume)

    # 初始化结果
    result = {
        "today_score": None,
        "avg_score_8d": None,
        "metrics": {
            "momentum": None,
            "attack": None,
            "pullback": None,
            "opening": None,
            "support": None,
            "volume_div": None,
            "ztb": 0,
        },
        "score_history": [],
    }

    # 数据长度校验
    if not close or len(close) < 2:
        _log.warning(f"股票 {stock_code}: 数据长度不足")
        return result

    min_len = min(len(close), len(high), len(low), len(open_), len(volume))
    if min_len < 2:
        _log.warning(f"股票 {stock_code}: 数据长度不一致")
        return result

    close = close[:min_len]
    high = high[:min_len]
    low = low[:min_len]
    open_ = open_[:min_len]
    volume = volume[:min_len]

    # ZDF: 涨跌幅因子
    daily_limit_pct = get_daily_limit(stock_code)
    zdf = daily_limit_pct / 100.0

    def calc_ma_volume(vol_list, idx, n):
        start = max(0, idx - n + 1)
        window = [v for v in vol_list[start:idx+1] if v is not None and v > 0]
        if len(window) < n:
            return None
        return float(np.mean(window))

    last_idx = len(close) - 1
    if last_idx < 1:
        return result

    c = close[last_idx] if last_idx < len(close) else None
    h = high[last_idx] if last_idx < len(high) else None
    l = low[last_idx] if last_idx < len(low) else None
    o = open_[last_idx] if last_idx < len(open_) else None
    v = volume[last_idx] if last_idx < len(volume) else None
    prev_close = close[last_idx - 1] if (last_idx - 1) >= 0 else None

    # 检查 NaN 值
    def is_valid_num(v):
        if v is None:
            return False
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            return False
        return isinstance(v, (int, float)) and v > 0

    if not is_valid_num(c) or not is_valid_num(prev_close):
        return result

    # 计算通达信公式变量
    dl = _safe_pct_change(c, prev_close) / 100.0 if c is not None else None
    zd = _safe_pct_change(h, prev_close) / 100.0 if h is not None else None
    zk = _safe_pct_change(l, prev_close) / 100.0 if l is not None else None
    jj = _safe_pct_change(o, prev_close) / 100.0 if o is not None else None
    fq = (1.0 - h / c) if (h is not None and c is not None and c > 0) else None
    cj = (c / o - 1.0) if (c is not None and o is not None and o > 0) else None
    wh = (c / l - 1.0) if (c is not None and l is not None and l > 0) else None

    zt_price = prev_close * (1.0 + daily_limit_pct / 100.0)
    ztb = bool(
        c is not None and h is not None and 
        abs(h - c) < 0.001 and abs(c - zt_price) < 0.01
    ) if c is not None else False

    ma_v = calc_ma_volume(volume, last_idx, n)
    fqln = (ma_v / v - 1.0) if (ma_v is not None and v is not None and v > 0) else None

    # 计算EVE评分
    eve_score = None
    if dl is not None and zdf > 0:
        part1 = 0.0
        part1 += 30.0 * dl
        if zd is not None: part1 += 15.0 * zd
        if zk is not None: part1 += 10.0 * zk
        if jj is not None: part1 += 15.0 * jj
        if fq is not None: part1 += 15.0 * fq
        if cj is not None: part1 += 5.0 * cj
        if wh is not None: part1 += 5.0 * wh
        part1 = part1 / zdf
        part1 += 10.0 if ztb else 0.0

        part2 = 0.0
        if fqln is not None:
            multiplier = -1.0 if (dl < 0 and fqln > 1) else 1.0
            part2 = 10.0 * fqln * multiplier
        eve_score = part1 + part2

    result["today_score"] = round(eve_score, 2) if eve_score is not None else None
    result["metrics"] = {
        "momentum": dl * 100 if dl is not None else None,
        "attack": zd * 100 if zd is not None else None,
        "pullback": zk * 100 if zk is not None else None,
        "opening": jj * 100 if jj is not None else None,
        "support": cj * 100 if cj is not None else None,
        "volume_div": fqln * 100 if fqln is not None else None,
        "ztb": 1 if ztb else 0,
    }

# 计算历史评分（用于8日平均）
    score_history = []
    for i in range(len(close) - 1, 0, -1):
        if i >= len(close) or i < 1:
            score_history.append(None)
            continue
        c = close[i] if i < len(close) else None
        h = high[i] if i < len(high) else None
        l = low[i] if i < len(low) else None
        o = open_[i] if i < len(open_) else None
        v = volume[i] if i < len(volume) else None
        
        prev_close_day = close[i - 1] if (i - 1) >= 0 else None
        
        # Skip if any critical value is None or NaN or non-positive
        if not is_valid_num(prev_close_day) or not is_valid_num(c):
            score_history.append(None)
            continue

        dl_day = _safe_pct_change(c, prev_close_day) / 100.0 if c is not None else None
        if dl_day is None or zdf <= 0:
            score_history.append(None)
            continue

        zd_day = _safe_pct_change(h, prev_close_day) / 100.0 if h is not None else None
        zk_day = _safe_pct_change(l, prev_close_day) / 100.0 if l is not None else None
        jj_day = _safe_pct_change(o, prev_close_day) / 100.0 if o is not None else None
        fq_day = (1.0 - h / c) if (h is not None and c is not None and c > 0) else None
        cj_day = (c / o - 1.0) if (c is not None and o is not None and o > 0) else None
        wh_day = (c / l - 1.0) if (c is not None and l is not None and l > 0) else None

        zt_price_day = prev_close_day * (1.0 + daily_limit_pct / 100.0)
        ztb_day = bool(
            c is not None and h is not None and 
            abs(h - c) < 0.001 and
            abs(c - zt_price_day) < 0.01
        ) if c is not None else False

        ma_v_day = calc_ma_volume(volume, i, n)
        v_today = volume[i] if i < len(volume) else None
        fqln_day = (ma_v_day / v_today - 1.0) if (ma_v_day is not None and v_today is not None and v_today > 0) else None

        eve_score_day = None
        if dl_day is not None:
            part1 = 0.0
            part1 += 30.0 * dl_day
            if zd_day is not None: part1 += 15.0 * zd_day
            if zk_day is not None: part1 += 10.0 * zk_day
            if jj_day is not None: part1 += 15.0 * jj_day
            if fq_day is not None: part1 += 15.0 * fq_day
            if cj_day is not None: part1 += 5.0 * cj_day
            if wh_day is not None: part1 += 5.0 * wh_day
            part1 = part1 / zdf if zdf > 0 else part1
            part1 += 10.0 if ztb_day else 0.0
            part2 = 0.0
            if fqln_day is not None:
                multiplier = -1.0 if (dl_day < 0 and fqln_day > 1) else 1.0
                part2 = 10.0 * fqln_day * multiplier
            eve_score_day = part1 + part2
        
        # Only append valid scores (not None and not NaN)
        if eve_score_day is not None and not (isinstance(eve_score_day, float) and np.isnan(eve_score_day)):
            score_history.append(eve_score_day)
        else:
            score_history.append(None)

    score_history.reverse()
    # Filter out None and NaN values for valid scores
    valid_scores = [s for s in score_history[:days] if s is not None and not (isinstance(s, float) and np.isnan(s))]
    if valid_scores:
        result["avg_score_8d"] = round(float(np.mean(valid_scores)), 2)
    result["score_history"] = score_history[:days]
    return result