<template>
  <Teleport to="body">
    <button
      v-if="!isOpen"
      class="teacher-ai-launcher"
      type="button"
      aria-label="打开AI助手"
      @click="isOpen = true"
    >
      <span class="launcher-sparkle">✦</span>
      <span>AI 助手</span>
    </button>

    <section v-else class="teacher-ai-panel" aria-label="老师AI助手">
      <header class="assistant-header">
        <div class="assistant-title">
          <span class="assistant-avatar">✦</span>
          <div>
            <strong>老师 AI 助手</strong>
            <small>帮你设计、批改、发布</small>
          </div>
        </div>
        <button class="assistant-close" type="button" aria-label="关闭" @click="isOpen = false">×</button>
      </header>

      <div ref="messageList" class="assistant-messages">
        <div
          v-for="(item, index) in messages"
          :key="`${item.role}-${index}`"
          :class="['assistant-message', item.role]"
        >
          <div class="message-bubble">
            {{ item.content }}
            <div v-if="item.sources?.length" class="agent-sources">
              <small v-for="source in item.sources" :key="source.id">[{{ source.id }}] {{ source.title }}</small>
            </div>
            <button v-if="item.action?.requires_confirmation" class="agent-confirm" type="button" @click="confirmAgentAction(item)">
              {{ item.action.label || '确认执行' }}
            </button>
          </div>
        </div>
        <div v-if="loading" class="assistant-message assistant">
          <div class="message-bubble loading-bubble"><span></span><span></span><span></span></div>
        </div>
      </div>

      <div v-if="draft" class="assistant-draft">
        <div class="draft-heading">
          <span>📋</span>
          <div>
            <strong>已生成作业草稿</strong>
            <small>{{ draft.questions?.length || 0 }} 道题 · {{ draft.total_score || 0 }} 分</small>
          </div>
        </div>
        <p class="draft-title">{{ draft.title || '未命名作业' }}</p>
        <p v-if="draft.description" class="draft-description">{{ draft.description }}</p>
        <div class="draft-meta">
          <span v-if="draft.due_date">截止 {{ formatDraftDate(draft.due_date) }}</span>
          <span v-else>截止时间待补充</span>
        </div>
        <button class="apply-draft-button" type="button" @click="applyDraft">
          应用到发布表单
        </button>
      </div>

      <div v-if="suggestions.length" class="assistant-suggestions">
        <button v-for="suggestion in suggestions" :key="suggestion" type="button" @click="sendMessage(suggestion)">
          {{ suggestion }}
        </button>
      </div>

      <div v-if="showQuickActions" class="assistant-quick-actions">
        <button type="button" @click="sendMessage('请帮我生成一份适合当前课程的作业草稿，包含题目、分值和参考答案')">生成作业草稿</button>
        <button type="button" @click="sendMessage('请帮我分析当前作业的批改重点，并给出评分建议')">分析批改重点</button>
        <button type="button" @click="sendMessage('请帮我写一段提醒学生按时提交作业的通知')">写作业提醒</button>
      </div>

      <form class="assistant-input" @submit.prevent="sendMessage()">
        <textarea
          v-model="input"
          rows="1"
          maxlength="2000"
          placeholder="例如：帮我出一份数据库第三章作业…"
          @keydown.enter.exact.prevent="sendMessage()"
        ></textarea>
        <button type="submit" :disabled="loading || !input.trim()" aria-label="发送">↑</button>
      </form>
      <p class="assistant-disclaimer">AI 生成内容仅供参考，发布和评分前请老师复核。</p>
    </section>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { aiAssistantAPI } from '@/api/ai_assistant'
import { knowledgeAPI } from '@/api/knowledge'

const route = useRoute()
const router = useRouter()

const isOpen = ref(false)
const loading = ref(false)
const input = ref('')
const draft = ref(null)
const suggestions = ref([])
const messageList = ref(null)
const messages = ref([
  {
    role: 'assistant',
    content: '你好，我可以帮你生成作业草稿、梳理批改重点、撰写评语和作业提醒。你想先处理哪件事？'
  }
])

const showQuickActions = computed(() => messages.value.length === 1 && !loading.value)

const currentContext = () => {
  const sharedContext = window.__teacherAiContext || {}
  return {
    ...sharedContext,
    route: route.fullPath,
    page: route.name || route.path,
    course_id: route.params.id || sharedContext.course_id || null,
    assignment_id: sharedContext.assignment_id || null,
    submission_id: sharedContext.submission_id || null
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight
  }
}

const sendMessage = async (preset = '') => {
  const content = (preset || input.value).trim()
  if (!content || loading.value) return

  messages.value.push({ role: 'user', content })
  input.value = ''
  draft.value = null
  suggestions.value = []
  loading.value = true
  await scrollToBottom()

  try {
    const context = currentContext()
    // The permission-aware local agent handles course lookup, grading
    // progress, reminders and assignment drafts without model tokens.
    try {
      const agentResponse = await knowledgeAPI.agent({ message: content, course_id: context.course_id })
      const agentData = agentResponse.data || {}
      if (agentData.mode === 'agent' || agentData.action || agentData.sources?.length) {
        messages.value.push({ role: 'assistant', content: agentData.reply || '已完成查询。', action: agentData.action, sources: agentData.sources })
        draft.value = null
        suggestions.value = []
        return
      }
    } catch (agentError) {
      // Fall through to the existing model assistant for free-form teaching requests.
    }

    const response = await aiAssistantAPI.ask({
      message: content,
      context,
      history: messages.value.slice(-8).map(item => ({ role: item.role, content: item.content }))
    })
    const data = response.data || {}
    if (data.success === false) throw new Error(data.error || 'AI助手暂时不可用')
    messages.value.push({ role: 'assistant', content: data.reply || '我已经处理好了，可以继续告诉我你的具体要求。' })
    draft.value = data.draft || null
    suggestions.value = Array.isArray(data.suggestions) ? data.suggestions : []
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: error.response?.data?.error || error.message || 'AI助手暂时不可用，请稍后重试。'
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

const confirmAgentAction = async (message) => {
  if (!message.action || loading.value) return
  const action = message.action
  message.action = null
  loading.value = true
  messages.value.push({ role: 'user', content: `确认：${action.label || '执行该操作'}` })
  await scrollToBottom()
  try {
    const response = await knowledgeAPI.agent({
      message: '确认执行', confirm: true, action: action.type, payload: action.payload
    })
    messages.value.push({ role: 'assistant', content: response.data?.reply || '操作已完成。' })
  } catch (error) {
    messages.value.push({ role: 'assistant', content: error.response?.data?.error || error.message || '操作失败，请稍后重试。' })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

const applyDraft = async () => {
  if (!draft.value) return
  const payload = {
    ...draft.value,
    course_id: route.params.id || window.__teacherAiContext?.course_id || null
  }

  if (!payload.course_id) {
    messages.value.push({
      role: 'assistant',
      content: '请先进入要发布作业的具体课程，再点击“应用到发布表单”。这样我才能把草稿放进正确的课程。'
    })
    await scrollToBottom()
    return
  }

  if (String(route.params.id) === String(payload.course_id) && route.name === 'TeacherCourseDetail') {
    window.dispatchEvent(new CustomEvent('teacher-ai-apply-draft', { detail: payload }))
    isOpen.value = false
    return
  }

  sessionStorage.setItem('teacher-ai-assignment-draft', JSON.stringify(payload))
  await router.push(`/teacher/course/${payload.course_id}`)
  isOpen.value = false
}

const formatDraftDate = (value) => {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

watch(isOpen, (open) => {
  if (open) scrollToBottom()
})
</script>

<style scoped>
.teacher-ai-launcher {
  position: fixed;
  right: 24px;
  bottom: 92px;
  z-index: 1200;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 999px;
  padding: 12px 17px 12px 13px;
  color: #fff;
  background: linear-gradient(135deg, #5d6df8, #8a52cf);
  box-shadow: 0 10px 26px rgba(83, 79, 190, .32);
  font-weight: 700;
  cursor: pointer;
  transition: transform .2s, box-shadow .2s;
}
.teacher-ai-launcher:hover { transform: translateY(-2px); box-shadow: 0 13px 30px rgba(83, 79, 190, .4); }
.launcher-sparkle { font-size: 18px; }
.teacher-ai-panel {
  position: fixed;
  right: 24px;
  bottom: 88px;
  z-index: 1200;
  width: min(390px, calc(100vw - 32px));
  overflow: hidden;
  border: 1px solid rgba(105, 112, 232, .2);
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 18px 60px rgba(39, 44, 97, .24);
}
.assistant-header { display: flex; justify-content: space-between; align-items: center; padding: 15px 17px; color: #fff; background: linear-gradient(135deg, #596bf4, #8450c9); }
.assistant-title { display: flex; align-items: center; gap: 10px; }
.assistant-avatar { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 11px; color: #596bf4; background: #fff; font-size: 20px; }
.assistant-title strong, .assistant-title small { display: block; }
.assistant-title strong { font-size: 14px; }
.assistant-title small { margin-top: 3px; opacity: .8; font-size: 11px; }
.assistant-close { border: 0; color: #fff; background: transparent; font-size: 25px; line-height: 1; cursor: pointer; opacity: .85; }
.assistant-messages { max-height: 300px; overflow-y: auto; padding: 15px; background: #f7f8fc; }
.assistant-message { display: flex; margin-bottom: 11px; }
.assistant-message.user { justify-content: flex-end; }
.message-bubble { max-width: 88%; padding: 10px 12px; border-radius: 13px 13px 13px 4px; color: #33384e; background: #fff; white-space: pre-wrap; line-height: 1.55; font-size: 13px; box-shadow: 0 2px 8px rgba(39, 44, 97, .06); }
.agent-sources { display: grid; gap: 3px; margin-top: 8px; color: #6875c5; font-size: 11px; }
.agent-confirm { width: 100%; margin-top: 9px; padding: 7px 9px; border: 0; border-radius: 8px; color: #fff; background: #6875e9; font-size: 12px; cursor: pointer; }
.agent-confirm:hover { background: #5362dc; }
.assistant-message.user .message-bubble { border-radius: 13px 13px 4px 13px; color: #fff; background: #6875e9; }
.loading-bubble { display: flex; gap: 4px; padding: 13px; }
.loading-bubble span { width: 5px; height: 5px; border-radius: 50%; background: #8290e7; animation: assistant-bounce 1s infinite ease-in-out; }
.loading-bubble span:nth-child(2) { animation-delay: .15s; }
.loading-bubble span:nth-child(3) { animation-delay: .3s; }
@keyframes assistant-bounce { 0%, 80%, 100% { transform: translateY(0); opacity: .45; } 40% { transform: translateY(-4px); opacity: 1; } }
.assistant-quick-actions, .assistant-suggestions { display: flex; flex-wrap: wrap; gap: 7px; padding: 0 15px 12px; background: #f7f8fc; }
.assistant-quick-actions button, .assistant-suggestions button { padding: 7px 10px; border: 1px solid #dfe2f4; border-radius: 999px; color: #5964be; background: #fff; font-size: 11px; cursor: pointer; }
.assistant-quick-actions button:hover, .assistant-suggestions button:hover { border-color: #8b93ed; background: #f1f2ff; }
.assistant-draft { margin: 12px 15px; padding: 13px; border: 1px solid #dfe3ff; border-radius: 13px; background: linear-gradient(135deg, #f6f7ff, #fcfaff); }
.draft-heading { display: flex; align-items: center; gap: 9px; color: #4f5cc7; }
.draft-heading strong, .draft-heading small { display: block; }
.draft-heading small { margin-top: 2px; color: #7d83a4; font-size: 11px; }
.draft-title { margin: 10px 0 5px; color: #30344a; font-weight: 700; }
.draft-description { margin: 0; color: #666d86; font-size: 12px; line-height: 1.45; }
.draft-meta { margin: 8px 0 11px; color: #7d83a4; font-size: 11px; }
.apply-draft-button { width: 100%; padding: 9px; border: 0; border-radius: 8px; color: #fff; background: #6472e9; font-weight: 600; cursor: pointer; }
.apply-draft-button:hover { background: #5362dc; }
.assistant-input { display: flex; align-items: flex-end; gap: 8px; padding: 12px 15px 6px; border-top: 1px solid #eef0f6; background: #fff; }
.assistant-input textarea { flex: 1; max-height: 80px; resize: none; border: 1px solid #e0e3ef; border-radius: 10px; padding: 9px 10px; outline: none; color: #33384e; font: inherit; font-size: 13px; }
.assistant-input textarea:focus { border-color: #7782e8; }
.assistant-input button { width: 32px; height: 32px; border: 0; border-radius: 9px; color: #fff; background: #6875e9; font-size: 19px; cursor: pointer; }
.assistant-input button:disabled { background: #c7cae2; cursor: not-allowed; }
.assistant-disclaimer { margin: 0; padding: 0 15px 11px; color: #a1a6bb; font-size: 10px; }
@media (max-width: 520px) {
  .teacher-ai-launcher { right: 14px; bottom: 82px; }
  .teacher-ai-panel { right: 8px; bottom: 76px; width: calc(100vw - 16px); }
}
</style>
