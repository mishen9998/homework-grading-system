<template>
  <div class="teacher-messages">
    <div class="messages-header">
      <h2>消息中心</h2>
      <div class="header-tabs">
        <button 
          :class="['tab-btn', { active: activeTab === 'messages' }]"
          @click="activeTab = 'messages'"
        >
          消息
        </button>
        <button 
          :class="['tab-btn', { active: activeTab === 'friends' }]"
          @click="activeTab = 'friends'"
        >
          好友
          <span v-if="pendingRequests.length > 0" class="badge">{{ pendingRequests.length }}</span>
        </button>
      </div>
    </div>

    <div v-if="activeTab === 'messages'" class="messages-content">
      <div class="filter-tabs">
        <button 
          :class="['filter-tab', { active: activeFilter === 'all' }]"
          @click="activeFilter = 'all'"
        >
          全部
        </button>
        <button 
          :class="['filter-tab', { active: activeFilter === 'unread' }]"
          @click="activeFilter = 'unread'"
        >
          未读
        </button>
      </div>

      <div class="messages-list">
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="filteredMessages.length === 0" class="empty">
          {{ activeFilter === 'unread' ? '暂无未读消息' : '暂无消息' }}
        </div>
        <div v-else>
          <div 
            v-for="message in filteredMessages" 
            :key="message.id" 
            :class="['message-item', { unread: !message.read }]"
            @click="handleMessageClick(message)"
          >
            <div class="message-icon">
              <span v-if="message.type === 'submission'">📝</span>
              <span v-else-if="message.type === 'student'">👨‍🎓</span>
              <span v-else>📢</span>
            </div>
            <div class="message-content">
              <div class="message-header">
                <h4>{{ message.title }}</h4>
                <span class="message-time">{{ formatTime(message.created_at) }}</span>
              </div>
              <p class="message-text">{{ message.content }}</p>
              <div v-if="message.student_name" class="message-student">
                学生：{{ message.student_name }}
              </div>
            </div>
            <div v-if="!message.read" class="unread-dot"></div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'friends'" class="friends-content">
      <div class="my-code-card">
        <h3>我的好友代码</h3>
        <div class="code-display">
          <span class="code">{{ currentUser?.friend_code || '加载中...' }}</span>
          <button class="copy-btn" @click="copyFriendCode">复制</button>
        </div>
        <p class="code-hint">分享此代码给学生或同事，让他们添加你</p>
      </div>

      <div class="add-friend-card">
        <h3>添加好友</h3>
        <div class="add-friend-form">
          <input 
            v-model="friendCodeInput" 
            type="text" 
            placeholder="输入好友代码"
            maxlength="10"
            @keyup.enter="searchFriend"
          >
          <button class="search-btn" @click="searchFriend" :disabled="searching">
            {{ searching ? '搜索中...' : '搜索' }}
          </button>
        </div>
        <div v-if="searchResult" class="search-result">
          <div class="user-info">
            <div class="avatar">{{ searchResult.name?.charAt(0) }}</div>
            <div class="info">
              <span class="name">{{ searchResult.name }}</span>
              <span class="role">{{ searchResult.role === 'student' ? '学生' : '老师' }}</span>
              <span v-if="searchResult.college" class="college">{{ searchResult.college }}</span>
            </div>
          </div>
          <button class="add-btn" @click="addFriend" :disabled="adding">
            {{ adding ? '添加中...' : '添加好友' }}
          </button>
        </div>
        <div v-if="searchError" class="search-error">{{ searchError }}</div>
      </div>

      <div v-if="pendingRequests.length > 0" class="pending-requests">
        <h3>好友请求 ({{ pendingRequests.length }})</h3>
        <div class="requests-list">
          <div v-for="request in pendingRequests" :key="request.id" class="request-item">
            <div class="user-info">
              <div class="avatar">{{ request.user?.name?.charAt(0) }}</div>
              <div class="info">
                <span class="name">{{ request.user?.name }}</span>
                <span class="role">{{ request.user?.role === 'student' ? '学生' : '老师' }}</span>
              </div>
            </div>
            <div class="request-actions">
              <button class="accept-btn" @click="acceptRequest(request.id)">接受</button>
              <button class="reject-btn" @click="rejectRequest(request.id)">拒绝</button>
            </div>
          </div>
        </div>
      </div>

      <div class="friends-list-section">
        <h3>我的好友 ({{ friends.length }})</h3>
        <div v-if="friendsLoading" class="loading">加载中...</div>
        <div v-else-if="friends.length === 0" class="empty-friends">
          暂无好友，快去添加吧！
        </div>
        <div v-else class="friends-list">
          <div v-for="friend in friends" :key="friend.id" class="friend-item" @click="goToChat(friend)">
            <div class="user-info">
              <div class="avatar">{{ friend.user?.name?.charAt(0) }}</div>
              <div class="info">
                <span class="name">{{ friend.user?.name }}</span>
                <span class="role">{{ friend.user?.role === 'student' ? '学生' : '老师' }}</span>
                <span v-if="friend.user?.college" class="college">{{ friend.user?.college }}</span>
              </div>
            </div>
            <div class="friend-actions">
              <button class="chat-btn" @click.stop="goToChat(friend)">聊天</button>
              <button class="delete-btn" @click.stop="removeFriend(friend.friendship_id, friend.user?.name)">
                删除
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { friendsAPI } from '@/api/friends'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const authStore = useAuthStore()
const currentUser = computed(() => authStore.user)

const activeTab = ref('messages')
const loading = ref(true)
const activeFilter = ref('all')
const messages = ref([])

const friendsLoading = ref(false)
const friends = ref([])
const pendingRequests = ref([])

const friendCodeInput = ref('')
const searching = ref(false)
const searchResult = ref(null)
const searchError = ref('')
const adding = ref(false)

let loadingTimeout = null
let abortController = null

const filteredMessages = computed(() => {
  if (activeFilter.value === 'unread') {
    return messages.value.filter(m => !m.read)
  }
  return messages.value
})

const formatTime = (dateString) => {
  const date = new Date(dateString)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / (1000 * 60))
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
}

const handleMessageClick = (message) => {
  if (!message.read) {
    message.read = true
  }
}

const loadFriends = async () => {
  friendsLoading.value = true
  try {
    const [friendsRes, pendingRes] = await Promise.all([
      friendsAPI.getFriends(),
      friendsAPI.getPendingRequests()
    ])
    friends.value = friendsRes.data.friends || []
    pendingRequests.value = pendingRes.data.requests || []
  } catch (error) {
    console.error('加载好友失败:', error)
    friends.value = []
    pendingRequests.value = []
  } finally {
    friendsLoading.value = false
  }
}

const copyFriendCode = () => {
  if (currentUser.value?.friend_code) {
    navigator.clipboard.writeText(currentUser.value.friend_code)
    alert('好友代码已复制！')
  }
}

const searchFriend = async () => {
  if (!friendCodeInput.value.trim()) {
    searchError.value = '请输入好友代码'
    return
  }
  
  searching.value = true
  searchResult.value = null
  searchError.value = ''
  
  try {
    const res = await friendsAPI.searchUser(friendCodeInput.value.trim())
    searchResult.value = res.data.user
  } catch (error) {
    searchError.value = error.response?.data?.error || '搜索失败'
    searchResult.value = null
  } finally {
    searching.value = false
  }
}

const addFriend = async () => {
  if (!searchResult.value) return
  
  adding.value = true
  try {
    await friendsAPI.addFriend(searchResult.value.friend_code)
    alert('好友请求已发送！')
    searchResult.value = null
    friendCodeInput.value = ''
    loadFriends()
  } catch (error) {
    alert(error.response?.data?.error || '添加失败')
  } finally {
    adding.value = false
  }
}

const acceptRequest = async (requestId) => {
  try {
    await friendsAPI.acceptRequest(requestId)
    pendingRequests.value = pendingRequests.value.filter(r => r.id !== requestId)
    loadFriends()
    alert('已接受好友请求！')
  } catch (error) {
    alert(error.response?.data?.error || '操作失败')
  }
}

const rejectRequest = async (requestId) => {
  try {
    await friendsAPI.rejectRequest(requestId)
    pendingRequests.value = pendingRequests.value.filter(r => r.id !== requestId)
  } catch (error) {
    alert(error.response?.data?.error || '操作失败')
  }
}

const removeFriend = async (friendshipId, friendName) => {
  if (!confirm(`确定要删除好友 ${friendName} 吗？`)) return
  
  try {
    await friendsAPI.removeFriend(friendshipId)
    friends.value = friends.value.filter(f => f.friendship_id !== friendshipId)
  } catch (error) {
    alert(error.response?.data?.error || '删除失败')
  }
}

const goToChat = (friend) => {
  router.push({
    path: '/teacher/chat',
    query: { friendId: friend.user?.id, friendName: friend.user?.name }
  })
}

onMounted(() => {
  loading.value = true
  loadingTimeout = setTimeout(() => {
    messages.value = []
    loading.value = false
  }, 500)
  loadFriends()
})

onUnmounted(() => {
  if (loadingTimeout) {
    clearTimeout(loadingTimeout)
    loadingTimeout = null
  }
  if (abortController) {
    abortController.abort()
    abortController = null
  }
})
</script>

<style scoped>
.teacher-messages {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.messages-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.messages-header h2 {
  margin: 0;
  color: #333;
  font-size: 24px;
}

.header-tabs {
  display: flex;
  gap: 10px;
}

.tab-btn {
  padding: 10px 20px;
  background: white;
  border: 2px solid #e0e0e0;
  border-radius: 25px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
  position: relative;
}

.tab-btn.active {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

.badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background: #e74c3c;
  color: white;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.filter-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.filter-tab {
  padding: 8px 16px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
}

.filter-tab.active {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.loading,
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.message-item {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  display: flex;
  align-items: flex-start;
  gap: 15px;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
}

.message-item:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  transform: translateY(-2px);
}

.message-item.unread {
  background: #f8f9ff;
  border-left: 4px solid #667eea;
}

.message-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.message-content {
  flex: 1;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.message-header h4 {
  margin: 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.message-time {
  color: #999;
  font-size: 12px;
}

.message-text {
  margin: 0 0 8px 0;
  color: #666;
  font-size: 14px;
  line-height: 1.5;
}

.message-student {
  color: #667eea;
  font-size: 13px;
  font-weight: 500;
}

.unread-dot {
  width: 8px;
  height: 8px;
  background: #667eea;
  border-radius: 50%;
  position: absolute;
  top: 20px;
  right: 20px;
}

.friends-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.my-code-card,
.add-friend-card,
.pending-requests,
.friends-list-section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.my-code-card h3,
.add-friend-card h3,
.pending-requests h3,
.friends-list-section h3 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.code-display {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 10px;
}

.code {
  font-size: 28px;
  font-weight: bold;
  color: #667eea;
  letter-spacing: 4px;
}

.copy-btn {
  padding: 8px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.copy-btn:hover {
  background: #5568d3;
}

.code-hint {
  margin: 0;
  color: #999;
  font-size: 13px;
}

.add-friend-form {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
}

.add-friend-form input {
  flex: 1;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  text-transform: uppercase;
}

.add-friend-form input:focus {
  outline: none;
  border-color: #667eea;
}

.search-btn {
  padding: 12px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.search-btn:hover:not(:disabled) {
  background: #5568d3;
}

.search-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.search-result {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f8f9ff;
  border-radius: 8px;
  margin-top: 10px;
}

.search-error {
  color: #e74c3c;
  font-size: 14px;
  margin-top: 10px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.avatar {
  width: 45px;
  height: 45px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
  font-weight: bold;
}

.info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name {
  font-weight: 600;
  color: #333;
  font-size: 15px;
}

.role {
  font-size: 12px;
  color: #667eea;
}

.college {
  font-size: 12px;
  color: #999;
}

.add-btn {
  padding: 10px 20px;
  background: #27ae60;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.add-btn:hover:not(:disabled) {
  background: #219a52;
}

.add-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.requests-list,
.friends-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.request-item,
.friend-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.3s;
}

.friend-item:hover {
  background: #e8f4fd;
}

.request-actions {
  display: flex;
  gap: 8px;
}

.accept-btn {
  padding: 8px 16px;
  background: #27ae60;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.3s;
}

.accept-btn:hover {
  background: #219a52;
}

.reject-btn {
  padding: 8px 16px;
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.3s;
}

.reject-btn:hover {
  background: #c0392b;
}

.friend-actions {
  display: flex;
  gap: 8px;
}

.chat-btn {
  padding: 8px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.3s;
}

.chat-btn:hover {
  background: #5568d3;
}

.delete-btn {
  padding: 8px 16px;
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.3s;
}

.delete-btn:hover {
  background: #c0392b;
}

.empty-friends {
  text-align: center;
  padding: 30px;
  color: #999;
}
</style>
