<template>
  <div class="login-container">
    <div class="login-card">
      <img src="@/assets/images/logo.png" alt="Logo" class="login-logo" />
      <h2>登录</h2>
      
      <div class="role-selector">
        <button 
          :class="['role-btn', { active: selectedRole === 'student' }]"
          @click="selectedRole = 'student'"
        >
          学生
        </button>
        <button 
          :class="['role-btn', { active: selectedRole === 'teacher' }]"
          @click="selectedRole = 'teacher'"
        >
          老师
        </button>
        <button 
          :class="['role-btn', { active: selectedRole === 'admin' }]"
          @click="selectedRole = 'admin'"
        >
          管理员
        </button>
      </div>

      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label>账号</label>
          <input 
            v-model="form.username" 
            type="text" 
            placeholder="请输入账号（学号/工号）" 
            required
          >
        </div>
        <div class="form-group">
          <label>密码</label>
          <input 
            v-model="form.password" 
            type="password" 
            placeholder="请输入密码" 
            required
          >
        </div>
        <button type="submit" class="btn btn-primary" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
      <p class="register-link">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </p>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { authAPI } from '@/api/auth'

const router = useRouter()
const authStore = useAuthStore()

const selectedRole = ref('')

const form = ref({
  username: '',
  password: ''
})

const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  if (!selectedRole.value) {
    error.value = '请先选择身份（学生、老师或管理员）'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    const response = await authAPI.login({
      ...form.value,
      role: selectedRole.value
    })
    
    if (!response.data) {
      error.value = '服务器返回数据格式错误'
      return
    }
    
    authStore.setToken(response.data.access_token)
    authStore.setUser(response.data.user)
    
    if (response.data.user.role === 'student') {
      router.push('/student')
    } else if (response.data.user.role === 'teacher') {
      router.push('/teacher')
    } else if (response.data.user.role === 'admin') {
      router.push('/admin')
    }
  } catch (err) {
    error.value = err.response?.data?.error || '登录失败，请检查账号和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  position: relative;
  background-image: url('@/assets/images/login-background.jpg');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  background-attachment: fixed;
}

.login-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 0;
}

.login-card {
  background: rgba(255, 255, 255, 0.95);
  padding: 40px;
  padding-top: 80px;
  border-radius: 10px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
  width: 100%;
  max-width: 400px;
  position: relative;
  z-index: 1;
  backdrop-filter: blur(10px);
}

.login-logo {
  position: absolute;
  top: 15px;
  left: 15px;
  height: 60px;
  width: auto;
  object-fit: contain;
}

.login-card h2 {
  text-align: center;
  margin-bottom: 20px;
  color: #333;
}

.role-selector {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.role-btn {
  flex: 1;
  padding: 12px;
  background: #f5f5f5;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s;
  color: #666;
}

.role-btn:hover {
  background: #e8e8e8;
  border-color: #d0d0d0;
}

.role-btn.active {
  background: #667eea;
  border-color: #667eea;
  color: white;
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
  transition: border-color 0.3s;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
}

.btn {
  width: 100%;
  padding: 12px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.3s;
}

.btn:hover:not(:disabled) {
  background: #5568d3;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.register-link {
  text-align: center;
  margin-top: 20px;
  color: #666;
}

.register-link a {
  color: #667eea;
  text-decoration: none;
}

.register-link a:hover {
  text-decoration: underline;
}

.error {
  color: #e74c3c;
  text-align: center;
  margin-top: 15px;
  font-size: 14px;
}
</style>
