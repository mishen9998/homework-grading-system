import api from './index'

export const adminAPI = {
  getUsers(params) {
    return api.get('/admin/users', { params })
  },
  
  getUser(userId) {
    return api.get(`/admin/users/${userId}`)
  },
  
  updateUser(userId, data) {
    return api.put(`/admin/users/${userId}`, data)
  },
  
  deleteUser(userId) {
    return api.delete(`/admin/users/${userId}`)
  },
  
  importUsers(formData) {
    return api.post('/admin/import', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  
  downloadTemplate() {
    return api.get('/admin/template', {
      responseType: 'blob'
    })
  },
  
  getStatistics() {
    return api.get('/admin/statistics')
  }
}
