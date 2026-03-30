import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { GameState, Card, PlayerState, WSMessage, ChatMessage } from '@/types'
import { useRoomStore } from './room'

export const useGameStore = defineStore('game', () => {
  const gameState = ref<GameState | null>(null)
  const chatMessages = ref<ChatMessage[]>([])
  const infoMessages = ref<{message: string, timestamp: number}[]>([])
  const connected = ref(false)
  const ws = ref<WebSocket | null>(null)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let currentRoomId: number | null = null
  let currentToken: string | null = null

  function connect(roomId: number, token: string) {
    currentRoomId = roomId
    currentToken = token

    if (ws.value) {
      ws.value.close()
    }

    const wsBaseUrl = import.meta.env.VITE_WS_BASE_URL ||
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    const wsUrl = `${wsBaseUrl}/ws/room/${roomId}?token=${token}`
    ws.value = new WebSocket(wsUrl)

    ws.value.onopen = () => {
      connected.value = true
      reconnectAttempts.value = 0
      console.log('WebSocket connected')
    }

    ws.value.onmessage = (event) => {
      const message: WSMessage = JSON.parse(event.data)
      handleMessage(message)
    }

    ws.value.onclose = () => {
      connected.value = false
      console.log('WebSocket disconnected')
      attemptReconnect()
    }

    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  function attemptReconnect() {
    if (reconnectAttempts.value >= maxReconnectAttempts) {
      console.log('Max reconnect attempts reached')
      return
    }

    if (!currentRoomId || !currentToken) {
      return
    }

    reconnectAttempts.value++
    console.log(`Reconnecting... attempt ${reconnectAttempts.value}`)

    reconnectTimer = setTimeout(() => {
      connect(currentRoomId!, currentToken!)
    }, reconnectDelay)
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    currentRoomId = null
    currentToken = null
    reconnectAttempts.value = 0

    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
    gameState.value = null
    chatMessages.value = []
    infoMessages.value = []
  }

  function handleMessage(message: WSMessage) {
    console.log('[WS] Received message:', message.type, message.data)
    switch (message.type) {
      case 'game_state':
        gameState.value = message.data
        console.log('[WS] Game state updated:', message.data)
        break
      case 'room_state':
        // Update room store with new room state
        const roomStore = useRoomStore()
        roomStore.updateRoomFromWS(message.data)
        break
      case 'chat':
        chatMessages.value.push(message.data)
        // Keep only last 100 messages
        if (chatMessages.value.length > 100) {
          chatMessages.value.shift()
        }
        break
      case 'user_joined':
        // Could show notification
        break
      case 'user_disconnected':
        // Player disconnected but can reconnect
        break
      case 'user_left':
        // Could show notification
        break
      case 'owner_changed':
        // Owner changed - show notification in chat
        // Note: owner_id is already updated via room_state message
        chatMessages.value.push({
          user_id: 0,
          username: '系统',
          message: `👑 房主已转移给 ${message.data.new_owner_name}`,
          is_system: true
        })
        break
      case 'room_deleted':
        // Room was deleted, clear state and redirect
        gameState.value = null
        connected.value = false
        break
      case 'hand_complete':
        // Show hand results in chat
        if (message.data.result_message) {
          chatMessages.value.push({
            user_id: 0,
            username: '系统',
            message: message.data.result_message,
            is_system: true
          })
        }
        break
      case 'game_ended':
        gameState.value = null
        break
      case 'info':
        // Info message for current user - show as notification
        console.log('[WS] Info:', message.data.message)
        infoMessages.value.push({
          message: message.data.message,
          timestamp: Date.now()
        })
        break
      case 'error':
        console.error('Server error:', message.data.message)
        break
    }
  }

  function sendReady() {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify({ type: 'ready', data: {} }))
    }
  }

  function sendUnready() {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify({ type: 'unready', data: {} }))
    }
  }

  function sendStartGame() {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify({ type: 'start_game', data: {} }))
    }
  }

  function sendAction(action: string, amount?: number) {
    if (ws.value && connected.value) {
      console.log('[WS] Sending action:', action, 'amount:', amount)
      ws.value.send(JSON.stringify({
        type: 'action',
        data: { action, amount }
      }))
    } else {
      console.log('[WS] Cannot send action - ws:', ws.value, 'connected:', connected.value)
    }
  }

  function sendChat(message: string) {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify({
        type: 'chat',
        data: { message }
      }))
    }
  }

  function sendStopGame() {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify({ type: 'stop_game', data: {} }))
    }
  }

  return {
    gameState,
    chatMessages,
    infoMessages,
    connected,
    connect,
    disconnect,
    sendReady,
    sendUnready,
    sendStartGame,
    sendAction,
    sendChat,
    sendStopGame
  }
})
