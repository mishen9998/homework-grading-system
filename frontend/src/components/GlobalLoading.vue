<template>
  <Transition name="fade">
    <div v-if="show" class="global-loading-overlay">
      <div class="loading-spinner">
        <div class="spinner"></div>
        <p class="loading-text">{{ loadingText }}</p>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { setLoadingCallback } from '@/api/index'

const show = ref(false)
let loadingTimeout = null
let cleanup = null
let loadingStartTime = null

const loadingText = ref('加载中...')

const handleLoadingChange = (loading) => {
  if (loading) {
    if (loadingTimeout) {
      clearTimeout(loadingTimeout)
    }
    loadingStartTime = Date.now()
    loadingTimeout = setTimeout(() => {
      show.value = true
    }, 300)
  } else {
    if (loadingTimeout) {
      clearTimeout(loadingTimeout)
      loadingTimeout = null
    }
    
    if (show.value && loadingStartTime) {
      const elapsed = Date.now() - loadingStartTime
      if (elapsed < 200) {
        setTimeout(() => {
          show.value = false
        }, 200 - elapsed)
        return
      }
    }
    
    show.value = false
    loadingStartTime = null
  }
}

onMounted(() => {
  cleanup = setLoadingCallback(handleLoadingChange)
})

onUnmounted(() => {
  if (cleanup) {
    cleanup()
  }
  if (loadingTimeout) {
    clearTimeout(loadingTimeout)
  }
})
</script>

<style scoped>
.global-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 15px;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-text {
  color: #667eea;
  font-size: 16px;
  font-weight: 500;
  margin: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
