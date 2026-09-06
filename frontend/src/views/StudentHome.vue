<template>
  <div class="student-home">
    <div class="welcome-section">
      <h2>{{ greeting }}</h2>
      <p class="date">{{ currentDate }}</p>
    </div>

    <div class="stats-section">
      <div class="stat-card">
        <div class="stat-icon">📚</div>
        <div class="stat-info">
          <div class="stat-number">{{ courses.length }}</div>
          <div class="stat-label">课程总数</div>
        </div>
      </div>
      <div class="stat-card clickable" @click="showPendingModal = true">
        <div class="stat-icon">📝</div>
        <div class="stat-info">
          <div class="stat-number pending-count" :class="{ 'has-pending': pendingAssignments.length > 0 }">
            {{ pendingAssignments.length }}
          </div>
          <div class="stat-label">未完成作业</div>
        </div>
        <div v-if="pendingAssignments.length > 0" class="stat-badge">!</div>
      </div>
    </div>

    <div class="courses-section">
      <div class="section-header">
        <h3>课程列表</h3>
        <button @click="showJoinModal = true" class="btn btn-primary">
          + 加入课程
        </button>
      </div>
      
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="courses.length === 0" class="empty">
        <p>暂无课程，点击上方按钮加入课程</p>
      </div>
      <div v-else class="courses-grid">
        <div 
          v-for="course in courses" 
          :key="course.id" 
          class="course-card"
          @click="goToCourse(course.id)"
        >
          <div class="course-icon">{{ course.icon }}</div>
          <div class="course-info">
            <h4>{{ course.name }}</h4>
            <p class="course-teacher">老师：{{ course.teacher_name }}</p>
            <div class="course-stats">
              <span class="stat">📝 {{ course.assignment_count }} 作业</span>
              <span class="stat">📁 {{ course.resource_count }} 资源</span>
            </div>
          </div>
          <div class="course-arrow">→</div>
        </div>
      </div>
    </div>

    <div v-if="showJoinModal" class="modal-overlay" @click="showJoinModal = false">
      <div class="modal" @click.stop>
        <h3>加入课程</h3>
        <form @submit.prevent="handleJoinCourse">
          <div class="form-group">
            <label>课程码</label>
            <input 
              v-model="joinForm.code" 
              type="text" 
              placeholder="请输入课程码" 
              required
            />
          </div>
          <div class="modal-actions">
            <button type="button" @click="showJoinModal = false" class="btn btn-secondary">取消</button>
            <button type="submit" class="btn btn-primary" :disabled="joining">
              {{ joining ? '加入中...' : '加入' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showPendingModal" class="modal-overlay" @click="showPendingModal = false">
      <div class="modal pending-modal" @click.stop>
        <div class="modal-header">
          <h3>📋 未完成作业提醒</h3>
          <span class="badge">{{ pendingAssignments.length }}</span>
        </div>
        <div class="pending-list-modal" v-if="pendingAssignments.length > 0">
          <div 
            v-for="assignment in pendingAssignments" 
            :key="assignment.id" 
            class="pending-item"
            :class="{ 'overdue': assignment.is_overdue }"
            @click="goToAssignment(assignment.course_id, assignment.id)"
          >
            <div class="pending-info">
              <div class="pending-title">{{ assignment.title }}</div>
              <div class="pending-course">📚 {{ assignment.course_name }}</div>
            </div>
            <div class="pending-deadline">
              <div class="deadline-date">{{ formatDate(assignment.due_date) }}</div>
              <span v-if="assignment.is_overdue" class="deadline overdue-text">
                ⚠️ 已逾期
              </span>
              <span v-else-if="assignment.days_remaining === 0" class="deadline urgent">
                🔴 今天截止
              </span>
              <span v-else-if="assignment.days_remaining <= 3" class="deadline warning">
                🟠 剩余 {{ assignment.days_remaining }} 天
              </span>
              <span v-else class="deadline normal">
                🟢 剩余 {{ assignment.days_remaining }} 天
              </span>
            </div>
          </div>
        </div>
        <div v-else class="no-pending">
          <div class="no-pending-icon">🎉</div>
          <p>太棒了！没有未完成的作业</p>
        </div>
        <div class="modal-actions">
          <button type="button" @click="showPendingModal = false" class="btn btn-secondary">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { assignmentAPI } from '@/api/assignments'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(true)
const courses = ref([])
const pendingAssignments = ref([])
const showJoinModal = ref(false)
const showPendingModal = ref(false)
const joining = ref(false)

const joinForm = ref({
  code: ''
})

const currentDate = computed(() => {
  const now = new Date()
  const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }
  return now.toLocaleDateString('zh-CN', options)
})

const greeting = computed(() => {
  const hour = new Date().getHours()
  const userName = authStore.user?.name || '同学'
  let timeGreeting = ''
  
  if (hour >= 5 && hour < 12) {
    timeGreeting = '早上好'
  } else if (hour >= 12 && hour < 14) {
    timeGreeting = '中午好'
  } else if (hour >= 14 && hour < 18) {
    timeGreeting = '下午好'
  } else {
    timeGreeting = '晚上好'
  }
  
  return `${userName}同学，${timeGreeting}`
})

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', { 
    month: 'short', 
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const goToCourse = (courseId) => {
  router.push(`/student/course/${courseId}`)
}

const goToAssignment = (courseId, assignmentId) => {
  showPendingModal.value = false
  router.push(`/student/course/${courseId}`)
}

const handleJoinCourse = async () => {
  joining.value = true
  try {
    await assignmentAPI.joinCourse(joinForm.value.code)
    showJoinModal.value = false
    joinForm.value.code = ''
    await loadCourses()
    alert('加入课程成功！')
  } catch (error) {
    alert('加入课程失败：' + (error.response?.data?.error || '课程码无效'))
  } finally {
    joining.value = false
  }
}

const loadCourses = async () => {
  try {
    const response = await assignmentAPI.getMyCourses()
    courses.value = response.data.courses.map(course => ({
      ...course,
      icon: getCourseIcon(course.name)
    }))
  } catch (error) {
    console.error('加载课程失败:', error)
  } finally {
    loading.value = false
  }
}

const loadPendingAssignments = async () => {
  try {
    const response = await assignmentAPI.getPendingAssignments()
    pendingAssignments.value = response.data.pending_assignments
  } catch (error) {
    console.error('加载未完成作业失败:', error)
  }
}

const getCourseIcon = (courseName) => {
  const icons = {
    '高等数学': '📐',
    '线性代数': '📊',
    '编译原理': '💻',
    '单片机原理': '🔧',
    '人工智能导论': '🤖',
    '数据库': '🗄️',
    '数据结构': '🌳',
    '计算机网络': '🌐',
    '操作系统': '⚙️',
    '软件工程': '📋'
  }
  return icons[courseName] || '📚'
}

onMounted(() => {
  loadCourses()
  loadPendingAssignments()
})
</script>

<style scoped>
.student-home {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-section {
  background-image: url('@/assets/images/welcome-background.jpg');
  background-size: cover;
  background-position: center;
  color: white;
  padding: 30px;
  border-radius: 12px;
  margin-bottom: 30px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  position: relative;
}

.welcome-section::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.5) 0%, rgba(118, 75, 162, 0.5) 100%);
  border-radius: 12px;
  z-index: 0;
}

.welcome-section h2,
.welcome-section .date {
  position: relative;
  z-index: 1;
}

.welcome-section h2 {
  margin: 0 0 10px 0;
  font-size: 24px;
}

.date {
  margin: 0;
  opacity: 0.9;
  font-size: 14px;
}

.stats-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  display: flex;
  align-items: center;
  gap: 15px;
  position: relative;
}

.stat-card.clickable {
  cursor: pointer;
  transition: all 0.3s;
}

.stat-card.clickable:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.stat-icon {
  font-size: 32px;
}

.stat-info {
  flex: 1;
}

.stat-number {
  font-size: 28px;
  font-weight: bold;
  color: #333;
  margin-bottom: 5px;
}

.stat-number.pending-count.has-pending {
  color: #ff6b6b;
}

.stat-label {
  color: #999;
  font-size: 14px;
}

.stat-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background: #ff6b6b;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

.courses-section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid #f0f0f0;
}

.section-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

.loading,
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.courses-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.course-card {
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  padding: 20px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.course-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.15);
}

.course-icon {
  font-size: 48px;
  text-align: center;
}

.course-info {
  flex: 1;
}

.course-info h4 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
}

.course-teacher {
  margin: 0 0 10px 0;
  color: #666;
  font-size: 14px;
  text-align: center;
}

.course-stats {
  display: flex;
  justify-content: center;
  gap: 15px;
}

.course-stats .stat {
  color: #999;
  font-size: 13px;
}

.course-arrow {
  position: absolute;
  top: 20px;
  right: 20px;
  font-size: 20px;
  color: #667eea;
  opacity: 0;
  transition: opacity 0.3s;
}

.course-card:hover .course-arrow {
  opacity: 1;
}

.btn {
  padding: 8px 16px;
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

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #5a6268;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
  padding: 30px;
  border-radius: 10px;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal h3 {
  margin: 0 0 20px 0;
  color: #333;
}

.pending-modal {
  max-width: 600px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 2px solid #f0f0f0;
}

.modal-header h3 {
  margin: 0;
}

.badge {
  background: #ff6b6b;
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: bold;
}

.pending-list-modal {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
  max-height: 400px;
  overflow-y: auto;
}

.pending-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  border-left: 4px solid #667eea;
}

.pending-item:hover {
  background: #e9ecef;
  transform: translateX(5px);
}

.pending-item.overdue {
  border-left-color: #dc3545;
  background: #fff5f5;
}

.pending-info {
  flex: 1;
}

.pending-title {
  font-weight: 600;
  color: #333;
  margin-bottom: 5px;
}

.pending-course {
  font-size: 13px;
  color: #666;
}

.pending-deadline {
  text-align: right;
}

.deadline-date {
  font-size: 13px;
  color: #666;
  margin-bottom: 5px;
}

.deadline {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
}

.deadline.overdue-text {
  color: #dc3545;
  font-weight: bold;
}

.deadline.urgent {
  background: #ffe0e0;
  color: #dc3545;
}

.deadline.warning {
  background: #fff3cd;
  color: #856404;
}

.deadline.normal {
  background: #d4edda;
  color: #155724;
}

.no-pending {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.no-pending-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  color: #555;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
}

.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 1024px) {
  .courses-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .courses-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .stat-card {
    padding: 15px;
  }
  
  .stat-icon {
    font-size: 24px;
  }
  
  .stat-number {
    font-size: 20px;
  }

  .pending-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .pending-deadline {
    text-align: left;
  }
}

@media (max-width: 480px) {
  .courses-grid {
    grid-template-columns: 1fr;
  }
  
  .stats-section {
    grid-template-columns: 1fr;
  }
}
</style>
