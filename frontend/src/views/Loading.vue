<template>
  <div class="loading-container">
    <div class="loading-card">
      <div class="loading-icon">
        <div class="spinner" v-if="checking"></div>
        <div class="checkmark" v-else-if="isReady">✓</div>
        <div class="error-icon" v-else>!</div>
      </div>
      
      <h2>{{ title }}</h2>
      
      <div class="progress-bar" v-if="checking">
        <div class="progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
      
      <p class="status-message">{{ message }}</p>
      
      <div class="status-details" v-if="checking || isReady">
        <div class="status-item" :class="{ ready: backendReady }">
          <span class="status-icon">{{ backendReady ? '✓' : '○' }}</span>
          <span>后端服务</span>
          <span class="status-text">{{ backendReady ? '已就绪' : '检测中...' }}</span>
        </div>
      </div>
      
      <div v-if="isReady" class="ready-actions">
        <button @click="goToLogin" class="btn btn-primary">进入系统</button>
      </div>
      
      <div v-if="showRetry" class="retry-actions">
        <p class="error-hint">请先启动后端服务：</p>
        <code class="code-block">cd backend && python run.py</code>
        <button @click="checkBackend" class="btn btn-secondary">重新检测</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const checking = ref(true)
const progress = ref(0)
const message = ref('正在检测后端服务...')
const backendReady = ref(false)
const showRetry = ref(false)

const isReady = computed(() => backendReady.value)
const title = computed(() => {
  if (isReady.value) return '系统已就绪'
  if (showRetry.value) return '后端未启动'
  return '系统启动中'
})

let retryCount = 0
const MAX_RETRIES = 3

const checkBackend = async () => {
  checking.value = true
  showRetry.value = false
  progress.value = 0
  message.value = '正在检测后端服务...'
  
  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      progress.value = 30 + i * 20
      
      const response = await axios.get('http://127.0.0.1:5000/api/status/health', {
        timeout: 5000
      })
      
      if (response.data && response.data.status === 'healthy') {
        progress.value = 100
        backendReady.value = true
        message.value = '后端服务已就绪'
        checking.value = false
        
        setTimeout(() => {
          router.push('/login')
        }, 1000)
        return
      }
    } catch (err) {
      message.value = `检测中... (${i + 1}/${MAX_RETRIES})`
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  }
  
  checking.value = false
  showRetry.value = true
  message.value = '无法连接到后端服务'
  backendReady.value = false
}

const goToLogin = () => {
  router.push('/login')
}

onMounted(() => {
  checkBackend()
})
</script>

<style scoped>
.loading-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.loading-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  max-width: 400px;
  width: 100%;
  text-align: center;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.loading-icon {
  margin-bottom: 20px;
}

.spinner {
  width: 60px;
  height: 60px;
  border: 4px solid #e0e0e0;
  border-top-color: #667eea;
  border-radius: 50%;
  margin: 0 auto;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.checkmark {
  width: 60px;
  height: 60px;
  background: #4CAF50;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  color: white;
  font-size: 30px;
  font-weight: bold;
}

.error-icon {
  width: 60px;
  height: 60px;
  background: #e74c3c;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  color: white;
  font-size: 30px;
  font-weight: bold;
}

h2 {
  margin: 0 0 20px 0;
  color: #333;
  font-size: 24px;
}

.progress-bar {
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 15px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.status-message {
  color: #666;
  margin-bottom: 20px;
  font-size: 14px;
}

.status-details {
  text-align: left;
  background: #f5f5f5;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 20px;
}

.status-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  color: #999;
}

.status-item.ready {
  color: #4CAF50;
}

.status-icon {
  width: 24px;
  font-size: 16px;
}

.status-item span:nth-child(2) {
  flex: 1;
}

.status-text {
  font-size: 12px;
  opacity: 0.8;
}

.ready-actions,
.retry-actions {
  margin-top: 20px;
}

.btn {
  padding: 12px 30px;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
}

.btn-secondary {
  background: #e0e0e0;
  color: #666;
  margin-top: 15px;
}

.btn-secondary:hover {
  background: #d0d0d0;
}

.error-hint {
  color: #e74c3c;
  margin-bottom: 10px;
}

.code-block {
  display: block;
  background: #f5f5f5;
  padding: 10px 15px;
  border-radius: 6px;
  font-family: monospace;
  font-size: 13px;
  color: #333;
  margin-bottom: 15px;
}
</style>
