<template>
  <div class="admin-home">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">👥</div>
        <div class="stat-info">
          <div class="stat-value">{{ statistics.total_users }}</div>
          <div class="stat-label">总用户数</div>
        </div>
      </div>
      <div class="stat-card student">
        <div class="stat-icon">🎓</div>
        <div class="stat-info">
          <div class="stat-value">{{ statistics.student_count }}</div>
          <div class="stat-label">学生数</div>
        </div>
      </div>
      <div class="stat-card teacher">
        <div class="stat-icon">👨‍🏫</div>
        <div class="stat-info">
          <div class="stat-value">{{ statistics.teacher_count }}</div>
          <div class="stat-label">教师数</div>
        </div>
      </div>
      <div class="stat-card admin">
        <div class="stat-icon">🔐</div>
        <div class="stat-info">
          <div class="stat-value">{{ statistics.admin_count }}</div>
          <div class="stat-label">管理员数</div>
        </div>
      </div>
    </div>

    <div class="quick-actions">
      <h2>快捷操作</h2>
      <div class="actions-grid">
        <router-link to="/admin/users" class="action-card">
          <span class="action-icon">👥</span>
          <span class="action-label">用户管理</span>
        </router-link>
        <router-link to="/admin/import" class="action-card">
          <span class="action-icon">📥</span>
          <span class="action-label">批量导入</span>
        </router-link>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminAPI } from '@/api/admin'

const loading = ref(false)
const statistics = ref({
  total_users: 0,
  student_count: 0,
  teacher_count: 0,
  admin_count: 0
})

const loadStatistics = async () => {
  loading.value = true
  try {
    const response = await adminAPI.getStatistics()
    statistics.value = response.data
  } catch (error) {
    console.error('加载统计数据失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStatistics()
})
</script>

<style scoped>
.admin-home {
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 15px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  transition: transform 0.3s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-card.student {
  border-left: 4px solid #4CAF50;
}

.stat-card.teacher {
  border-left: 4px solid #2196F3;
}

.stat-card.admin {
  border-left: 4px solid #9C27B0;
}

.stat-icon {
  font-size: 40px;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 5px;
}

.quick-actions {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.quick-actions h2 {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #333;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
}

.action-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 10px;
  padding: 25px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  transition: transform 0.3s;
}

.action-card:hover {
  transform: translateY(-2px);
}

.action-icon {
  font-size: 32px;
}

.action-label {
  color: white;
  font-size: 14px;
  font-weight: 500;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #999;
}
</style>
