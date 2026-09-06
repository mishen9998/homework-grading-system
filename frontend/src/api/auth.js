import api from './index'

export const authAPI = {
  register(data) {
    return api.post('/auth/register', data)
  },
  
  login(data) {
    return api.post('/auth/login', data)
  },
  
  getCurrentUser() {
    return api.get('/auth/me')
  },
  
  updateProfile(data) {
    return api.put('/auth/update-profile', data)
  },
  
  uploadAvatar(formData) {
    return api.post('/auth/upload-avatar', formData)
  }
}
