<template>
  <div
    class="player-seat"
    :class="{
      'is-current': isCurrent,
      'is-folded': player?.status === 'folded',
      'is-all-in': player?.status === 'all_in',
      'is-empty': !seat.user_id,
      'is-me': isMe
    }"
    :style="seatStyle"
  >
    <div class="seat-content" :class="{ 'has-occupant': !!seat.user_id }">
      <!-- Player Info -->
      <div class="player-info" v-if="seat.user_id">
        <div class="player-name">
          {{ seat.user_name }}
          <span v-if="isOwner" class="owner-crown">👑</span>
          <span v-if="isMe" class="me-badge">我</span>
        </div>
        <div class="player-chips">{{ player?.chips ?? seat.chips }}</div>
        <div class="player-net" :class="seat.net_chips >= 0 ? 'net-positive' : 'net-negative'">
          净: {{ seat.net_chips >= 0 ? '+' : '' }}{{ seat.net_chips }}
        </div>
        <div class="player-bet-row">
          <span v-if="player?.current_bet">下注: {{ player.current_bet }}</span>
        </div>
        <div class="player-status">
          <span v-if="player?.is_dealer" class="dealer-btn">D</span>
          <span v-if="player?.is_sb" class="position-btn sb">SB</span>
          <span v-if="player?.is_bb" class="position-btn bb">BB</span>
        </div>
      </div>

      <!-- Empty Seat -->
      <div class="empty-seat" v-else @click="$emit('sit', seat.seat_index)">
        <span>空位</span>
      </div>

      <!-- Player Cards：占位保持高度，避免有牌/无牌时布局跳动 -->
      <div v-if="seat.user_id && player" class="player-cards">
        <template v-if="player.cards.length > 0">
          <div
            v-for="(card, index) in player.cards"
            :key="index"
            class="mini-card"
            :class="getSuitClass(card.suit)"
          >
            {{ card.rank }}{{ getSuitSymbol(card.suit) }}
          </div>
        </template>
        <!-- 玩家在游戏中但手牌不显示（应显示牌背） -->
        <template v-else-if="isPlayerInHand">
          <div v-for="i in 2" :key="'back-' + i" class="mini-card mini-card-back" />
        </template>
        <!-- 玩家不在游戏中（等待/准备状态）显示占位符 -->
        <template v-else>
          <div v-for="i in 2" :key="'ph-' + i" class="mini-card mini-card-placeholder" aria-hidden="true" />
        </template>
      </div>

      <!-- Folded Overlay -->
      <div class="folded-overlay" v-if="player?.status === 'folded'">
        已弃牌
      </div>

      <!-- All-in Badge -->
      <div class="all-in-badge" v-if="player?.status === 'all_in'">
        ALL IN
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Seat, PlayerState } from '@/types'

const props = defineProps<{
  seat: Seat
  player?: PlayerState
  isCurrent: boolean
  maxSeats: number
  isOwner: boolean
  isMe: boolean
}>()

// Calculate position around the table
const seatStyle = computed(() => {
  const index = props.seat.seat_index
  const total = props.maxSeats // Use actual max seats from room
  const angle = (index / total) * 2 * Math.PI - Math.PI / 2

  const radiusX = 40 // % of container width
  const radiusY = 35 // % of container height

  const x = 50 + radiusX * Math.cos(angle)
  const y = 50 + radiusY * Math.sin(angle)

  return {
    left: `${x}%`,
    top: `${y}%`,
    transform: 'translate(-50%, -50%)'
  }
})

// 判断玩家是否在当前这局牌中（有手牌但可能不显示）
const isPlayerInHand = computed(() => {
  if (!props.player) return false
  const status = props.player.status
  return status === 'playing' || status === 'all_in'
})

function getSuitClass(suit: string) {
  if (suit === 'h' || suit === 'd') return 'red'
  return 'black'
}

function getSuitSymbol(suit: string) {
  switch (suit) {
    case 'h': return '♥'
    case 'd': return '♦'
    case 'c': return '♣'
    case 's': return '♠'
    default: return ''
  }
}
</script>

<style scoped>
.player-seat {
  position: absolute;
  width: 100px;
  transition: all 0.3s ease;
}

.seat-content {
  background: rgba(0, 0, 0, 0.6);
  border-radius: 8px;
  padding: 8px;
  text-align: center;
  position: relative;
  border: 2px solid transparent;
  min-height: 120px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.seat-content.has-occupant {
  min-height: 152px;
}

.player-seat.is-current .seat-content {
  border-color: #67c23c;
  box-shadow: 0 0 10px rgba(103, 194, 60, 0.5);
}

.player-seat.is-folded .seat-content {
  border-color: #606266;
  opacity: 0.7;
}

.player-seat.is-all-in .seat-content {
  border-color: #e6a23c;
}

.player-seat.is-me .seat-content {
  background: rgba(64, 158, 255, 0.15);
}

.player-info {
  color: #fff;
}

.player-name {
  font-weight: bold;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.owner-crown {
  font-size: 10px;
}

.me-badge {
  font-size: 10px;
  background: #409eff;
  color: #fff;
  padding: 1px 4px;
  border-radius: 3px;
}

.player-chips {
  font-size: 14px;
  color: #ffd700;
}

.player-net {
  font-size: 11px;
}

.player-net.net-positive {
  color: #67c23a;
}

.player-net.net-negative {
  color: #f56c6c;
}

.player-bet-row {
  min-height: 16px;
  font-size: 11px;
  color: #67c23a;
}

.player-status {
  display: flex;
  justify-content: center;
  gap: 4px;
  margin-top: 4px;
}

.dealer-btn, .position-btn {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.dealer-btn {
  background: #fff;
  color: #000;
}

.position-btn.sb {
  background: #409eff;
  color: #fff;
}

.position-btn.bb {
  background: #67c23a;
  color: #fff;
}

.empty-seat {
  color: #666;
  font-size: 12px;
  cursor: pointer;
}

.empty-seat:hover {
  color: #999;
}

.player-cards {
  display: flex;
  justify-content: center;
  gap: 2px;
  margin-top: 4px;
  height: 32px;
  align-items: center;
  flex-shrink: 0;
}

.mini-card-placeholder {
  box-sizing: border-box;
  width: 24px;
  height: 32px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px dashed rgba(255, 255, 255, 0.22);
  border-radius: 3px;
}

.mini-card {
  width: 24px;
  height: 32px;
  background: #fff;
  border-radius: 3px;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.mini-card.red {
  color: #d32f2f;
}

.mini-card.black {
  color: #212121;
}

.mini-card-back {
  background: url('/cards/Background.png') center/cover no-repeat;
  border: 1px solid #0a1f3a;
}

.folded-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f56c6c;
  font-size: 12px;
}

.all-in-badge {
  position: absolute;
  top: -8px;
  left: 50%;
  transform: translateX(-50%);
  background: #e6a23c;
  color: #fff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: bold;
}
</style>
