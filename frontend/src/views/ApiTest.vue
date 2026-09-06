<template>
  <div class="test-container">
    <h1>API测试页面</h1>
    <div class="test-section">
      <h2>测试登录API</h2>
      <button @click="testLogin" class="btn">测试登录</button>
      <p v-if="loginResult" :class="['result', loginResult.success ? 'success' : 'error']">
        {{ loginResult.message }}
      </p>
      <p v-if="loginResult.data" class="data">
        {{ JSON.stringify(loginResult.data, null, 2) }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { authAPI } from '@/api/auth'

const loginResult = ref(null)

const testLogin = async () => {
  try {
    console.log('开始测试登录API...')
    const response = await authAPI.login({
      username: 'student1',
      password: '123456'
    })
    console.log('登录API响应:', response)
    loginResult.value = {
      success: true,
      message: '登录成功',
      data: response.data
    }
  } catch (err) {
    console.error('登录API错误:', err)
    loginResult.value = {
      success: false,
      message: '登录失败: ' + (err.response?.data?.error || err.message || '未知错误'),
      data: err.response?.data || null
    }
  }
}
</script>

<style scoped>
.test-container {
  padding: 40px;
  max-width: 800px;
  margin: 0 auto;
}

.test-section {
  background: white;
  padding: 30px;
  border-radius: 10px;
  margin-bottom: 20px;
}

.test-section h2 {
  margin-top: 0;
  color: #333;
}

.btn {
  padding: 12px 24px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
}

.btn:hover {
  background: #5568d3;
}

.result {
  padding: 15px;
  border-radius: 6px;
  margin-top: 15px;
}

.result.success {
  background: #d4edda;
  color: #155724;
}

.result.error {
  background: #f8d7da;
  color: #721c24;
}

.data {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  margin-top: 10px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>