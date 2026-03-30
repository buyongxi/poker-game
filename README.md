# 德州扑克游戏系统

一个为小型社交圈（≤20 人）设计的纯娱乐型在线德州扑克平台。

## 技术栈

- **后端**: Python 3.10+, FastAPI, SQLAlchemy (异步), SQLite
- **前端**: Vue 3, TypeScript, Vite, Pinia, Element Plus
- **实时通信**: WebSocket
- **认证**: JWT

## 功能特性

### 核心功能
- 用户注册与审核系统
- 房间创建/加入机制
- 实时游戏状态同步
- 断线重连支持（5 分钟超时）
- 内置聊天功能

### 德州扑克游戏逻辑
- **盲注系统**: 小盲注 10，大盲注 20（可配置）
- **买入范围**: 最小买入=大盲注，最大买入=2000（100 倍大盲注）
- **四轮下注**: 翻牌前（Preflop）、翻牌（Flop）、转牌（Turn）、河牌（River）
- **操作类型**: 弃牌（Fold）、过牌（Check）、跟注（Call）、加注（Raise）、全押（All-in）
- **底池管理**: 支持主池和边池计算（多人全押场景）
- **牌型判定**: 皇家同花顺 → 同花顺 → 四条 → 葫芦 → 同花 → 顺子 → 三条 → 两对 → 一对 → 高牌

### 管理员功能
- 用户审核（启用审核模式时）
- 房间管理
- 游戏监控

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 pnpm

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

# 编辑 .env 文件，设置 SECRET_KEY 和管理员账户
# 或直接在启动命令中指定管理员账户

# 启动服务器（同时创建初始管理员）
python run.py --admin-username admin --admin-password <YOUR_ADMIN_PASSWORD>

# 自定义配置启动
python run.py --admin-username admin --admin-password <YOUR_ADMIN_PASSWORD> --action-timeout 60
```

后端将在 http://localhost:8000 运行。

### 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 复制环境变量示例（可选）
cp .env.example .env.development

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:5173 运行。

## 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/              # REST API 路由 (auth, users, rooms, admin)
│   │   ├── game/             # 游戏核心逻辑
│   │   │   ├── engine.py     # 游戏引擎（状态管理、流程控制）
│   │   │   ├── deck.py       # 牌组管理
│   │   │   ├── hand_evaluator.py  # 牌型评估
│   │   │   ├── player.py     # 玩家状态
│   │   │   └── pot_manager.py # 底池管理
│   │   ├── models/           # SQLAlchemy 数据库模型
│   │   ├── schemas/          # Pydantic 数据模型
│   │   ├── services/         # 业务逻辑层
│   │   ├── websocket/        # WebSocket 连接管理
│   │   ├── config.py         # 配置管理
│   │   └── database.py       # 数据库初始化
│   ├── .env.example          # 环境变量示例
│   ├── requirements.txt      # Python 依赖
│   └── run.py                # 启动脚本
│
└── frontend/
    ├── src/
    │   ├── api/              # API 调用封装
    │   ├── components/       # Vue 组件
    │   ├── router/           # Vue Router 路由配置
    │   ├── stores/           # Pinia 状态管理
    │   │   ├── auth.ts       # 认证状态
    │   │   ├── game.ts       # 游戏状态
    │   │   └── room.ts       # 房间状态
    │   ├── types/            # TypeScript 类型定义
    │   └── views/            # 页面视图 (Login, Lobby, Room, Admin)
    ├── .env.example          # 前端环境变量示例
    ├── package.json
    └── vite.config.ts        # Vite 构建配置
```

## 游戏规则

### 盲注结构
- 小盲注（SB）：10
- 大盲注（BB）：20

### 买入规则
- 最小买入：大盲注金额（20）
- 最大买入：2000（100 倍大盲注）

### 玩家操作
| 操作 | 说明 |
|------|------|
| Fold（弃牌） | 放弃本局，失去已下注筹码 |
| Check（过牌） | 不加注，保持当前下注（仅当无人加注时可用） |
| Call（跟注） | 匹配当前最高下注 |
| Raise（加注） | 增加下注金额，最小加注为大盲注的 2 倍 |
| All-in（全押） | 押上所有筹码 |

### 牌型排名（从高到低）
1. **皇家同花顺** (Royal Flush): A K Q J 10 同花顺
2. **同花顺** (Straight Flush): 五张连续同花色牌
3. **四条** (Four of a Kind): 四张同点数牌
4. **葫芦** (Full House): 三条 + 一对
5. **同花** (Flush): 五张同花色牌
6. **顺子** (Straight): 五张连续牌（不同花）
7. **三条** (Three of a Kind): 三张同点数牌
8. **两对** (Two Pair): 两个对子
9. **一对** (One Pair): 两张同点数牌
10. **高牌** (High Card): 无以上牌型，比最大牌

### 游戏流程
1. **准备阶段**: 玩家加入房间 → 准备就绪
2. **开始游戏**: 房主开始游戏 → 分配座位
3. **盲注**: 小盲注 → 大盲注
4. **发牌**: 每位玩家 2 张底牌
5. **翻牌前下注**: 从大盲注左侧玩家开始
6. **翻牌**: 发出 3 张公共牌 → 第二轮下注
7. **转牌**: 发出 1 张公共牌 → 第三轮下注
8. **河牌**: 发出 1 张公共牌 → 第四轮下注
9. **摊牌**: 剩余玩家亮牌比牌
10. **结算**: 分配底池 → 开始下一手或返回房间

## 配置项

### 后端配置 (`backend/.env`)

```env
# 应用设置
DEBUG=true
SECRET_KEY=your-secret-key-change-in-production-use-long-random-string

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./poker.db

# JWT 认证
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# CORS（支持多个起源）
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"]

# 游戏设置
ACTION_TIMEOUT=30           # 玩家操作超时（秒）
RECONNECT_TIMEOUT=300       # 断线重连超时（秒）
AUTO_START_DELAY=3          # 自动开始下一手前延迟（秒）
MAX_CHAT_LENGTH=500         # 聊天消息最大长度

# 管理员账户（可选，留空则跳过自动创建）
ADMIN_USERNAME=
ADMIN_PASSWORD=
ADMIN_DISPLAY_NAME=
```

### 前端配置 (`frontend/.env.development`)

```env
# FastAPI 后端 HTTP 地址
VITE_API_BASE_URL=http://localhost:8000

# FastAPI 后端 WebSocket 地址
VITE_WS_BASE_URL=ws://localhost:8000
```

### 启动参数

```bash
python run.py --admin-username admin --admin-password <PASSWORD> --action-timeout 60
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--admin-username` | 初始管理员用户名 | - |
| `--admin-password` | 初始管理员密码 | - |
| `--admin-display-name` | 初始管理员显示名称 | 管理员 |
| `--action-timeout` | 玩家操作超时（秒） | 30 |

## API 文档

启动后端后访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## WebSocket 通信

### 连接
```
ws://localhost:8000/ws/room/{roomId}?token={jwt_token}
```

### 消息类型

#### 客户端 → 服务端
| 类型 | 说明 |
|------|------|
| `ready` | 准备就绪 |
| `unready` | 取消准备 |
| `start_game` | 开始游戏（房主） |
| `stop_game` | 停止游戏（房主） |
| `action` | 玩家操作（fold/check/call/raise/all_in） |
| `chat` | 发送聊天消息 |

#### 服务端 → 客户端
| 类型 | 说明 |
|------|------|
| `game_state` | 游戏状态更新 |
| `room_state` | 房间状态更新 |
| `chat` | 聊天消息 |
| `user_joined` | 用户加入 |
| `user_disconnected` | 用户断开连接 |
| `user_left` | 用户离开 |
| `owner_changed` | 房主变更 |
| `room_deleted` | 房间已删除 |
| `hand_complete` | 一局结束结果 |
| `game_ended` | 游戏结束 |
| `info` | 提示信息 |
| `error` | 错误信息 |

## 开发说明

### 添加新 API

1. 在 `backend/app/schemas/` 创建 Pydantic 模型
2. 在 `backend/app/services/` 创建服务类
3. 在 `backend/app/api/` 创建路由

### 添加新页面

1. 在 `frontend/src/views/` 创建 Vue 组件
2. 在 `frontend/src/router/index.ts` 添加路由
3. 如需状态管理，在 `frontend/src/stores/` 创建 Pinia store

### 代码检查

```bash
# 后端
cd backend
python -m compileall app

# 前端
cd frontend
npm ci && npm run build
```

## 限制说明

- 最大用户数：20
- 最大房间数：10
- 单房间最大玩家数：6（标准德州扑克桌）
- 会话超时：30 分钟无活动
- 登录锁定：15 分钟（5 次失败尝试后）

## 许可证

MIT License

## 联系方式

- 邮箱：buyongxi@foxmail.com
