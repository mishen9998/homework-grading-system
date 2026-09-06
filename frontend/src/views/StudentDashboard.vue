<template>
  <div class="student-dashboard">
    <div class="main-content">
      <router-view></router-view>
    </div>

    <div class="bottom-nav">
      <router-link to="/student/knowledge" class="nav-item" active-class="active"><span class="nav-icon">📚</span><span class="nav-label">知识库 · AI</span></router-link>
      <router-link 
        to="/student/home" 
        class="nav-item"
        :class="{ active: $route.path === '/student/home' }"
      >
        <span class="nav-icon">🏠</span>
        <span class="nav-label">首页</span>
      </router-link>
      <router-link 
        to="/student/messages" 
        class="nav-item"
        :class="{ active: $route.path === '/student/messages' }"
      >
        <span class="nav-icon-wrapper">
          <span class="nav-icon">💬</span>
          <span v-if="unreadCount > 0" class="unread-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </span>
        <span class="nav-label">消息</span>
      </router-link>
      <router-link 
        to="/student/profile" 
        class="nav-item"
        :class="{ active: $route.path === '/student/profile' }"
      >
        <span class="nav-icon">👤</span>
        <span class="nav-label">个人中心</span>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { chatsAPI } from '@/api/chats'

const route = useRoute()
const unreadCount = ref(0)
let pollInterval = null
let isPollingActive = ref(true)
let isVisible = ref(true)
let lastFetchTime = 0
const MIN_FETCH_INTERVAL = 5000

const fetchUnreadCount = async () => {
  if (!isPollingActive.value || !isVisible.value) return
  
  const now = Date.now()
  if (now - lastFetchTime < MIN_FETCH_INTERVAL) return
  lastFetchTime = now
  
  try {
    const response = await chatsAPI.getUnreadCount()
    unreadCount.value = response.data.unread_count
  } catch (error) {
    if (error.name !== 'CanceledError' && error.code !== 'ERR_CANCELED') {
      if (error.message?.includes('超时') || error.message?.includes('timeout')) {
        console.warn('获取未读消息数超时，将在下次轮询时重试')
      } else {
        console.error('获取未读消息数失败:', error)
      }
    }
  }
}

const startPolling = () => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
  isPollingActive.value = true
  fetchUnreadCount()
  pollInterval = setInterval(fetchUnreadCount, 120000)
}

const stopPolling = () => {
  isPollingActive.value = false
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

const handleVisibilityChange = () => {
  isVisible.value = document.visibilityState === 'visible'
  if (isVisible.value) {
    fetchUnreadCount()
    startPolling()
  } else {
    stopPolling()
  }
}

onMounted(() => {
  // startPolling()
  // document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

watch(
  () => route.path,
  (newPath, oldPath) => {
    if (newPath !== oldPath && isVisible.value) {
      fetchUnreadCount()
    }
  }
)
</script>

<style scoped>
.student-dashboard {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 70px;
}

.main-content {
  min-height: calc(100vh - 70px);
}

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  display: flex;
  justify-content: space-around;
  padding: 10px 0;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
  z-index: 1000;
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-decoration: none;
  color: #999;
  transition: all 0.3s;
  flex: 1;
}

.nav-item:hover {
  color: #667eea;
}

.nav-item.active {
  color: #667eea;
}

.nav-icon-wrapper {
  position: relative;
  display: inline-block;
}

.nav-icon {
  font-size: 24px;
}

.nav-label {
  font-size: 12px;
  margin-top: 4px;
}

.unread-badge {
  position: absolute;
  top: -8px;
  right: -12px;
  background: #e74c3c;
  color: white;
  font-size: 10px;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  font-weight: bold;
}
</style>
