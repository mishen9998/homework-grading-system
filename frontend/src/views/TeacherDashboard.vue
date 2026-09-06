<template>
  <div class="teacher-dashboard">
    <header class="dashboard-header">
      <h1>老师作业管理系统</h1>
      <div class="user-info">
        <span>欢迎，{{ authStore.user?.name }}</span>
      </div>
    </header>

    <div class="main-content">
      <router-view />
    </div>

    <nav class="bottom-nav">
      <router-link to="/teacher/knowledge" class="nav-item" active-class="active"><span class="nav-icon">📚</span><span class="nav-label">知识库 · AI</span></router-link>
      <router-link to="/teacher/home" class="nav-item" active-class="active">
        <span class="nav-icon">🏠</span>
        <span class="nav-label">首页</span>
      </router-link>
      <router-link to="/teacher/messages" class="nav-item" active-class="active">
        <span class="nav-icon-wrapper">
          <span class="nav-icon">💬</span>
          <span v-if="unreadCount > 0" class="unread-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </span>
        <span class="nav-label">消息</span>
      </router-link>
      <router-link to="/teacher/profile" class="nav-item" active-class="active">
        <span class="nav-icon">👤</span>
        <span class="nav-label">个人中心</span>
      </router-link>
    </nav>

    <div v-if="showSubmissionsModal" class="modal-overlay" @click="closeSubmissionsModal">
      <div class="modal submissions-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ selectedAssignment?.title }} - 学生提交</h3>
          <button @click="closeSubmissionsModal" class="close-btn">&times;</button>
        </div>
        <div v-if="submissionsLoading" class="loading">加载中...</div>
        <div v-else-if="submissions.length === 0" class="empty">暂无提交</div>
        <div v-else class="submissions-list">
          <div 
            v-for="submission in submissions" 
            :key="submission.id" 
            class="submission-item"
          >
            <div class="submission-info">
              <h4>学生 #{{ submission.student_id }}</h4>
              <p class="submit-time">提交时间：{{ formatDate(submission.submitted_at) }}</p>
              <p v-if="submission.content" class="content">{{ submission.content }}</p>
              <div v-if="submission.file_url" class="file-display">
                <p class="file-label">附件：</p>
                <img 
                  v-if="isImageFile(submission.file_url)" 
                  :src="getFileUrl(submission.file_url)" 
                  alt="学生提交的图片" 
                  class="submission-image"
                  @click="openImagePreview(getFileUrl(submission.file_url))"
                />
                <a v-else :href="getFileUrl(submission.file_url)" target="_blank" class="file-link">
                  下载文件
                </a>
              </div>
              <p class="status">状态：{{ getStatusText(submission.status) }}</p>
              <div v-if="submission.score !== null" class="grade-info">
                <span class="score">分数：{{ submission.score }}</span>
                <span v-if="submission.feedback" class="feedback">评语：{{ submission.feedback }}</span>
              </div>
            </div>
            <div v-if="submission.status === 'submitted'" class="grade-form">
              <div class="form-group">
                <label>分数</label>
                <input 
                  v-model.number="gradeForm.score" 
                  type="number" 
                  min="0" 
                  max="100" 
                  placeholder="0-100"
                >
              </div>
              <div class="form-group">
                <label>评语</label>
                <textarea 
                  v-model="gradeForm.feedback" 
                  rows="3" 
                  placeholder="请输入评语"
                ></textarea>
              </div>
              <button 
                @click="handleGrade(submission)" 
                class="btn btn-primary"
                :disabled="grading"
              >
                {{ grading ? '批改中...' : '提交批改' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, provide, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { assignmentAPI } from '@/api/assignments'
import { chatsAPI } from '@/api/chats'

const authStore = useAuthStore()
const route = useRoute()

const showSubmissionsModal = ref(false)
const selectedAssignment = ref(null)
const submissions = ref([])
const submissionsLoading = ref(false)
const grading = ref(false)
const unreadCount = ref(0)
let pollInterval = null
let isPollingActive = ref(true)
let isVisible = ref(true)
let lastFetchTime = 0
const MIN_FETCH_INTERVAL = 5000

const gradeForm = ref({
  score: null,
  feedback: ''
})

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

const openSubmissionsModal = async (assignment) => {
  selectedAssignment.value = assignment
  submissionsLoading.value = true
  showSubmissionsModal.value = true
  
  try {
    const response = await assignmentAPI.getSubmissions(assignment.id)
    submissions.value = response.data.submissions
  } catch (error) {
    console.error('加载提交失败:', error)
  } finally {
    submissionsLoading.value = false
  }
}

const closeSubmissionsModal = () => {
  showSubmissionsModal.value = false
  selectedAssignment.value = null
  submissions.value = []
}

const handleGrade = async (submission) => {
  if (!gradeForm.value.score && gradeForm.value.score !== 0) {
    alert('请输入分数')
    return
  }
  
  grading.value = true
  try {
    await assignmentAPI.gradeSubmission(submission.id, gradeForm.value)
    gradeForm.value = {
      score: null,
      feedback: ''
    }
    await openSubmissionsModal(selectedAssignment.value)
  } catch (error) {
    alert('批改失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    grading.value = false
  }
}

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString('zh-CN')
}

const getStatusText = (status) => {
  const statusMap = {
    'submitted': '已提交',
    'graded': '已批改'
  }
  return statusMap[status] || status
}

const isImageFile = (fileUrl) => {
  if (!fileUrl) return false
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
  return imageExtensions.some(ext => fileUrl.toLowerCase().endsWith(ext))
}

const getFileUrl = (fileUrl) => {
  return `http://localhost:5000${fileUrl}`
}

const openImagePreview = (imageUrl) => {
  window.open(imageUrl, '_blank')
}

provide('submissionsModal', {
  openSubmissionsModal,
  closeSubmissionsModal
})
</script>

<style scoped>
.teacher-dashboard {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 70px;
}

.dashboard-header {
  background: white;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dashboard-header h1 {
  margin: 0;
  color: #333;
  font-size: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-info span {
  color: #666;
  font-size: 14px;
}

.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-around;
  padding: 10px 0;
  z-index: 100;
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

.nav-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.nav-label {
  font-size: 12px;
}

.nav-icon-wrapper {
  position: relative;
  display: inline-block;
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

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal {
  background: white;
  border-radius: 10px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.submissions-modal {
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #333;
}

.submissions-list {
  padding: 20px;
  overflow-y: auto;
  max-height: calc(90vh - 80px);
}

.submission-item {
  background: #f9f9f9;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 15px;
}

.submission-info h4 {
  margin: 0 0 10px 0;
  color: #333;
}

.submit-time,
.status {
  color: #999;
  font-size: 14px;
  margin-bottom: 10px;
}

.content {
  color: #666;
  margin-bottom: 10px;
  background: white;
  padding: 10px;
  border-radius: 4px;
}

.file-display {
  margin-bottom: 10px;
  background: white;
  padding: 10px;
  border-radius: 4px;
}

.file-label {
  color: #666;
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 10px 0;
}

.submission-image {
  max-width: 100%;
  max-height: 400px;
  border-radius: 4px;
  cursor: pointer;
  transition: transform 0.3s;
}

.submission-image:hover {
  transform: scale(1.02);
}

.file-link {
  color: #667eea;
  text-decoration: none;
  padding: 8px 16px;
  background: rgba(102, 126, 234, 0.1);
  border-radius: 4px;
  display: inline-block;
  transition: all 0.3s;
}

.file-link:hover {
  background: rgba(102, 126, 234, 0.2);
}

.grade-info {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #eee;
}

.score {
  color: #4CAF50;
  font-weight: bold;
  margin-right: 15px;
}

.feedback {
  color: #666;
}

.grade-form {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ddd;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  color: #555;
  font-weight: 500;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  box-sizing: border-box;
}

.form-group textarea {
  resize: vertical;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #5568d3;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #999;
}
</style>
