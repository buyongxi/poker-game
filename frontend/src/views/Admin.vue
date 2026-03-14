<template>
  <div class="admin-container">
    <el-header class="admin-header">
      <div class="header-content">
        <h1>管理后台</h1>
        <el-button @click="router.push('/lobby')" text>返回大厅</el-button>
      </div>
    </el-header>

    <el-main class="admin-main">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="待审核用户" name="pending">
          <el-table :data="pendingUsers" style="width: 100%">
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="display_name" label="显示名称" />
            <el-table-column prop="created_at" label="注册时间">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button type="success" size="small" @click="activateUser(row.id)">
                  激活
                </el-button>
                <el-button type="danger" size="small" @click="disableUser(row.id)">
                  拒绝
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="所有用户" name="all">
          <el-table :data="allUsers" style="width: 100%">
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="display_name" label="显示名称" />
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="role" label="角色">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">
                  {{ row.role === 'admin' ? '管理员' : '用户' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="注册时间">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="300">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'disabled'"
                  type="success"
                  size="small"
                  @click="enableUser(row.id)"
                >
                  启用
                </el-button>
                <el-button
                  v-if="row.status === 'active'"
                  type="warning"
                  size="small"
                  @click="disableUser(row.id)"
                >
                  禁用
                </el-button>
                <el-button
                  v-if="row.role !== 'admin'"
                  type="primary"
                  size="small"
                  @click="setAdmin(row.id, true)"
                >
                  设为管理员
                </el-button>
                <el-button
                  v-if="row.role === 'admin' && row.id !== authStore.user?.id"
                  type="info"
                  size="small"
                  @click="setAdmin(row.id, false)"
                >
                  取消管理员
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { adminApi, userApi } from '@/api'
import type { User } from '@/types'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref('pending')
const pendingUsers = ref<User[]>([])
const allUsers = ref<User[]>([])

onMounted(async () => {
  await fetchData()
})

async function fetchData() {
  try {
    pendingUsers.value = await adminApi.getPendingUsers()
    allUsers.value = await userApi.getAllUsers()
  } catch (e) {
    ElMessage.error('获取数据失败')
  }
}

async function activateUser(userId: number) {
  try {
    await adminApi.activateUser(userId)
    ElMessage.success('用户已激活')
    await fetchData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

async function disableUser(userId: number) {
  try {
    await adminApi.disableUser(userId)
    ElMessage.success('用户已禁用')
    await fetchData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

async function enableUser(userId: number) {
  try {
    await adminApi.enableUser(userId)
    ElMessage.success('用户已启用')
    await fetchData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

async function setAdmin(userId: number, isAdmin: boolean) {
  try {
    await adminApi.setAdmin(userId, isAdmin)
    ElMessage.success(isAdmin ? '已设为管理员' : '已取消管理员')
    await fetchData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

function getStatusType(status: string) {
  switch (status) {
    case 'active': return 'success'
    case 'pending': return 'warning'
    case 'disabled': return 'danger'
    default: return 'info'
  }
}

function getStatusText(status: string) {
  switch (status) {
    case 'active': return '正常'
    case 'pending': return '待审核'
    case 'disabled': return '已禁用'
    default: return status
  }
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>

<style scoped>
.admin-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.admin-header {
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
}

.header-content h1 {
  color: #fff;
  margin: 0;
}

.admin-main {
  flex: 1;
  padding: 24px;
}
</style>
