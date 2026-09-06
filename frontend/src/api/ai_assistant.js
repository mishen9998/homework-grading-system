import { longApi } from './index'

export const aiAssistantAPI = {
  ask(data) {
    return longApi.post('/ai/assistant', data)
  }
}

