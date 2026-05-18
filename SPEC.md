# 股票选股监控系统 技术规格说明书 (SPEC)

## 1. 项目概述

**项目名称**: 股票选股监控系统 (Stock Selection & Monitoring System)  
**项目简称**: tdxplugins  
**版本**: 1.0.0  
**技术栈**: FastAPI + Vue 3 + SQLite + 通达信(TDX)插件接口  

**一句话描述**: 连接通达信股票软件，基于用户自定义的选股公式自动筛选股票，计算 EVE 综合评分，并通过 Web 仪表盘实时展示筛选结果和指标数据。

---

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                       Frontend (Vue 3 SPA)                       │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐   │
│  │ Dashboard   │  │ StockList  │  │ FilterConfig             │   │
│  │ (概览统计)   │  │ (股票列表)  │  │ (公式 + 筛选配置)         │   │
│  └──────┬──────┘  └──────┬─────┘  └───────────┬──────────────┘   │
│         └───────────────┬┴────────────────────┘                  │
│                         │ Axios HTTP /api/*                      │
│                         │ (Vite proxy → localhost:8000)          │
└─────────────────────────┼────────────────────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────────────────────┐
│                Backend (FastAPI, port 8000)                      │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  Router Layer (4 modules)                                 │   │
│  │  /api/stocks*  /api/filters*  /api/formulas*  /api/*      │   │
│  └──────────────────────────┬────────────────────────────────┘   │
│                             │                                     │
│  ┌──────────────────────────┼────────────────────────────────┐    │
│  │  Services Layer (4 modules)                               │    │
│  │  TDXService · FilterService · FormulasService             │    │
│  │  RefreshService (主编排器，协调数据刷新全流程)               │    │
│  └──────────────────────────┼────────────────────────────────┘    │
│                             │                                     │
│  ┌──────────────────────────┼────────────────────────────────┐    │
│  │  Metrics Engine (common.py)                               │    │
│  │  compute_tdx_metrics() — EVE 评分核心算法                  │    │
│  └──────────────────────────┼────────────────────────────────┘    │
│                             │                                     │
│  ┌──────────────────────────┼────────────────────────────────┐    │
│  │  Database (SQLite via SQLAlchemy)                         │    │
│  │  6 张表: Stock, StockMetrics, StockFormula,              │    │
│  │         UserFilter, UserFormula, RefreshLog               │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                  │
│  外部依赖: 通达信软件 + tqcenter 插件 (TDX_PLUGIN_PATH)           │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 系统功能

### 3.1 核心业务流程

```
定时器(每10分钟)  ──→  refresh_stock_data()
                           │
手动触发(完整刷新) ──→      │
                           │
                           ├─ 1. 获取用户启用的选股公式 (get_active_formulas)
                           │
                           ├─ 2. 运行公式选股 (TDXService.run_multiple_formulas)
                           │       └── 支持 OR/AND 组合模式
                           │
                           ├─ 3. 获取行情数据 OHLCV (get_market_data, 20天)
                           │
                           ├─ 4. 计算 EVE 评分及6项指标 (process_market_data)
                           │       └── compute_tdx_metrics() for each stock
                           │
                           ├─ 5. 增量写入数据库 (当天数据删除后重新写入)
                           │       ├── Stock 表 (基本信息/板块/市值)
                           │       ├── StockMetrics 表 (OHLCV/6指标/评分)
                           │       └── StockFormula 表 (公式关联)
                           │
                           └─ 6. 更新 RefreshLog
```

### 3.2 功能清单

| 功能 | 描述 | 后端 | 前端 |
|------|------|------|------|
| 选股公式管理 | 从5大类25个公式中选择，支持OR/AND组合 | `formulas.py` + `formulas_service.py` | `FilterConfig.vue` |
| 数据自动刷新 | APScheduler 定时每10分钟拉取数据 | `refresh_service.py` | Dashboard 开关 |
| 股票列表展示 | 分页、排序、按公式/板块/市场/ST/市值等筛选 | `stocks.py` + `filter_service.py` | `StockList.vue` |
| EVE 评分系统 | 基于通达信公式逻辑的加权评分算法 | `common.py: compute_tdx_metrics()` | 表格列展示 |
| 筛选配置 | 多组筛选配置，可激活其中一组 | `filters.py` + `filter_service.py` | `FilterConfig.vue` |
| 系统监控 | 健康检查、刷新状态、DB 记录数 | `system.py` | Dashboard |
| 数据导出 CSV | 导出当前列表为 CSV 文件 | — | `StockList.vue: exportData()` |

---

## 4. 数据库设计 (SQLite)

### 4.1 ER 概览

```
stocks ──1:N── stock_metrics
stocks ──1:N── stock_formulas
stocks ──1:N── stock_sectors
user_filters (独立表)
user_formulas (独立表)
refresh_logs (独立表)
```

### 4.2 表结构

#### stocks (股票基本信息)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| code | VARCHAR(10) UNIQUE | 股票代码 (含后缀, 如 `000001.SH`) |
| name | VARCHAR(50) | 股票名称 |
| market | VARCHAR(10) | `SH` / `SZ` |
| is_mainboard | BOOLEAN | 是否主板 |
| listing_date | VARCHAR(10) | 上市日期 (YYYYMMDD) |
| market_cap | FLOAT | 流通市值 (元) |
| sectors | VARCHAR(500) | 板块列表 (逗号分隔) |

#### stock_metrics (日线指标)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| stock_code | VARCHAR(10) FK | 股票代码 |
| trade_date | VARCHAR(10) | 交易日 (YYYYMMDD) |
| open/high/low/close | FLOAT | OHLC 价格 |
| volume | INTEGER | 成交量 |
| amount | FLOAT | 成交额 |
| pct_change | FLOAT | 涨跌幅 (%) |
| momentum | FLOAT | 动量指标 |
| attack | FLOAT | 攻击波指标 |
| pullback | FLOAT | 回撤指标 |
| opening | FLOAT | 竞价指标 |
| support | FLOAT | 支撑指标 |
| volume_div | FLOAT | 量比指标 |
| score | FLOAT | EVE 今日评分 |
| avg_score_8d | FLOAT | 8 日平均评分 |
| created_at | VARCHAR(30) | 记录时间 |

**索引**: UNIQUE(stock_code, trade_date)

#### stock_formulas (股票-公式关联)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| stock_code | VARCHAR(10) | 股票代码 |
| formula_name | VARCHAR(100) | 公式名称 |
| trade_date | VARCHAR(10) | 交易日 |
| created_at | VARCHAR(30) | 记录时间 |

**索引**: UNIQUE(stock_code, formula_name, trade_date)

#### user_filters (筛选配置)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| name | VARCHAR(100) | 配置名称 |
| config | VARCHAR(1000) JSON | 筛选条件 (JSON) |
| is_active | BOOLEAN | 是否激活 |
| created_at / updated_at | VARCHAR(30) | 时间戳 |

特殊记录: `name = "__formula_combine_mode__"` 用于存储公式组合模式 (OR/AND)

#### user_formulas (用户公式)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| name | VARCHAR(100) | 公式名称 |
| description | VARCHAR(500) | 描述 |
| formula | VARCHAR(1000) | 原始公式 (保留字段) |
| category | VARCHAR(50) | 分类 (涨停类/跌停类/趋势类/形态类/其他) |
| formula_arg | VARCHAR(50) | 公式参数 |
| is_active | BOOLEAN | 是否启用 |
| created_at / updated_at | VARCHAR(30) | 时间戳 |

##### stock_sectors (股票板块关联，规范化存储)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| stock_code | VARCHAR(10) INDEX | 股票代码 |
| block_code | VARCHAR(20) | 板块代码 (如 `881355.SH`) |
| block_name | VARCHAR(100) | 板块名称 (如 `软件服务`) |
| block_type | VARCHAR(20) | 板块类型 (行业/概念/地区/风格/指数) |
| trade_date | VARCHAR(10) | 交易日 |

**索引**: INDEX(stock_code, block_type), INDEX(block_name)

### refresh_logs (刷新日志)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| action | VARCHAR(100) | 操作名称 |
| status | VARCHAR(20) | `running` / `success` / `failed` |
| details | VARCHAR(500) | 详情/错误信息 |
| started_at / created_at | VARCHAR(30) | 时间戳 |

---

## 5. API 接口规范

### 5.1 股票 API (`/api/stocks`)

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | `/` | 股票列表(分页+筛选+排序) | `page`, `page_size`, `sort_by`, `sort_order`, `search`, `market`, `formulas`, `sector`, `block_type`, `is_mainboard`, `min_pct_change`, `max_pct_change`, `min_amount`, `min_score` |
| GET | `/{stock_code}` | 股票详情+近30天指标 | `stock_code` |
| GET | `/filter-options/options` | 筛选选项(市场/评分范围/成交额范围) | — |
| GET | `/sectors/list` | 板块列表(按类型分组) | — |
| GET | `/stats/summary` | 统计概览 | — |

### 5.2 筛选配置 API (`/api/filters`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 筛选配置列表 |
| POST | `/` | 创建筛选配置 |
| PUT | `/{filter_id}` | 更新筛选配置 |
| DELETE | `/{filter_id}` | 删除筛选配置 |
| POST | `/{filter_id}/activate` | 激活筛选配置 |
| GET | `/default` | 获取默认筛选配置 |
| GET | `/active` | 获取当前激活的筛选配置 |

### 5.3 公式 API (`/api/formulas`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/categories` | 公式分类列表 |
| GET | `/combine-modes` | 组合模式选项 |
| GET | `/user` | 用户公式配置 |
| POST | `/user` | 保存用户公式 |
| POST | `/{formula_id}/toggle` | 切换公式启用状态 |
| GET | `/test/{formula_name}` | 测试单个公式 |

### 5.4 系统 API (`/api`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 + TDX 连接状态 |
| GET | `/refresh/status` | 刷新状态 |
| POST | `/refresh/trigger` | 完整刷新 (数据+公式+指标) |
| POST | `/refresh/formula-trigger` | 轻量刷新 (仅公式选股+指标) |
| POST | `/refresh/scheduler/start|stop` | 定时器启停 |
| GET | `/tdx/test` | 测试 TDX 连接 |
| GET | `/debug/db-status` | 各表记录数 |

### 5.5 认证机制

- 可选 API Token 认证，通过环境变量 `API_TOKEN` 配置
- 启用时前端需在请求头 `X-API-Token` 携带 token
- 认证作用于 `system` 和 `formulas` 路由
- 未配置 token 时认证自动跳过

---

## 6. EVE 评分算法

### 6.1 公式变量定义

基于通达信公式引擎的变量体系：

| 变量 | 公式 | 含义 |
|------|------|------|
| `dl` | `(收盘/昨收 - 1)` | 当日涨跌幅 |
| `zd` | `(最高/昨收 - 1)` | 当日最高涨幅 |
| `zk` | `(最低/昨收 - 1)` | 当日最低涨幅 |
| `jj` | `(开盘/昨收 - 1)` | 开盘涨幅 |
| `fq` | `1 - 最高/收盘` | 振幅因子 (上影线) |
| `cj` | `收盘/开盘 - 1` | 收盘相对开盘涨幅 |
| `wh` | `收盘/最低 - 1` | 收盘相对最低涨幅 |
| `fqln` | `均量/当日量 - 1` | 量比 (N日均量 / 当日量) |

### 6.2 评分计算

**EVE 评分 = part1 + part2**

**part1** (价格动量分): `(30·dl + 15·zd + 10·zk + 15·jj + 15·fq + 5·cj + 5·wh) / zdf + 涨停奖励(+10)`

其中 `zdf = daily_limit_pct / 100` (涨跌幅归一化因子)

**part2** (量能调节分): `10 · fqln · multiplier`

其中 `multiplier = -1 if (dl<0 and fqln>1) else 1` (价跌量增时负向调节)

**8日平均评分**: 对最近8个交易日的 EVE 评分取均值

### 6.3 6 项明细指标

| 指标 | 值 | 含义 |
|------|----|------|
| `momentum` | `dl * 100` | 动量 (当日涨跌幅%) |
| `attack` | `zd * 100` | 攻击波 (最高涨幅%) |
| `pullback` | `zk * 100` | 回撤 (最低涨幅%) |
| `opening` | `jj * 100` | 竞价 (开盘涨幅%) |
| `support` | `cj * 100` | 支撑 (收盘/开盘) |
| `volume_div` | `fqln * 100` | 量比 |

---

## 7. 配置系统

### 7.1 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TDX_PLUGIN_PATH` | `(空)` | 通达信插件路径（必填，如 `C:/new_tdx64/PYPlugins/user`） |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | CORS 允许源 |
| `API_TOKEN` | `(空)` | API 认证 Token (为空时禁用认证) |

### 7.2 默认筛选条件

```python
FILTER_DEFAULT = {
    "min_pct_change": None,    # 最小涨跌幅
    "max_pct_change": None,    # 最大涨跌幅
    "min_amount": None,         # 最小成交额
    "min_volume": None,         # 最小成交量
    "min_score": None,          # 最小评分
    "market": ["SH", "SZ"],     # 市场
    "exclude_sectors": [],      # 排除板块
    "include_sectors": [],      # 包含板块
    "min_listing_days": 0,      # 最小上市天数
    "is_mainboard_only": True,  # 仅主板
    "exclude_st": True,         # 排除 ST
    "min_market_cap": 2e9,      # 最小流通市值 (20亿)
}
```

### 7.3 公式分类

5 大类共 25 个选股公式：

| 分类 | 公式列表 |
|------|----------|
| 涨停类 (11) | 低位启动, 涨停试盘, 曾涨停, 20CM, 1进2, 5板以上, 4进5, 3进4, 2进3, 断板, 炸板反包 |
| 跌停类 (2) | 曾跌停, 跌停反转 |
| 趋势类 (4) | 权重趋势, 强趋势股, 超买行情1, 回调 |
| 形态类 (4) | N型涨停双响炮, 九转低9选股, 短庄起爆牛, 神龙出海 |
| 其他 (4) | 低市值, 龙头股炸板, B011, B012 |

默认激活: `["1进2", "2进3", "断板"]`

---

## 8. 前端路由与页面

### 8.1 路由

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | `Dashboard.vue` | 仪表盘 (统计卡片 + 嵌入 StockList) |
| `/stocks` | `StockList.vue` | 股票列表 (独立页面) |

注意: `FilterConfig.vue` 已在代码中存在但未注册到路由中。

### 8.2 页面功能

**Dashboard.vue**
- 4 个统计卡片: 股票总数 / 上涨数 / 涨停数 / 最新交易日
- 嵌入 StockList 组件
- 快捷筛选按钮 (按评分/涨幅/涨停)
- 定时刷新开关

**StockList.vue**
- 表格列: 代码, 名称, 市场, 涨跌幅, 现价, 成交额, 成交量, 今日评分, 8日评分, 板块, 公式来源
- 筛选栏: 搜索框, 市场, 板块, 主板/ST开关, 市值, 最小涨幅
- 公式选择: 多选 checkbox + 应用按钮 (调用公式刷新)
- 分页组件
- CSV 导出

**FilterConfig.vue** (未注册路由)
- 左侧: 公式选择 (按分类 Tab 展示) + 组合模式 (OR/AND)
- 右侧: 默认筛选条件编辑 (涨幅/成交额/评分/市场/主板/上市天数)
- 公式测试对话框

---

## 9. 数据流与状态管理

### 9.1 前端状态 (Pinia Store: `stores/stocks.js`)

```javascript
state: {
  stocks: [],      // 股票列表数据
  total: 0,        // 总数
  loading: false,  // 加载状态
  stats: {},       // 统计信息
  params: {        // 查询参数
    page: 1, page_size: 50, sort_by: 'score', sort_order: 'desc'
  }
}
actions: fetchStocks(), fetchStats(), refreshData(), setParams()
```

### 9.2 后端刷新状态

```python
last_refresh_status = {
    "running": False,
    "last_run": None,
    "last_status": None,        # "success" / "failed" / None
    "stock_count": 0,
    "formulas_count": 0,
    "formulas_used": [],
    "error": None,
}
```

---

## 10. 定时任务

- **调度器**: APScheduler `AsyncIOScheduler`
- **间隔**: 10 分钟 (可通过 `REFRESH_INTERVAL_MINUTES` 配置)
- **任务**: `refresh_stock_data()` — 完整刷新流程
- **并发控制**: 线程锁 `_refresh_lock` 防止并发调用
- **后端启动时自动注册** (在 `lifespan` 事件中)

---

## 11. 依赖与部署

### 11.1 后端依赖 (`requirements.txt`)

| 包 | 版本 | 用途 |
|----|------|------|
| fastapi | >=0.104.0 | RESTful API 框架 |
| uvicorn[standard] | >=0.24.0 | ASGI 服务器 |
| sqlalchemy | >=2.0.0 | ORM 框架 |
| apscheduler | >=3.10.0 | 任务调度 |
| starlette | >=0.27.0 | ASGI 工具 |
| numpy | >=1.24.0 | 数值计算 |
| tqcenter | (外部, 需手动安装) | 通达信 Python 插件接口 |

### 11.2 前端依赖 (`package.json`)

- Vue 3.4+ · Vue Router 4.2+ · Pinia 2.1+
- Axios 1.6+ · Element Plus 2.5+ · @element-plus/icons-vue 2.3+
- Vite 5+ (dev)

### 11.3 启动方式

```bash
# 后端
cd backend
pip install -r requirements.txt
python main.py                    # → http://localhost:8000

# 前端
cd frontend
npm install
npm run dev                       # → http://localhost:5173
npm run build                     # 生产构建
```

### 11.4 关键外部依赖: 通达信插件

- 路径: 由 `TDX_PLUGIN_PATH` 环境变量指定（如 `C:/new_tdx64/PYPlugins/user`）
- 模块: `tqcenter.tq` — 通达信 Python 插件 SDK
- 功能依赖: 获取股票列表、板块成分股、行情数据、运行选股公式、获取股票信息
- 无此依赖时系统无法获取数据 (所有数据接口返回空结果)

---

## 12. 已知问题 / 待改进

| 问题 | 描述 | 影响 |
|------|------|------|
| 前端 FilterConfig 未注册路由 | `FilterConfig.vue` 已实现但未在 `router/index.js` 注册 | 用户无法通过导航访问公式配置页 |
| `common.py:compute_stock_metrics` 未使用 | 旧的评分算法 (百分位排名法) 未被任何代码引用 | 死代码 |
| `tdx_service.py:calculate_score` 重复 | 与 `common.py:calculate_composite_score` 功能重复 | 重复代码 |
| 后端日志有调试/警告级别输出 | 存在多处 `logger.warning`/`logger.debug` 调试日志 | 生产环境日志噪音 |
| 数据库迁移硬编码 | `_ensure_market_cap_column()` 使用原生 sqlite3 而非 SQLAlchemy | 技术债务 |
| 增量刷新容错 | 如果公式选股失败使用 JZZT 板块备选，但备选逻辑未持久化 | 数据一致性问题 |
| 市值字段获取可靠性 | `get_market_cap()` 使用 `get_gb_info()` 获取流通股本 | 部分股票可能获取失败 |
| 无测试覆盖 | 项目无任何单元测试/集成测试 | 回归风险高 |

---

## 13. 文件清单

```
E:\py_work\tdxplugins\
├── backend/
│   ├── main.py                      # FastAPI 入口 + 生命周期管理
│   ├── config.py                    # 全局配置 (路径/默认值/公式分类)
│   ├── database.py                  # SQLAlchemy 引擎/会话/迁移
│   ├── auth.py                      # API Token 认证
│   ├── common.py                    # 工具函数 + EVE 评分算法
│   ├── requirements.txt             # Python 依赖
│   ├── data/stock_data.db           # SQLite 数据库 (自动创建)
│   ├── models/__init__.py           # 7 个 ORM 模型（含 StockSector）
│   ├── routers/
│   │   ├── __init__.py              # 路由聚合导出
│   │   ├── stocks.py                # 股票相关 API (5 endpoints)
│   │   ├── filters.py               # 筛选配置 API (7 endpoints)
│   │   ├── formulas.py              # 公式管理 API (6 endpoints)
│   │   └── system.py                # 系统管理 API (9 endpoints)
│   └── services/
│       ├── __init__.py              # 服务导出
│       ├── tdx_service.py           # 通达信数据源封装 + 公式执行
│       ├── refresh_service.py       # 数据刷新编排 (完整+轻量)
│       ├── filter_service.py        # 筛选配置 CRUD + 应用过滤
│       └── formulas_service.py      # 公式管理 CRUD
├── frontend/
│   ├── index.html                   # HTML 入口
│   ├── package.json                 # npm 配置
│   ├── vite.config.js               # Vite 构建配置 (/api 代理)
│   └── src/
│       ├── main.js                  # Vue 应用入口
│       ├── App.vue                  # 根组件
│       ├── api/index.js             # Axios API 客户端 (4 模块)
│       ├── router/index.js          # Vue Router (2 路由)
│       ├── stores/stocks.js         # Pinia 状态管理
│       └── views/
│           ├── Dashboard.vue        # 仪表盘
│           ├── StockList.vue        # 股票列表
│           └── FilterConfig.vue     # 公式+筛选配置
├── logs/backend.log                 # 运行日志
└── SPEC.md                          # 本文档
```

---

## 14. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | — | 初始版本，基础架构 + EVE 评分 + 增量刷新 |
