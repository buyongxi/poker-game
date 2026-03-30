# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

德州扑克游戏系统 - 为小型社交圈（≤20 人）设计的纯娱乐型在线德州扑克平台。

## 技术架构

**后端**
- FastAPI + SQLAlchemy (异步) + SQLite
- WebSocket 实时通信
- JWT 认证
- 核心游戏逻辑：`backend/app/game/engine.py` (游戏引擎), `deck.py`, `hand_evaluator.py`, `pot_manager.py`

**前端**
- Vue 3 + TypeScript + Vite + Pinia
- Element Plus UI 组件库
- 路径别名：`@` → `frontend/src`

## 开发命令

### 后端
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py --admin-username admin --admin-password <PASSWORD>
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

### 检查
- 后端：`python -m compileall backend/app`
- 前端：`cd frontend && npm ci && npm run build`

## 核心配置

**后端配置** (`backend/app/config.py`):
- `ACTION_TIMEOUT`: 玩家操作超时 (秒，默认 30)
- `MAX_USERS`: 最大用户数 (20)
- `MAX_ROOMS`: 最大房间数 (10)

**环境变量** (`backend/.env`):
```
SECRET_KEY=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<password>
```

## 代码结构

**后端关键模块**:
- `app/api/`: REST API 路由 (auth, users, rooms, admin)
- `app/game/`: 游戏核心逻辑
- `app/websocket/`: WebSocket 连接管理
- `app/services/`: 业务逻辑层

**前端关键模块**:
- `src/views/`: 页面组件 (Login, Register, Lobby, Room, Admin)
- `src/stores/`: Pinia 状态管理 (auth, game, room)
- `src/api/`: API 调用封装

## 游戏流程

1. 用户注册/登录 → 进入大厅
2. 创建/加入房间 → 准备
3. 游戏开始 → 盲注 → 发牌 → 四轮下注 (翻牌前/翻牌/转牌/河牌) → 摊牌 → 结算
4. 自动开始下一手或返回房间
