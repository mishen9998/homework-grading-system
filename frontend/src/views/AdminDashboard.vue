<template>
  <div class="admin-dashboard">
    <header class="dashboard-header">
      <h1>管理员后台</h1>
      <div class="user-info">
        <span>欢迎，{{ authStore.user?.name }}</span>
        <button @click="handleLogout" class="logout-btn">退出登录</button>
      </div>
    </header>

    <div class="main-content">
      <router-view />
    </div>

    <nav class="bottom-nav">
      <router-link to="/admin/knowledge" class="nav-item" active-class="active"><span class="nav-icon">📚</span><span class="nav-label">知识库审批</span></router-link>
      <router-link to="/admin/home" class="nav-item" active-class="active">
        <span class="nav-icon">🏠</span>
        <span class="nav-label">首页</span>
      </router-link>
      <router-link to="/admin/users" class="nav-item" active-class="active">
        <span class="nav-icon">👥</span>
        <span class="nav-label">用户管理</span>
      </router-link>
      <router-link to="/admin/import" class="nav-item" active-class="active">
        <span class="nav-icon">📥</span>
        <span class="nav-label">批量导入</span>
      </router-link>
      <router-link to="/admin/schedule" class="nav-item" active-class="active">
        <span class="nav-icon">📅</span>
        <span class="nav-label">课表管理</span>
      </router-link>
      <router-link to="/admin/profile" class="nav-item" active-class="active">
        <span class="nav-icon">👤</span>
        <span class="nav-label">个人中心</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const authStore = useAuthStore()

const handleLogout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-dashboard {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 70px;
}

.dashboard-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: white;
}

.dashboard-header h1 {
  margin: 0;
  font-size: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.user-info span {
  font-size: 14px;
}

.logout-btn {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.logout-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-around;
  padding: 10px 0;
  z-index: 100;
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-decoration: none;
  color: #999;
  transition: all 0.3s;
  flex: 1;
}

.nav-item:hover {
  color: #667eea;
}

.nav-item.active {
  color: #667eea;
}

.nav-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.nav-label {
  font-size: 12px;
}
</style>
