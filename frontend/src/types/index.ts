// User types
export interface User {
  id: number
  username: string
  display_name: string
  status: 'pending' | 'active' | 'disabled'
  role: 'user' | 'admin'
  created_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  password: string
  display_name: string
}

export interface Token {
  access_token: string
  token_type: string
}

// Room types
export interface Room {
  id: number
  name: string
  has_password: boolean
  small_blind: number
  big_blind: number
  max_seats: number
  max_buyin: number
  owner_id: number
  status: 'idle' | 'waiting' | 'playing'
  seats: Seat[]
  player_count: number
}

export interface Seat {
  seat_index: number
  user_id: number | null
  user_name: string | null
  chips: number
  total_buyin: number  // 累计买入金额
  net_chips: number    // 净筹码 = chips - total_buyin
  status: 'empty' | 'waiting' | 'ready' | 'playing' | 'folded' | 'all_in' | 'disconnected'
}

export interface CreateRoomRequest {
  name: string
  password?: string
  small_blind: number
  max_seats: number
  max_buyin: number
}

export interface JoinRoomRequest {
  password?: string
  buyin: number
}

// Game types
export interface Card {
  rank: string
  suit: string
}

export interface PlayerState {
  user_id: number
  username: string
  seat_index: number
  chips: number
  current_bet: number
  total_bet: number
  status: string
  cards: Card[]
  is_dealer: boolean
  is_sb: boolean
  is_bb: boolean
  is_current: boolean
  is_in_hand?: boolean
}

export interface PotInfo {
  amount: number
  players: number[]
}

export interface GameState {
  room_id: number
  phase: 'preflop' | 'flop' | 'turn' | 'river' | 'showdown' | 'ended'
  community_cards: Card[]
  pots: PotInfo[]
  current_pot: number
  current_bet: number
  min_raise: number
  current_player_id: number | null
  dealer_seat: number
  sb_seat: number
  bb_seat: number
  players: PlayerState[]
  winners: WinnerInfo[]
  is_active: boolean
  action_timeout?: number
  remaining_time?: number
}

export interface WinnerInfo {
  user_id: number
  amount: number
  hand?: string
}

export interface GameAction {
  action: 'fold' | 'check' | 'call' | 'raise' | 'all_in'
  amount?: number
}

// WebSocket message types
export interface WSMessage {
  type: string
  data: any
}

export interface ChatMessage {
  user_id: number
  username: string
  message: string
  is_system?: boolean
}
