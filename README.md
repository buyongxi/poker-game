# 德州扑克游戏系统

一个为小型社交圈（≤20人）设计的纯娱乐型在线德州扑克平台。

## 技术栈

- **后端**: Python 3.10+, FastAPI, SQLAlchemy, SQLite
- **前端**: Vue 3, TypeScript, Vite, Element Plus
- **实时通信**: WebSocket

## 功能特性

- 用户注册与审核系统
- 创建/加入房间
- 完整德州扑克游戏逻辑
  - 盲注系统
  - 下注轮次（翻牌前、翻牌、转牌、河牌）
  - 底池与边池计算
  - 牌型判定（皇家同花顺到高牌）
- 实时游戏状态同步
- 聊天功能
- 断线重连支持

## 快速开始

### 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制环境配置
cp .env.example .env

# 启动服务器
python run.py
```

后端将在 http://localhost:8000 运行。

### 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:5173 运行。

### 初始化管理员账户

首次运行时，调用以下 API 创建初始管理员账户：

```bash
curl -X POST http://localhost:8000/api/admin/init-admin
```

默认管理员账户：
- 用户名: `admin`
- 密码: `admin123`

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── game/         # 游戏引擎核心
│   │   ├── models/       # 数据库模型
│   │   ├── schemas/      # Pydantic 模型
│   │   ├── services/     # 业务逻辑
│   │   └── websocket/    # WebSocket 处理
│   ├── requirements.txt
│   └── run.py
│
└── frontend/
    ├── src/
    │   ├── api/          # API 调用
    │   ├── components/   # Vue 组件
    │   ├── router/       # 路由配置
    │   ├── stores/       # Pinia 状态管理
    │   ├── types/        # TypeScript 类型
    │   └── views/        # 页面视图
    ├── package.json
    └── vite.config.ts
```

## 游戏规则

### 盲注
- 小盲注：默认 10
- 大盲注：小盲注 × 2

### 买入
- 最小买入：大盲注
- 最大买入：默认 2000（100倍大盲注）

### 操作
- 弃牌（Fold）：放弃本局
- 过牌（Check）：不加注（仅当无人加注时）
- 跟注（Call）：匹配当前下注
- 加注（Raise）：增加下注金额
- 全押（All-in）：押上所有筹码

### 牌型排名（从高到低）
1. 皇家同花顺
2. 同花顺
3. 四条
4. 葫芦
5. 同花
6. 顺子
7. 三条
8. 两对
9. 一对
10. 高牌

## 配置项

编辑 `backend/.env` 文件：

```env
DEBUG=true
SECRET_KEY=your-secret-key
MAX_USERS=20
MAX_ROOMS=10
ACTION_TIMEOUT=30        # 操作超时（秒）
RECONNECT_TIMEOUT=300    # 重连超时（秒）
```

## API 文档

启动后端后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发说明

### 添加新 API

1. 在 `backend/app/schemas/` 创建 Pydantic 模型
2. 在 `backend/app/services/` 创建服务类
3. 在 `backend/app/api/` 创建路由

### 添加新页面

1. 在 `frontend/src/views/` 创建 Vue 组件
2. 在 `frontend/src/router/index.ts` 添加路由

## 许可证

MIT License
