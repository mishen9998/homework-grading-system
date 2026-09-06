<template>
  <div id="app">
    <GlobalLoading />
    <router-view v-slot="{ Component, route }">
      <keep-alive :include="cachedViews">
        <component :is="Component" :key="route.fullPath" />
      </keep-alive>
    </router-view>
    <TeacherAiAssistant v-if="showTeacherAi" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { cancelAllRequests, clearCache } from '@/api/index'
import GlobalLoading from '@/components/GlobalLoading.vue'
import TeacherAiAssistant from '@/components/TeacherAiAssistant.vue'

const route = useRoute()
const authStore = useAuthStore()
const showTeacherAi = computed(() => authStore.user?.role === 'teacher')
const cachedViews = ref([
  'StudentHome',
  'TeacherHome',
  'AdminHome',
  'StudentMessages',
  'TeacherMessages',
  'StudentProfile',
  'TeacherProfile',
  'AdminProfile',
  'StudentSchedule',
  'TeacherSchedule',
  'AdminSchedule',
  'AdminUsers'
])

const handleKeyDown = (event) => {
  if (event.key === 'F5' || (event.ctrlKey && event.key === 'r') || (event.metaKey && event.key === 'r')) {
    event.preventDefault()
    clearCacheAndRefresh()
  }
}

const clearCacheAndRefresh = () => {
  const token = localStorage.getItem('token')
  const user = localStorage.getItem('user')
  
  localStorage.clear()
  sessionStorage.clear()
  
  if (token && user) {
    localStorage.setItem('token', token)
    localStorage.setItem('user', user)
  }
  
  cancelAllRequests()
  clearCache()
  
  window.location.reload()
}

const handleBeforeUnload = () => {
  cancelAllRequests()
}

const handleVisibilityChange = () => {
  if (document.visibilityState === 'hidden') {
    cancelAllRequests()
  }
}

watch(
  () => route.path,
  (newPath, oldPath) => {
    if (newPath !== oldPath) {
      cancelAllRequests()
    }
  }
)

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('beforeunload', handleBeforeUnload)
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('beforeunload', handleBeforeUnload)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}
</style>
