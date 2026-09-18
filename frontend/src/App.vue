<template>
  <div id="app">
    <GlobalLoading />
    <router-view v-slot="{ Component, route }">
      <keep-alive :key="authStore.user?.id || 'guest'" :include="cachedViews">
        <component :is="Component" :key="route.fullPath" />
      </keep-alive>
    </router-view>
    <TeacherAiAssistant v-if="showTeacherAi" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { cancelAllRequests, clearCache } from '@/api/index'
import GlobalLoading from '@/components/GlobalLoading.vue'
import TeacherAiAssistant from '@/components/TeacherAiAssistant.vue'

const authStore = useAuthStore()
const route = useRoute()
const showTeacherAi = computed(() =>
  authStore.user?.role === 'teacher' && route.path.startsWith('/teacher')
)
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
  // Refresh must not erase drafts or preferences belonging to the user.
  cancelAllRequests()
  clearCache()
  
  window.location.reload()
}

const handleBeforeUnload = () => {
  cancelAllRequests()
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('beforeunload', handleBeforeUnload)
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
