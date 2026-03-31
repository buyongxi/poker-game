# 终端前端实现计划

## 阶段一：基础架构优化

### 任务 1.1 - 优化显示模块
**文件**: `ui/display.py`
**目标**: 实现状态刷新机制，消除临时状态残留

**实现要点**:
- 使用 `rich.live.Live` 实现动态刷新
- 分离"临时状态"和"持久状态"的渲染
- 添加 `clear_temporary_messages()` 方法

**代码结构**:
```python
class TerminalDisplay:
    def __init__(self):
        self.console = Console()
        self.current_layout = None
        
    def render_game_state(self, game, current_player_id=None):
        """渲染持久状态"""
        
    def render_action_prompt(self, message):
        """渲染临时操作提示"""
        
    def clear_temporary(self):
        """清除临时状态显示"""
```

### 任务 1.2 - 优化游戏客户端
**文件**: `poker_terminal.py`
**目标**: 重构游戏循环，确保状态正确刷新

**实现要点**:
- 在每局开始时清屏
- 在玩家行动前刷新显示
- 在结果显示后清屏

---

## 阶段二：Web 功能移植

### 任务 2.1 - 玩家座位信息
**参考**: `frontend/src/components/game/PlayerSeat.vue`

**新增字段**:
- 净筹码 (`net_chips`) - 记录本局输赢
- 房主标记 - 识别房主玩家
- 更详细的状态显示

**实现**:
```python
@dataclass
class SeatInfo:
    user_id: int
    username: str
    seat_index: int
    chips: int
    net_chips: int  # 新增
    current_bet: int
    cards: List[Card]
    status: str
    is_dealer: bool
    is_sb: bool
    is_bb: bool
    is_current: bool
    is_owner: bool  # 新增
```

### 任务 2.2 - 公共牌显示优化
**参考**: `frontend/src/views/Room.vue`

**实现要点**:
- 未发牌时显示空位占位符
- 已发牌显示具体牌面
- 固定高度布局

### 任务 2.3 - 操作面板
**参考**: `frontend/src/views/Room.vue` - Action Panel

**实现功能**:
- 根据游戏状态显示可用操作
- 加注金额选择（滑块模拟）
- 倒计时显示
- 等待提示

---

## 阶段三：AI 增强

### 任务 3.1 - AI 模块重构
**新建文件**: `ui/ai_bot.py`

**AI 类型**:
```python
class AIBot:
    def __init__(self, user_id, username, personality='normal'):
        self.personality = personality  # 'conservative', 'normal', 'aggressive'
        
    def evaluate_hand_strength(self, game, player):
        """评估手牌强度"""
        
    def decide_action(self, game, valid_actions):
        """决策逻辑"""
```

### 任务 3.2 - 手牌评估器
**实现要点**:
- 考虑 hole cards 强度
- 考虑公共牌配合
- 考虑位置因素
- 考虑底池赔率

---

## 阶段四：视觉效果增强

### 任务 4.1 - 牌桌布局
**实现**: 使用 rich 的表格和面板创建圆形牌桌效果

### 任务 4.2 - 动画效果
- 发牌顺序显示
- 清屏过渡
- 获胜者高亮

---

## 实施顺序

```
阶段一（基础架构）
├── 任务 1.1: 显示模块优化
└── 任务 1.2: 游戏客户端优化

阶段二（Web 功能移植）
├── 任务 2.1: 玩家座位信息
├── 任务 2.2: 公共牌显示
└── 任务 2.3: 操作面板

阶段三（AI 增强）
├── 任务 3.1: AI 模块重构
└── 任务 3.2: 手牌评估器

阶段四（视觉效果）
├── 任务 4.1: 牌桌布局
└── 任务 4.2: 动画效果
```

## 文件结构

```
terminal/
├── README.md
├── REQUIREMENTS.md      # 需求文档
├── IMPLEMENTATION.md    # 本文件
├── requirements.txt
├── poker_terminal.py    # 主入口
├── ai_bot.py            # 新建：AI 模块
└── ui/
    ├── __init__.py
    ├── display.py       # 优化：显示模块
    └── input.py         # 优化：输入处理
```
