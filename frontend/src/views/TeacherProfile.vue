<template>
  <div class="teacher-profile">
    <div class="profile-header">
      <div class="avatar-section">
        <div class="avatar-wrapper" @click="triggerAvatarUpload">
          <img 
            v-if="authStore.user?.avatar_url" 
            :src="getAvatarUrl(authStore.user.avatar_url)" 
            class="avatar-img"
            alt="头像"
          />
          <div v-else class="avatar">
            <span>{{ authStore.user?.name?.charAt(0) || '老' }}</span>
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
        <h2>{{ authStore.user?.name }}</h2>
        <p class="teacher-id">工号：{{ authStore.user?.teacher_id || '未填写' }}</p>
      </div>
      <button @click="handleLogout" class="logout-btn">退出登录</button>
    </div>

    <div class="quick-actions">
      <router-link to="/teacher/teaching-plan" class="action-card">
        <span class="action-icon">📚</span>
        <div class="action-info">
          <span class="action-title">授课计划</span>
          <span class="action-desc">查看教学课程安排</span>
        </div>
        <span class="action-arrow">›</span>
      </router-link>
    </div>

    <div class="profile-sections">
      <div class="section">
        <div class="section-header">
          <h3>基本信息</h3>
          <button v-if="!isEditing" @click="startEdit" class="edit-btn">编辑</button>
          <div v-else class="edit-actions">
            <button @click="saveEdit" class="save-btn" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
            <button @click="cancelEdit" class="cancel-btn">取消</button>
          </div>
        </div>
        <div class="info-list">
          <div class="info-item">
            <span class="label">账号</span>
            <span class="value">{{ authStore.user?.username }}</span>
          </div>
          <div class="info-item">
            <span class="label">姓名</span>
            <span v-if="!isEditing" class="value">{{ authStore.user?.name }}</span>
            <input v-else v-model="form.name" type="text" class="edit-input" placeholder="请输入姓名" />
          </div>
          <div class="info-item">
            <span class="label">工号</span>
            <span v-if="!isEditing" class="value">{{ authStore.user?.teacher_id || '未填写' }}</span>
            <input v-else v-model="form.teacher_id" type="text" class="edit-input" placeholder="请输入工号" />
          </div>
          <div class="info-item">
            <span class="label">手机号</span>
            <span v-if="!isEditing" class="value">{{ authStore.user?.phone || '未填写' }}</span>
            <input v-else v-model="form.phone" type="text" class="edit-input" placeholder="请输入手机号" />
          </div>
          <div class="info-item">
            <span class="label">学院</span>
            <span v-if="!isEditing" class="value">{{ authStore.user?.college || '未填写' }}</span>
            <input v-else v-model="form.college" type="text" class="edit-input" placeholder="如：计算机学院" />
          </div>
          <div class="info-item">
            <span class="label">邮箱</span>
            <span v-if="!isEditing" class="value">{{ authStore.user?.email }}</span>
            <input v-else v-model="form.email" type="email" class="edit-input" placeholder="请输入邮箱" />
          </div>
          <div class="info-item">
            <span class="label">角色</span>
            <span class="value">老师</span>
          </div>
        </div>
      </div>
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

const isEditing = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref('')
const avatarInput = ref(null)

const form = ref({
  name: '',
  teacher_id: '',
  phone: '',
  college: '',
  email: ''
})

const getAvatarUrl = (url) => {
  if (!url) return null
  if (url.startsWith('http')) return url
  return url
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

const startEdit = () => {
  form.value = {
    name: authStore.user?.name || '',
    teacher_id: authStore.user?.teacher_id || '',
    phone: authStore.user?.phone || '',
    college: authStore.user?.college || '',
    email: authStore.user?.email || ''
  }
  isEditing.value = true
  error.value = ''
  success.value = ''
}

const cancelEdit = () => {
  isEditing.value = false
  error.value = ''
  success.value = ''
}

const saveEdit = async () => {
  saving.value = true
  error.value = ''
  success.value = ''
  
  try {
    const response = await authAPI.updateProfile(form.value)
    authStore.setUser(response.data.user)
    isEditing.value = false
    success.value = '保存成功！'
    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (err) {
    error.value = err.response?.data?.error || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

const handleLogout = () => {
  if (confirm('确定要退出登录吗？')) {
    authStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.teacher-profile {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
  min-height: calc(100vh - 40px);
  background-image: url('@/assets/images/profile-background.jpg');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  background-attachment: fixed;
}

.profile-header {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.7) 0%, rgba(118, 75, 162, 0.7) 100%);
  color: white;
  padding: 30px;
  border-radius: 12px;
  margin-bottom: 30px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  backdrop-filter: blur(8px);
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
}

.avatar-wrapper {
  position: relative;
  cursor: pointer;
}

.avatar, .avatar-img {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar {
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: bold;
  backdrop-filter: blur(10px);
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
  font-size: 12px;
  font-weight: 500;
}

.avatar-section h2 {
  margin: 0 0 5px 0;
  font-size: 24px;
}

.teacher-id {
  margin: 0;
  opacity: 0.9;
  font-size: 14px;
}

.logout-btn {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
}

.logout-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.quick-actions {
  margin-bottom: 20px;
}

.action-card {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.85);
  padding: 16px 20px;
  border-radius: 12px;
  text-decoration: none;
  color: inherit;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  transition: all 0.3s;
  backdrop-filter: blur(8px);
}

.action-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}

.action-icon {
  font-size: 28px;
  margin-right: 15px;
}

.action-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.action-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.action-desc {
  font-size: 12px;
  color: #999;
}

.action-arrow {
  font-size: 24px;
  color: #ccc;
  font-weight: 300;
}

.profile-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section {
  background: rgba(255, 255, 255, 0.85);
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  backdrop-filter: blur(8px);
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

.edit-btn {
  background: #667eea;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.edit-btn:hover {
  background: #5568d3;
}

.edit-actions {
  display: flex;
  gap: 10px;
}

.save-btn {
  background: #28a745;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.save-btn:hover:not(:disabled) {
  background: #218838;
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cancel-btn {
  background: #6c757d;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.cancel-btn:hover {
  background: #5a6268;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item .label {
  color: #999;
  font-size: 14px;
  min-width: 80px;
}

.info-item .value {
  color: #333;
  font-size: 14px;
  font-weight: 500;
  text-align: right;
  flex: 1;
}

.edit-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  text-align: right;
  max-width: 250px;
}

.edit-input:focus {
  outline: none;
  border-color: #667eea;
}

.error-msg {
  color: #e74c3c;
  text-align: center;
  margin-top: 15px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.85);
  padding: 10px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
}

.success-msg {
  color: #28a745;
  text-align: center;
  margin-top: 15px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.85);
  padding: 10px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
}
</style>
