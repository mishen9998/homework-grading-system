import api, { longApi } from './index'

export const knowledgeAPI = {
  libraries: () => api.get('/knowledge/libraries', { cache: false }),
  list: params => api.get('/knowledge/entries', { params, cache: false }),
  detail: id => api.get(`/knowledge/entries/${id}`, { cache: false }),
  submit: data => api.post('/knowledge/entries', data),
  review: (id, data) => api.post(`/knowledge/entries/${id}/review`, data),
  ask: data => longApi.post('/knowledge/assistant', data),
  agent: data => longApi.post('/knowledge/agent', data),
  download: id => api.get(`/knowledge/entries/${id}/attachment`, { responseType: 'blob', cache: false })
}
