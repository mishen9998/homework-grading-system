import api, { longApi } from './index'
import { resolveAiResponse } from './ai_jobs'

export const assignmentAPI = {
  createCourse(data) {
    return api.post('/courses/create', data)
  },
  
  createAssignment(data) {
    return api.post('/assignments', data)
  },
  
  getAssignments() {
    return api.get('/assignments')
  },
  
  getAssignment(id) {
    return api.get(`/assignments/${id}`)
  },
  
  updateAssignment(id, data) {
    return api.put(`/assignments/${id}`, data)
  },
  
  submitAssignment(assignmentId, data) {
    const formData = new FormData()
    if (data.content) {
      formData.append('content', data.content)
    }
    if (data.file) {
      formData.append('file', data.file)
    }
    if (data.answers) {
      formData.append('answers', JSON.stringify(data.answers))
    }
    return api.post(`/assignments/${assignmentId}/submit`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  
  getSubmissions(assignmentId) {
    return api.get(`/assignments/${assignmentId}/submissions`)
  },
  
  gradeSubmission(submissionId, data) {
    return api.put(`/assignments/submissions/${submissionId}/grade`, data)
  },
  
  getMySubmissions() {
    return api.get('/assignments/my-submissions')
  },

  getMyCourses() {
    return api.get('/courses/my-courses')
  },

  getStudentCount(courseId) {
    return api.get(`/courses/${courseId}/students`)
  },

  joinCourse(code) {
    return api.post('/courses/join', { code })
  },

  getCourseDetail(courseId) {
    return api.get(`/courses/${courseId}`)
  },

  getCourseAssignments(courseId) {
    return api.get(`/courses/${courseId}/assignments`)
  },

  getCourseResources(courseId) {
    return api.get(`/courses/${courseId}/resources`)
  },

  getCourseNotes(courseId) {
    return api.get(`/courses/${courseId}/notes`)
  },

  saveNote(courseId, data) {
    return api.post(`/courses/${courseId}/notes`, data)
  },

  updateNote(noteId, data) {
    return api.put(`/courses/notes/${noteId}`, data)
  },

  deleteNote(noteId) {
    return api.delete(`/courses/notes/${noteId}`)
  },

  createAssignmentForCourse(courseId, data) {
    return api.post(`/courses/${courseId}/assignments`, data)
  },

  createResource(courseId, data) {
    if (data instanceof FormData) {
      return api.post(`/courses/${courseId}/resources`, data, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
    }
    return api.post(`/courses/${courseId}/resources`, data)
  },

  uploadResourceFile(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/courses/upload-resource', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  deleteResource(resourceId) {
    return api.delete(`/courses/resources/${resourceId}`)
  },

  getPendingAssignments() {
    return api.get('/courses/pending-assignments')
  },

  getQuestions(assignmentId) {
    return api.get(`/questions/assignment/${assignmentId}`)
  },

  createQuestion(data) {
    return api.post('/questions', data)
  },

  createQuestionsBatch(data) {
    return api.post('/questions/batch', data)
  },

  updateQuestion(questionId, data) {
    return api.put(`/questions/${questionId}`, data)
  },

  deleteQuestion(questionId) {
    return api.delete(`/questions/${questionId}`)
  },

  uploadQuestionImage(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/questions/upload-image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  async aiGradeQuestion(data) {
    return resolveAiResponse(await longApi.post('/assignments/ai-grade', data))
  },

  async generateOverallComment(submissionId) {
    return resolveAiResponse(await longApi.post(`/assignments/submissions/${submissionId}/generate-comment`))
  },

  lockComment(submissionId, action = 'lock') {
    return api.post(`/assignments/submissions/${submissionId}/lock-comment`, { action })
  },

  updateComment(submissionId, data) {
    return api.put(`/assignments/submissions/${submissionId}/update-comment`, data)
  },

  importQuestions(assignmentId, file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/assignments/${assignmentId}/import-questions`, formData)
  },

  downloadQuestionsTemplate() {
    return api.get('/assignments/import-template', {
      responseType: 'blob'
    })
  },

  clearQuestions(assignmentId) {
    return api.delete(`/assignments/${assignmentId}/clear-questions`)
  },

  importTextQuestions(assignmentId, text) {
    return api.post(`/assignments/${assignmentId}/import-text`, { text })
  },

  importFileQuestions(assignmentId, file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/assignments/${assignmentId}/import-file`, formData)
  },

  async aiParseQuestions(assignmentId, text) {
    return resolveAiResponse(await longApi.post(`/assignments/${assignmentId}/ai-parse`, { text }))
  },

  checkAIStatus() {
    return api.get('/assignments/ai-status')
  },

  testAIConnection() {
    return api.post('/assignments/ai-test')
  },

  getTeacherPendingSubmissions() {
    return api.get('/courses/teacher/pending-submissions')
  },

  getUnsubmittedStudents(assignmentId) {
    return api.get(`/courses/assignments/${assignmentId}/unsubmitted-students`)
  },

  sendAssignmentReminder(assignmentId, data = {}) {
    return api.post(`/courses/assignments/${assignmentId}/send-reminder`, data)
  },

  getMessages() {
    return api.get('/courses/messages')
  },

  markMessageRead(messageId) {
    return api.put(`/courses/messages/${messageId}/read`)
  },

  getAssignmentStatistics(assignmentId) {
    return api.get(`/courses/assignments/${assignmentId}/statistics`)
  }
}
