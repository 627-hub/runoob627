# 股票选股监控系统

基于通达信数据源的实时选股监控系统，支持自定义公式、EVE 评分算法、板块筛选。

## 功能

- **选股公式** — 25 个内置公式（涨停板、连板、趋势、竞价），支持自定义启用/禁用
- **EVE 评分** — 多维指标加权评分（动量、攻击力、开盘强度、量能背离等）
- **板块筛选** — 按行业/概念/地区/风格分类筛选，支持多板块交集
- **滚动平均评分** — 8 日历史评分滚动平均，评分稳定性可参考
- **定时刷新** — 每 10 分钟自动刷新全量公式选股
- **前端面板** — Vue 3 实时数据展示，支持多条件组合筛选

## 目录结构

```
tdxplugins/
├── backend/                  # FastAPI 后端
│   ├── main.py               # 应用入口
│   ├── config.py             # 配置
│   ├── database.py           # 数据库初始化
│   ├── common.py             # EVE 评分算法
│   ├── models/               # SQLAlchemy 模型
│   ├── routers/              # API 路由
│   ├── services/             # 业务逻辑
│   │   ├── tdx_service.py    # 通达信数据获取
│   │   ├── refresh_service.py # 数据刷新调度
│   │   └── formulas_service.py # 公式管理
│   └── data/                 # SQLite 数据库
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── views/            # 页面组件
│   │   ├── stores/           # Pinia 状态
│   │   └── api/              # API 调用
│   └── vite.config.js
├── start_backend.bat         # 后端启动脚本
├── .env.example              # 环境变量模板
├── .gitignore
└── README.md
```

## 快速开始

### 前置条件

- Python 3.9+
- Node.js 18+
- 通达信软件（含 `tqcenter` 插件，路径如 `C:/new_tdx64/PYPlugins/user`）

### 后端

```bash
cd backend
cp ../.env.example .env        # 按需修改配置
start_backend.bat               # 或手动设置环境变量
```

或手动启动：

```bash
cd backend
set TDX_PLUGIN_PATH=C:/new_tdx64/PYPlugins/user
python main.py
```

后端默认监听 `http://localhost:8000`。

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认监听 `http://localhost:5173`，Vite 自动代理 `/api` 到后端。

## API 文档

启动后端后访问 `http://localhost:8000/docs` 查看 Swagger 文档。

### 主要接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stocks` | GET | 查询股票列表，支持公式/板块/评分筛选 |
| `/api/refresh/status` | GET | 刷新状态 |
| `/api/refresh/trigger` | POST | 手动触发刷新 |
| `/api/formulas` | GET | 获取所有公式及激活状态 |
| `/api/formulas/active` | PUT | 更新激活公式 |
| `/api/sectors` | GET | 获取板块列表 |

## 配置

通过 `.env` 或环境变量配置：

| 变量 | 说明 |
|------|------|
| `TDX_PLUGIN_PATH` | 通达信 tqcenter 插件路径（必填） |
| `CORS_ORIGINS` | 允许的前端域名，逗号分隔 |
| `API_TOKEN` | 可选 API 认证令牌 |

## 选股公式

内置 5 类 25 个公式：

- **涨停板** (7) — 首板、1进2、2进3、3进4、4进5、5板以上、断板
- **连板** (1) — 连板
- **趋势** (5) — 突破、主升、加速、调整、反弹
- **竞价** (4) — 高开、抢筹、弱转强、分歧转一致
- **首板涨停** (1) — 首板

## 评分算法

EVE 评分基于当日开盘/收盘/最高/最低价及成交量，计算 6 维指标：

- **动量** — 当日涨跌幅贡献
- **攻击力** — 最高价相对昨收的强度
- **支撑** — 收盘相对开盘的强度
- **开盘强度** — 开盘相对昨收
- **量能** — 均量偏离度
- **回撤** — 最低价相对昨收

评分范围 ≈ -50 ~ +150（正值表示强势）。

## 技术栈

- **后端**: Python, FastAPI, SQLAlchemy, APScheduler, SQLite
- **前端**: Vue 3, Vite, Pinia, Axios
- **数据源**: 通达信 tqcenter 插件

## 许可

MIT
