import api from './index'

export const chatsAPI = {
  getConversations() {
    return api.get('/chats/conversations')
  },
  
  getMessages(friendId, page = 1, perPage = 50) {
    return api.get(`/chats/messages/${friendId}?page=${page}&per_page=${perPage}`)
  },
  
  sendMessage(data) {
    return api.post('/chats/send', data)
  },
  
  uploadFile(formData) {
    return api.post('/chats/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },
  
  downloadFile(messageId) {
    return api.get(`/chats/download/${messageId}`, {
      responseType: 'blob'
    })
  },
  
  getUnreadCount() {
    return api.get('/chats/unread-count')
  }
}
