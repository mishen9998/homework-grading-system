<template>
  <div class="assignment-statistics">
    <div class="page-header">
      <button @click="goBack" class="btn-back">← 返回</button>
      <h2>{{ assignment.title }} - 统计分析</h2>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    
    <div v-else class="statistics-content">
      <div class="summary-cards">
        <div class="summary-card">
          <div class="card-icon">👥</div>
          <div class="card-info">
            <div class="card-value">{{ summary.total_students || 0 }}</div>
            <div class="card-label">总人数</div>
          </div>
        </div>
        <div class="summary-card">
          <div class="card-icon">📝</div>
          <div class="card-info">
            <div class="card-value">{{ summary.submitted_count || 0 }}</div>
            <div class="card-label">已提交</div>
          </div>
        </div>
        <div class="summary-card">
          <div class="card-icon">⏳</div>
          <div class="card-info">
            <div class="card-value">{{ summary.pending_count || 0 }}</div>
            <div class="card-label">待批改</div>
          </div>
        </div>
        <div class="summary-card">
          <div class="card-icon">✅</div>
          <div class="card-info">
            <div class="card-value">{{ summary.graded_count || 0 }}</div>
            <div class="card-label">已批改</div>
          </div>
        </div>
      </div>

      <div class="submission-section">
        <h3>提交情况</h3>
        <div class="student-list">
          <div class="student-column">
            <h4>已提交 ({{ submittedStudents.length }}人)</h4>
            <div class="student-scroll">
              <div v-for="student in submittedStudents" :key="student.id" class="student-item">
                <span class="student-name">{{ student.name }}</span>
                <span class="student-id">{{ student.student_id }}</span>
              </div>
              <div v-if="submittedStudents.length === 0" class="empty-tip">暂无学生提交</div>
            </div>
          </div>
          <div class="student-column">
            <h4>未提交 ({{ unsubmittedStudents.length }}人)</h4>
            <div class="student-scroll">
              <div v-for="student in unsubmittedStudents" :key="student.id" class="student-item">
                <span class="student-name">{{ student.name }}</span>
                <span class="student-id">{{ student.student_id }}</span>
              </div>
              <div v-if="unsubmittedStudents.length === 0" class="empty-tip">全部已提交</div>
            </div>
          </div>
        </div>
      </div>

      <div class="score-ranking-section">
        <h3>成绩排名</h3>
        <div class="ranking-table">
          <div class="ranking-header">
            <span class="rank-col">排名</span>
            <span class="name-col">姓名</span>
            <span class="id-col">学号</span>
            <span class="score-col">分数</span>
          </div>
          <div class="ranking-body">
            <div v-for="(student, index) in scoreRanking" :key="student.id" class="ranking-item" :class="student.status">
              <span class="rank-col" :class="'rank-' + (index + 1)">{{ index + 1 }}</span>
              <span class="name-col">{{ student.name }}</span>
              <span class="id-col">{{ student.student_id }}</span>
              <span class="score-col" :class="student.status">
                {{ student.score_display }}
              </span>
            </div>
            <div v-if="scoreRanking.length === 0" class="empty-tip">暂无数据</div>
          </div>
        </div>
      </div>

      <div class="question-stats-section" v-if="questionStats.length > 0">
        <h3>题目统计</h3>
        <div class="question-stats-table">
          <div class="question-stats-header">
            <span class="q-num-col">题号</span>
            <span class="q-type-col">类型</span>
            <span class="q-score-col">分值</span>
            <span class="q-correct-col">正确人数</span>
            <span class="q-wrong-col">错误人数</span>
            <span class="q-rate-col">正确率</span>
          </div>
          <div class="question-stats-body">
            <div v-for="(q, index) in questionStats" :key="index" class="question-stats-item">
              <span class="q-num-col">第{{ q.question_number }}题</span>
              <span class="q-type-col">{{ getQuestionTypeLabel(q.question_type) }}</span>
              <span class="q-score-col">{{ q.score }}分</span>
              <span class="q-correct-col">{{ q.correct_count }}人</span>
              <span class="q-wrong-col">{{ q.total_graded - q.correct_count }}人</span>
              <span class="q-rate-col" :class="getRateClass(q.correct_rate)">{{ q.correct_rate }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { assignmentAPI } from '@/api/assignments'

const router = useRouter()
const route = useRoute()

const loading = ref(true)
const assignment = ref({})
const summary = ref({})
const submittedStudents = ref([])
const unsubmittedStudents = ref([])
const scoreRanking = ref([])
const questionStats = ref([])

const goBack = () => {
  router.back()
}

const getQuestionTypeLabel = (type) => {
  const labels = {
    'single_choice': '单选题',
    'true_false': '判断题',
    'fill_blank': '填空题',
    'text': '文本题',
    'comprehensive': '综合题'
  }
  return labels[type] || type
}

const getRateClass = (rate) => {
  if (rate >= 80) return 'rate-high'
  if (rate >= 60) return 'rate-medium'
  return 'rate-low'
}

const loadStatistics = async () => {
  loading.value = true
  try {
    const assignmentId = route.params.assignmentId
    const res = await assignmentAPI.getAssignmentStatistics(assignmentId)
    
    assignment.value = res.data.assignment || {}
    summary.value = res.data.summary || {}
    submittedStudents.value = res.data.submitted_students || []
    unsubmittedStudents.value = res.data.unsubmitted_students || []
    scoreRanking.value = res.data.score_ranking || []
    questionStats.value = res.data.question_stats || []
  } catch (error) {
    console.error('加载统计数据失败:', error)
    alert('加载失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStatistics()
})
</script>

<style scoped>
.assignment-statistics {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 30px;
}

.page-header h2 {
  margin: 0;
  color: #333;
  font-size: 24px;
}

.btn-back {
  padding: 8px 16px;
  background: #f0f0f0;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-back:hover {
  background: #e0e0e0;
}

.loading {
  text-align: center;
  padding: 60px;
  color: #999;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 30px;
}

.summary-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  display: flex;
  align-items: center;
  gap: 15px;
}

.card-icon {
  font-size: 36px;
}

.card-info {
  flex: 1;
}

.card-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.card-label {
  font-size: 14px;
  color: #999;
  margin-top: 5px;
}

.submission-section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.submission-section h3 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.student-list {
  display: flex;
  gap: 20px;
}

.student-column {
  flex: 1;
}

.student-column h4 {
  margin: 0 0 10px 0;
  color: #666;
  font-size: 14px;
  padding-bottom: 10px;
  border-bottom: 2px solid #f0f0f0;
}

.student-scroll {
  max-height: 200px;
  overflow-y: auto;
}

.student-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
  margin-bottom: 6px;
}

.student-name {
  font-weight: 500;
  color: #333;
}

.student-id {
  color: #999;
  font-size: 12px;
}

.empty-tip {
  text-align: center;
  color: #999;
  padding: 20px;
  font-size: 14px;
}

.score-ranking-section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.score-ranking-section h3 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.ranking-table {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.ranking-header {
  display: grid;
  grid-template-columns: 60px 1fr 120px 80px;
  background: #f8f9fa;
  padding: 12px 15px;
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.ranking-body {
  max-height: 300px;
  overflow-y: auto;
}

.ranking-item {
  display: grid;
  grid-template-columns: 60px 1fr 120px 80px;
  padding: 10px 15px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.ranking-item:last-child {
  border-bottom: none;
}

.rank-col {
  text-align: center;
}

.rank-1 {
  color: #ffd700;
  font-weight: bold;
}

.rank-2 {
  color: #c0c0c0;
  font-weight: bold;
}

.rank-3 {
  color: #cd7f32;
  font-weight: bold;
}

.name-col {
  color: #333;
}

.id-col {
  color: #666;
}

.score-col {
  text-align: center;
  font-weight: 600;
  color: #667eea;
}

.score-col.graded {
  color: #667eea;
}

.score-col.submitted {
  color: #ffc107;
}

.score-col.unsubmitted {
  color: #dc3545;
}

.ranking-item.submitted {
  background: #fffbe6;
}

.ranking-item.unsubmitted {
  background: #fff2f0;
}

.ranking-item.graded {
  background: white;
}

.question-stats-section {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.question-stats-section h3 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.question-stats-table {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.question-stats-header {
  display: grid;
  grid-template-columns: 80px 80px 60px 100px 100px 80px;
  background: #f8f9fa;
  padding: 12px 15px;
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.question-stats-body {
  max-height: 300px;
  overflow-y: auto;
}

.question-stats-item {
  display: grid;
  grid-template-columns: 80px 80px 60px 100px 100px 80px;
  padding: 10px 15px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.question-stats-item:last-child {
  border-bottom: none;
}

.q-num-col {
  color: #333;
  font-weight: 500;
}

.q-type-col {
  color: #666;
}

.q-score-col {
  text-align: center;
  color: #666;
}

.q-correct-col {
  text-align: center;
  color: #28a745;
  font-weight: 500;
}

.q-wrong-col {
  text-align: center;
  color: #dc3545;
  font-weight: 500;
}

.q-rate-col {
  text-align: center;
  font-weight: 600;
}

.q-rate-col.rate-high {
  color: #28a745;
}

.q-rate-col.rate-medium {
  color: #ffc107;
}

.q-rate-col.rate-low {
  color: #dc3545;
}

@media (max-width: 768px) {
  .summary-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .student-list {
    flex-direction: column;
  }
}
</style>
