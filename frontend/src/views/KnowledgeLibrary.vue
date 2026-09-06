<template>
  <main class="knowledge-page">
    <header class="hero">
      <div><span class="eyebrow">CAMPUS LIBRARY · 校园图书馆</span><h1>{{ isAdmin ? '知识库管理' : libraryName }}</h1>
        <p>{{ isAdmin ? '审核师生分享，让可靠的知识在校园流动。' : '了解学校，发现课程，让每一份经验都有处可寻。' }}</p></div>
      <button class="primary" @click="showForm = !showForm">{{ showForm ? '收起表单' : '＋ 上传知识' }}</button>
    </header>
    <div v-if="isAdmin" class="tabs"><button v-for="item in libraries" :key="item.id" :class="{ selected: library === item.id }" @click="switchLibrary(item.id)">{{ item.name }}</button></div>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <form v-if="showForm" class="panel upload-form" @submit.prevent="submit">
      <h2>分享至{{ libraryName }}</h2><p>提交后由管理员审批，通过后才能被其他人和 AI 查阅。</p>
      <label>标题<input v-model="form.title" maxlength="200" required placeholder="给这份知识起一个清晰的标题"></label>
      <label>分类<select v-model="form.category" required><option value="" disabled>请选择分类</option><option v-for="category in categories" :key="category">{{ category }}</option></select></label>
      <label>正文 / 资料摘要<textarea v-model="form.content" rows="7" maxlength="50000" required placeholder="填写可供阅读和 AI 检索的内容。附件不会自动提取全文，请在这里录入重要信息。"></textarea></label>
      <label>来源或线上课程链接（选填）<input v-model="form.source_url" type="url" maxlength="1000" placeholder="https://"></label>
      <label>附件（选填，最大 5MB）<input :key="fileKey" type="file" accept=".pdf,.docx,.txt,.md,.pptx,.xlsx,.png,.jpg,.jpeg" @change="file = $event.target.files[0]"></label>
      <small>支持 PDF、Word、TXT、Markdown、PPT、Excel 和图片。</small>
      <button class="primary" :disabled="submitting">{{ submitting ? '正在提交…' : '提交审核' }}</button>
    </form>
    <div class="workspace" :class="{ 'admin-workspace': isAdmin }">
      <section class="shelves">
        <div class="tabs"><button :class="{ selected: !mine }" @click="setMine(false)">{{ isAdmin ? '审核与资料' : '浏览知识库' }}</button><button :class="{ selected: mine }" @click="setMine(true)">我的提交</button></div>
        <form class="filters" @submit.prevent="load(1)">
          <input v-model="keyword" placeholder="搜索标题、正文关键词" aria-label="搜索知识">
          <select v-model="category" aria-label="筛选分类" @change="load(1)"><option value="">全部分类</option><option v-for="item in categories" :key="item">{{ item }}</option></select>
          <select v-if="isAdmin || mine" v-model="status" aria-label="审核状态" @change="load(1)"><option value="">全部状态</option><option value="pending">待审核</option><option value="approved">已通过</option><option value="rejected">已驳回</option></select>
          <button type="submit">搜索</button>
        </form>
        <p class="muted">共 {{ total }} 份资料 · {{ libraryName }}</p>
        <div v-if="loading" class="empty">正在整理书架…</div>
        <div v-else-if="!items.length" class="empty"><span>📚</span><h2>{{ mine ? '还没有符合条件的提交' : '书架已就绪，等待知识入馆' }}</h2><p>{{ mine ? '上传自己的内容后，可以在这里查看审批进度和驳回原因。' : '可以调整筛选条件，或上传第一份资料。审核通过后将在这里展示。' }}</p></div>
        <div v-else class="cards"><button v-for="item in items" :key="item.id" class="card" @click="openEntry(item.id)"><div class="card-top"><span>{{ item.category }}</span><span :class="item.status">{{ statusLabel[item.status] }}</span></div><h2>{{ item.title }}</h2><p>{{ item.excerpt }}</p><small>{{ item.author_name }} · {{ formatDate(item.created_at) }}{{ item.filename ? ' · 含附件' : '' }}</small><p v-if="item.review_note" class="review-note">审核意见：{{ item.review_note }}</p></button></div>
        <div v-if="pages > 1" class="pagination"><button :disabled="page <= 1" @click="load(page - 1)">上一页</button><span>{{ page }} / {{ pages }}</span><button :disabled="page >= pages" @click="load(page + 1)">下一页</button></div>
      </section>
      <aside v-if="!isAdmin" class="panel assistant">
        <span class="eyebrow">AI ASSISTANT · AGENT</span><h2>{{ library === 'student' ? '学生' : '教师' }}智能助手</h2><p class="muted">优先本地混合检索。它可以查课程、查看作业和进度；教师还可以生成作业草稿、预览提醒，确认后执行。</p>
        <div class="conversation" aria-live="polite"><p v-if="!messages.length" class="assistant-welcome">你好！可以问“我的课程”“查看批改进度”“图书馆在哪一层”，教师还可以说“生成 Python 程序设计作业”。</p><div v-for="(message, index) in messages" :key="index" :class="['bubble', message.role]"><small>{{ message.role === 'user' ? '我' : message.mode === 'deepseek' ? 'DeepSeek 深入解答' : message.mode === 'agent' ? '权限智能体' : '本地知识库查询' }}</small><p>{{ message.content }}</p><button v-for="source in message.sources" :key="source.id" class="source" @click="openEntry(source.id)">[{{ source.id }}] {{ source.title }}</button><button v-if="message.can_deepen" class="source" :disabled="asking" @click="deepen(message)">AI 深入解答（调用 DeepSeek）</button><button v-if="message.action?.requires_confirmation" class="source confirm-action" :disabled="asking" @click="confirmAction(message)">{{ message.action.label }}</button></div><p v-if="asking">正在处理…</p></div>
        <form @submit.prevent="ask"><label>向知识库提问<textarea v-model="question" rows="3" maxlength="2000" required placeholder="请输入具体问题"></textarea></label><button class="primary" :disabled="asking || !question.trim()">{{ asking ? '查阅中…' : '查询知识库' }}</button></form>
      </aside>
    </div>
    <div v-if="selected" class="detail-overlay" @click.self="selected = null"><section class="detail panel" role="dialog" aria-modal="true" aria-label="知识详情"><button class="close" @click="selected = null">关闭 ×</button><span class="eyebrow">{{ selected.category }} · {{ statusLabel[selected.status] }}</span><h2>{{ selected.title }}</h2><p class="muted">{{ selected.author_name }} · {{ formatDate(selected.created_at) }}</p><p v-if="selected.privacy_flags?.length" class="privacy-warning">隐私提示：检测到{{ selected.privacy_flags.join('、') }}，请管理员核实是否适合向本知识库公开。调用外部 AI 时系统会自动脱敏。</p><div class="body-text">{{ selected.content }}</div><a v-if="selected.source_url" :href="selected.source_url" target="_blank" rel="noopener noreferrer">打开来源 / 课程链接 ↗</a><button v-if="selected.filename" :disabled="downloading" @click="download">{{ downloading ? '下载中…' : '下载附件：' + selected.filename }}</button><p v-if="selected.review_note">审核意见：{{ selected.review_note }}</p>
        <form v-if="isAdmin && selected.status === 'pending'" class="review-form" @submit.prevent="review('approved')"><label>审核意见（驳回时必填）<textarea v-model="reviewNote" maxlength="1000" rows="3"></textarea></label><button class="primary" :disabled="reviewing">通过审核</button><button type="button" :disabled="reviewing" @click="review('rejected')">驳回</button></form>
        <p v-if="detailError" class="error" role="alert">{{ detailError }}</p>
      </section></div>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/store/auth'
import { knowledgeAPI } from '@/api/knowledge'

const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')
const library = ref(isAdmin.value ? 'student' : auth.user?.role)
const libraries = ref([])
const libraryName = computed(() => libraries.value.find(x => x.id === library.value)?.name || '校园知识库')
const categories = computed(() => libraries.value.find(x => x.id === library.value)?.categories || [])
const items = ref([]), total = ref(0), pages = ref(0), page = ref(1)
const keyword = ref(''), category = ref(''), status = ref(isAdmin.value ? 'pending' : ''), mine = ref(false)
const error = ref(''), notice = ref(''), loading = ref(false), showForm = ref(false), submitting = ref(false)
const form = ref({ title: '', category: '', content: '', source_url: '' }), file = ref(null), fileKey = ref(0)
const selected = ref(null), detailError = ref(''), reviewNote = ref(''), reviewing = ref(false), downloading = ref(false)
const question = ref(''), messages = ref([]), asking = ref(false)
const statusLabel = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
const formatDate = value => value?.slice(0, 10)
const errorText = e => e.response?.data?.error || e.message || '操作失败，请重试'
let loadId = 0
async function load(nextPage = 1) {
  const id = ++loadId
  loading.value = true; error.value = ''
  try {
    const { data } = await knowledgeAPI.list({ library: library.value, mine: mine.value, status: status.value, category: category.value, q: keyword.value, page: nextPage })
    if (id !== loadId) return
    if (nextPage > 1 && !data.items.length) { await load(Math.max(1, data.pages)); return }
    items.value = data.items; total.value = data.total; pages.value = data.pages; page.value = nextPage
  } catch (e) { if (id === loadId) error.value = errorText(e) }
  finally { if (id === loadId) loading.value = false }
}
function switchLibrary(value) { library.value = value; category.value = ''; form.value.category = ''; selected.value = null; load(1) }
function setMine(value) { mine.value = value; status.value = isAdmin.value && !value ? 'pending' : ''; load(1) }
async function submit() {
  if (submitting.value) return
  error.value = ''; notice.value = ''
  if (file.value?.size > 5 * 1024 * 1024) { error.value = '附件不能超过 5MB'; return }
  submitting.value = true
  try {
    const data = new FormData()
    Object.entries(form.value).forEach(([key, value]) => data.append(key, value))
    data.append('library', library.value)
    if (file.value) data.append('file', file.value)
    await knowledgeAPI.submit(data)
    notice.value = '提交成功，等待管理员审核。'; showForm.value = false
    form.value = { title: '', category: '', content: '', source_url: '' }; file.value = null; fileKey.value++
    mine.value = true; status.value = ''; keyword.value = ''; category.value = ''; await load(1)
  } catch (e) { error.value = errorText(e) } finally { submitting.value = false }
}
async function openEntry(id) {
  try { selected.value = (await knowledgeAPI.detail(id)).data; reviewNote.value = ''; detailError.value = '' }
  catch (e) { error.value = errorText(e) }
}
async function review(value) {
  if (reviewing.value) return
  if (value === 'rejected' && !reviewNote.value.trim()) { detailError.value = '请填写驳回原因'; return }
  reviewing.value = true; detailError.value = ''
  try {
    const { data } = await knowledgeAPI.review(selected.value.id, { status: value, review_note: reviewNote.value })
    selected.value = null
    notice.value = value === 'approved' && data.semantic_indexed ? '审核通过，语义索引已自动更新。' : '审核完成。'
    await load(page.value)
  }
  catch (e) { detailError.value = errorText(e) } finally { reviewing.value = false }
}
async function download() {
  downloading.value = true
  try {
    const entry = selected.value
    const { data } = await knowledgeAPI.download(entry.id)
    const url = URL.createObjectURL(data), anchor = document.createElement('a')
    anchor.href = url; anchor.download = entry.filename; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) { detailError.value = errorText(e) } finally { downloading.value = false }
}
async function deepen(previous) {
  if (asking.value) return
  await queryKnowledge(previous.question, 'deepseek')
}
async function confirmAction(message) {
  if (asking.value || !message.action) return
  const action = message.action
  message.action = null
  asking.value = true
  try {
    const { data } = await knowledgeAPI.agent({ message: '确认执行', action: action.type, payload: action.payload, confirm: true })
    messages.value.push({ role: 'assistant', content: data.reply, sources: data.sources, mode: data.mode, action: data.action })
  } catch (e) { messages.value.push({ role: 'assistant', content: '执行失败：' + errorText(e), mode: 'agent' }) }
  finally { asking.value = false }
}
async function queryKnowledge(message, mode) {
  asking.value = true
  try {
    const { data } = await knowledgeAPI.ask({ message, library: library.value, mode })
    messages.value.push({ role: 'assistant', content: data.reply, sources: data.sources, mode: data.mode, can_deepen: data.can_deepen, question: message })
  } catch (e) { messages.value.push({ role: 'assistant', content: '查询失败：' + errorText(e) }) }
  finally { asking.value = false }
}
async function ask() {
  if (asking.value || !question.value.trim()) return
  const message = question.value.trim(); question.value = ''; asking.value = true
  messages.value.push({ role: 'user', content: message })
  await queryAgent(message)
}
async function queryAgent(message) {
  asking.value = true
  try {
    const { data } = await knowledgeAPI.agent({ message })
    messages.value.push({ role: 'assistant', content: data.reply, sources: data.sources, mode: data.mode, can_deepen: data.can_deepen, action: data.action, question: message })
  } catch (e) { messages.value.push({ role: 'assistant', content: '查询失败：' + errorText(e), mode: 'agent' }) }
  finally { asking.value = false }
}
onMounted(async () => {
  try { libraries.value = (await knowledgeAPI.libraries()).data; await load() }
  catch (e) { error.value = errorText(e) }
})
</script>

<style scoped>
.knowledge-page{max-width:1240px;margin:auto;padding:28px 20px 48px;color:#26334b}.hero{display:flex;justify-content:space-between;align-items:center;gap:20px;background:linear-gradient(120deg,#edf0ff,#f3f7fc);border:1px solid #e0e5f4;border-radius:20px;padding:30px;margin-bottom:24px}.eyebrow{font-size:11px;font-weight:700;letter-spacing:1.4px;color:#6776a4}h1{font-size:28px;margin:12px 0}h2{font-size:18px;margin:12px 0}p{line-height:1.7}.hero p,.muted,small{color:#738097}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:24px}.admin-workspace{grid-template-columns:1fr}button,input,select,textarea{font:inherit}button{cursor:pointer;border:1px solid #dce2ee;background:white;padding:10px 16px;border-radius:9px;color:#445273}button:hover{border-color:#7180d6}button:disabled{opacity:.5;cursor:wait}.primary{background:#6575ce;color:white;border-color:#6575ce}.tabs{display:flex;gap:8px;margin-bottom:18px}.tabs .selected{background:#e9edff;border-color:#a4b0ed;color:#4758b5}.filters{display:flex;flex-wrap:wrap;gap:8px}.filters input{flex:1;min-width:160px}input,textarea,select{padding:11px;border:1px solid #dae0ec;border-radius:8px;background:white;color:#26334b;box-sizing:border-box}textarea{resize:vertical}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.card{text-align:left;padding:20px;min-width:0;overflow-wrap:anywhere;box-shadow:0 4px 16px #26334b04}.card p{font-size:13px;color:#778197}.card-top{display:flex;justify-content:space-between;gap:8px;font-size:11px;color:#6675bd}.approved{color:#21836b}.rejected{color:#b75353}.pending{color:#af7b24}.panel{background:white;border:1px solid #e0e5ee;border-radius:15px;padding:24px}.assistant{align-self:start}.assistant h2{margin-top:10px}.assistant .muted{font-size:13px}.conversation{max-height:440px;overflow:auto;margin:20px 0}.assistant-welcome,.bubble{background:#f3f5fa;padding:14px;border-radius:10px;font-size:13px}.bubble{margin-bottom:12px;overflow-wrap:anywhere}.bubble p{white-space:pre-wrap}.bubble.user{background:#ecefff}.source{display:block;text-align:left;width:100%;font-size:12px;margin-top:7px}.assistant form button{width:100%}label{display:flex;flex-direction:column;gap:8px;margin-bottom:16px;font-size:14px}.upload-form{margin-bottom:24px}.upload-form small{display:block;margin-bottom:18px}.empty{text-align:center;background:#fafbfe;border:1px dashed #d9dfec;border-radius:14px;padding:48px 20px;color:#7b879c}.empty>span{font-size:40px}.empty p{font-size:13px}.pagination{display:flex;justify-content:center;align-items:center;gap:20px;margin-top:20px}.notice{padding:12px 16px;background:#ebf7ef;border-radius:9px}.error{color:#b33f48;background:#fff0f0;padding:12px;border-radius:8px}.privacy-warning{padding:12px 14px;background:#fff7e6;border:1px solid #efd395;border-radius:9px;color:#825a18}.detail-overlay{position:fixed;inset:0;z-index:2000;background:#18254080;display:flex;align-items:center;justify-content:center;padding:20px}.detail{width:720px;max-height:85vh;overflow:auto}.close{float:right}.body-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9;margin:24px 0}.detail>a,.detail>button:not(.close){display:block;margin:16px 0}.review-form{border-top:1px solid #e5e8ef;margin-top:24px;padding-top:20px}.review-form button{margin-right:12px}@media(max-width:900px){.workspace{grid-template-columns:1fr}.hero{padding:22px;flex-wrap:wrap}.knowledge-page{padding:16px 12px 40px}}@media(max-width:520px){.cards{grid-template-columns:1fr}.filters>*{max-width:100%}h1{font-size:24px}}
</style>
