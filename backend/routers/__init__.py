# -*- coding: utf-8 -*-
from routers.stocks import router as stocks_router
from routers.filters import router as filters_router
from routers.system import router as system_router
from routers.formulas import router as formulas_router

__all__ = ["stocks_router", "filters_router", "system_router", "formulas_router"]
