import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 10000
})

const longApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 180000
})

let requestCount = 0
let loadingCallbacks = []
const pendingRequests = new Map()
const requestCache = new Map()
const CACHE_DURATION = 30000

const generateCacheKey = (config) => {
  const { method, url, params, data } = config
  return `${method?.toUpperCase()}_${url}_${JSON.stringify(params || {})}_${JSON.stringify(data || {})}`
}

const getCache = (key) => {
  const cached = requestCache.get(key)
  if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
    return cached.data
  }
  requestCache.delete(key)
  return null
}

const setCache = (key, data) => {
  requestCache.set(key, {
    data,
    timestamp: Date.now()
  })
}

export const clearCache = (pattern) => {
  if (pattern) {
    for (const key of requestCache.keys()) {
      if (key.includes(pattern)) {
        requestCache.delete(key)
      }
    }
  } else {
    requestCache.clear()
  }
}

export const setLoadingCallback = (callback) => {
  loadingCallbacks.push(callback)
  return () => {
    loadingCallbacks = loadingCallbacks.filter(cb => cb !== callback)
  }
}

const notifyLoadingChange = (loading) => {
  loadingCallbacks.forEach(cb => cb(loading))
}

const addPendingRequest = (config) => {
  const key = generateCacheKey(config)
  if (pendingRequests.has(key)) {
    const controller = pendingRequests.get(key)
    controller.abort()
  }
  const controller = new AbortController()
  config.signal = controller.signal
  pendingRequests.set(key, controller)
  return key
}

const removePendingRequest = (key) => {
  pendingRequests.delete(key)
}

const setupInterceptors = (axiosInstance, isLongRequest = false) => {
  axiosInstance.interceptors.request.use(
    (config) => {
      const token = localStorage.getItem('token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      
      if (!(config.data instanceof FormData)) {
        config.headers['Content-Type'] = 'application/json'
      }
      
      if (config.method?.toLowerCase() === 'get' && config.cache !== false) {
        const cacheKey = generateCacheKey(config)
        const cachedData = getCache(cacheKey)
        if (cachedData) {
          config._cached = true
          config._cacheData = cachedData
          return config
        }
        config._cacheKey = cacheKey
      }
      
      if (!isLongRequest) {
        const requestKey = addPendingRequest(config)
        config._requestKey = requestKey
      }
      
      requestCount++
      if (requestCount === 1) {
        notifyLoadingChange(true)
      }
      
      return config
    },
    (error) => {
      requestCount = Math.max(0, requestCount - 1)
      if (requestCount === 0) {
        notifyLoadingChange(false)
      }
      return Promise.reject(error)
    }
  )

  axiosInstance.interceptors.response.use(
    (response) => {
      if (response.config._requestKey) {
        removePendingRequest(response.config._requestKey)
      }
      
      if (response.config._cached && response.config._cacheData) {
        requestCount = Math.max(0, requestCount - 1)
        if (requestCount === 0) {
          notifyLoadingChange(false)
        }
        return response.config._cacheData
      }
      
      if (response.config._cacheKey) {
        setCache(response.config._cacheKey, response)
      }
      
      requestCount = Math.max(0, requestCount - 1)
      if (requestCount === 0) {
        notifyLoadingChange(false)
      }
      return response
    },
    (error) => {
      if (error.config?._requestKey) {
        removePendingRequest(error.config._requestKey)
      }
      
      requestCount = Math.max(0, requestCount - 1)
      if (requestCount === 0) {
        notifyLoadingChange(false)
      }
      
      if (error.name === 'CanceledError' || error.code === 'ERR_CANCELED') {
        return Promise.reject(new Error('请求已取消'))
      }
      
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        console.warn('请求超时，请检查网络连接')
        return Promise.reject(new Error('请求超时，请稍后重试'))
      }
      
      if (error.response) {
        const status = error.response.status
        
        if (status === 401) {
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          
          if (window.location.pathname !== '/login' && window.location.pathname !== '/loading') {
            window.location.href = '/login'
          }
        }
        
        if (status === 500) {
          console.warn('服务器错误，请检查后端服务是否正常运行')
        }
        
        if (status === 429) {
          console.warn('请求过于频繁，请稍后再试')
        }
      } else if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
        console.warn('无法连接到后端服务，请确保后端已启动 (python run.py)')
      }
      
      return Promise.reject(error)
    }
  )
}

setupInterceptors(api, false)
setupInterceptors(longApi, true)

export const cancelAllRequests = () => {
  pendingRequests.forEach((controller, key) => {
    controller.abort()
  })
  pendingRequests.clear()
  requestCount = 0
  notifyLoadingChange(false)
}

export const getPendingRequestCount = () => requestCount

export const isLoadingState = () => requestCount > 0

export { longApi }

export default api
