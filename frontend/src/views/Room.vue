<template>
  <div class="room-container">
    <!-- Room Header -->
    <div class="room-header">
      <div class="room-title">
        <el-button @click="handleLeave" :icon="ArrowLeft" circle :disabled="!canLeave" />
        <h2>{{ roomStore.currentRoom?.name }}</h2>
        <el-tag :type="getStatusType(roomStore.currentRoom?.status)">
          {{ getStatusText(roomStore.currentRoom?.status) }}
        </el-tag>
      </div>
      <div class="room-info">
        <span>盲注: {{ roomStore.currentRoom?.small_blind }}/{{ roomStore.currentRoom?.big_blind }}</span>
        <span>买入: {{ roomStore.currentRoom?.max_buyin }}</span>
      </div>
    </div>

    <!-- Game Area -->
    <div class="game-area">
      <!-- Poker Table -->
      <div class="poker-table">
        <!-- Community Cards -->
        <div class="community-cards">
          <div
            v-for="(card, index) in gameStore.gameState?.community_cards || []"
            :key="index"
            class="card"
          >
            <Card :card="card" />
          </div>
          <div v-for="i in (5 - (gameStore.gameState?.community_cards?.length || 0))" :key="'empty-' + i" class="card empty" />
        </div>

        <!-- Pot Info -->
        <div class="pot-info">
          <span>底池: {{ gameStore.gameState?.current_pot || 0 }}</span>
          <span v-if="gameStore.gameState?.current_bet">
            当前注: {{ gameStore.gameState.current_bet }}
          </span>
        </div>

        <!-- Players -->
        <div class="players-container">
          <PlayerSeat
            v-for="seat in sortedSeats"
            :key="seat.seat_index"
            :seat="seat"
            :player="getPlayer(seat.user_id)"
            :is-current="gameStore.gameState?.current_player_id === seat.user_id"
            :max-seats="roomStore.currentRoom?.max_seats || 9"
            :is-owner="seat.user_id === roomStore.currentRoom?.owner_id"
            :is-me="seat.user_id === myUserId"
            @sit="handleSit"
          />
        </div>
      </div>

      <!-- Action Panel -->
      <div class="action-panel" v-if="showActionPanel">
        <div class="my-cards" v-if="myPlayer">
          <template v-if="myPlayer.cards.length > 0">
            <Card v-for="(card, i) in myPlayer.cards" :key="i" :card="card" />
          </template>
          <div v-else class="my-cards-placeholder" aria-hidden="true">
            <span class="card-slot" /><span class="card-slot" />
          </div>
        </div>

        <div class="my-info" v-if="myPlayer">
          <span>筹码: {{ myPlayer.chips }}</span>
          <span>当前下注: {{ myPlayer.current_bet }}</span>
          <span>净筹码: <span :class="mySeat?.net_chips >= 0 ? 'net-positive' : 'net-negative'">{{ mySeat?.net_chips >= 0 ? '+' : '' }}{{ mySeat?.net_chips }}</span></span>
        </div>

        <div class="action-turn-zone">
          <div class="action-buttons" v-if="isMyTurn">
          <div class="timeout-warning" v-if="remainingTime !== null">
            <span :class="{ 'time-critical': isTimeCritical }">
              剩余时间: {{ remainingTime }}秒
            </span>
          </div>
          <el-button @click="handleAction('fold')" type="danger">弃牌</el-button>
          <el-button
            v-if="canCheck"
            @click="handleAction('check')"
            type="info"
          >
            过牌
          </el-button>
          <el-button
            v-if="canCall"
            @click="handleAction('call')"
            type="primary"
          >
            跟注 {{ callAmount }}
          </el-button>
          <el-popover
            v-if="canRaise"
            placement="top"
            :width="320"
            trigger="click"
            v-model:visible="showRaiseDialog"
          >
            <template #reference>
              <el-button type="success">加注</el-button>
            </template>
            <div class="raise-popover">
              <div class="raise-amount">加注到: {{ raiseAmount }}</div>
              <el-slider
                v-model="raiseAmount"
                :min="minRaise"
                :max="maxRaise"
                :step="roomStore.currentRoom?.big_blind || 20"
              />
              <div class="raise-presets">
                <el-button size="small" v-for="preset in raisePresets" :key="preset.label" @click="applyPreset(preset.value)">
                  {{ preset.label }}
                </el-button>
              </div>
              <div class="raise-actions">
                <el-button size="small" @click="showRaiseDialog = false">取消</el-button>
                <el-button size="small" type="primary" @click="confirmRaise">确认</el-button>
              </div>
            </div>
          </el-popover>
          <el-button @click="handleAction('all_in')" type="warning">全押</el-button>
        </div>

          <div class="waiting-info" v-else-if="gameStore.gameState?.is_active">
            <span>等待其他玩家...</span>
          </div>
        </div>

        <!-- In-game unready button -->
        <div class="in-game-actions" v-if="gameStore.gameState?.is_active">
          <el-button size="small" type="info" @click="handleInGameUnready">
            {{ isOwner ? '本局结束后停止游戏' : '本局结束后退出' }}
          </el-button>
        </div>
      </div>

      <!-- Pre-game Panel -->
      <div class="pregame-panel" v-if="!gameStore.gameState?.is_active">
        <div class="my-seat-info" v-if="mySeat">
          <div class="seat-row">
            <span class="seat-label">座位</span>
            <span class="seat-value">{{ mySeat.seat_index + 1 }}</span>
          </div>
          <div class="seat-row">
            <span class="seat-label">筹码</span>
            <span class="seat-value chips">{{ mySeat.chips }}</span>
          </div>
          <div class="seat-row">
            <span class="seat-label">净筹码</span>
            <span class="seat-value" :class="mySeat.net_chips >= 0 ? 'net-positive' : 'net-negative'">
              {{ mySeat.net_chips >= 0 ? '+' : '' }}{{ mySeat.net_chips }}
            </span>
          </div>
          <div class="seat-row">
            <span class="seat-label">状态</span>
            <el-tag size="small" :type="mySeat.status === 'ready' ? 'success' : 'info'">
              {{ mySeat.status === 'ready' ? '已准备' : '未准备' }}
            </el-tag>
          </div>
        </div>

        <!-- 固定高度区域，避免补充筹码面板出现/消失时整页跳动 -->
        <div class="pregame-rebuy-area" v-if="mySeat">
          <div class="rebuy-panel" v-if="mySeat.chips === 0">
            <el-alert type="warning" :closable="false" show-icon>
              你的筹码已用完，请补充筹码后继续游戏
            </el-alert>
            <div class="rebuy-form">
              <el-input-number
                v-model="rebuyAmount"
                :min="roomStore.currentRoom?.big_blind || 20"
                :max="roomStore.currentRoom?.max_buyin || 2000"
                :step="100"
              />
              <el-button type="primary" @click="handleRebuy">补充筹码</el-button>
            </div>
          </div>
        </div>

        <div class="pregame-actions">
          <el-button
            v-if="mySeat && mySeat.chips > 0 && mySeat.status !== 'ready'"
            type="success"
            @click="gameStore.sendReady()"
          >
            准备
          </el-button>
          <el-button
            v-if="mySeat && mySeat.status === 'ready'"
            type="info"
            @click="gameStore.sendUnready()"
          >
            取消准备
          </el-button>
          <el-button
            v-if="isOwner && canStart"
            type="primary"
            @click="gameStore.sendStartGame()"
          >
            开始游戏
          </el-button>
        </div>

        <div class="game-actions" v-if="gameStore.gameState?.is_active">
          <el-button
            type="warning"
            @click="gameStore.sendStopGame()"
          >
            停止游戏
          </el-button>
        </div>

        <div class="ready-count">
          已准备: {{ readyCount }} / {{ playerCount }}
        </div>
      </div>
    </div>

    <!-- Chat Panel -->
    <div class="chat-panel">
      <div class="chat-messages" ref="chatRef">
        <div
          v-for="(msg, index) in gameStore.chatMessages"
          :key="index"
          class="chat-message"
          :class="{ 'is-system': msg.is_system }"
        >
          <span class="chat-user" :class="{ 'is-system': msg.is_system }">{{ msg.username }}:</span>
          <span class="chat-text" :class="{ 'is-system': msg.is_system }">{{ msg.message }}</span>
        </div>
      </div>
      <div class="chat-input">
        <el-input
          v-model="chatMessage"
          placeholder="输入消息..."
          @keyup.enter="sendChat"
        >
          <template #append>
            <el-button @click="sendChat">发送</el-button>
          </template>
        </el-input>
      </div>
    </div>

    <!-- Hand Complete Dialog -->
    <el-dialog
      v-model="showHandComplete"
      title="本局结束"
      width="400px"
      :close-on-click-modal="true"
      :close-on-press-escape="true"
    >
      <div class="winners">
        <div v-for="winner in handWinners" :key="winner.user_id" class="winner">
          <span>{{ winner.username || `玩家${winner.user_id}` }}</span>
          <span>赢得 {{ winner.amount }}</span>
          <span v-if="winner.hand">{{ winner.hand }}</span>
        </div>
      </div>
      <template #footer>
        <span class="hand-complete-hint">下一局即将自动开始...</span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElNotification } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useGameStore } from '@/stores/game'
import PlayerSeat from '@/components/game/PlayerSeat.vue'
import Card from '@/components/game/Card.vue'
import type { PlayerState } from '@/types'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const gameStore = useGameStore()

const chatMessage = ref('')
const chatRef = ref<HTMLElement>()
const showRaiseDialog = ref(false)
const showHandComplete = ref(false)
const handWinners = ref<any[]>([])
const raiseAmount = ref(0)
const rebuyAmount = ref(0)
const isLeavingIntentionally = ref(false)
const remainingTime = ref<number | null>(null)
let countdownInterval: ReturnType<typeof setInterval> | null = null

const roomId = computed(() => parseInt(route.params.id as string))

const myUserId = computed(() => authStore.user?.id)

const mySeat = computed(() =>
  roomStore.currentRoom?.seats.find(s => s.user_id === myUserId.value)
)

const myPlayer = computed(() =>
  gameStore.gameState?.players.find(p => p.user_id === myUserId.value)
)

const isMyTurn = computed(
  () => gameStore.gameState?.current_player_id === myUserId.value
)

const actionTimeoutSeconds = computed(
  () => gameStore.gameState?.action_timeout ?? 30
)

/** 剩余时间低于该阈值时高亮（随服务器配置的思考时间上限成比例） */
const isTimeCritical = computed(() => {
  const rem = remainingTime.value
  if (rem === null) return false
  const t = actionTimeoutSeconds.value
  const threshold = Math.max(3, Math.min(15, Math.ceil(t / 3)))
  return rem <= threshold
})

const canLeave = computed(() => {
  // Owner can always leave (will transfer ownership)
  if (isOwner.value) {
    // But not during active game hand
    if (gameStore.gameState?.is_active) {
      const myPlayer = gameStore.gameState.players?.find((p: any) => p.user_id === myUserId.value)
      if (myPlayer && myPlayer.is_in_hand) {
        return false
      }
    }
    return true
  }

  // Non-owner: Can leave if not in an active game hand
  if (gameStore.gameState?.is_active) {
    // In active game - can only leave if not playing (folded out or not in game)
    const myPlayer = gameStore.gameState.players?.find((p: any) => p.user_id === myUserId.value)
    if (myPlayer && myPlayer.is_in_hand) {
      return false
    }
  }
  // Cannot leave if ready (must unready first)
  if (mySeat.value && mySeat.value.status === 'ready') {
    return false
  }
  return true
})

const isOwner = computed(
  () => roomStore.currentRoom?.owner_id === myUserId.value
)

const canStart = computed(() => {
  const readyCount = roomStore.currentRoom?.seats.filter(s => s.status === 'ready').length || 0
  return readyCount >= 2
})

const readyCount = computed(() =>
  roomStore.currentRoom?.seats.filter(s => s.status === 'ready').length || 0
)

const playerCount = computed(() =>
  roomStore.currentRoom?.seats.filter(s => s.status !== 'empty').length || 0
)

const showActionPanel = computed(() =>
  gameStore.gameState?.is_active && myPlayer.value
)

const currentBet = computed(() => gameStore.gameState?.current_bet || 0)

const canCheck = computed(() =>
  myPlayer.value && myPlayer.value.current_bet >= currentBet.value
)

const canCall = computed(() =>
  myPlayer.value && myPlayer.value.current_bet < currentBet.value && myPlayer.value.chips > 0
)

const canRaise = computed(() => {
  if (!myPlayer.value || !gameStore.gameState) return false
  const chipsNeededForCall = currentBet.value - myPlayer.value.current_bet
  const chipsAfterCall = myPlayer.value.chips - chipsNeededForCall
  const maxPossibleRaise = myPlayer.value.chips + myPlayer.value.current_bet
  const minRaiseTotal = gameStore.gameState.min_raise || 0
  // Can only raise if we have enough chips and the min raise is not too high
  // (min raise might be very high after an all-in that didn't fully raise)
  return chipsAfterCall > 0 && maxPossibleRaise >= minRaiseTotal
})

const callAmount = computed(() => {
  if (!myPlayer.value) return 0
  return Math.min(currentBet.value - myPlayer.value.current_bet, myPlayer.value.chips)
})

const minRaise = computed(() => {
  if (!gameStore.gameState || !myPlayer.value) return 0
  // min_raise from backend is already the total amount needed
  return gameStore.gameState.min_raise
})

const maxRaise = computed(() => {
  if (!myPlayer.value) return 0
  return myPlayer.value.chips + myPlayer.value.current_bet
})

const currentPot = computed(() => gameStore.gameState?.current_pot || 0)

const raisePresets = computed(() => {
  const pot = currentPot.value
  const bb = roomStore.currentRoom?.big_blind || 20
  const min = minRaise.value
  const max = maxRaise.value

  const presets = [
    { label: '1/3池', value: pot / 3 },
    { label: '1/2池', value: pot / 2 },
    { label: '2/3池', value: pot * 2 / 3 },
    { label: '满池', value: pot },
    { label: '2x池', value: pot * 2 },
  ]

  // Round to nearest big blind, clamp to [min, max], deduplicate
  const seen = new Set<number>()
  return presets
    .map(p => {
      let v = Math.round(p.value / bb) * bb
      v = Math.max(min, Math.min(max, v))
      return { label: p.label, value: v }
    })
    .filter(p => {
      if (seen.has(p.value)) return false
      seen.add(p.value)
      return true
    })
})

function applyPreset(value: number) {
  raiseAmount.value = value
}

const sortedSeats = computed(() =>
  [...(roomStore.currentRoom?.seats || [])].sort((a, b) => a.seat_index - b.seat_index)
)

function getPlayer(userId: number | null): PlayerState | undefined {
  if (!userId) return undefined
  return gameStore.gameState?.players.find(p => p.user_id === userId)
}

function getStatusType(status?: string) {
  switch (status) {
    case 'idle': return 'info'
    case 'waiting': return 'success'
    case 'playing': return 'warning'
    default: return 'info'
  }
}

function getStatusText(status?: string) {
  switch (status) {
    case 'idle': return '空闲'
    case 'waiting': return '等待中'
    case 'playing': return '游戏中'
    default: return status || ''
  }
}

function handleAction(action: string) {
  gameStore.sendAction(action)
}

function confirmRaise() {
  gameStore.sendAction('raise', raiseAmount.value)
  showRaiseDialog.value = false
}

function sendChat() {
  if (chatMessage.value.trim()) {
    gameStore.sendChat(chatMessage.value.trim())
    chatMessage.value = ''
  }
}

async function handleLeave() {
  console.log('[DEBUG] handleLeave called, canLeave=', canLeave.value, 'isOwner=', isOwner.value)
  if (!canLeave.value) {
    if (gameStore.gameState?.is_active) {
      const myPlayer = gameStore.gameState.players?.find((p: any) => p.user_id === myUserId.value)
      if (myPlayer && myPlayer.is_in_hand) {
        ElMessage.warning('你正在游戏中，请先弃牌后再离开房间')
      } else {
        ElMessage.warning('游戏进行中，请等待本局结束后离开')
      }
    } else if (mySeat.value?.status === 'ready') {
      ElMessage.warning('请先取消准备后再离开房间')
    }
    return
  }
  // Mark as intentional leave
  isLeavingIntentionally.value = true
  console.log('[DEBUG] Calling leaveRoom API for room', roomId.value)
  await roomStore.leaveRoom(roomId.value)
  gameStore.disconnect()
  router.push('/lobby')
}

async function handleSit(seatIndex: number) {
  if (mySeat.value) {
    // Already have a seat, switch to new seat
    await roomStore.switchSeat(roomId.value, seatIndex)
  } else {
    // No seat yet, need to join with buyin
    // This shouldn't happen normally as users join through lobby
    console.log('Need to join room first')
  }
}

async function handleRebuy() {
  if (rebuyAmount.value > 0) {
    const success = await roomStore.rebuyChips(roomId.value, rebuyAmount.value)
    if (success) {
      ElMessage.success('补充筹码成功')
    }
  }
}

function handleInGameUnready() {
  gameStore.sendUnready()
  if (isOwner.value) {
    ElMessage.info('已请求停止游戏，本局结束后将停止')
  } else {
    ElMessage.info('已取消准备，本局结束后将不会参与下一局')
  }
}

// Watch for raise dialog to set initial value
watch(showRaiseDialog, (show) => {
  if (show) {
    raiseAmount.value = minRaise.value
  }
})

// Watch for hand complete
watch(() => gameStore.gameState?.winners, (winners) => {
  if (winners && winners.length > 0 && gameStore.gameState?.phase === 'showdown') {
    handWinners.value = winners.map(w => ({
      ...w,
      username: gameStore.gameState?.players.find(p => p.user_id === w.user_id)?.username
    }))
    showHandComplete.value = true
  }
}, { deep: true })

// Auto-close hand complete dialog when next hand starts
watch(() => gameStore.gameState?.phase, (phase) => {
  if (phase === 'preflop' && showHandComplete.value) {
    showHandComplete.value = false
  }
})

// Watch chat messages to scroll
watch(() => gameStore.chatMessages.length, () => {
  nextTick(() => {
    if (chatRef.value) {
      chatRef.value.scrollTop = chatRef.value.scrollHeight
    }
  })
})

// Watch for room deletion (redirect to lobby)
watch(() => gameStore.connected, (connected) => {
  // If disconnected and not intentional, check if we should redirect
  if (!connected && !isLeavingIntentionally.value && gameStore.gameState === null) {
    // Room might have been deleted, redirect to lobby
    router.push('/lobby')
  }
})

// Watch for game state changes to update countdown
watch(() => gameStore.gameState, (newState) => {
  if (newState && newState.remaining_time !== undefined && newState.remaining_time !== null) {
    remainingTime.value = newState.remaining_time
    // Start local countdown
    if (countdownInterval) {
      clearInterval(countdownInterval)
    }
    countdownInterval = setInterval(() => {
      if (remainingTime.value !== null && remainingTime.value > 0) {
        remainingTime.value--
      }
    }, 1000)
  } else {
    remainingTime.value = null
    if (countdownInterval) {
      clearInterval(countdownInterval)
      countdownInterval = null
    }
  }
}, { deep: true })

// Watch for info messages
watch(() => gameStore.infoMessages.length, () => {
  const messages = gameStore.infoMessages
  if (messages.length > 0) {
    const lastMessage = messages[messages.length - 1]
    ElMessage.warning(lastMessage.message)
  }
})

// Initialize
onMounted(async () => {
  await roomStore.fetchRoom(roomId.value)

  // Set default rebuy amount to max buyin
  rebuyAmount.value = roomStore.currentRoom?.max_buyin || 2000

  if (roomStore.currentRoom && authStore.token) {
    gameStore.connect(roomId.value, authStore.token)
  }
})

onUnmounted(() => {
  // Clear countdown interval
  if (countdownInterval) {
    clearInterval(countdownInterval)
    countdownInterval = null
  }
  // Only disconnect WebSocket, don't leave the room
  // unless it was an intentional leave via the back button
  if (!isLeavingIntentionally.value) {
    // Browser navigation - just disconnect WS, keep seat
    gameStore.disconnect()
  }
})

// Handle browser back/forward navigation
import { onBeforeRouteLeave } from 'vue-router'
onBeforeRouteLeave((to, from, next) => {
  // If not intentional leave (back button click), just disconnect WS
  if (!isLeavingIntentionally.value) {
    gameStore.disconnect()
  }
  next()
})
</script>

<style scoped>
.room-container {
  display: grid;
  grid-template-columns: 1fr 300px;
  grid-template-rows: auto 1fr;
  height: 100vh;
  gap: 0;
  overflow: hidden;
}

.room-header {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.room-title {
  display: flex;
  align-items: center;
  gap: 16px;
}

.room-title h2 {
  margin: 0;
  color: #fff;
}

.room-info {
  display: flex;
  gap: 24px;
  color: #aaa;
}

.game-area {
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow: auto;
  min-height: 0;
}

.poker-table {
  flex: 1;
  background: #0d5c2e;
  border-radius: 200px;
  position: relative;
  min-height: 400px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 8px solid #8b4513;
  box-shadow: inset 0 0 50px rgba(0, 0, 0, 0.3);
}

.community-cards {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.pot-info {
  display: flex;
  gap: 24px;
  font-size: 18px;
  font-weight: bold;
  color: #fff;
  text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);
}

.players-container {
  position: absolute;
  width: 100%;
  height: 100%;
}

.action-panel, .pregame-panel {
  margin-top: 24px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.action-panel {
  min-height: 280px;
}

.pregame-panel {
  min-height: 280px;
}

.my-cards {
  display: flex;
  gap: 8px;
  min-height: 84px;
  height: 84px;
  align-items: center;
  justify-content: center;
}

.my-cards-placeholder {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: center;
}

.card-slot {
  width: 60px;
  height: 84px;
  border-radius: 6px;
  border: 2px dashed rgba(255, 255, 255, 0.2);
  background: rgba(0, 0, 0, 0.15);
  box-sizing: border-box;
}

.action-turn-zone {
  width: 100%;
  min-height: 132px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
}

.my-info {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  color: #aaa;
  font-size: 14px;
  justify-content: center;
  min-height: 22px;
}

.my-seat-info {
  display: flex;
  flex-direction: row;
  gap: 24px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.seat-row {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.seat-label {
  font-size: 12px;
  color: #888;
}

.seat-value {
  font-size: 16px;
  font-weight: bold;
  color: #fff;
}

.seat-value.chips {
  color: #ffd700;
}

.seat-value.net-positive {
  color: #67c23a;
}

.seat-value.net-negative {
  color: #f56c6c;
}

.rebuy-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  background: rgba(230, 162, 60, 0.1);
  border-radius: 8px;
  width: 100%;
  max-width: 400px;
}

.rebuy-form {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: center;
}

.action-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
  min-height: 40px;
  align-items: center;
}

.timeout-warning {
  width: 100%;
  text-align: center;
  margin-bottom: 8px;
  font-size: 14px;
  color: #e6a23c;
}

.timeout-warning .time-critical {
  color: #f56c6c;
  font-weight: bold;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.waiting-info {
  color: #aaa;
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.in-game-actions {
  margin-top: 8px;
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.net-positive {
  color: #67c23a;
}

.net-negative {
  color: #f56c6c;
}

.pregame-rebuy-area {
  width: 100%;
  max-width: 420px;
  min-height: 108px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.pregame-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  min-height: 48px;
  align-items: center;
  justify-content: center;
}

.game-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.ready-count {
  color: #aaa;
  font-size: 14px;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  background: rgba(0, 0, 0, 0.2);
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
  min-height: 0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.chat-message {
  font-size: 14px;
}

.chat-message.is-system {
  background: rgba(103, 194, 60, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
  margin: 2px 0;
}

.chat-user {
  color: #409eff;
  margin-right: 8px;
}

.chat-user.is-system {
  color: #67c23c;
  font-weight: bold;
}

.chat-text {
  color: #ddd;
  white-space: pre-wrap;
}

.chat-text.is-system {
  color: #a0cfa0;
}

.chat-input {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.winners {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hand-complete-hint {
  color: #999;
  font-size: 13px;
}

.raise-popover {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.raise-amount {
  font-weight: bold;
  text-align: center;
}

.raise-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.raise-presets {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px;
}

.raise-presets .el-button {
  margin: 0;
  padding: 4px 10px;
  font-size: 12px;
}

.winner {
  display: flex;
  justify-content: space-between;
  padding: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}
</style>
