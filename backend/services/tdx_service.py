# -*- coding: utf-8 -*-
"""
通达信数据服务
"""

import sys
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

import config

# 确保后端 common.py 优先，再确保能找到 tqcenter 模块
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if config.TDX_PLUGIN_PATH not in sys.path:
    sys.path.insert(0, config.TDX_PLUGIN_PATH)

try:
    from tqcenter import tq

    TDX_AVAILABLE = True
except ImportError:
    TDX_AVAILABLE = False
    logging.warning("通达信接口未安装")
from common import (
    compute_stock_metrics,
    compute_tdx_metrics,
    percentile_rank,
    WEIGHTS,
    is_mainboard_stock,
    get_today_str,
)
import common

logger = logging.getLogger(__name__)
logger.warning(f"Mmmm compute_tdx_metrics ID: {id(compute_tdx_metrics)}")


FORMULA_DEFAULT_ARGS = {
    "1进2": "10",
    "2进3": "10",
    "3进4": "10",
    "4进5": "10",
    "5板以上": "10",
    "断板": "10",
}


class TDXService:
    """通达信数据源封装"""

    _initialized = False

    @classmethod
    def initialize(cls):
        """初始化通达信连接"""
        if not TDX_AVAILABLE:
            logger.warning("通达信接口不可用")
            return False

        if cls._initialized:
            return True

        try:
            # 使用当前模块路径初始化
            import inspect

            current_file = inspect.getfile(cls)
            tq.initialize(current_file)
            cls._initialized = True
            logger.info("通达信初始化成功")
            return True
        except Exception as e:
            logger.error(f"通达信初始化失败: {e}")
            return False

    @classmethod
    def get_limit_up_stocks(cls) -> List[Dict]:
        """获取今曾涨停股票"""
        if not cls._initialized:
            cls.initialize()

        if not TDX_AVAILABLE:
            return []

        try:
            stocks = tq.get_stock_list_in_sector(
                config.TDX_CONFIG["limit_up_block"],
                block_type=1,
                list_type=1,
            )
            return stocks or []
        except Exception as e:
            logger.error(f"获取涨停股票失败: {e}")
            return []

    @classmethod
    def get_multi_board_stocks(cls) -> List[Dict]:
        """获取多板股票"""
        if not cls._initialized:
            cls.initialize()

        if not TDX_AVAILABLE:
            return []

        try:
            stocks = tq.get_stock_list_in_sector(
                config.TDX_CONFIG["multi_board_sector"],
                block_type=0,
                list_type=1,
            )
            return stocks or []
        except Exception as e:
            logger.error(f"获取多板股票失败: {e}")
            return []

    @classmethod
    def get_all_a_stocks(cls) -> List[Dict]:
        """获取所有A股（从通达信指数成分股获取）"""
        if not cls._initialized:
            cls.initialize()

        if not TDX_AVAILABLE:
            return []

        all_stocks = set()

        index_codes = ["000001.SH", "399001.SZ"]

        for idx_code in index_codes:
            try:
                stocks = tq.get_stock_list_in_sector(
                    idx_code, block_type=0, list_type=1
                )
                if stocks:
                    for s in stocks:
                        code = s.get("Code", "")
                        if code:
                            all_stocks.add(code)
            except Exception as e:
                logger.warning(f"获取指数成分股失败 {idx_code}: {e}")
                continue

        return [{"Code": code} for code in all_stocks]

    @classmethod
    def get_market_data(cls, stock_codes: List[str], days: int = 4) -> Optional[Dict]:
        """获取市场数据"""
        if not cls._initialized:
            cls.initialize()

        if not TDX_AVAILABLE or not stock_codes:
            return None

        try:
            data = tq.get_market_data(
                stock_list=stock_codes,
                period="1d",
                count=days,
                dividend_type="none",
                fill_data=True,
            )
            return data
        except Exception as e:
            logger.error(f"获取行情数据失败: {e}")
            return None

    @classmethod
    def get_stock_info(cls, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        if not cls._initialized:
            cls.initialize()

        if not TDX_AVAILABLE:
            return None

        try:
            info = tq.get_stock_info(stock_code)
            return info
        except Exception as e:
            logger.error(f"获取股票信息失败 {stock_code}: {e}")
            return None

    @classmethod
    def get_stock_sector(cls, stock_code: str) -> Optional[str]:
        """获取股票所属板块（旧版，仅返回一个板块）"""
        info = cls.get_stock_info(stock_code)
        if info:
            return info.get("ZJBH", "")
        return None

    @classmethod
    def get_stock_sectors(cls, stock_code: str) -> List[Dict]:
        """获取股票所属所有板块信息
        
        Returns:
            [{"BlockCode": "xxx", "BlockName": "xxx", "BlockType": "行业/概念/风格/指数", ...}, ...]
        """
        if not cls._initialized:
            cls.initialize()

        if not TDX_AVAILABLE:
            return []

        try:
            result = tq.get_relation(stock_code=stock_code)
            return result if result else []
        except Exception as e:
            logger.debug(f"获取股票板块失败 {stock_code}: {e}")
            return []

    @classmethod
    def get_trading_dates(cls, market: str = "SH", count: int = 10) -> List[str]:
        """获取最近交易日

        Args:
            market: 市场代码（SH/SZ）
            count: 返回最近count个交易日（默认10）
        """
        if not cls._initialized:
            cls.initialize()

        if not TDX_AVAILABLE:
            return []

        try:
            dates = tq.get_trading_dates(market=market, count=count)
            return dates or []
        except Exception as e:
            logger.debug(f"获取交易日失败: {e}")
            return []

    @classmethod
    def get_market_cap(cls, stock_code: str, count: int = 2) -> Optional[float]:
        """获取流通市值（单位：元）"""
        if not cls._initialized:
            cls.initialize()
        if not TDX_AVAILABLE:
            return None
        try:
            date_list = cls.get_trading_dates(count=10)
            if not date_list:
                return None
            if count > 0:
                date_list = date_list[:count]
            result = tq.get_gb_info(stock_code=stock_code, date_list=date_list, count=count)
            if result and len(result) > 0:
                ltgb = result[0].get("Ltgb", 0)
                if ltgb and ltgb > 0:
                    return ltgb * 100
            return None
        except Exception as e:
            logger.debug(f"获取流通市值失败 {stock_code}: {e}")
            return None

    @classmethod
    def run_xg_formula(
        cls, formula_name: str, formula_arg: str = ""
    ) -> Dict[str, List[str]]:
        """运行选股公式

        Returns:
            {stock_code: [formula_name]}, 值为'1'表示满足条件
        """
        logger.info(
            f"=== run_xg_formula called: {formula_name}, arg='{formula_arg}' ==="
        )

        # 如果 arg 为空，使用默认参数
        if not formula_arg:
            formula_arg = FORMULA_DEFAULT_ARGS.get(formula_name, "")
            logger.info(f"Using default arg: '{formula_arg}'")

        if not cls._initialized:
            logger.info("Initializing TDX...")
            cls.initialize()

        if not TDX_AVAILABLE:
            logger.warning("TDX not available")
            return {}

        try:
            # 获取全市场股票列表
            stock_list = tq.get_stock_list(market="5")
            if not stock_list:
                logger.warning(f"获取股票列表失败")
                return {}

            logger.info(
                f"公式 {formula_name}, 参数: '{formula_arg}', 股票数: {len(stock_list)}"
            )

            result = tq.formula_process_mul_xg(
                formula_name=formula_name,
                formula_arg=formula_arg,
                return_count=1,
                return_date=False,
                stock_list=stock_list,
                stock_period="1d",
                count=30,
                dividend_type=1,
            )

            # 打印原始返回结果用于调试
            if result:
                stock_keys = [k for k in result.keys() if k != "ErrorId"]
                logger.info(
                    f"返回股票数: {len(stock_keys)}, ErrorId: {result.get('ErrorId')}"
                )

            # 处理返回结果
            # 格式: {stock_code: {formula_name: [values]}, ...}，值为'1'表示满足条件
            matched_stocks = {}
            if result and isinstance(result, dict):
                if "ErrorId" in result and result.get("ErrorId") != "0":
                    logger.warning(f"公式 {formula_name} 执行出错: {result}")
                    return {}

                for stock, data in result.items():
                    if stock == "ErrorId":
                        continue
                    if isinstance(data, dict):
                        for formula, values in data.items():
                            if isinstance(values, list) and "1" in values:
                                matched_stocks[stock] = [formula]
                                break

            if not matched_stocks:
                logger.info(f"公式 {formula_name} 无选股结果")
            else:
                logger.info(f"公式 {formula_name} 选出 {len(matched_stocks)} 只")

            return matched_stocks
        except Exception as e:
            logger.warning(f"公式 {formula_name} 执行失败: {e}")
            return {}

    @classmethod
    def run_zb_formula(cls, formula_name: str, formula_arg: str = "") -> Dict:
        """运行指标公式"""
        if not cls._initialized:
            cls.initialize()

        if not TDX_AVAILABLE:
            return {}

        try:
            result = tq.formula_process_mul_zb(
                formula_name=formula_name,
                formula_arg=formula_arg,
                return_count=1,
                return_date=True,
                stock_list=[],
                stock_period="1d",
                count=5,
                dividend_type=1,
            )
            return result or {}
        except Exception as e:
            logger.warning(f"指标公式 {formula_name} 执行失败: {e}")
            return {}

    @classmethod
    def run_multiple_formulas(
        cls, formulas: List[Dict], combine_mode: str = "or"
    ) -> Dict:
        """运行多个公式，合并结果

        Args:
            formulas: [{"name": "涨停试盘", "arg": ""}, ...]
            combine_mode: "or" 任一公式选中即可, "and" 需同时满足

        Returns:
            {"stocks": {"股票代码": ["公式1", "公式2"]}, "total": 数量}
        """
        all_stocks = {}  # {stock_code: [formula_names]}

        for formula in formulas:
            name = formula.get("name", "")
            arg = formula.get("arg", "")

            # 如果 arg 为空，使用默认参数
            if not arg:
                arg = FORMULA_DEFAULT_ARGS.get(name, "")

            if not name:
                continue

            logger.info(f"运行公式: {name}, 参数: '{arg}'")

            try:
                # run_xg_formula 现在返回 {stock_code: [formula_name]}
                result = cls.run_xg_formula(name, arg)

                for stock in result.keys():
                    if stock not in all_stocks:
                        all_stocks[stock] = []
                    if name not in all_stocks[stock]:
                        all_stocks[stock].append(name)

            except Exception as e:
                logger.warning(f"公式 {name} 执行失败: {e}")
                continue

        if combine_mode == "and":
            # AND模式：只保留被所有公式都选中的股票
            formulas_count = len(formulas)
            filtered_stocks = {}
            for stock, formulas_list in all_stocks.items():
                if len(formulas_list) >= formulas_count:
                    filtered_stocks[stock] = formulas_list
            all_stocks = filtered_stocks

        return {"stocks": all_stocks, "total": len(all_stocks)}


def calculate_score(metrics: Dict) -> Optional[float]:
    """根据指标计算综合评分"""
    if not metrics:
        return None

    keys = ["momentum", "attack", "pullback", "opening", "support", "volume_div"]
    valid_keys = [k for k in keys if metrics.get(k) is not None]

    if not valid_keys:
        return None

    values = [metrics[k] for k in valid_keys]
    ascending = [True, True, True, True, True, False]

    key_asc = {k: a for k, a in zip(keys, ascending)}
    ranks = percentile_rank(values, ascending=key_asc[valid_keys[0]])

    score = sum(ranks[i] * WEIGHTS[valid_keys[i]] for i in range(len(valid_keys)))
    return round(score, 2)


def process_market_data(
    data: Dict, stock_codes: List[str], days: int = 3
) -> Dict[str, Dict]:
    """处理市场数据，批量计算指标"""
    import pandas as pd

    result = {}

    if not data or "Close" not in data:
        return result

    close_df = data["Close"]
    is_date_index = (
        isinstance(close_df.index[0], pd.Timestamp)
        if len(close_df.index) > 0
        else False
    )
    
    # 调试日志：输出数据格式信息
    logger.info(f"process_market_data: is_date_index={is_date_index}")
    logger.info(f"  close_df shape: {close_df.shape}")
    if len(close_df.index) > 0:
        if is_date_index:
            logger.info(f"  close_df.columns (股票代码) 示例: {list(close_df.columns)[:10]}")
            logger.info(f"  close_df.index (日期) 示例: {list(close_df.index)[:5]}")
        else:
            logger.info(f"  close_df.index (股票代码) 示例: {list(close_df.index)[:10]}")
            logger.info(f"  close_df.columns (日期) 示例: {list(close_df.columns)[:5]}")
    logger.info(f"  stock_codes 示例: {stock_codes[:10]}")

    # 规范化股票代码：去掉 .SH/.SZ 后缀
    normalized_codes = {}
    for code in stock_codes:
        normalized = code.split('.')[0] if '.' in code else code
        normalized_codes[code] = normalized
    logger.info(f"  规范化后 stock_codes 示例: {list(normalized_codes.items())[:5]}")

    for stock in stock_codes:
        try:
            # 尝试用原始代码和规范化代码两种方式
            stock_to_use = stock
            if is_date_index:
                if stock not in close_df.columns:
                    # 尝试规范化代码
                    norm = normalized_codes.get(stock)
                    if norm and norm in close_df.columns:
                        stock_to_use = norm
                        logger.info(f"股票 {stock} 使用规范化代码 {norm}")
                    else:
                        logger.warning(f"股票 {stock} 不在 close_df.columns 中，跳过")
                        continue
                close_series = close_df[stock_to_use]
                high_df = data.get("High", pd.DataFrame())
                low_df = data.get("Low", pd.DataFrame())
                open_df = data.get("Open", pd.DataFrame())
                vol_df = data.get("Volume", pd.DataFrame())

                high_series = (
                    high_df[stock_to_use] if stock_to_use in high_df.columns else pd.Series()
                )
                low_series = low_df[stock_to_use] if stock_to_use in low_df.columns else pd.Series()
                open_series = (
                    open_df[stock_to_use] if stock_to_use in open_df.columns else pd.Series()
                )
                volume_series = (
                    vol_df[stock_to_use] if stock_to_use in vol_df.columns else pd.Series()
                )
            else:
                if stock not in close_df.index:
                    # 尝试规范化代码
                    norm = normalized_codes.get(stock)
                    if norm and norm in close_df.index:
                        stock_to_use = norm
                        logger.info(f"股票 {stock} 使用规范化代码 {norm}")
                    else:
                        logger.warning(f"股票 {stock} 不在 close_df.index 中，跳过")
                        continue
                close_series = close_df.loc[stock_to_use]
                high_df = data.get("High", pd.DataFrame())
                low_df = data.get("Low", pd.DataFrame())
                open_df = data.get("Open", pd.DataFrame())
                vol_df = data.get("Volume", pd.DataFrame())

                high_series = (
                    high_df[stock_to_use] if stock_to_use in high_df.columns else pd.Series()
                )
                low_series = low_df[stock_to_use] if stock_to_use in low_df.columns else pd.Series()
                open_series = (
                    open_df[stock_to_use] if stock_to_use in open_df.columns else pd.Series()
                )
                volume_series = (
                    vol_df[stock_to_use] if stock_to_use in vol_df.columns else pd.Series()
                )

            close_list = close_series.tolist()
            high_list = high_series.tolist()
            low_list = low_series.tolist()
            open_list = open_series.tolist()
            volume_list = volume_series.tolist()

            # 数据长度校验
            min_len = min(len(close_list), len(high_list), len(low_list), len(open_list), len(volume_list))
            if min_len < 2:
                logger.warning(f"股票 {stock}: 数据长度不足，close={len(close_list)}, high={len(high_list)}, low={len(low_list)}, open={len(open_list)}, volume={len(volume_list)}")
                continue

            # 调试日志
            valid_close = [c for c in close_list if c is not None and c > 0]
            logger.info(f"股票 {stock}: close_list长度={len(close_list)}, 有效close={len(valid_close)}")
            logger.info(f"[debug] {stock}: high={len(high_list)}, low={len(low_list)}, open={len(open_list)}, vol={len(volume_list)}")
            logger.info(f"[debug] {stock}: close前3={close_list[:3]}, close后3={close_list[-3:]}")
            
            # 数据长度校验
            min_len = min(len(close_list), len(high_list), len(low_list), len(open_list), len(volume_list))
            if min_len < 2:
                logger.warning(f"股票 {stock}: 数据长度不足，close={len(close_list)}, high={len(high_list)}, low={len(low_list)}, open={len(open_list)}, volume={len(volume_list)}")
                continue

            # 使用 compute_tdx_metrics 计算今日评分和8日平均评分
            logger.warning(f"ZZZ 调用前: {stock}, close最后3={close_list[-3:]}")
            tdx_result = compute_tdx_metrics(
                stock,
                close_list,
                high_list,
                low_list,
                open_list,
                volume_list,
                days=8,
            )

            logger.info(f"股票 {stock} compute_tdx_metrics 结果: type={type(tdx_result)}, today_score={tdx_result.get('today_score')}, avg_score_8d={tdx_result.get('avg_score_8d')}, metrics存在={tdx_result.get('metrics') is not None}")
            # 调试：输出 metrics 内容
            if tdx_result and tdx_result.get('metrics'):
                logger.info(f"  指标内容: {tdx_result['metrics']}")

            if tdx_result and tdx_result.get("metrics"):
                metrics = tdx_result["metrics"]
                # 添加今日评分和8日平均评分
                metrics["score"] = tdx_result.get("today_score")
                metrics["avg_score_8d"] = tdx_result.get("avg_score_8d")
                
                # 添加涨跌幅和价格数据
                valid_closes = [c for c in close_list if c is not None and c > 0]
                if len(valid_closes) >= 2:
                    close_val = valid_closes[-1]
                    prev_close = valid_closes[-2]
                    metrics["pct_change"] = (close_val - prev_close) / prev_close * 100
                    metrics["close"] = close_val
                elif valid_closes:
                    metrics["close"] = valid_closes[-1]
                valid_opens = [o for o in open_list if o is not None and o > 0]
                if valid_opens:
                    metrics["open"] = valid_opens[-1]
                valid_highs = [h for h in high_list if h is not None and h > 0]
                if valid_highs:
                    metrics["high"] = valid_highs[-1]
                valid_lows = [l for l in low_list if l is not None and l > 0]
                if valid_lows:
                    metrics["low"] = valid_lows[-1]
                valid_vols = [v for v in volume_list if v is not None and v > 0]
                if len(valid_vols) >= 2:
                    metrics["volume"] = valid_vols[-1]
                    if metrics.get("close"):
                        metrics["amount"] = valid_vols[-1] * metrics["close"]
                result[stock] = metrics
                logger.info(f"股票 {stock} 指标计算成功，加入结果")

        except Exception as e:
            logger.error(f"处理股票 {stock} 失败: {e}")
            continue

    return result
