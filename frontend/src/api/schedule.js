import api from './index'

export const scheduleAPI = {
  uploadSchedule(formData) {
    return api.post('/schedules/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  
  getStudentSchedule() {
    return api.get('/schedules/student')
  },
  
  getTeacherSchedule() {
    return api.get('/schedules/teacher')
  },
  
  clearSchedule() {
    return api.delete('/schedules/clear')
  },
  
  async downloadTemplate() {
    const response = await api.get('/schedules/template', {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '课表导入模板.xlsx')
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }
}
