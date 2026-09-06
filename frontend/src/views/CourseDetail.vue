<template>
  <div class="course-detail">
    <div class="course-header">
      <button @click="goBack" class="back-btn">← 返回</button>
      <div class="course-info">
        <div class="course-icon">{{ course.icon }}</div>
        <div class="course-details">
          <h2>{{ course.name }}</h2>
          <p>老师：{{ course.teacher_name }}</p>
        </div>
      </div>
    </div>

    <div class="tabs">
      <button 
        :class="['tab', { active: activeTab === 'assignments' }]"
        @click="activeTab = 'assignments'"
      >
        📝 作业
      </button>
      <button 
        :class="['tab', { active: activeTab === 'resources' }]"
        @click="activeTab = 'resources'"
      >
        📁 资源
      </button>
      <button 
        :class="['tab', { active: activeTab === 'notes' }]"
        @click="activeTab = 'notes'"
      >
        📝 笔记
      </button>
    </div>

    <div class="content">
      <div v-if="activeTab === 'assignments'" class="assignments-section">
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="assignments.length === 0" class="empty">暂无作业</div>
        <div v-else class="assignment-list">
          <div 
            v-for="assignment in assignments" 
            :key="assignment.id" 
            class="assignment-item"
          >
            <div class="assignment-info">
              <h4>{{ assignment.title }}</h4>
              <p class="description">{{ assignment.description || '无描述' }}</p>
              <p class="due-date">截止：{{ formatDate(assignment.due_date) }}</p>
              <p class="question-count">题目数：{{ assignment.question_count || 0 }} 题</p>
              <div v-if="getSubmissionStatus(assignment.id) === 'graded'" class="graded-info-student">
                <div class="score-display">
                  <span class="score-label">得分：</span>
                  <span class="score-value">{{ getSubmissionScore(assignment.id) }}</span>
                  <span class="score-total">/ {{ assignment.total_score || 100 }}</span>
                </div>
                <div v-if="getSubmissionOverallComment(assignment.id)" class="overall-comment-student">
                  <div class="comment-header-student">
                    <span class="comment-icon">💬</span>
                    <span class="comment-title">老师总评</span>
                  </div>
                  <p class="comment-text">{{ getSubmissionOverallComment(assignment.id) }}</p>
                </div>
              </div>
            </div>
            <button 
              @click="openSubmitModal(assignment)" 
              class="btn"
              :class="getSubmitButtonClass(assignment)"
              :disabled="isOverdue(assignment)"
            >
              {{ getSubmitButtonText(assignment) }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'resources'" class="resources-section">
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="resources.length === 0" class="empty">暂无资源</div>
        <div v-else class="resource-list">
          <div 
            v-for="resource in resources" 
            :key="resource.id" 
            class="resource-item"
          >
            <div class="resource-icon">{{ getResourceIcon(resource.file_type, resource.url) }}</div>
            <div class="resource-info">
              <h4>{{ resource.title }}</h4>
              <p class="resource-desc">{{ resource.description || '无描述' }}</p>
              <div class="resource-meta">
                <span v-if="resource.file_type" class="resource-type">{{ getResourceTypeName(resource.file_type) }}</span>
                <span v-if="resource.file_size" class="resource-size">{{ formatFileSize(resource.file_size) }}</span>
                <span class="resource-date">{{ formatDate(resource.created_at) }}</span>
              </div>
            </div>
            <a 
              v-if="resource.url" 
              :href="resource.url" 
              target="_blank" 
              class="download-btn"
            >
              {{ isPreviewable(resource) ? '👁️ 预览' : '📥 下载' }}
            </a>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'notes'" class="notes-section">
        <div class="notes-header">
          <h3>我的笔记</h3>
          <button @click="openNoteModal" class="btn btn-primary">
            + 新建笔记
          </button>
        </div>
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="notes.length === 0" class="empty">暂无笔记</div>
        <div v-else class="notes-list">
          <div 
            v-for="note in notes" 
            :key="note.id" 
            class="note-item"
          >
            <div class="note-header">
              <h4>{{ note.title }}</h4>
              <div class="note-actions">
                <button @click="editNote(note)" class="action-btn">编辑</button>
                <button @click="deleteNote(note.id)" class="action-btn delete">删除</button>
              </div>
            </div>
            <p class="note-content">{{ note.content }}</p>
            <p class="note-date">{{ formatDate(note.updated_at) }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showSubmitModal" class="modal-overlay" @click="closeSubmitModal">
      <div class="modal submit-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ isResubmit ? '重新提交作业' : '提交作业' }}</h3>
          <button @click="closeSubmitModal" class="close-btn">×</button>
        </div>
        
        <div class="modal-body">
          <p class="assignment-title">{{ selectedAssignment?.title }}</p>
          <p v-if="isResubmit" class="resubmit-hint">💡 您已提交过此作业，可以修改后重新提交</p>
          
          <div v-if="assignmentQuestions.length > 0" class="questions-section">
            <div 
              v-for="(question, index) in assignmentQuestions" 
              :key="question.id" 
              class="question-answer-item"
            >
              <div class="question-header">
                <span class="question-number">第 {{ index + 1 }} 题</span>
                <span :class="['question-type-badge', question.question_type]">
                  {{ getQuestionTypeName(question.question_type) }}
                </span>
                <span class="question-score">({{ question.score }}分)</span>
              </div>
              
              <div class="question-content">
                <p>{{ question.content }}</p>
                <img v-if="question.image_url" :src="question.image_url" class="question-image" />
              </div>

              <div v-if="question.question_type === 'single_choice' && answerForm.answers[question.id]" class="choice-answer single-choice">
                <div class="options-list">
                  <label 
                    v-for="optionKey in ['A', 'B', 'C', 'D']" 
                    :key="optionKey"
                    :class="['option-label', { selected: answerForm.answers[question.id]?.answer_text === optionKey }]"
                  >
                    <input 
                      type="radio" 
                      :name="`question_${question.id}`"
                      :value="optionKey"
                      v-model="answerForm.answers[question.id].answer_text"
                    />
                    <span class="option-circle">{{ optionKey }}</span>
                    <span class="option-text">{{ question.options?.[optionKey] || '' }}</span>
                  </label>
                </div>
              </div>

              <div v-else-if="question.question_type === 'multiple_choice' && answerForm.answers[question.id]" class="choice-answer multiple-choice">
                <p class="multi-hint">⚠️ 本题为多选题，请选择所有正确答案</p>
                <div class="options-list">
                  <label 
                    v-for="optionKey in ['A', 'B', 'C', 'D']" 
                    :key="optionKey"
                    :class="['option-label', { selected: answerForm.answers[question.id]?.answer_texts?.includes(optionKey) }]"
                  >
                    <input 
                      type="checkbox" 
                      :value="optionKey"
                      v-model="answerForm.answers[question.id].answer_texts"
                    />
                    <span class="option-checkbox">{{ optionKey }}</span>
                    <span class="option-text">{{ question.options?.[optionKey] || '' }}</span>
                  </label>
                </div>
              </div>

              <div v-else-if="question.question_type === 'fill_blank' && answerForm.answers[question.id]" class="fill-blank-answer">
                <p class="fill-hint">📝 请在下方输入框中填写答案</p>
                <input 
                  type="text" 
                  v-model="answerForm.answers[question.id].answer_text"
                  placeholder="请输入答案..."
                  class="fill-input"
                />
              </div>

              <div v-else-if="question.question_type === 'true_false' && answerForm.answers[question.id]" class="true-false-answer">
                <p class="tf-hint">⚖️ 请判断以下说法是否正确</p>
                <div class="tf-options">
                  <label 
                    :class="['tf-option', 'tf-true', { selected: answerForm.answers[question.id]?.answer_text === 'true' }]"
                  >
                    <input 
                      type="radio" 
                      :name="`tf_${question.id}`"
                      value="true"
                      v-model="answerForm.answers[question.id].answer_text"
                    />
                    <span class="tf-icon">✓</span>
                    <span class="tf-text">正确</span>
                  </label>
                  <label 
                    :class="['tf-option', 'tf-false', { selected: answerForm.answers[question.id]?.answer_text === 'false' }]"
                  >
                    <input 
                      type="radio" 
                      :name="`tf_${question.id}`"
                      value="false"
                      v-model="answerForm.answers[question.id].answer_text"
                    />
                    <span class="tf-icon">✗</span>
                    <span class="tf-text">错误</span>
                  </label>
                </div>
              </div>

              <div v-else-if="answerForm.answers[question.id]" class="text-answer">
                <textarea 
                  v-model="answerForm.answers[question.id].answer_text"
                  rows="4"
                  placeholder="请在此处作答..."
                ></textarea>
                <div class="answer-image-upload">
                  <input 
                    type="file" 
                    :ref="el => answerFileInputRefs[question.id] = el"
                    @change="(e) => handleAnswerImageUpload(e, question.id)"
                    accept="image/*"
                    class="file-input"
                  />
                  <button @click="triggerAnswerImageUpload(question.id)" class="btn btn-upload">
                    📷 上传答案图片
                  </button>
                  <div v-if="answerForm.answers[question.id]?.answer_image_url" class="answer-image-preview">
                    <img :src="answerForm.answers[question.id].answer_image_url" alt="答案图片" />
                    <button @click="removeAnswerImage(question.id)" class="remove-image">×</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="legacy-submit">
            <div class="form-group">
              <label>作业内容</label>
              <textarea 
                v-model="submitForm.content" 
                rows="6" 
                placeholder="请输入作业内容（可选）" 
              ></textarea>
            </div>
            <div class="form-group">
              <label>上传文件</label>
              <input 
                type="file" 
                ref="fileInput"
                @change="handleFileChange"
                accept="image/*,.pdf,.doc,.docx"
              />
              <div v-if="filePreview" class="file-preview">
                <img v-if="isImage(filePreview)" :src="filePreview" alt="预览" />
                <p v-else>已选择文件: {{ submitForm.file?.name }}</p>
                <button type="button" @click="clearFile" class="clear-btn">清除</button>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <div class="progress-info">
            已答 <strong>{{ answeredCount }}</strong> / {{ assignmentQuestions.length }} 题
          </div>
          <div class="modal-actions">
            <button type="button" @click="closeSubmitModal" class="btn btn-secondary">取消</button>
            <button 
              type="button" 
              @click="handleSubmit" 
              class="btn btn-primary" 
              :disabled="submitting"
            >
              {{ submitting ? '提交中...' : (isResubmit ? '重新提交' : '提交') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showNoteModal" class="modal-overlay" @click="closeNoteModal">
      <div class="modal" @click.stop>
        <h3>{{ editingNote ? '编辑笔记' : '新建笔记' }}</h3>
        <form @submit.prevent="handleSaveNote">
          <div class="form-group">
            <label>标题</label>
            <input 
              v-model="noteForm.title" 
              type="text" 
              placeholder="请输入笔记标题" 
              required
            />
          </div>
          <div class="form-group">
            <label>内容</label>
            <textarea 
              v-model="noteForm.content" 
              rows="10" 
              placeholder="请输入笔记内容" 
              required
            ></textarea>
          </div>
          <div class="modal-actions">
            <button type="button" @click="closeNoteModal" class="btn btn-secondary">取消</button>
            <button type="submit" class="btn btn-primary" :disabled="saving">
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { assignmentAPI } from '@/api/assignments'

const route = useRoute()
const router = useRouter()

const courseId = computed(() => route.params.id)
const activeTab = ref('assignments')
const loading = ref(true)

const course = ref({})
const assignments = ref([])
const resources = ref([])
const notes = ref([])
const mySubmissions = ref([])

const showSubmitModal = ref(false)
const selectedAssignment = ref(null)
const submitting = ref(false)
const submitForm = ref({ content: '', file: null })
const filePreview = ref(null)
const existingSubmission = ref(null)
const assignmentQuestions = ref([])
const answerFileInputRefs = ref({})

const answerForm = ref({
  answers: {}
})

const showNoteModal = ref(false)
const editingNote = ref(null)
const saving = ref(false)
const noteForm = ref({ title: '', content: '' })

const goBack = () => {
  router.push('/student/home')
}

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleString('zh-CN')
}

const isSubmitted = (assignmentId) => {
  return mySubmissions.value.some(s => s.assignment_id === assignmentId)
}

const getSubmissionStatus = (assignmentId) => {
  const submission = mySubmissions.value.find(s => s.assignment_id === assignmentId)
  return submission?.status || null
}

const getSubmissionScore = (assignmentId) => {
  const submission = mySubmissions.value.find(s => s.assignment_id === assignmentId)
  return submission?.score || 0
}

const getSubmissionOverallComment = (assignmentId) => {
  const submission = mySubmissions.value.find(s => s.assignment_id === assignmentId)
  return submission?.overall_comment || ''
}

const isOverdue = (assignment) => {
  if (!assignment || !assignment.due_date) return false
  return new Date(assignment.due_date) < new Date()
}

const isResubmit = computed(() => {
  return existingSubmission.value !== null
})

const getQuestionTypeName = (type) => {
  const names = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'fill_blank': '填空题',
    'true_false': '判断题',
    'text': '大题',
    'choice': '选择题'
  }
  return names[type] || type
}

const answeredCount = computed(() => {
  const answers = answerForm.value.answers
  return Object.values(answers).filter(a => {
    if (a.answer_texts && a.answer_texts.length > 0) return true
    if (a.answer_text) return true
    if (a.answer_image_url) return true
    return false
  }).length
})

const getSubmitButtonClass = (assignment) => {
  if (isOverdue(assignment)) return 'btn-disabled'
  if (isSubmitted(assignment.id)) return 'btn-resubmit'
  return 'btn-primary'
}

const getSubmitButtonText = (assignment) => {
  if (isOverdue(assignment)) return '已截止'
  if (isSubmitted(assignment.id)) return '重新提交'
  return '提交作业'
}

const openSubmitModal = async (assignment) => {
  selectedAssignment.value = assignment
  const submission = mySubmissions.value.find(s => s.assignment_id === assignment.id)
  existingSubmission.value = submission || null
  
  try {
    const res = await assignmentAPI.getAssignment(assignment.id)
    assignmentQuestions.value = res.data.assignment.questions || []
    
    const newAnswers = {}
    for (const q of assignmentQuestions.value) {
      const existingAnswer = submission?.answers?.[q.id]
      if (q.question_type === 'multiple_choice') {
        let selectedOptions = []
        if (existingAnswer?.answer_text) {
          selectedOptions = existingAnswer.answer_text.split(',').filter(a => a)
        }
        newAnswers[q.id] = {
          question_id: q.id,
          answer_text: selectedOptions.join(','),
          answer_texts: [...selectedOptions],
          answer_image_url: existingAnswer?.answer_image_url || ''
        }
      } else if (q.question_type === 'single_choice') {
        newAnswers[q.id] = {
          question_id: q.id,
          answer_text: existingAnswer?.answer_text || '',
          answer_image_url: existingAnswer?.answer_image_url || ''
        }
      } else if (q.question_type === 'fill_blank') {
        newAnswers[q.id] = {
          question_id: q.id,
          answer_text: existingAnswer?.answer_text || '',
          answer_image_url: existingAnswer?.answer_image_url || ''
        }
      } else if (q.question_type === 'true_false') {
        newAnswers[q.id] = {
          question_id: q.id,
          answer_text: existingAnswer?.answer_text || '',
          answer_image_url: existingAnswer?.answer_image_url || ''
        }
      } else {
        newAnswers[q.id] = {
          question_id: q.id,
          answer_text: existingAnswer?.answer_text || '',
          answer_image_url: existingAnswer?.answer_image_url || ''
        }
      }
    }
    answerForm.value = { answers: newAnswers }
    console.log('初始化答案表单:', answerForm.value.answers)
  } catch (error) {
    console.error('加载题目失败:', error)
    assignmentQuestions.value = []
  }
  
  if (submission) {
    submitForm.value = { 
      content: submission.content || '', 
      file: null 
    }
  } else {
    submitForm.value = { content: '', file: null }
  }
  filePreview.value = null
  showSubmitModal.value = true
}

const closeSubmitModal = () => {
  showSubmitModal.value = false
  selectedAssignment.value = null
  submitForm.value = { content: '', file: null }
  filePreview.value = null
  existingSubmission.value = null
  assignmentQuestions.value = []
  answerForm.value = { answers: {} }
}

const triggerAnswerImageUpload = (questionId) => {
  const input = answerFileInputRefs.value[questionId]
  if (input) {
    input.click()
  }
}

const handleAnswerImageUpload = async (event, questionId) => {
  const file = event.target.files[0]
  if (!file) return
  
  try {
    const res = await assignmentAPI.uploadQuestionImage(file)
    answerForm.value.answers[questionId].answer_image_url = res.data.image_url
  } catch (error) {
    alert('上传图片失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const removeAnswerImage = (questionId) => {
  answerForm.value.answers[questionId].answer_image_url = ''
}

const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    submitForm.value.file = file
    if (file.type.startsWith('image/')) {
      const reader = new FileReader()
      reader.onload = (e) => {
        filePreview.value = e.target.result
      }
      reader.readAsDataURL(file)
    } else {
      filePreview.value = file.name
    }
  }
}

const isImage = (preview) => {
  return preview && preview.startsWith('data:image')
}

const clearFile = () => {
  submitForm.value.file = null
  filePreview.value = null
}

const handleSubmit = async () => {
  submitting.value = true
  try {
    const answersArray = Object.values(answerForm.value.answers).map(a => {
      let answerText = a.answer_text
      if (a.answer_texts && a.answer_texts.length > 0) {
        answerText = a.answer_texts.sort().join(',')
      }
      return {
        question_id: a.question_id,
        answer_text: answerText,
        answer_image_url: a.answer_image_url
      }
    })
    
    await assignmentAPI.submitAssignment(selectedAssignment.value.id, {
      content: submitForm.value.content,
      answers: answersArray
    })
    closeSubmitModal()
    await loadCourseData()
    alert('提交成功！')
  } catch (error) {
    alert('提交失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    submitting.value = false
  }
}

const openNoteModal = () => {
  editingNote.value = null
  noteForm.value = { title: '', content: '' }
  showNoteModal.value = true
}

const closeNoteModal = () => {
  showNoteModal.value = false
  editingNote.value = null
  noteForm.value = { title: '', content: '' }
}

const editNote = (note) => {
  editingNote.value = note
  noteForm.value = { title: note.title, content: note.content }
  showNoteModal.value = true
}

const handleSaveNote = async () => {
  saving.value = true
  try {
    if (editingNote.value) {
      await assignmentAPI.updateNote(editingNote.value.id, noteForm.value)
    } else {
      await assignmentAPI.saveNote(courseId.value, noteForm.value)
    }
    closeNoteModal()
    await loadNotes()
  } catch (error) {
    alert('保存失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    saving.value = false
  }
}

const deleteNote = async (noteId) => {
  if (!confirm('确定要删除这条笔记吗？')) return
  try {
    await assignmentAPI.deleteNote(noteId)
    await loadNotes()
  } catch (error) {
    alert('删除失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const loadCourseData = async () => {
  try {
    const [courseRes, assignmentsRes, resourcesRes, submissionsRes] = await Promise.all([
      assignmentAPI.getCourseDetail(courseId.value),
      assignmentAPI.getCourseAssignments(courseId.value),
      assignmentAPI.getCourseResources(courseId.value),
      assignmentAPI.getMySubmissions()
    ])
    
    course.value = {
      ...courseRes.data.course,
      icon: getCourseIcon(courseRes.data.course.name)
    }
    assignments.value = assignmentsRes.data.assignments
    resources.value = resourcesRes.data.resources
    mySubmissions.value = submissionsRes.data.submissions
    
    const questionPromises = assignments.value.map(async (assignment) => {
      try {
        const qRes = await assignmentAPI.getQuestions(assignment.id)
        assignment.question_count = qRes.data.questions?.length || 0
      } catch (e) {
        assignment.question_count = 0
      }
    })
    await Promise.all(questionPromises)
  } catch (error) {
    console.error('加载课程数据失败:', error)
  } finally {
    loading.value = false
  }
}

const loadNotes = async () => {
  try {
    const response = await assignmentAPI.getCourseNotes(courseId.value)
    notes.value = response.data.notes
  } catch (error) {
    console.error('加载笔记失败:', error)
  }
}

const getCourseIcon = (courseName) => {
  const icons = {
    '高等数学': '📐',
    '线性代数': '📊',
    '编译原理': '💻',
    '单片机原理': '🔧',
    '人工智能导论': '🤖',
    '数据库': '🗄️',
    '数据结构': '🌳',
    '计算机网络': '🌐',
    '操作系统': '⚙️',
    '软件工程': '📋'
  }
  return icons[courseName] || '📚'
}

const formatFileSize = (bytes) => {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

const getResourceIcon = (fileType, url) => {
  if (fileType === 'image') return '🖼️'
  if (fileType === 'document') return '📄'
  if (fileType === 'video') return '🎬'
  if (fileType === 'audio') return '🎵'
  if (fileType === 'link') return '🔗'
  return '📁'
}

const getResourceTypeName = (fileType) => {
  const names = {
    'image': '图片',
    'document': '文档',
    'video': '视频',
    'audio': '音频',
    'link': '链接',
    'other': '其他'
  }
  return names[fileType] || '文件'
}

const isPreviewable = (resource) => {
  if (resource.file_type === 'image') return true
  if (resource.file_type === 'video') return true
  if (resource.file_type === 'audio') return true
  if (resource.url && resource.url.endsWith('.pdf')) return true
  return false
}

onMounted(async () => {
  await loadCourseData()
  if (activeTab.value === 'notes') {
    await loadNotes()
  }
})

watch(activeTab, async (newTab) => {
  if (newTab === 'notes') {
    await loadNotes()
  }
})
</script>

<style scoped>
.course-detail {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 80px;
}

.course-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 20px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.back-btn {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.course-info {
  display: flex;
  align-items: center;
  gap: 15px;
  flex: 1;
}

.course-icon {
  font-size: 48px;
}

.course-details h2 {
  margin: 0 0 5px 0;
  font-size: 20px;
}

.course-details p {
  margin: 0;
  opacity: 0.9;
  font-size: 14px;
}

.tabs {
  background: white;
  padding: 0 20px;
  display: flex;
  gap: 10px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.tab {
  padding: 15px 20px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  border-bottom: 3px solid transparent;
  transition: all 0.3s;
}

.tab.active {
  color: #667eea;
  border-bottom-color: #667eea;
  font-weight: 600;
}

.content {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.loading,
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.assignment-list,
.resource-list,
.notes-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.assignment-item {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.assignment-info {
  flex: 1;
}

.assignment-info h4 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 16px;
}

.description {
  margin: 0 0 10px 0;
  color: #666;
  font-size: 14px;
  line-height: 1.5;
}

.due-date,
.question-count {
  margin: 0 0 5px 0;
  color: #999;
  font-size: 14px;
}

.graded-info-student {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px dashed #e0e0e0;
}

.score-display {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 10px;
}

.score-label {
  color: #666;
  font-size: 14px;
}

.score-value {
  color: #667eea;
  font-size: 24px;
  font-weight: bold;
}

.score-total {
  color: #999;
  font-size: 14px;
}

.overall-comment-student {
  background: linear-gradient(135deg, #fff9e6 0%, #fff5f0 100%);
  padding: 12px 15px;
  border-radius: 8px;
  border-left: 4px solid #ffc107;
  margin-top: 10px;
}

.comment-header-student {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.comment-icon {
  font-size: 16px;
}

.comment-title {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.comment-text {
  margin: 0;
  color: #333;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.resource-item {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  display: flex;
  align-items: center;
  gap: 15px;
}

.resource-icon {
  font-size: 32px;
}

.resource-info {
  flex: 1;
}

.resource-info h4 {
  margin: 0 0 5px 0;
  color: #333;
  font-size: 16px;
}

.resource-desc {
  margin: 0 0 5px 0;
  color: #666;
  font-size: 14px;
}

.resource-date {
  margin: 0;
  color: #999;
  font-size: 12px;
}

.resource-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 5px;
}

.resource-type {
  background: #e3f2fd;
  color: #1976d2;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.resource-size {
  color: #999;
  font-size: 12px;
}

.download-btn {
  padding: 8px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.3s;
}

.download-btn:hover {
  background: #5568d3;
}

.notes-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.notes-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

.note-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.note-header h4 {
  margin: 0;
  color: #333;
  font-size: 16px;
}

.note-actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  padding: 4px 12px;
  background: #f0f0f0;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.3s;
}

.action-btn:hover {
  background: #e0e0e0;
}

.action-btn.delete {
  background: #fee;
  color: #c33;
}

.action-btn.delete:hover {
  background: #fdd;
}

.note-content {
  margin: 0 0 10px 0;
  color: #666;
  font-size: 14px;
  line-height: 1.6;
}

.note-date {
  margin: 0;
  color: #999;
  font-size: 12px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #5568d3;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #5a6268;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-resubmit {
  background: #ff9800;
  color: white;
}

.btn-resubmit:hover:not(:disabled) {
  background: #f57c00;
}

.btn-disabled {
  background: #ccc;
  color: #666;
  cursor: not-allowed;
}

.btn-upload {
  background: #6c757d;
  color: white;
  padding: 6px 12px;
  font-size: 13px;
}

.resubmit-hint {
  background: #fff3cd;
  color: #856404;
  padding: 10px 15px;
  border-radius: 6px;
  margin-bottom: 15px;
  font-size: 14px;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal {
  background: white;
  padding: 30px;
  border-radius: 10px;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
}

.submit-modal {
  max-width: 800px;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 30px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.modal-header .close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.modal-body {
  padding: 20px 30px;
  max-height: 60vh;
  overflow-y: auto;
}

.modal-footer {
  padding: 20px 30px;
  border-top: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal h3 {
  margin: 0 0 20px 0;
  color: #333;
}

.assignment-title {
  color: #666;
  margin-bottom: 20px;
  font-size: 16px;
}

.questions-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.question-answer-item {
  background: #f9f9f9;
  padding: 20px;
  border-radius: 10px;
  border-left: 4px solid #667eea;
}

.question-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.question-number {
  font-weight: 600;
  color: #667eea;
  font-size: 15px;
}

.question-type-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.question-type-badge.single_choice {
  background: #e3f2fd;
  color: #1976d2;
}

.question-type-badge.multiple_choice {
  background: #fff3e0;
  color: #f57c00;
}

.question-type-badge.fill_blank {
  background: #e0f7fa;
  color: #00838f;
}

.question-type-badge.true_false {
  background: #e8f5e9;
  color: #2e7d32;
}

.question-type-badge.text {
  background: #f3e5f5;
  color: #7b1fa2;
}

.question-score {
  color: #999;
  font-size: 13px;
}

.question-content {
  margin-bottom: 15px;
}

.question-content p {
  margin: 0 0 10px 0;
  color: #333;
  line-height: 1.6;
}

.question-image {
  max-width: 100%;
  max-height: 200px;
  border-radius: 6px;
  margin-top: 10px;
}

.choice-answer {
  margin-top: 10px;
}

.multi-hint {
  background: #fff8e1;
  color: #f57c00;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 13px;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.option-label {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 15px;
  background: white;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.option-label:hover {
  border-color: #667eea;
  background: #f8f9ff;
}

.option-label.selected {
  border-color: #667eea;
  background: #e8f0fe;
}

.option-label input {
  display: none;
}

.option-circle {
  width: 28px;
  height: 28px;
  background: #667eea;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.option-checkbox {
  width: 28px;
  height: 28px;
  background: #fd7e14;
  color: white;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.option-text {
  flex: 1;
  color: #333;
  font-size: 14px;
}

.fill-blank-answer {
  margin-top: 15px;
}

.fill-hint {
  font-size: 14px;
  color: #17a2b8;
  margin-bottom: 10px;
}

.fill-input {
  width: 100%;
  padding: 12px 15px;
  border: 2px solid #17a2b8;
  border-radius: 8px;
  font-size: 16px;
  transition: all 0.3s;
}

.fill-input:focus {
  outline: none;
  border-color: #138496;
  box-shadow: 0 0 0 3px rgba(23, 162, 184, 0.2);
}

.true-false-answer {
  margin-top: 15px;
}

.tf-hint {
  font-size: 14px;
  color: #6c757d;
  margin-bottom: 15px;
}

.tf-options {
  display: flex;
  gap: 20px;
}

.tf-option {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 15px 25px;
  border: 2px solid #ddd;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s;
}

.tf-option input[type="radio"] {
  display: none;
}

.tf-option:hover {
  border-color: #999;
}

.tf-option.tf-true.selected {
  border-color: #28a745;
  background: #e8f5e9;
}

.tf-option.tf-false.selected {
  border-color: #dc3545;
  background: #ffebee;
}

.tf-icon {
  font-size: 24px;
  font-weight: bold;
}

.tf-option.tf-true .tf-icon {
  color: #28a745;
}

.tf-option.tf-false .tf-icon {
  color: #dc3545;
}

.tf-text {
  font-size: 16px;
  font-weight: 500;
}

.text-answer textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  min-height: 100px;
}

.text-answer textarea:focus {
  outline: none;
  border-color: #667eea;
}

.answer-image-upload {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.file-input {
  display: none;
}

.answer-image-preview {
  position: relative;
  display: inline-block;
}

.answer-image-preview img {
  max-width: 150px;
  max-height: 100px;
  border-radius: 6px;
  object-fit: cover;
}

.remove-image {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 20px;
  height: 20px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
}

.progress-info {
  font-size: 14px;
  color: #666;
}

.progress-info strong {
  color: #667eea;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  color: #555;
  font-weight: 500;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group textarea {
  font-family: inherit;
  resize: vertical;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #667eea;
}

.form-group input[type="file"] {
  padding: 8px;
  background: white;
}

.file-preview {
  margin-top: 10px;
  padding: 10px;
  background: #f9f9f9;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-preview img {
  max-width: 200px;
  max-height: 200px;
  border-radius: 4px;
  object-fit: contain;
}

.file-preview p {
  flex: 1;
  margin: 0;
  color: #666;
  font-size: 14px;
}

.clear-btn {
  padding: 4px 12px;
  background: #ff4d4f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.3s;
}

.clear-btn:hover {
  background: #ff7875;
}

.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.legacy-submit {
  margin-top: 20px;
}

@media (max-width: 768px) {
  .tabs {
    padding: 0 10px;
  }
  
  .tab {
    padding: 12px 15px;
    font-size: 13px;
  }
  
  .assignment-item {
    flex-direction: column;
    gap: 15px;
  }
  
  .question-header {
    flex-wrap: wrap;
  }
}
</style>
