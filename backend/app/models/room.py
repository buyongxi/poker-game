import enum


class RoomStatus(str, enum.Enum):
    IDLE = "idle"        # 空闲，无人
    WAITING = "waiting"  # 等待玩家准备
    PLAYING = "playing"  # 游戏中


class SeatStatus(str, enum.Enum):
    EMPTY = "empty"      # 空座位
    WAITING = "waiting"  # 等待准备
    READY = "ready"      # 已准备
    PLAYING = "playing"  # 游戏中
    FOLDED = "folded"    # 已弃牌
    ALL_IN = "all_in"    # 全押
    DISCONNECTED = "disconnected"  # 断线
