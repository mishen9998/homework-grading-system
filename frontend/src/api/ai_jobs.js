import api from './index'

const delay = ms => new Promise(resolve => setTimeout(resolve, ms))

/** Turn a 202 background-AI response into the same response shape callers used before. */
export async function resolveAiResponse(response, timeoutMs = 180000) {
  const jobId = response?.data?.job_id
  if (response?.status !== 202 || !jobId) return response

  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    await delay(900)
    const poll = await api.get(`/ai/jobs/${jobId}`, { cache: false })
    if (poll.data.status === 'completed') {
      return { ...response, status: 200, data: poll.data.result || {} }
    }
    if (poll.data.status === 'failed') {
      throw new Error(poll.data.error || 'AI任务执行失败')
    }
  }
  throw new Error('AI任务仍在排队，请稍后重试')
}
