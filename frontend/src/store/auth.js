import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { cancelAllRequests } from '@/api/index'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  let savedUser = null
  try { savedUser = JSON.parse(localStorage.getItem('user') || 'null') } catch {
    localStorage.removeItem('user')
    localStorage.removeItem('token')
    token.value = ''
  }
  const user = ref(savedUser)

  const isAuthenticated = computed(() => !!token.value)

  function setToken(newToken) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  function setUser(newUser) {
    user.value = newUser
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  function logout() {
    cancelAllRequests()
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return {
    token,
    user,
    isAuthenticated,
    setToken,
    setUser,
    logout
  }
})
