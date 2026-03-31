# 德州扑克游戏系统 - 快速参考

## 项目结构

```
poker-game/
├── backend/           # FastAPI 后端
├── frontend/          # Vue 3 Web 前端
├── terminal/          # Python 终端前端
└── docs/             # 项目文档（如有）
```

## 快速启动

### 1. 启动后端服务

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py --admin-username admin --admin-password <password>
```

后端运行在：http://localhost:8000

### 2. 启动 Web 前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在：http://localhost:5173

### 3. 启动终端前端

```bash
cd terminal
pip install -r requirements.txt
python main.py              # 在线模式
# 或
python poker_terminal.py    # 离线模式
```

## 客户端对比

| 特性 | Web 客户端 | 终端客户端 |
|-----|----------|-----------|
| 界面 | 图形化 GUI | 命令行 CLI |
| 操作 | 鼠标 + 键盘 | 键盘 |
| 在线模式 | ✅ | ✅ |
| 离线模式 | ❌ | ✅ |
| 适用场景 | 桌面浏览器 | 终端/SSH |

## 默认配置

### 后端
- HTTP 端口：8000
- WebSocket 端口：8000
- 数据库：SQLite (poker.db)
- ACTION_TIMEOUT: 30 秒
- RECONNECT_TIMEOUT: 300 秒

### 前端
- 开发端口：5173
- API 地址：http://localhost:8000
- WebSocket 地址：ws://localhost:8000

### 终端前端
- 后端地址：http://localhost:8000
- 盲注：10/20（可配置）
- 最大买入：2000

## 游戏流程

1. **登录/注册** → 进入大厅
2. **创建/加入房间** → 准备
3. **游戏开始**
   - 盲注 → 发底牌 → 翻牌前下注
   - 翻牌 → 下注
   - 转牌 → 下注
   - 河牌 → 下注
   - 摊牌 → 结算
4. **下一局** 或 **离开房间**

## 玩家操作

| 操作 | 说明 | 条件 |
|-----|------|------|
| Fold (弃牌) | 放弃本局 | 任何时候 |
| Check (过牌) | 不加注通过 | 无人加注时 |
| Call (跟注) | 匹配当前下注 | 有人加注时 |
| Raise (加注) | 增加下注 | 有足够筹码 |
| All-in (全押) | 押上所有筹码 | 任何时候 |

## 牌型大小

```
皇家同花顺 > 同花顺 > 四条 > 葫芦 > 同花 > 顺子 > 三条 > 两对 > 一对 > 高牌
```

## API 文档

启动后端后访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## WebSocket 连接

```
ws://localhost:8000/ws/room/{roomId}?token={jwt_token}
```

## 常用命令

### 后端
```bash
cd backend
python run.py --admin-username admin --admin-password <password>
python -m compileall app  # 语法检查
```

### Web 前端
```bash
cd frontend
npm install        # 安装依赖
npm run dev        # 开发服务器
npm run build      # 生产构建
```

### 终端前端
```bash
cd terminal
pip install -r requirements.txt  # 安装依赖
python main.py                   # 在线模式
python poker_terminal.py         # 离线模式
python test_features.py          # 功能测试
```

## 环境变量

### 后端 (.env)
```env
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite+aiosqlite:///./poker.db
ACTION_TIMEOUT=30
RECONNECT_TIMEOUT=300
```

### Web 前端 (.env.development)
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

## 限制说明

- 最大用户数：20
- 最大房间数：10
- 单房间最大玩家数：6
- 会话超时：30 分钟

## 相关文档

- [README.md](README.md) - 项目主文档
- [CONTRIBUTING.md](CONTRIBUTING.md) - 贡献指南
- [CLAUDE.md](CLAUDE.md) - Claude Code 开发指南
- [terminal/README.md](terminal/README.md) - 终端前端文档
- [terminal/QUICKSTART.md](terminal/QUICKSTART.md) - 终端前端快速参考

## 联系方式

- 邮箱：buyongxi@foxmail.com
