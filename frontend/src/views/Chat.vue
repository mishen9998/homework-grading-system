<template>
  <div class="chat-container">
    <div class="conversations-list">
      <div class="conversations-header">
        <h3>消息</h3>
        <span v-if="totalUnread > 0" class="unread-badge">{{ totalUnread }}</span>
      </div>
      
      <div v-if="loadingConversations" class="loading">加载中...</div>
      
      <div v-else-if="conversations.length === 0" class="empty">
        <p>暂无好友</p>
        <p class="hint">添加好友后即可开始聊天</p>
      </div>
      
      <div v-else class="conversation-items">
        <div 
          v-for="conv in conversations" 
          :key="conv.friend.id"
          :class="['conversation-item', { active: selectedFriend?.id === conv.friend.id }]"
          @click="selectConversation(conv)"
        >
          <div class="avatar">
            {{ conv.friend.name?.charAt(0) || '?' }}
          </div>
          <div class="conversation-info">
            <div class="conversation-name">{{ conv.friend.name }}</div>
            <div class="last-message" v-if="conv.last_message">
              <span v-if="conv.last_message.file_name" class="file-indicator">📎</span>
              {{ conv.last_message.file_name || conv.last_message.content }}
            </div>
          </div>
          <div class="conversation-meta">
            <div class="time" v-if="conv.last_message">{{ formatTime(conv.last_message.created_at) }}</div>
            <span v-if="conv.unread_count > 0" class="unread-dot">{{ conv.unread_count }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <div class="chat-area" v-if="selectedFriend">
      <div class="chat-header">
        <div class="friend-info">
          <div class="avatar">{{ selectedFriend.name?.charAt(0) || '?' }}</div>
          <div class="name">{{ selectedFriend.name }}</div>
        </div>
      </div>
      
      <div class="messages-container" ref="messagesContainer">
        <div v-if="loadingMessages" class="loading">加载中...</div>
        
        <div v-else class="messages-list">
          <template v-for="(group, index) in groupedMessages" :key="index">
            <div class="date-divider">
              <span>{{ group.date }}</span>
            </div>
            <div 
              v-for="msg in group.messages" 
              :key="msg.id"
              :class="['message', { 'my-message': msg.sender_id === currentUserId }]"
            >
              <div class="message-content">
                <div v-if="msg.file_name" class="file-message" @click="downloadFile(msg)">
                  <span class="file-icon">📎</span>
                  <div class="file-info">
                    <div class="file-name">{{ msg.file_name }}</div>
                    <div class="file-size">{{ formatFileSize(msg.file_size) }}</div>
                  </div>
                  <span class="download-icon">⬇</span>
                </div>
                <div v-else class="text-message">{{ msg.content }}</div>
              </div>
              <div class="message-time">{{ formatMessageTime(msg.created_at) }}</div>
            </div>
          </template>
        </div>
      </div>
      
      <div class="chat-input">
        <label class="file-upload-btn">
          <input type="file" ref="fileInput" @change="handleFileSelect" hidden>
          <span>📎</span>
        </label>
        <input 
          v-model="newMessage" 
          @keyup.enter="sendMessage"
          placeholder="输入消息..."
          class="message-input"
        >
        <button @click="sendMessage" class="send-btn" :disabled="!newMessage.trim() && !selectedFile">
          发送
        </button>
      </div>
      
      <div v-if="selectedFile" class="file-preview">
        <span>📎 {{ selectedFile.name }}</span>
        <button @click="cancelFile" class="cancel-btn">×</button>
        <button @click="sendFile" class="send-file-btn">发送文件</button>
      </div>
    </div>
    
    <div class="no-chat-selected" v-else>
      <div class="placeholder">
        <span class="icon">💬</span>
        <p>选择一个好友开始聊天</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { chatsAPI } from '@/api/chats'

const route = useRoute()
const authStore = useAuthStore()
const currentUserId = computed(() => authStore.user?.id)

const conversations = ref([])
const messages = ref([])
const selectedFriend = ref(null)
const newMessage = ref('')
const loadingConversations = ref(false)
const loadingMessages = ref(false)
const messagesContainer = ref(null)
const fileInput = ref(null)
const selectedFile = ref(null)
const totalUnread = ref(0)

const groupedMessages = computed(() => {
  const groups = []
  let currentGroup = null
  
  messages.value.forEach(msg => {
    const date = formatDate(msg.created_at)
    
    if (!currentGroup || currentGroup.date !== date) {
      currentGroup = {
        date: date,
        messages: []
      }
      groups.push(currentGroup)
    }
    
    currentGroup.messages.push(msg)
  })
  
  return groups
})

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  
  if (date.toDateString() === today.toDateString()) {
    return '今天'
  } else if (date.toDateString() === yesterday.toDateString()) {
    return '昨天'
  } else {
    return date.toLocaleDateString('zh-CN', { 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric',
      weekday: 'long'
    })
  }
}

const loadConversations = async () => {
  loadingConversations.value = true
  try {
    const response = await chatsAPI.getConversations()
    conversations.value = response.data.conversations
    totalUnread.value = conversations.value.reduce((sum, c) => sum + c.unread_count, 0)
    
    if (route.query.friendId) {
      const friendId = parseInt(route.query.friendId)
      const conv = conversations.value.find(c => c.friend.id === friendId)
      if (conv) {
        await selectConversation(conv)
      } else if (route.query.friendName) {
        selectedFriend.value = {
          id: friendId,
          name: route.query.friendName
        }
      }
    }
  } catch (error) {
    console.error('加载会话失败:', error)
  } finally {
    loadingConversations.value = false
  }
}

const selectConversation = async (conv) => {
  selectedFriend.value = conv.friend
  await loadMessages()
}

const loadMessages = async () => {
  if (!selectedFriend.value) return
  
  loadingMessages.value = true
  try {
    const response = await chatsAPI.getMessages(selectedFriend.value.id)
    messages.value = response.data.messages
    
    await nextTick()
    scrollToBottom()
    
    const conv = conversations.value.find(c => c.friend.id === selectedFriend.value.id)
    if (conv) {
      conv.unread_count = 0
      totalUnread.value = conversations.value.reduce((sum, c) => sum + c.unread_count, 0)
    }
  } catch (error) {
    console.error('加载消息失败:', error)
  } finally {
    loadingMessages.value = false
  }
}

const sendMessage = async () => {
  if (!newMessage.value.trim() || !selectedFriend.value) return
  
  try {
    const response = await chatsAPI.sendMessage({
      receiver_id: selectedFriend.value.id,
      content: newMessage.value.trim()
    })
    
    messages.value.push(response.data.chat_message)
    newMessage.value = ''
    
    await nextTick()
    scrollToBottom()
    
    updateLastMessage(response.data.chat_message)
  } catch (error) {
    console.error('发送消息失败:', error)
    alert('发送失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const handleFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
  }
}

const cancelFile = () => {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const sendFile = async () => {
  if (!selectedFile.value || !selectedFriend.value) return
  
  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('receiver_id', selectedFriend.value.id)
  
  try {
    const response = await chatsAPI.uploadFile(formData)
    
    messages.value.push(response.data.chat_message)
    cancelFile()
    
    await nextTick()
    scrollToBottom()
    
    updateLastMessage(response.data.chat_message)
  } catch (error) {
    console.error('发送文件失败:', error)
    alert('发送失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const downloadFile = async (msg) => {
  try {
    const response = await chatsAPI.downloadFile(msg.id)
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', msg.file_name)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('下载文件失败:', error)
    alert('下载失败')
  }
}

const updateLastMessage = (msg) => {
  const conv = conversations.value.find(c => c.friend.id === selectedFriend.value.id)
  if (conv) {
    conv.last_message = msg
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

const formatMessageTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const formatFileSize = (bytes) => {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(() => {
  loadConversations()
})
</script>

<style scoped>
.chat-container {
  display: flex;
  height: calc(100vh - 120px);
  background: #f5f5f5;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.conversations-list {
  width: 300px;
  background: white;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
}

.conversations-header {
  padding: 20px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.conversations-header h3 {
  margin: 0;
  color: #333;
}

.unread-badge {
  background: #e74c3c;
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.loading, .empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
}

.empty .hint {
  font-size: 12px;
  margin-top: 8px;
}

.conversation-items {
  flex: 1;
  overflow-y: auto;
}

.conversation-item {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid #f0f0f0;
}

.conversation-item:hover {
  background: #f5f5f5;
}

.conversation-item.active {
  background: #e8f4fd;
}

.avatar {
  width: 45px;
  height: 45px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
  flex-shrink: 0;
}

.conversation-info {
  flex: 1;
  margin-left: 12px;
  overflow: hidden;
}

.conversation-name {
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.last-message {
  font-size: 13px;
  color: #999;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-indicator {
  margin-right: 4px;
}

.conversation-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  margin-left: 10px;
}

.time {
  font-size: 11px;
  color: #999;
  margin-bottom: 4px;
}

.unread-dot {
  background: #e74c3c;
  color: white;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
}

.chat-header {
  padding: 15px 20px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  align-items: center;
}

.friend-info {
  display: flex;
  align-items: center;
}

.friend-info .avatar {
  width: 40px;
  height: 40px;
  font-size: 16px;
}

.friend-info .name {
  margin-left: 12px;
  font-weight: 500;
  color: #333;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #fafafa;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.date-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 10px 0;
}

.date-divider span {
  background: rgba(0, 0, 0, 0.1);
  color: #666;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.message {
  max-width: 70%;
}

.message.my-message {
  align-self: flex-end;
}

.message-content {
  padding: 10px 15px;
  border-radius: 12px;
  background: white;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.message.my-message .message-content {
  background: #667eea;
  color: white;
}

.text-message {
  word-break: break-word;
  line-height: 1.4;
}

.file-message {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 8px 12px;
  background: #f0f0f0;
  border-radius: 8px;
  transition: background 0.2s;
}

.message.my-message .file-message {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.file-message:hover {
  background: #e0e0e0;
}

.file-icon {
  font-size: 24px;
}

.file-info {
  flex: 1;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
}

.file-size {
  font-size: 11px;
  opacity: 0.7;
}

.download-icon {
  font-size: 16px;
}

.message-time {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
  text-align: right;
}

.message.my-message .message-time {
  color: rgba(255, 255, 255, 0.7);
}

.chat-input {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  border-top: 1px solid #e0e0e0;
  background: white;
  gap: 10px;
}

.file-upload-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 50%;
  background: #f0f0f0;
  transition: background 0.2s;
}

.file-upload-btn:hover {
  background: #e0e0e0;
}

.message-input {
  flex: 1;
  padding: 10px 15px;
  border: 1px solid #e0e0e0;
  border-radius: 20px;
  outline: none;
  font-size: 14px;
}

.message-input:focus {
  border-color: #667eea;
}

.send-btn {
  padding: 10px 20px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #5568d3;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-preview {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: #f5f5f5;
  border-top: 1px solid #e0e0e0;
  font-size: 13px;
}

.cancel-btn {
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-file-btn {
  background: #667eea;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 12px;
}

.no-chat-selected {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
}

.placeholder {
  text-align: center;
  color: #999;
}

.placeholder .icon {
  font-size: 60px;
  display: block;
  margin-bottom: 15px;
}
</style>
