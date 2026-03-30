import axios from 'axios'
import type { User, LoginRequest, RegisterRequest, Token } from '@/types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ? `${import.meta.env.VITE_API_BASE_URL}/api` : '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  async login(data: LoginRequest): Promise<Token> {
    const formData = new FormData()
    formData.append('username', data.username)
    formData.append('password', data.password)
    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async register(data: RegisterRequest): Promise<User> {
    const response = await api.post('/auth/register', data)
    return response.data
  },

  async getMe(): Promise<User> {
    const response = await api.get('/auth/me')
    return response.data
  }
}

export const userApi = {
  async getCurrentUser(): Promise<User> {
    const response = await api.get('/users/me')
    return response.data
  },

  async getAllUsers(): Promise<User[]> {
    const response = await api.get('/users/')
    return response.data
  }
}

export const adminApi = {
  async getPendingUsers(): Promise<User[]> {
    const response = await api.get('/admin/pending')
    return response.data
  },

  async activateUser(userId: number): Promise<void> {
    await api.post(`/admin/users/${userId}/activate`)
  },

  async disableUser(userId: number): Promise<void> {
    await api.post(`/admin/users/${userId}/disable`)
  },

  async enableUser(userId: number): Promise<void> {
    await api.post(`/admin/users/${userId}/enable`)
  },

  async initAdmin(
    username: string,
    password: string,
    displayName = '管理员'
  ): Promise<{ message: string; username?: string }> {
    const response = await api.post('/admin/init-admin', {
      username,
      password,
      display_name: displayName
    })
    return response.data
  },

  async setAdmin(userId: number, isAdmin: boolean): Promise<void> {
    const response = await api.post('/admin/set-admin', {
      user_id: userId,
      is_admin: isAdmin
    })
    return response.data
  }
}

export const roomApi = {
  async create(data: import('@/types').CreateRoomRequest): Promise<import('@/types').Room> {
    const response = await api.post('/rooms/', data)
    return response.data
  },

  async getAll(): Promise<import('@/types').Room[]> {
    const response = await api.get('/rooms/')
    return response.data
  },

  async getById(roomId: number): Promise<import('@/types').Room> {
    const response = await api.get(`/rooms/${roomId}`)
    return response.data
  },

  async delete(roomId: number): Promise<void> {
    await api.delete(`/rooms/${roomId}`)
  },

  async join(roomId: number, data: import('@/types').JoinRoomRequest): Promise<import('@/types').Seat> {
    const response = await api.post(`/rooms/${roomId}/join`, data)
    return response.data
  },

  async leave(roomId: number): Promise<void> {
    await api.post(`/rooms/${roomId}/leave`)
  },

  async ready(roomId: number): Promise<void> {
    await api.post(`/rooms/${roomId}/ready`)
  },

  async unready(roomId: number): Promise<void> {
    await api.post(`/rooms/${roomId}/unready`)
  },

  async switchSeat(roomId: number, seatIndex: number): Promise<import('@/types').Seat> {
    const response = await api.post(`/rooms/${roomId}/switch-seat`, { seat_index: seatIndex })
    return response.data
  },

  async rebuy(roomId: number, amount: number): Promise<import('@/types').Seat> {
    const response = await api.post(`/rooms/${roomId}/rebuy`, { amount })
    return response.data
  }
}

export default api
