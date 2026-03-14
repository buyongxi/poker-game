import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Room, Seat } from '@/types'
import { roomApi } from '@/api'

export const useRoomStore = defineStore('room', () => {
  const rooms = ref<Room[]>([])
  const currentRoom = ref<Room | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchRooms() {
    loading.value = true
    try {
      rooms.value = await roomApi.getAll()
    } catch (e: any) {
      error.value = e.response?.data?.detail || '获取房间列表失败'
    } finally {
      loading.value = false
    }
  }

  async function createRoom(data: {
    name: string
    password?: string
    small_blind: number
    max_seats: number
    max_buyin: number
  }) {
    loading.value = true
    error.value = null
    try {
      const room = await roomApi.create(data)
      rooms.value.push(room)
      return room
    } catch (e: any) {
      error.value = e.response?.data?.detail || '创建房间失败'
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchRoom(roomId: number) {
    loading.value = true
    try {
      currentRoom.value = await roomApi.getById(roomId)
    } catch (e: any) {
      error.value = e.response?.data?.detail || '获取房间信息失败'
    } finally {
      loading.value = false
    }
  }

  async function joinRoom(roomId: number, password: string | undefined, buyin: number) {
    loading.value = true
    error.value = null
    try {
      await roomApi.join(roomId, { password, buyin })
      await fetchRoom(roomId)
      return true
    } catch (e: any) {
      error.value = e.response?.data?.detail || '加入房间失败'
      return false
    } finally {
      loading.value = false
    }
  }

  async function leaveRoom(roomId: number) {
    try {
      await roomApi.leave(roomId)
      currentRoom.value = null
    } catch (e: any) {
      // Room might have been deleted, that's ok
      if (e.response?.status === 404) {
        currentRoom.value = null
      } else {
        error.value = e.response?.data?.detail || '离开房间失败'
      }
    }
  }

  async function setReady(roomId: number) {
    try {
      await roomApi.ready(roomId)
      if (currentRoom.value) {
        const seat = currentRoom.value.seats.find(
          s => s.user_id === parseInt(localStorage.getItem('userId') || '0')
        )
        if (seat) {
          seat.status = 'ready'
        }
      }
    } catch (e: any) {
      error.value = e.response?.data?.detail || '设置准备状态失败'
    }
  }

  async function setUnready(roomId: number) {
    try {
      await roomApi.unready(roomId)
      if (currentRoom.value) {
        const seat = currentRoom.value.seats.find(
          s => s.user_id === parseInt(localStorage.getItem('userId') || '0')
        )
        if (seat) {
          seat.status = 'waiting'
        }
      }
    } catch (e: any) {
      error.value = e.response?.data?.detail || '取消准备状态失败'
    }
  }

  function updateRoomFromWS(data: { room_id: number; status: string; seats: Seat[] }) {
    if (currentRoom.value && currentRoom.value.id === data.room_id) {
      currentRoom.value.status = data.status as any
      currentRoom.value.seats = data.seats
    }
  }

  async function switchSeat(roomId: number, seatIndex: number) {
    try {
      await roomApi.switchSeat(roomId, seatIndex)
      await fetchRoom(roomId)
    } catch (e: any) {
      error.value = e.response?.data?.detail || '切换座位失败'
    }
  }

  return {
    rooms,
    currentRoom,
    loading,
    error,
    fetchRooms,
    createRoom,
    fetchRoom,
    joinRoom,
    leaveRoom,
    setReady,
    setUnready,
    updateRoomFromWS,
    switchSeat
  }
})
