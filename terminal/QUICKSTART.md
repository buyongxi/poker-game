# 终端前端快速参考

本文档提供终端前端的快速参考指南。

## 快速启动

### 在线模式（需要后端服务）

```bash
# 1. 启动后端（在 backend 目录）
python run.py --admin-username admin --admin-password <password>

# 2. 启动终端前端（在 terminal 目录）
cd terminal
pip install -r requirements.txt
python main.py
```

### 离线模式（无需后端）

```bash
cd terminal
pip install -r requirements.txt
python poker_terminal.py
```

## 项目结构

```
terminal/
├── main.py              # 主入口（在线模式）
├── poker_terminal.py    # 离线游戏客户端
├── online_client.py     # 在线游戏客户端（WebSocket）
├── websocket_client.py  # WebSocket 客户端
├── api_client.py        # REST API 客户端
├── lobby.py             # 游戏大厅模块
├── requirements.txt     # Python 依赖
└── ui/
    ├── display.py       # 显示模块
    ├── input.py         # 输入处理
    └── auth.py          # 认证界面
```

## 依赖

- `rich>=13.0.0` - 终端美化库
- `httpx>=0.24.0` - HTTP 客户端
- `websocket-client>=1.5.0` - WebSocket 客户端

安装：`pip install -r requirements.txt`

## 功能特性

### 认证系统
- 用户登录/注册
- JWT Token 认证
- 离线模式支持

### 游戏大厅
- 房间列表显示
- 创建/加入房间
- 房间密码支持

### 在线游戏
- WebSocket 实时连接
- 聊天系统
- 准备/取消准备
- 补充筹码（Rebuy）
- 切换座位
- 剩余时间倒计时

### 游戏显示
- 彩色终端界面
- 位置标记（D/SB/BB）
- 玩家状态（游戏中/弃牌/ALL-IN）
- 牌背显示
- 净筹码统计
- 每局结束结果展示

## 游戏操作

### 在线模式

| 操作 | 说明 |
|-----|------|
| ready | 准备 |
| unready | 取消准备 |
| chat <消息> | 发送聊天 |
| quit | 离开房间 |

### 离线模式

| 操作 | 快捷键 | 说明 |
|-----|--------|------|
| 弃牌 (Fold) | [1] | 放弃当前手牌 |
| 过牌 (Check) | [2] | 不下注通过 |
| 跟注 (Call) | [3] | 跟随当前下注 |
| 加注 (Raise) | [4] | 增加下注金额 |
| 全押 (All-in) | [5] | 押上所有筹码 |

## 牌型大小

```
皇家同花顺 > 同花顺 > 四条 > 葫芦 > 同花 > 顺子 > 三条 > 两对 > 一对 > 高牌
```

## 花色显示

- **红桃 ♥** - 红色
- **方块 ♦** - 红色
- **梅花 ♣** - 白色
- **黑桃 ♠** - 白色

## 位置标记

| 标记 | 含义 |
|-----|------|
| D | 庄家 (Dealer) |
| S | 小盲注 (Small Blind) |
| B | 大盲注 (Big Blind) |
| → | 当前行动玩家 |

## 状态显示

| 状态 | 显示 |
|-----|------|
| 游戏中 | ● 游戏中 |
| 已弃牌 | × 弃牌 |
| 全押 | ★ ALL-IN |
| 准备 | ○ 准备 |
| 等待中 | ○ 等待 |
| 断线 | ○ 断线 |

## 测试

运行功能测试：

```bash
cd terminal
python test_features.py
```

## 常见问题

### 无法连接到后端

确保后端服务正在运行：
```bash
cd backend
python run.py --admin-username admin --admin-password <password>
```

### 依赖安装失败

尝试升级 pip 并重新安装：
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 终端显示异常

确保终端支持真彩色，窗口宽度至少 80 字符。

## 相关文档

- [README.md](README.md) - 终端前端详细文档
- [FEATURES_PLAN.md](FEATURES_PLAN.md) - 功能完善计划
- [SUMMARY.md](SUMMARY.md) - 功能完成总结
