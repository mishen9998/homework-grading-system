<template>
  <div class="register-container">
    <div class="register-card">
      <img src="@/assets/images/logo.png" alt="Logo" class="register-logo" />
      <h2>注册</h2>
      
      <div class="role-selector">
        <button 
          type="button"
          :class="['role-btn', { active: form.role === 'student' }]"
          @click="switchRole('student')"
        >
          学生
        </button>
        <button 
          type="button"
          :class="['role-btn', { active: form.role === 'teacher' }]"
          @click="switchRole('teacher')"
        >
          老师
        </button>
      </div>

      <form @submit.prevent="handleRegister">
        <div class="form-group">
          <label>姓名 <span class="required">*</span></label>
          <input 
            v-model="form.name" 
            type="text" 
            placeholder="请输入真实姓名" 
            required
          >
        </div>
        
        <div class="form-group">
          <label>账号 <span class="required">*</span></label>
          <input 
            v-model="form.account" 
            type="text" 
            :placeholder="accountPlaceholder"
            required
          >
          <p class="field-hint">{{ accountHint }}</p>
        </div>

        <div class="form-group">
          <label>邮箱</label>
          <input 
            v-model="form.email" 
            type="email" 
            placeholder="请输入邮箱（选填）"
          >
        </div>
        
        <div class="form-group">
          <label>密码 <span class="required">*</span></label>
          <input 
            v-model="form.password" 
            type="password" 
            placeholder="请输入密码（至少6位）" 
            required
          >
        </div>
        
        <div class="form-group">
          <label>确认密码 <span class="required">*</span></label>
          <input 
            v-model="form.confirmPassword" 
            type="password" 
            placeholder="请再次输入密码" 
            required
          >
        </div>

        <button type="submit" class="btn btn-primary" :disabled="loading || !form.role">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>
      <p class="login-link">
        已有账号？<router-link to="/login">立即登录</router-link>
      </p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="success" class="success">{{ success }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { authAPI } from '@/api/auth'

const router = useRouter()

const form = ref({
  name: '',
  account: '',
  email: '',
  password: '',
  confirmPassword: '',
  role: ''
})

const loading = ref(false)
const error = ref('')
const success = ref('')

const accountPlaceholder = computed(() => {
  if (form.value.role === 'student') {
    return '请输入学号'
  } else if (form.value.role === 'teacher') {
    return '请输入工号'
  } else if (form.value.role === 'admin') {
    return '请输入工号'
  }
  return '请输入账号'
})

const accountHint = computed(() => {
  if (form.value.role === 'student') {
    return '学号将作为您的登录账号'
  } else if (form.value.role === 'teacher') {
    return '工号将作为您的登录账号'
  } else if (form.value.role === 'admin') {
    return '工号将作为您的登录账号'
  }
  return ''
})

const switchRole = (role) => {
  form.value.role = role
  form.value.account = ''
}

const handleRegister = async () => {
  error.value = ''
  success.value = ''
  
  if (!form.value.role) {
    error.value = '请选择身份'
    return
  }
  
  if (!form.value.account) {
    error.value = form.value.role === 'student' ? '请输入学号' : '请输入工号'
    return
  }
  
  if (form.value.password !== form.value.confirmPassword) {
    error.value = '两次输入的密码不一致'
    return
  }
  
  if (form.value.password.length < 6) {
    error.value = '密码长度至少6位'
    return
  }
  
  loading.value = true
  
  try {
    const registerData = {
      username: form.value.account,
      name: form.value.name,
      password: form.value.password,
      role: form.value.role,
      email: form.value.email || `${form.value.account}@example.com`
    }
    
    if (form.value.role === 'student') {
      registerData.student_id = form.value.account
    } else {
      registerData.teacher_id = form.value.account
    }
    
    await authAPI.register(registerData)
    success.value = `注册成功！您的账号是 ${form.value.account}，即将跳转到登录页面...`
    
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err) {
    error.value = err.response?.data?.error || '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-container {
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
  padding: 20px 0;
}

.register-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 0;
}

.register-card {
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
  max-height: 90vh;
  overflow-y: auto;
}

.register-logo {
  position: absolute;
  top: 15px;
  left: 15px;
  height: 60px;
  width: auto;
  object-fit: contain;
}

.register-card h2 {
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
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  color: #555;
  font-weight: 500;
  font-size: 14px;
}

.required {
  color: #e74c3c;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.3s;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
}

.field-hint {
  font-size: 12px;
  color: #999;
  margin: 4px 0 0 0;
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
  margin-top: 10px;
}

.btn:hover:not(:disabled) {
  background: #5568d3;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-link {
  text-align: center;
  margin-top: 20px;
  color: #666;
}

.login-link a {
  color: #667eea;
  text-decoration: none;
}

.login-link a:hover {
  text-decoration: underline;
}

.error {
  color: #e74c3c;
  text-align: center;
  margin-top: 15px;
  font-size: 14px;
}

.success {
  color: #27ae60;
  text-align: center;
  margin-top: 15px;
  font-size: 14px;
}
</style>
