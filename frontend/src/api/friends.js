import api from './index'

export const friendsAPI = {
  getFriends() {
    return api.get('/friends/list')
  },
  
  getPendingRequests() {
    return api.get('/friends/pending')
  },
  
  addFriend(friendCode) {
    return api.post('/friends/add', { friend_code: friendCode })
  },
  
  acceptRequest(requestId) {
    return api.post(`/friends/accept/${requestId}`)
  },
  
  rejectRequest(requestId) {
    return api.post(`/friends/reject/${requestId}`)
  },
  
  removeFriend(friendshipId) {
    return api.delete(`/friends/remove/${friendshipId}`)
  },
  
  searchUser(code) {
    return api.get(`/friends/search?code=${code}`)
  }
}
