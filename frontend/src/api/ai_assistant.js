import { longApi } from './index'
import { resolveAiResponse } from './ai_jobs'

export const aiAssistantAPI = {
  async ask(data) {
    return resolveAiResponse(await longApi.post('/ai/assistant', data))
  }
}
