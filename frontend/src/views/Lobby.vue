<template>
  <div class="lobby-container">
    <el-header class="lobby-header">
      <h1>德州扑克</h1>
      <div class="user-info">
        <span>{{ authStore.user?.display_name }}</span>
        <el-button v-if="authStore.isAdmin" @click="router.push('/admin')" text>
          管理后台
        </el-button>
        <el-button @click="handleLogout" text>退出</el-button>
      </div>
    </el-header>

    <el-main class="lobby-main">
      <div class="lobby-content">
        <div class="lobby-actions">
          <el-button type="primary" @click="showCreateDialog = true">
            创建房间
          </el-button>
          <el-button @click="roomStore.fetchRooms()">刷新</el-button>
        </div>

        <div class="rooms-grid">
          <el-card
            v-for="room in roomStore.rooms"
            :key="room.id"
            class="room-card"
            shadow="hover"
            @click="handleJoinRoom(room)"
          >
            <div class="room-info">
              <h3>{{ room.name }}</h3>
              <div class="room-details">
                <span>盲注: {{ room.small_blind }}/{{ room.big_blind }}</span>
                <span>人数: {{ room.player_count }}/{{ room.max_seats }}</span>
              </div>
              <div class="room-status">
                <el-tag :type="getStatusType(room.status)">
                  {{ getStatusText(room.status) }}
                </el-tag>
                <el-tag v-if="room.has_password" type="warning">私密</el-tag>
              </div>
            </div>
          </el-card>

          <el-empty v-if="roomStore.rooms.length === 0" description="暂无房间" />
        </div>
      </div>
    </el-main>

    <!-- Create Room Dialog -->
    <el-dialog v-model="showCreateDialog" title="创建房间" width="400px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="80px">
        <el-form-item label="房间名" prop="name">
          <el-input v-model="createForm.name" placeholder="请输入房间名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="createForm.password" placeholder="留空表示公开房间" />
        </el-form-item>
        <el-form-item label="小盲注" prop="small_blind">
          <el-input-number v-model="createForm.small_blind" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="最大人数" prop="max_seats">
          <el-input-number v-model="createForm.max_seats" :min="2" :max="9" />
        </el-form-item>
        <el-form-item label="最大买入" prop="max_buyin">
          <el-input-number v-model="createForm.max_buyin" :min="100" :step="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateRoom">创建</el-button>
      </template>
    </el-dialog>

    <!-- Join Room Dialog -->
    <el-dialog v-model="showJoinDialog" title="加入房间" width="400px">
      <el-form :model="joinForm" ref="joinFormRef" label-width="80px">
        <el-form-item v-if="selectedRoom?.has_password" label="密码" prop="password">
          <el-input v-model="joinForm.password" type="password" placeholder="请输入房间密码" />
        </el-form-item>
        <el-form-item label="买入金额" prop="buyin">
          <el-input-number
            v-model="joinForm.buyin"
            :min="selectedRoom?.big_blind || 20"
            :max="selectedRoom?.max_buyin || 2000"
            :step="selectedRoom?.big_blind || 20"
          />
          <span style="margin-left: 8px; color: #999">
            ({{ selectedRoom?.big_blind }} - {{ selectedRoom?.max_buyin }})
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showJoinDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmJoinRoom">加入</el-button>
      </template>

      <el-alert
        v-if="roomStore.error"
        :title="roomStore.error"
        type="error"
        show-icon
        :closable="false"
        style="margin-top: 16px"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import type { Room } from '@/types'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const roomStore = useRoomStore()

const showCreateDialog = ref(false)
const showJoinDialog = ref(false)
const selectedRoom = ref<Room | null>(null)
const createFormRef = ref<FormInstance>()
const joinFormRef = ref<FormInstance>()

const createForm = reactive({
  name: '',
  password: '',
  small_blind: 10,
  max_seats: 9,
  max_buyin: 2000
})

const joinForm = reactive({
  password: '',
  buyin: 1000
})

const createRules: FormRules = {
  name: [{ required: true, message: '请输入房间名', trigger: 'blur' }],
  small_blind: [{ required: true, message: '请设置小盲注', trigger: 'blur' }],
  max_seats: [{ required: true, message: '请设置最大人数', trigger: 'blur' }],
  max_buyin: [{ required: true, message: '请设置最大买入', trigger: 'blur' }]
}

onMounted(() => {
  roomStore.fetchRooms()
})

function getStatusType(status: string) {
  switch (status) {
    case 'idle': return 'info'
    case 'waiting': return 'success'
    case 'playing': return 'warning'
    default: return 'info'
  }
}

function getStatusText(status: string) {
  switch (status) {
    case 'idle': return '空闲'
    case 'waiting': return '等待中'
    case 'playing': return '游戏中'
    default: return status
  }
}

async function handleCreateRoom() {
  const valid = await createFormRef.value?.validate()
  if (!valid) return

  const room = await roomStore.createRoom(createForm)
  if (room) {
    showCreateDialog.value = false
    createFormRef.value?.resetFields()
    router.push(`/room/${room.id}`)
  }
}

function handleJoinRoom(room: Room) {
  selectedRoom.value = room
  joinForm.buyin = room.max_buyin
  joinForm.password = ''
  roomStore.error = null
  showJoinDialog.value = true
}

async function confirmJoinRoom() {
  if (!selectedRoom.value) return

  const success = await roomStore.joinRoom(
    selectedRoom.value.id,
    joinForm.password || undefined,
    joinForm.buyin
  )

  if (success) {
    showJoinDialog.value = false
    router.push(`/room/${selectedRoom.value.id}`)
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.lobby-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.lobby-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.lobby-header h1 {
  color: #fff;
  font-size: 24px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.lobby-main {
  flex: 1;
  padding: 24px;
}

.lobby-content {
  max-width: 1200px;
  margin: 0 auto;
}

.lobby-actions {
  margin-bottom: 24px;
  display: flex;
  gap: 12px;
}

.rooms-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.room-card {
  cursor: pointer;
  transition: transform 0.2s;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.room-card:hover {
  transform: translateY(-4px);
}

.room-info h3 {
  margin: 0 0 12px 0;
  color: #fff;
}

.room-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #aaa;
  font-size: 14px;
  margin-bottom: 12px;
}

.room-status {
  display: flex;
  gap: 8px;
}
</style>
