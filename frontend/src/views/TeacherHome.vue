<template>
  <div class="teacher-home">
    <div class="welcome-section">
      <h2>{{ greeting }}</h2>
      <p class="date">{{ currentDate }}</p>
    </div>

    <div v-if="pendingStats.total_pending > 0" class="reminder-section" @click="goToPendingAssignments">
      <div class="reminder-icon">🔔</div>
      <div class="reminder-content">
        <div class="reminder-title">作业提醒</div>
        <div class="reminder-text">您有 <strong>{{ pendingStats.total_pending }}</strong> 份作业待批改</div>
        <div v-if="pendingStats.pending_assignments.length > 0" class="reminder-detail">
          {{ pendingStats.pending_assignments[0].course_name }} - {{ pendingStats.pending_assignments[0].assignment_title }}
          <span v-if="pendingStats.pending_assignments.length > 1">等 {{ pendingStats.pending_assignments.length }} 个作业</span>
        </div>
      </div>
      <div class="reminder-arrow">→</div>
    </div>

    <div class="stats-section">
      <div class="stat-card">
        <div class="stat-icon">📚</div>
        <div class="stat-info">
          <div class="stat-number">{{ stats.totalCourses }}</div>
          <div class="stat-label">课程总数</div>
        </div>
      </div>
      <div class="stat-card pending-stat" @click="goToPendingAssignments">
        <div class="stat-icon">📝</div>
        <div class="stat-info">
          <div class="stat-number">{{ pendingStats.total_pending }}</div>
          <div class="stat-label">待批改</div>
        </div>
      </div>
    </div>

    <div class="courses-section">
      <div class="section-header">
        <h3>我的课程</h3>
        <button @click="showCreateCourseModal = true" class="btn btn-primary">
          + 创建课程
        </button>
      </div>

      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="loadError" class="error-state">
        <p>{{ loadError }}</p>
        <button @click="loadCourses()" class="btn btn-primary">重试</button>
      </div>
      <div v-else-if="courses.length === 0" class="empty">
        <p>暂无课程，点击上方按钮创建课程</p>
      </div>
      <div v-else class="courses-grid">
        <div 
          v-for="course in courses" 
          :key="course.id" 
          class="course-card"
          @click="viewCourse(course)"
        >
          <div class="course-icon">{{ getCourseIcon(course.name) }}</div>
          <div class="course-info">
            <h4>{{ course.name }}</h4>
            <p class="course-code">课程码：{{ course.code }}</p>
            <p v-if="course.class_name" class="course-class">
              📌 {{ course.class_name }}<span v-if="course.expected_students">（预计{{ course.expected_students }}人）</span>
            </p>
            <p v-if="course.code_expiry" class="course-expiry">
              有效期至：{{ formatDate(course.code_expiry) }}
            </p>
            <div class="course-stats">
              <span class="stat">📝 {{ course.assignment_count || 0 }} 作业</span>
              <span class="stat">👥 {{ course.student_count || 0 }} 学生</span>
            </div>
          </div>
          <div class="course-arrow">→</div>
        </div>
      </div>
    </div>

    <div v-if="showCreateCourseModal" class="modal-overlay" @click="showCreateCourseModal = false">
      <div class="modal" @click.stop>
        <h3>创建新课程</h3>
        <form @submit.prevent="handleCreateCourse">
          <div class="form-group">
            <label>课程名称</label>
            <input 
              v-model="createCourseForm.name" 
              type="text" 
              placeholder="请输入课程名称" 
              required
            />
          </div>
          <div class="form-group">
            <label>课程描述</label>
            <textarea 
              v-model="createCourseForm.description" 
              rows="3" 
              placeholder="请输入课程描述"
            ></textarea>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>班级名称</label>
              <input 
                v-model="createCourseForm.class_name" 
                type="text" 
                placeholder="如：计算机2301班"
              />
            </div>
            <div class="form-group">
              <label>预计人数</label>
              <input 
                v-model.number="createCourseForm.expected_students" 
                type="number" 
                min="1"
                placeholder="如：50"
              />
            </div>
          </div>
          <div class="form-group">
            <label>课程码有效期（可选）</label>
            <input 
              v-model="createCourseForm.code_expiry" 
              type="datetime-local" 
            />
            <p class="hint">留空表示课程码永久有效</p>
          </div>
          <div class="modal-actions">
            <button type="button" @click="showCreateCourseModal = false" class="btn btn-secondary">取消</button>
            <button type="submit" class="btn btn-primary" :disabled="creating">
              {{ creating ? '创建中...' : '创建课程' }}
            </button>
          </div>
        </form>
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
const showCreateCourseModal = ref(false)
const creating = ref(false)
const loadError = ref(null)

const createCourseForm = ref({
  name: '',
  description: '',
  class_name: '',
  expected_students: null,
  code_expiry: ''
})

const stats = ref({
  totalCourses: 0
})

const pendingStats = ref({
  total_pending: 0,
  pending_assignments: []
})

const currentDate = computed(() => {
  const now = new Date()
  const options = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }
  return now.toLocaleDateString('zh-CN', options)
})

const greeting = computed(() => {
  const hour = new Date().getHours()
  const userName = authStore.user?.name || '老师'
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
  
  return `${userName}老师，${timeGreeting}`
})

const loadCourses = async (retryCount = 0) => {
  loading.value = true
  loadError.value = null
  try {
    const response = await assignmentAPI.getMyCourses()
    courses.value = response.data.courses
    stats.value.totalCourses = courses.value.length
  } catch (error) {
    console.error('加载课程失败:', error)
    if (retryCount < 3 && (error.code === 'ERR_CANCELED' || error.message?.includes('timeout') || error.message?.includes('网络'))) {
      console.log(`正在重试加载课程 (${retryCount + 1}/3)...`)
      await new Promise(resolve => setTimeout(resolve, 500))
      return loadCourses(retryCount + 1)
    }
    loadError.value = error.message || '加载失败'
  } finally {
    loading.value = false
  }
}

const loadPendingStats = async () => {
  try {
    const response = await assignmentAPI.getTeacherPendingSubmissions()
    pendingStats.value = response.data
  } catch (error) {
    console.error('加载待批改统计失败:', error)
  }
}

const goToPendingAssignments = () => {
  if (pendingStats.value.pending_assignments.length > 0) {
    const firstPending = pendingStats.value.pending_assignments[0]
    router.push(`/teacher/course/${firstPending.course_id}`)
  }
}

const handleCreateCourse = async () => {
  creating.value = true
  try {
    await assignmentAPI.createCourse(createCourseForm.value)
    createCourseForm.value = {
      name: '',
      description: '',
      class_name: '',
      expected_students: null,
      code_expiry: ''
    }
    showCreateCourseModal.value = false
    await loadCourses()
    alert('创建成功！')
  } catch (error) {
    alert('创建失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    creating.value = false
  }
}

const viewCourse = (course) => {
  router.push(`/teacher/course/${course.id}`)
}

const formatDate = (dateString) => {
  if (!dateString) return '永久有效'
  return new Date(dateString).toLocaleString('zh-CN')
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
  loadPendingStats()
})
</script>

<style scoped>
.teacher-home {
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

.reminder-section {
  background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%);
  color: white;
  padding: 20px 25px;
  border-radius: 12px;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 15px;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
}

.reminder-section:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(255, 107, 107, 0.4);
}

.reminder-icon {
  font-size: 36px;
  animation: bell-ring 1s ease-in-out infinite;
}

@keyframes bell-ring {
  0%, 100% { transform: rotate(0); }
  25% { transform: rotate(10deg); }
  75% { transform: rotate(-10deg); }
}

.reminder-content {
  flex: 1;
}

.reminder-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 5px;
}

.reminder-text {
  font-size: 14px;
  opacity: 0.95;
}

.reminder-text strong {
  font-size: 18px;
  font-weight: 700;
}

.reminder-detail {
  font-size: 12px;
  opacity: 0.85;
  margin-top: 5px;
}

.reminder-arrow {
  font-size: 24px;
  opacity: 0.8;
}

.stats-section {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  padding: 20px 40px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  display: flex;
  align-items: center;
  gap: 15px;
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

.stat-label {
  color: #999;
  font-size: 14px;
}

.stat-card.pending-stat {
  cursor: pointer;
  transition: all 0.3s;
}

.stat-card.pending-stat:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
}

.stat-card.pending-stat .stat-number {
  color: #ff6b6b;
}

.assignments-section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
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

.error-state {
  text-align: center;
  padding: 60px 20px;
  color: #ff6b6b;
}

.error-state p {
  margin-bottom: 15px;
}

.assignments-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.assignment-card {
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  padding: 20px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
}

.assignment-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.15);
}

.assignment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.assignment-header h4 {
  margin: 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
}

.assignment-status {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.assignment-description {
  margin: 0 0 15px 0;
  color: #666;
  font-size: 14px;
  line-height: 1.5;
}

.assignment-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
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

.course-code {
  margin: 0 0 10px 0;
  color: #667eea;
  font-size: 14px;
  text-align: center;
  font-weight: 500;
}

.course-class {
  margin: 0 0 10px 0;
  color: #28a745;
  font-size: 14px;
  text-align: center;
  font-weight: 500;
  background: rgba(40, 167, 69, 0.1);
  padding: 6px 12px;
  border-radius: 6px;
}

.course-expiry {
  margin: 0 0 10px 0;
  color: #999;
  font-size: 13px;
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

.form-group {
  margin-bottom: 15px;
}

.form-row {
  display: flex;
  gap: 15px;
}

.form-row .form-group {
  flex: 1;
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

.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .courses-grid {
    grid-template-columns: 1fr;
  }
}
</style>
