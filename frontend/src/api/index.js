import axios from 'axios'

const baseURL = import.meta.env?.VITE_API_BASE || '/api'
const api = axios.create({ baseURL, timeout: 10000 })
const longApi = axios.create({ baseURL, timeout: 180000 })
let loadingCallbacks = []
const pendingRequests = new Map()

const notifyLoadingChange = () => {
  loadingCallbacks.forEach(callback => callback(pendingRequests.size > 0))
}

export const setLoadingCallback = callback => {
  loadingCallbacks.push(callback)
  return () => { loadingCallbacks = loadingCallbacks.filter(item => item !== callback) }
}

// Compatibility for callers. Never replace fresh business responses with an
// old process-wide cache. Server-side knowledge caching remains available.
export const clearCache = () => {}

const finish = config => {
  if (config?._requestId) pendingRequests.delete(config._requestId)
  config?._detachAbort?.()
  notifyLoadingChange()
}

const setupInterceptors = instance => {
  instance.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    config._sessionToken = token
    if (token) config.headers.Authorization = `Bearer ${token}`
    else delete config.headers.Authorization
    if (!(config.data instanceof FormData)) config.headers['Content-Type'] = 'application/json'

    // Duplicate POSTs must not abort an already committing transaction.
    const controller = new AbortController()
    const callerSignal = config.signal
    if (callerSignal) {
      const abort = () => controller.abort()
      if (callerSignal.aborted) abort()
      else callerSignal.addEventListener('abort', abort, { once: true })
      config._detachAbort = () => callerSignal.removeEventListener('abort', abort)
    }
    config.signal = controller.signal
    config._requestId = Symbol('request')
    pendingRequests.set(config._requestId, { controller, method: config.method?.toLowerCase() })
    notifyLoadingChange()
    return config
  })

  instance.interceptors.response.use(response => {
    finish(response.config)
    if (response.config._sessionToken !== localStorage.getItem('token')) {
      throw new axios.CanceledError('账号已切换，忽略旧会话响应')
    }
    return response
  }, error => {
    finish(error.config)
    const sameSession = error.config?._sessionToken === localStorage.getItem('token')
    if (error.response?.status === 401 && sameSession) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      cancelAllRequests()
      if (!['/login', '/loading'].includes(window.location.pathname)) window.location.href = '/login'
    }
    // Preserve Axios status/codes for retry and form error handling.
    return Promise.reject(error)
  })
}

export const cancelAllRequests = () => {
  pendingRequests.forEach(({ controller }) => controller.abort())
  pendingRequests.clear()
  notifyLoadingChange()
}
export const cancelPendingReads = () => {
  pendingRequests.forEach(({ controller, method }, key) => {
    if (method === 'get' || method === 'head') {
      controller.abort()
      pendingRequests.delete(key)
    }
  })
  notifyLoadingChange()
}
export const getPendingRequestCount = () => pendingRequests.size
export const isLoadingState = () => pendingRequests.size > 0

setupInterceptors(api)
setupInterceptors(longApi)
export { longApi }
export default api
