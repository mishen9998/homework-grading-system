<template>
  <div class="admin-profile">
    <div class="profile-card">
      <div class="profile-header">
        <div class="avatar-wrapper" @click="triggerAvatarUpload">
          <img 
            v-if="authStore.user?.avatar_url" 
            :src="getAvatarUrl(authStore.user.avatar_url)" 
            class="avatar-img"
            alt="头像"
          />
          <div v-else class="avatar">
            {{ authStore.user?.name?.charAt(0) || 'A' }}
          </div>
          <div class="avatar-overlay">
            <span>更换头像</span>
          </div>
          <input 
            ref="avatarInput" 
            type="file" 
            accept="image/*" 
            @change="handleAvatarChange"
            hidden
          />
        </div>
        <div class="profile-info">
          <h2>{{ authStore.user?.name }}</h2>
          <span class="role-badge">管理员</span>
        </div>
      </div>
      
      <div class="profile-details">
        <div class="detail-item">
          <span class="label">账号</span>
          <span class="value">{{ authStore.user?.username }}</span>
        </div>
        <div class="detail-item">
          <span class="label">邮箱</span>
          <span class="value">{{ authStore.user?.email }}</span>
        </div>
      </div>
    </div>

    <div class="actions-card">
      <h3>账号操作</h3>
      <button @click="handleLogout" class="action-btn logout">
        <span class="icon">🚪</span>
        <span>退出登录</span>
      </button>
    </div>

    <p v-if="error" class="error-msg">{{ error }}</p>
    <p v-if="success" class="success-msg">{{ success }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { authAPI } from '@/api/auth'

const router = useRouter()
const authStore = useAuthStore()
const avatarInput = ref(null)
const error = ref('')
const success = ref('')

const getAvatarUrl = (url) => {
  if (!url) return null
  if (url.startsWith('http')) return url
  return `http://localhost:5000${url}`
}

const triggerAvatarUpload = () => {
  avatarInput.value.click()
}

const handleAvatarChange = async (event) => {
  const file = event.target.files[0]
  if (!file) return
  
  const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif']
  if (!allowedTypes.includes(file.type)) {
    error.value = '只支持 png, jpg, jpeg, gif 格式的图片'
    setTimeout(() => { error.value = '' }, 3000)
    return
  }
  
  if (file.size > 2 * 1024 * 1024) {
    error.value = '图片大小不能超过 2MB'
    setTimeout(() => { error.value = '' }, 3000)
    return
  }
  
  const formData = new FormData()
  formData.append('file', file)
  
  try {
    const response = await authAPI.uploadAvatar(formData)
    authStore.setUser(response.data.user)
    success.value = '头像更新成功！'
    setTimeout(() => { success.value = '' }, 3000)
  } catch (err) {
    error.value = err.response?.data?.error || '头像上传失败'
    setTimeout(() => { error.value = '' }, 3000)
  }
  
  event.target.value = ''
}

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-profile {
  padding: 20px;
}

.profile-card {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f0f0f0;
}

.avatar-wrapper {
  position: relative;
  cursor: pointer;
}

.avatar, .avatar-img {
  width: 70px;
  height: 70px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: bold;
}

.avatar-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s;
}

.avatar-wrapper:hover .avatar-overlay {
  opacity: 1;
}

.avatar-overlay span {
  color: white;
  font-size: 11px;
  font-weight: 500;
}

.profile-info h2 {
  margin: 0 0 8px 0;
  color: #333;
}

.role-badge {
  background: #f3e5f5;
  color: #9C27B0;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.profile-details {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f5f5f5;
}

.detail-item:last-child {
  border-bottom: none;
}

.label {
  color: #999;
  font-size: 14px;
}

.value {
  color: #333;
  font-weight: 500;
}

.actions-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.actions-card h3 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.action-btn {
  width: 100%;
  padding: 15px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.3s;
}

.action-btn.logout {
  background: #ffebee;
  color: #f44336;
}

.action-btn.logout:hover {
  background: #ffcdd2;
}

.action-btn .icon {
  font-size: 18px;
}

.error-msg {
  color: #e74c3c;
  text-align: center;
  margin-top: 15px;
  font-size: 14px;
  background: white;
  padding: 10px;
  border-radius: 6px;
}

.success-msg {
  color: #28a745;
  text-align: center;
  margin-top: 15px;
  font-size: 14px;
  background: white;
  padding: 10px;
  border-radius: 6px;
}
</style>
