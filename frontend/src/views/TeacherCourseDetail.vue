<template>
  <div class="teacher-course-detail">
    <div class="course-header">
      <button @click="goBack" class="back-btn">← 返回</button>
      <div class="course-info">
        <div class="course-icon">{{ courseIcon }}</div>
        <div class="course-details">
          <h2>{{ course.name }}</h2>
          <p>课程码：{{ course.code }}</p>
          <p v-if="course.code_expiry">有效期至：{{ formatDate(course.code_expiry) }}</p>
        </div>
      </div>
    </div>

    <div class="tabs">
      <button 
        :class="['tab', { active: activeTab === 'assignments' }]"
        @click="activeTab = 'assignments'"
      >
        📝 发布作业
      </button>
      <button 
        :class="['tab', { active: activeTab === 'grading' }]"
        @click="activeTab = 'grading'"
      >
        ✅ 批改作业
      </button>
      <button 
        :class="['tab', { active: activeTab === 'resources' }]"
        @click="activeTab = 'resources'"
      >
        📁 发布资源
      </button>
      <button 
        :class="['tab', { active: activeTab === 'students' }]"
        @click="activeTab = 'students'"
      >
        👥 学生列表
      </button>
    </div>

    <div class="content">
      <div v-if="activeTab === 'assignments'" class="assignments-section">
        <div class="section-header">
          <h3>作业列表</h3>
          <button @click="openCreateAssignmentModal" class="btn btn-primary">
            + 发布作业
          </button>
        </div>
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="assignments.length === 0" class="empty">暂无作业，点击上方按钮发布作业</div>
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
              <p class="submission-count">已提交：{{ getSubmissionCount(assignment.id) }} 人</p>
            </div>
            <div class="assignment-actions">
              <button @click="editAssignment(assignment)" class="btn btn-edit">编辑题目</button>
              <button @click="viewSubmissions(assignment)" class="btn btn-secondary">
                查看提交
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'grading'" class="grading-section">
        <div class="section-header">
          <h3>待批改作业</h3>
          <div class="header-actions">
            <button 
              v-if="selectedAssignmentId" 
              @click="goToStatistics" 
              class="btn btn-statistics"
            >
              📊 查看统计
            </button>
            <button 
              v-if="selectedAssignmentId" 
              @click="showReminderModal = true" 
              class="btn btn-reminder"
            >
              🔔 发送作业提醒
            </button>
            <select v-model="selectedAssignmentId" class="assignment-select">
              <option value="">选择作业</option>
              <option v-for="assignment in assignments" :key="assignment.id" :value="assignment.id">
                {{ assignment.title }}
              </option>
            </select>
          </div>
        </div>
        
        <div v-if="!selectedAssignmentId" class="empty-state">
          <div class="empty-icon">📋</div>
          <p class="empty-title">请选择一个作业进行批改</p>
          <p class="empty-hint">从上方下拉菜单中选择要批改的作业</p>
          <div v-if="pendingSubmissionsCount > 0" class="pending-reminder">
            <span class="reminder-badge">🔔</span>
            <span>当前课程有 <strong>{{ pendingSubmissionsCount }}</strong> 份作业待批改</span>
          </div>
        </div>
        
        <div v-else-if="pendingSubmissionsForAssignment > 0" class="grading-reminder">
          <div class="reminder-icon">📝</div>
          <div class="reminder-info">
            <span class="reminder-text">当前作业有 <strong>{{ pendingSubmissionsForAssignment }}</strong> 份待批改</span>
            <span class="reminder-hint">请逐一批改学生提交的作业</span>
          </div>
        </div>
        
        <div v-if="selectedAssignmentId && submissions.length > 0" class="grading-filter-section">
          <div class="filter-tabs">
            <button 
              :class="['filter-tab', { active: gradingFilter === 'pending' }]"
              @click="gradingFilter = 'pending'"
            >
              <span class="tab-icon">📝</span>
              <span class="tab-text">待批改</span>
              <span class="tab-count">{{ pendingSubmissionsForAssignment }}</span>
            </button>
            <button 
              :class="['filter-tab', { active: gradingFilter === 'graded' }]"
              @click="gradingFilter = 'graded'"
            >
              <span class="tab-icon">✅</span>
              <span class="tab-text">已批改</span>
              <span class="tab-count">{{ gradedSubmissionsForAssignment }}</span>
            </button>
          </div>
        </div>
        
        <div v-if="selectedAssignmentId && submissions.length === 0 && !loadingSubmissions" class="empty">暂无学生提交</div>
        <div v-else-if="selectedAssignmentId && loadingSubmissions" class="loading">加载中...</div>
        <div v-else-if="selectedAssignmentId && filteredSubmissions.length === 0 && submissions.length > 0" class="empty">
          {{ gradingFilter === 'pending' ? '暂无待批改作业' : '暂无已批改作业' }}
        </div>
        <div v-else-if="selectedAssignmentId && paginatedSubmissions.length > 0" class="submission-list">
          <div 
            v-for="submission in paginatedSubmissions" 
            :key="submission.id" 
            :id="`submission-${submission.id}`"
            class="submission-item"
          >
            <div class="submission-header">
              <div class="student-info">
                <span class="student-name">{{ submission.student_name || `学生${submission.student_id}` }}</span>
                <span class="submit-time">{{ formatDate(submission.submitted_at) }}</span>
              </div>
              <span :class="['status-badge', submission.status]">
                {{ submission.status === 'graded' ? '已批改' : '待批改' }}
              </span>
            </div>
            
            <div v-if="assignmentQuestions.length > 0" class="questions-review-section">
              <h4 class="section-title">📝 题目与答案</h4>
              <div 
                v-for="(question, qIndex) in assignmentQuestions" 
                :key="question.id" 
                class="question-review-item"
              >
                <div class="question-review-header">
                  <span class="question-num">第 {{ qIndex + 1 }} 题</span>
                  <span :class="['question-type-badge', question.question_type]">
                    {{ getQuestionTypeName(question.question_type) }}
                  </span>
                  <span class="question-score-info">（{{ question.score }}分）</span>
                </div>
                
                <div class="question-review-content">
                  <p class="question-text">{{ question.content }}</p>
                  
                  <div v-if="question.question_type === 'single_choice' || question.question_type === 'multiple_choice'" class="options-review">
                    <div 
                      v-for="optionKey in ['A', 'B', 'C', 'D']" 
                      :key="optionKey"
                      :class="['option-review-item', {
                        'correct-option': question.correct_answer?.includes(optionKey),
                        'student-selected': submission.answers?.[question.id]?.answer_text?.includes(optionKey)
                      }]"
                    >
                      <span class="option-key">{{ optionKey }}</span>
                      <span class="option-value">{{ question.options?.[optionKey] || '' }}</span>
                      <span v-if="question.correct_answer?.includes(optionKey)" class="correct-mark">✓ 正确答案</span>
                      <span v-if="submission.answers?.[question.id]?.answer_text?.includes(optionKey)" class="student-mark">学生选择</span>
                    </div>
                  </div>
                  
                  <div v-else-if="question.question_type === 'fill_blank'" class="fill-blank-review">
                    <div class="correct-answer-box">
                      <span class="answer-label">正确答案：</span>
                      <span class="answer-value">{{ question.correct_answer?.split('|').join(' 或 ') || '未设置' }}</span>
                    </div>
                  </div>
                  
                  <div v-else-if="question.question_type === 'true_false'" class="true-false-review">
                    <div class="correct-answer-box">
                      <span class="answer-label">正确答案：</span>
                      <span class="answer-value" :class="question.correct_answer">
                        {{ question.correct_answer === 'true' ? '✓ 正确' : '✗ 错误' }}
                      </span>
                    </div>
                  </div>
                </div>
                
                <div class="student-answer-section">
                  <div class="answer-label">学生答案：</div>
                  <div v-if="submission.answers?.[question.id]" class="student-answer-content">
                    <span v-if="question.question_type === 'single_choice' || question.question_type === 'multiple_choice'" class="answer-text">
                      {{ submission.answers[question.id].answer_text || '未作答' }}
                    </span>
                    <span v-else-if="question.question_type === 'fill_blank'" class="answer-text fill-answer">
                      {{ submission.answers[question.id].answer_text || '未作答' }}
                    </span>
                    <span v-else-if="question.question_type === 'true_false'" class="answer-text tf-answer" :class="submission.answers[question.id].answer_text">
                      {{ submission.answers[question.id].answer_text === 'true' ? '✓ 正确' : (submission.answers[question.id].answer_text === 'false' ? '✗ 错误' : '未作答') }}
                    </span>
                    <p v-else class="answer-text">{{ submission.answers[question.id].answer_text || '未作答' }}</p>
                    <img v-if="submission.answers[question.id].answer_image_url" :src="submission.answers[question.id].answer_image_url" class="answer-image" />
                    <div v-if="submission.answers[question.id].score !== null" class="answer-score-info">
                      <span :class="['score-badge', submission.answers[question.id].is_correct ? 'correct' : 'wrong']">
                        {{ submission.answers[question.id].score }} 分
                      </span>
                      <span v-if="submission.answers[question.id].is_correct" class="correct-text">✓ 正确</span>
                      <span v-else-if="submission.answers[question.id].score > 0" class="partial-text">部分正确</span>
                      <p v-if="submission.answers[question.id].feedback" class="answer-feedback-text">
                        评语：{{ submission.answers[question.id].feedback }}
                      </p>
                    </div>
                    
                    <div v-if="submission.status !== 'graded' && question.question_type === 'text'" class="text-grade-section">
                      <div class="ai-grade-btn-section">
                        <button 
                          @click="aiGradeQuestion(submission, question)" 
                          class="btn btn-ai-grade"
                          :disabled="aiGradingKey === `${submission.id}_${question.id}`"
                        >
                          <span v-if="aiGradingKey === `${submission.id}_${question.id}`">🤖 AI评分中...</span>
                          <span v-else>🤖 AI智能评分</span>
                        </button>
                        <p class="ai-grade-hint">点击调用DeepSeek AI帮您批改这道大题</p>
                      </div>
                      <div class="text-grade-row">
                        <label class="text-grade-label">本题得分：</label>
                        <input 
                          type="number" 
                          v-model.number="getAnswerGradeForm(submission.id, question.id).score" 
                          :min="0" 
                          :max="question.score"
                          class="text-score-input"
                          placeholder="分数"
                        />
                        <span class="max-score-hint">/ {{ question.score }}分</span>
                      </div>
                      <div v-if="getAnswerGradeForm(submission.id, question.id).aiFeedback" class="ai-feedback-section">
                        <div class="ai-feedback-header">
                          <span class="ai-feedback-icon">🤖</span>
                          <span class="ai-feedback-title">AI评语</span>
                        </div>
                        <p class="ai-feedback-text">{{ getAnswerGradeForm(submission.id, question.id).aiFeedback }}</p>
                        <p v-if="getAnswerGradeForm(submission.id, question.id).aiAnalysis" class="ai-analysis-text">
                          <strong>答案分析：</strong>{{ getAnswerGradeForm(submission.id, question.id).aiAnalysis }}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div v-else class="no-answer">未作答</div>
                </div>
              </div>
            </div>
            
            <div v-else-if="submission.content" class="submission-content">
              <p>{{ submission.content }}</p>
              <div v-if="submission.file_url" class="file-preview">
                <div v-if="isImageFile(submission.file_url)" class="image-preview">
                  <img 
                    :src="submission.file_url" 
                    alt="作业图片" 
                    @click="openImagePreview(submission.file_url)"
                    class="preview-image"
                  />
                </div>
                <a v-else :href="submission.file_url" target="_blank" class="file-link">
                  📎 查看附件
                </a>
              </div>
            </div>
            
            <div v-if="submission.status === 'graded'" class="graded-info">
              <div class="graded-score-section">
                <p class="total-score-display">总分：<strong>{{ submission.score }}</strong> 分</p>
                <span class="graded-badge">✓ 已批改</span>
              </div>
              <div v-if="submission.overall_comment" class="overall-comment-display">
                <div class="comment-header">
                  <span class="comment-icon">💬</span>
                  <span class="comment-title">老师总评</span>
                  <span v-if="submission.comment_locked" class="locked-badge">🔒 已锁定</span>
                </div>
                <p class="comment-content">{{ submission.overall_comment }}</p>
              </div>
              <p v-else-if="submission.feedback" class="feedback-text">总评：{{ submission.feedback }}</p>
            </div>
            <div v-else class="grade-form">
              <div class="auto-grade-section">
                <button @click="autoGradeSubmission(submission)" class="btn btn-auto-grade" :disabled="gradingId === submission.id">
                  🤖 自动批改客观题
                </button>
                <p class="auto-grade-hint">系统将自动批改单选题、多选题、填空题和判断题，大题需手动评分或使用AI评分</p>
              </div>
              <div class="score-summary">
                <div class="score-summary-row">
                  <span class="score-label">客观题得分：</span>
                  <span class="score-value">{{ calculateAutoScore(submission) }} 分</span>
                </div>
                <div class="score-summary-row">
                  <span class="score-label">大题得分：</span>
                  <span class="score-value">{{ calculateTextScore(submission) }} 分</span>
                </div>
                <div class="score-summary-row total">
                  <span class="score-label">总分：</span>
                  <span class="score-value highlight">{{ calculateAutoScore(submission) + calculateTextScore(submission) }} 分</span>
                </div>
              </div>
              <div class="overall-comment-section">
                <div class="comment-section-header">
                  <label class="feedback-label">📝 老师总评</label>
                  <div class="comment-actions">
                    <button 
                      @click="generateOverallComment(submission)" 
                      class="btn btn-ai-comment"
                      :disabled="generatingCommentId === submission.id"
                      type="button"
                    >
                      <span v-if="generatingCommentId === submission.id">🤖 生成中...</span>
                      <span v-else>🤖 AI生成总评</span>
                    </button>
                    <button 
                      v-if="gradeForms[submission.id].overall_comment"
                      @click="toggleCommentLock(submission)" 
                      class="btn"
                      :class="gradeForms[submission.id].comment_locked ? 'btn-locked' : 'btn-lock'"
                      type="button"
                    >
                      <span v-if="gradeForms[submission.id].comment_locked">🔒 已锁定</span>
                      <span v-else>🔓 锁定评语</span>
                    </button>
                  </div>
                </div>
                <textarea 
                  v-model="gradeForms[submission.id].overall_comment" 
                  placeholder="请输入对该学生作业的总体评价和指导建议，或点击上方按钮使用AI生成..."
                  rows="4"
                  class="feedback-textarea"
                  :disabled="gradeForms[submission.id].comment_locked"
                  :class="{ 'textarea-locked': gradeForms[submission.id].comment_locked }"
                ></textarea>
                <p class="comment-hint">💡 提示：AI生成的总评仅供参考，您可以修改后再锁定。锁定后学生将看到最终评语。</p>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label>调整总分（可选）</label>
                  <input type="number" v-model.number="gradeForms[submission.id].score" min="0" :max="getTotalScore()" :placeholder="String(calculateAutoScore(submission) + calculateTextScore(submission))" />
                </div>
              </div>
              <div class="grade-actions">
                <button 
                  v-if="gradeForms[submission.id].comment_locked"
                  @click="unlockAndEdit(submission)" 
                  class="btn btn-secondary"
                  type="button"
                >
                  ✏️ 解锁编辑
                </button>
                <button @click="gradeSubmission(submission)" class="btn btn-primary" :disabled="gradingId === submission.id">
                  {{ gradingId === submission.id ? '批改中...' : '✓ 确认批改' }}
                </button>
                <button 
                  v-if="getNextSubmission(submission)" 
                  @click="goToNextSubmission(submission)" 
                  class="btn btn-next"
                  type="button"
                >
                  下一份作业 →
                </button>
              </div>
            </div>
          </div>
          
          <div v-if="totalGradingPages > 1" class="pagination-section">
            <div class="pagination-info">
              共 {{ gradingTotalCount }} 份作业，第 {{ gradingPage }} / {{ totalGradingPages }} 页
            </div>
            <div class="pagination-controls">
              <button 
                class="pagination-btn"
                :disabled="gradingPage === 1"
                @click="gradingPage = 1"
              >
                首页
              </button>
              <button 
                class="pagination-btn"
                :disabled="gradingPage === 1"
                @click="gradingPage--"
              >
                上一页
              </button>
              <span class="page-indicator">{{ gradingPage }} / {{ totalGradingPages }}</span>
              <button 
                class="pagination-btn"
                :disabled="gradingPage === totalGradingPages"
                @click="gradingPage++"
              >
                下一页
              </button>
              <button 
                class="pagination-btn"
                :disabled="gradingPage === totalGradingPages"
                @click="gradingPage = totalGradingPages"
              >
                末页
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'resources'" class="resources-section">
        <div class="section-header">
          <h3>课程资源</h3>
          <button @click="openCreateResourceModal" class="btn btn-primary">
            + 发布资源
          </button>
        </div>
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="resources.length === 0" class="empty">暂无资源，点击上方按钮发布资源</div>
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
            <div class="resource-actions">
              <a 
                v-if="resource.url" 
                :href="resource.url" 
                target="_blank" 
                class="btn btn-secondary"
              >
                {{ isPreviewable(resource) ? '预览' : '下载' }}
              </a>
              <button @click="deleteResource(resource.id)" class="btn btn-danger">
                删除
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'students'" class="students-section">
        <div class="section-header">
          <h3>班级学生列表</h3>
          <span class="student-count">共 {{ students.length }} 名学生</span>
        </div>
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="students.length === 0" class="empty">暂无学生加入此课程</div>
        <div v-else class="student-list">
          <div class="student-table">
            <div class="table-header">
              <div class="col">序号</div>
              <div class="col">姓名</div>
              <div class="col">班级</div>
              <div class="col">加入时间</div>
            </div>
            <div 
              v-for="(student, index) in students" 
              :key="student.id" 
              class="table-row"
            >
              <div class="col">{{ index + 1 }}</div>
              <div class="col">{{ student.name }}</div>
              <div class="col">{{ student.class_name || '未设置' }}</div>
              <div class="col">{{ formatDate(student.joined_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showCreateAssignmentModal" class="modal-overlay" @click="closeAssignmentModal">
      <div class="modal assignment-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ editingAssignment ? '编辑作业' : '发布作业' }}</h3>
          <button @click="closeAssignmentModal" class="close-btn">×</button>
        </div>
        
        <div class="modal-body">
          <div class="basic-info">
            <div class="form-group">
              <label>作业标题 <span class="required">*</span></label>
              <input 
                v-model="assignmentForm.title" 
                type="text" 
                placeholder="请输入作业标题" 
              />
            </div>
            <div class="form-group">
              <label>截止时间 <span class="required">*</span></label>
              <input 
                v-model="assignmentForm.due_date" 
                type="datetime-local" 
              />
            </div>
          </div>

          <div class="form-group assignment-description-field">
            <label>作业说明（可选）</label>
            <textarea
              v-model="assignmentForm.description"
              rows="2"
              placeholder="补充学习目标、提交要求或评分说明"
            ></textarea>
          </div>

          <div class="questions-section">
            <div class="questions-header">
              <h4>题目列表</h4>
              <div class="add-question-btns">
                <button @click="addQuestion('single_choice')" class="btn btn-add btn-single">
                  + 单选题
                </button>
                <button @click="addQuestion('multiple_choice')" class="btn btn-add btn-multiple">
                  + 多选题
                </button>
                <button @click="addQuestion('fill_blank')" class="btn btn-add btn-fill">
                  + 填空题
                </button>
                <button @click="addQuestion('true_false')" class="btn btn-add btn-true-false">
                  + 判断题
                </button>
                <button @click="addQuestion('text')" class="btn btn-add btn-text">
                  + 大题
                </button>
                <button @click="showImportModal = true" class="btn btn-add btn-import">
                  📥 导入题目
                </button>
              </div>
            </div>

            <div class="score-tips">
              <span class="tip-item">💡 单选题推荐2分</span>
              <span class="tip-item">💡 多选题推荐3分</span>
              <span class="tip-item">💡 填空题推荐5分</span>
              <span class="tip-item">💡 判断题推荐2分</span>
              <span class="tip-item">💡 大题推荐10分</span>
            </div>

            <div v-if="assignmentForm.questions.length === 0" class="empty-questions">
              <p>暂无题目，点击上方按钮添加题目或导入题目</p>
            </div>

            <div v-else class="questions-list">
              <div 
                v-for="(question, index) in assignmentForm.questions" 
                :key="index" 
                class="question-item"
              >
                <div class="question-header">
                  <span class="question-number">第 {{ index + 1 }} 题</span>
                  <span :class="['question-type-badge', question.question_type]">
                    {{ getQuestionTypeName(question.question_type) }}
                  </span>
                  <div class="question-actions">
                    <label class="score-label">
                      分值:
                      <input 
                        type="number" 
                        v-model.number="question.score" 
                        min="1" 
                        max="100"
                        class="score-input"
                      />
                      <span v-if="question.score !== getRecommendedScore(question.question_type)" class="score-hint">
                        (推荐{{ getRecommendedScore(question.question_type) }}分)
                      </span>
                    </label>
                    <button @click="removeQuestion(index)" class="btn btn-remove">×</button>
                  </div>
                </div>

                <div class="question-content">
                  <div class="form-group">
                    <label>题目内容</label>
                    <textarea 
                      v-model="question.content" 
                      rows="2" 
                      placeholder="请输入题目内容"
                    ></textarea>
                  </div>

                  <div v-if="question.question_type === 'single_choice' || question.question_type === 'multiple_choice'" class="choice-options">
                    <label>选项</label>
                    <div class="options-grid">
                      <div 
                        v-for="optionKey in ['A', 'B', 'C', 'D']" 
                        :key="optionKey" 
                        class="option-item"
                      >
                        <span class="option-label">{{ optionKey }}</span>
                        <input 
                          type="text" 
                          v-model="question.options[optionKey]" 
                          :placeholder="`选项${optionKey}`"
                        />
                      </div>
                    </div>
                    <div class="correct-answer">
                      <label>{{ question.question_type === 'single_choice' ? '正确答案（单选）' : '正确答案（多选）' }}</label>
                      <div v-if="question.question_type === 'single_choice'" class="single-select">
                        <label v-for="optionKey in ['A', 'B', 'C', 'D']" :key="optionKey" class="radio-label">
                          <input 
                            type="radio" 
                            :name="`correct_${index}`"
                            :value="optionKey"
                            v-model="question.correct_answer"
                          />
                          <span class="radio-custom"></span>
                          {{ optionKey }}
                        </label>
                      </div>
                      <div v-else class="multi-select">
                        <label v-for="optionKey in ['A', 'B', 'C', 'D']" :key="optionKey" class="checkbox-label">
                          <input 
                            type="checkbox" 
                            :value="optionKey"
                            v-model="question.correct_answers"
                          />
                          <span class="checkbox-custom"></span>
                          {{ optionKey }}
                        </label>
                        <p class="multi-hint">⚠️ 多选题评分规则：全对得满分，选对但不全得一半分，选错得0分</p>
                      </div>
                    </div>
                  </div>

                  <div v-else-if="question.question_type === 'fill_blank'" class="fill-blank-question">
                    <div class="form-group">
                      <label>正确答案</label>
                      <input 
                        type="text" 
                        v-model="question.fill_answer" 
                        placeholder="请输入正确答案（多个答案用 | 分隔，如：答案1|答案2）"
                      />
                      <p class="fill-hint">💡 提示：使用 | 分隔多个可能的正确答案，学生答案与任一答案匹配即得分</p>
                    </div>
                    <div class="form-group">
                      <label>题目图片（可选）</label>
                      <div class="image-upload">
                        <input 
                          type="file" 
                          :ref="el => fileInputRefs[index] = el"
                          @change="(e) => handleQuestionImageUpload(e, index)"
                          accept="image/*"
                          class="file-input"
                        />
                        <button @click="triggerImageUpload(index)" class="btn btn-upload">
                          📷 上传图片
                        </button>
                        <div v-if="question.image_url" class="image-preview-inline">
                          <img :src="question.image_url" alt="题目图片" />
                          <button @click="removeQuestionImage(index)" class="remove-image">×</button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-else-if="question.question_type === 'true_false'" class="true-false-question">
                    <div class="form-group">
                      <label>正确答案</label>
                      <div class="true-false-options">
                        <label class="radio-label true-option">
                          <input 
                            type="radio" 
                            :name="`true_false_${index}`"
                            value="true"
                            v-model="question.true_false_answer"
                          />
                          <span class="radio-custom"></span>
                          ✓ 正确
                        </label>
                        <label class="radio-label false-option">
                          <input 
                            type="radio" 
                            :name="`true_false_${index}`"
                            value="false"
                            v-model="question.true_false_answer"
                          />
                          <span class="radio-custom"></span>
                          ✗ 错误
                        </label>
                      </div>
                    </div>
                    <div class="form-group">
                      <label>题目图片（可选）</label>
                      <div class="image-upload">
                        <input 
                          type="file" 
                          :ref="el => fileInputRefs[index] = el"
                          @change="(e) => handleQuestionImageUpload(e, index)"
                          accept="image/*"
                          class="file-input"
                        />
                        <button @click="triggerImageUpload(index)" class="btn btn-upload">
                          📷 上传图片
                        </button>
                        <div v-if="question.image_url" class="image-preview-inline">
                          <img :src="question.image_url" alt="题目图片" />
                          <button @click="removeQuestionImage(index)" class="remove-image">×</button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div v-else class="text-question">
                    <div class="form-group">
                      <label>参考答案（可选）</label>
                      <textarea 
                        v-model="question.correct_answer" 
                        rows="3" 
                        placeholder="请输入参考答案或评分标准"
                      ></textarea>
                    </div>
                    <div class="form-group">
                      <label>题目图片（可选）</label>
                      <div class="image-upload">
                        <input 
                          type="file" 
                          :ref="el => fileInputRefs[index] = el"
                          @change="(e) => handleQuestionImageUpload(e, index)"
                          accept="image/*"
                          class="file-input"
                        />
                        <button @click="triggerImageUpload(index)" class="btn btn-upload">
                          📷 上传图片
                        </button>
                        <div v-if="question.image_url" class="image-preview-inline">
                          <img :src="question.image_url" alt="题目图片" />
                          <button @click="removeQuestionImage(index)" class="remove-image">×</button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <div class="total-score">
            总分：<strong>{{ calculateTotalScore() }}</strong> 分
          </div>
          <div class="modal-actions">
            <button type="button" @click="closeAssignmentModal" class="btn btn-secondary">取消</button>
            <button 
              type="button" 
              @click="handleCreateAssignment" 
              class="btn btn-primary" 
              :disabled="creating || !assignmentForm.title || !assignmentForm.due_date"
            >
              {{ creating ? '保存中...' : (editingAssignment ? '保存修改' : '发布作业') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showImportModal" class="modal-overlay" @click="showImportModal = false">
      <div class="modal import-modal" @click.stop>
        <div class="modal-header">
          <h3>📥 导入题目</h3>
          <button @click="showImportModal = false" class="close-btn">×</button>
        </div>
        
        <div class="modal-body">
          <div class="import-tabs">
            <button 
              :class="['import-tab', { active: importTab === 'excel' }]"
              @click="importTab = 'excel'"
            >
              📊 Excel导入
            </button>
            <button 
              :class="['import-tab', { active: importTab === 'text' }]"
              @click="importTab = 'text'"
            >
              📝 文本导入
            </button>
            <button 
              :class="['import-tab', { active: importTab === 'file' }]"
              @click="importTab = 'file'"
            >
              📄 文件导入
            </button>
          </div>

          <div v-if="importTab === 'excel'" class="import-content">
            <div class="import-steps">
              <div class="import-step">
                <div class="step-num">1</div>
                <div class="step-content">
                  <h4>下载模板</h4>
                  <p>下载Excel模板，按照模板格式填写题目</p>
                  <button @click="downloadTemplate" class="btn btn-download">
                    📥 下载题目导入模板
                  </button>
                </div>
              </div>
              
              <div class="import-step">
                <div class="step-num">2</div>
                <div class="step-content">
                  <h4>填写题目</h4>
                  <p>在Excel中填写题目信息，支持：单选题、多选题、填空题、判断题、大题</p>
                </div>
              </div>
              
              <div class="import-step">
                <div class="step-num">3</div>
                <div class="step-content">
                  <h4>上传文件</h4>
                  <p>选择填好的Excel文件并导入</p>
                  <div class="upload-area" @click="triggerImportFile" @dragover.prevent @drop.prevent="handleDropImport">
                    <input 
                      ref="importFileInput" 
                      type="file" 
                      accept=".xlsx,.xls" 
                      @change="handleImportFile"
                      hidden
                    />
                    <div v-if="!importFile" class="upload-placeholder">
                      <span class="upload-icon">📁</span>
                      <p>点击或拖拽文件到此处</p>
                      <p class="upload-hint">支持 .xlsx 和 .xls 格式</p>
                    </div>
                    <div v-else class="file-selected">
                      <span class="file-icon">📄</span>
                      <span class="file-name">{{ importFile.name }}</span>
                      <button @click.stop="clearImportFile" class="clear-btn">×</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="importTab === 'text'" class="import-content">
            <div class="ai-parse-section">
              <div class="ai-buttons">
                <button 
                  @click="handleAIParse" 
                  class="btn btn-ai-parse"
                  :disabled="aiParsing || !importText.trim()"
                >
                  <span v-if="aiParsing">🤖 AI智能解析中...（请耐心等待）</span>
                  <span v-else>🤖 AI智能解析</span>
                </button>
                <button 
                  @click="handleTestAI" 
                  class="btn btn-test-ai"
                  :disabled="testingAI"
                  type="button"
                >
                  <span v-if="testingAI">测试中...</span>
                  <span v-else>🔧 测试连接</span>
                </button>
              </div>
              <p class="ai-parse-hint">使用DeepSeek AI智能识别题目格式，自动提取题目、选项和答案</p>
              <p class="ai-parse-time-hint">⏱️ AI解析可能需要30-180秒，请保持网络连接稳定</p>
            </div>
            <div class="format-hint">
              <h4>文本格式说明</h4>
              <p>支持的格式示例：</p>
              <pre>一、单选题
1. Python中用于输出的函数是？
A. print()
B. input()
C. output()
D. display()

二、判断题
1. Python是一种解释型语言。
2. Python中列表是不可变的。

三、填空题
1. Python中用于定义函数的关键字是____。

四、大题
1. 请简述Python的特点。

参考答案
一、单选题
1. A
二、判断题
1. 正确
2. 错误
三、填空题
1. def</pre>
            </div>
            <div class="form-group">
              <label>题目文本</label>
              <textarea 
                v-model="importText" 
                class="form-control import-textarea"
                placeholder="请粘贴题目文本..."
                rows="10"
              ></textarea>
            </div>
          </div>

          <div v-if="importTab === 'file'" class="import-content">
            <div class="format-hint">
              <h4>文件导入说明</h4>
              <p>上传 .txt 文本文件，系统将自动识别题目格式</p>
              <p>支持 UTF-8 和 GBK 编码</p>
            </div>
            <div class="upload-area" @click="triggerTxtFileUpload" @dragover.prevent @drop.prevent="handleTxtFileDrop">
              <input 
                ref="txtFileInput" 
                type="file" 
                accept=".txt" 
                @change="handleTxtFileSelect"
                hidden
              />
              <div v-if="!importTxtFile" class="upload-placeholder">
                <span class="upload-icon">📄</span>
                <p>点击或拖拽文本文件到此处</p>
                <p class="upload-hint">支持 .txt 格式</p>
              </div>
              <div v-else class="file-selected">
                <span class="file-icon">📄</span>
                <span class="file-name">{{ importTxtFile.name }}</span>
                <button @click.stop="clearTxtFile" class="clear-btn">×</button>
              </div>
            </div>
          </div>
          
          <div v-if="importResult" class="import-result">
            <div class="result-header" :class="{ success: importResult.success_count > 0 }">
              <span class="result-icon">{{ importResult.success_count > 0 ? '✅' : '❌' }}</span>
              <span>{{ importResult.message }}</span>
            </div>
            <div class="result-stats">
              <div class="stat-item success">
                <span class="stat-num">{{ importResult.success_count }}</span>
                <span class="stat-label">成功</span>
              </div>
              <div v-if="importResult.error_count > 0" class="stat-item error">
                <span class="stat-num">{{ importResult.error_count }}</span>
                <span class="stat-label">失败</span>
              </div>
            </div>
            <div v-if="importResult.errors && importResult.errors.length > 0" class="error-list">
              <h5>错误详情：</h5>
              <ul>
                <li v-for="(err, idx) in importResult.errors" :key="idx">{{ err }}</li>
              </ul>
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <button 
            v-if="editingAssignment?.id"
            @click="handleClearQuestions" 
            class="btn btn-danger" 
            :disabled="clearingQuestions"
          >
            {{ clearingQuestions ? '清除中...' : '🗑️ 清除已导入题目' }}
          </button>
          <div style="flex: 1"></div>
          <button @click="showImportModal = false" class="btn btn-secondary">取消</button>
          <button 
            @click="handleImportQuestions" 
            class="btn btn-primary" 
            :disabled="importing || (importTab === 'excel' && !importFile) || (importTab === 'text' && !importText.trim()) || (importTab === 'file' && !importTxtFile)"
          >
            {{ importing ? '导入中...' : '开始导入' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showCreateResourceModal" class="modal-overlay" @click="showCreateResourceModal = false">
      <div class="modal resource-modal" @click.stop>
        <div class="modal-header">
          <h3>发布资源</h3>
          <button @click="showCreateResourceModal = false" class="close-btn">×</button>
        </div>
        
        <div class="modal-body">
          <div class="form-group">
            <label>资源标题 <span class="required">*</span></label>
            <input 
              v-model="resourceForm.title" 
              type="text" 
              placeholder="请输入资源标题" 
            />
          </div>
          <div class="form-group">
            <label>资源描述</label>
            <textarea 
              v-model="resourceForm.description" 
              rows="3" 
              placeholder="请输入资源描述"
            ></textarea>
          </div>
          
          <div class="upload-tabs">
            <button 
              :class="['tab-btn', { active: resourceUploadType === 'file' }]"
              @click="resourceUploadType = 'file'"
            >
              📎 上传文件
            </button>
            <button 
              :class="['tab-btn', { active: resourceUploadType === 'link' }]"
              @click="resourceUploadType = 'link'"
            >
              🔗 外部链接
            </button>
          </div>
          
          <div v-if="resourceUploadType === 'file'" class="file-upload-section">
            <div class="upload-area" @click="triggerResourceFileUpload" @dragover.prevent @drop.prevent="handleResourceFileDrop">
              <input 
                type="file" 
                ref="resourceFileInput"
                @change="handleResourceFileSelect"
                accept="image/*,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.mp4,.mp3,.wav,.txt"
                class="file-input"
              />
              <div v-if="!resourceForm.file" class="upload-placeholder">
                <span class="upload-icon">📁</span>
                <p>点击或拖拽文件到此处上传</p>
                <p class="upload-hint">支持：图片、PDF、Word、PPT、Excel、视频、音频等（最大100MB）</p>
                <p class="upload-warning">⚠️ 注意：请上传单个文件，不支持文件夹</p>
              </div>
              <div v-else class="file-preview">
                <div class="file-info">
                  <span class="file-icon">{{ getFileIcon(resourceForm.file.name) }}</span>
                  <div class="file-details">
                    <p class="file-name">{{ resourceForm.file.name }}</p>
                    <p class="file-size">{{ formatFileSize(resourceForm.file.size) }}</p>
                  </div>
                  <button @click.stop="clearResourceFile" class="clear-file-btn">×</button>
                </div>
              </div>
            </div>
            <div v-if="uploadProgress > 0 && uploadProgress < 100" class="upload-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
              </div>
              <span>{{ uploadProgress }}%</span>
            </div>
          </div>
          
          <div v-else class="link-input-section">
            <div class="form-group">
              <label>资源链接 <span class="required">*</span></label>
              <input 
                v-model="resourceForm.url" 
                type="url" 
                placeholder="请输入资源链接（如网盘链接等）" 
              />
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <div class="modal-actions">
            <button type="button" @click="showCreateResourceModal = false" class="btn btn-secondary">取消</button>
            <button 
              type="button" 
              @click="handleCreateResource" 
              class="btn btn-primary" 
              :disabled="creating || !resourceForm.title || (resourceUploadType === 'file' ? !resourceForm.file : !resourceForm.url)"
            >
              {{ creating ? '发布中...' : '发布资源' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showImagePreview" class="image-preview-modal" @click="showImagePreview = false">
      <div class="image-preview-content" @click.stop>
        <button class="close-btn" @click="showImagePreview = false">×</button>
        <img :src="previewImageUrl" alt="作业图片预览" />
      </div>
    </div>

    <div v-if="showReminderModal" class="modal-overlay" @click="showReminderModal = false">
      <div class="modal reminder-modal" @click.stop>
        <div class="modal-header">
          <h3>🔔 发送作业提醒</h3>
          <button @click="showReminderModal = false" class="close-btn">×</button>
        </div>
        
        <div class="modal-body">
          <div v-if="loadingUnsubmitted" class="loading">加载中...</div>
          <div v-else>
            <div class="reminder-stats">
              <div class="stat-item">
                <span class="stat-label">已加入课程</span>
                <span class="stat-value">{{ unsubmittedData.total_enrolled || 0 }} 人</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">已提交</span>
                <span class="stat-value submitted">{{ unsubmittedData.submitted_count || 0 }} 人</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">未提交</span>
                <span class="stat-value unsubmitted">{{ unsubmittedData.unsubmitted_count || 0 }} 人</span>
              </div>
            </div>
            
            <div v-if="unsubmittedData.unsubmitted_count > 0" class="unsubmitted-section">
              <h4>未提交学生列表</h4>
              <div class="student-list-container">
                <div 
                  v-for="student in unsubmittedData.unsubmitted_students" 
                  :key="student.id" 
                  class="student-item"
                >
                  <span class="student-name">{{ student.name }}</span>
                  <span class="student-info">{{ student.student_id || '-' }} | {{ student.class_name || '-' }}</span>
                </div>
              </div>
              
              <div class="custom-message-section">
                <label>自定义提醒内容（可选）</label>
                <textarea 
                  v-model="reminderMessage" 
                  placeholder="留空将使用默认提醒内容..."
                  rows="3"
                ></textarea>
              </div>
            </div>
            
            <div v-else class="all-submitted">
              <span class="check-icon">✅</span>
              <p>所有学生都已提交作业！</p>
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <button @click="showReminderModal = false" class="btn btn-secondary">取消</button>
          <button 
            v-if="unsubmittedData.unsubmitted_count > 0"
            @click="sendReminder" 
            class="btn btn-primary"
            :disabled="sendingReminder"
          >
            {{ sendingReminder ? '发送中...' : `发送提醒 (${unsubmittedData.unsubmitted_count}人)` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { assignmentAPI } from '@/api/assignments'

const route = useRoute()
const router = useRouter()

const courseId = computed(() => route.params.id)
const activeTab = ref('assignments')
const loading = ref(true)
const loadingSubmissions = ref(false)

const course = ref({})
const assignments = ref([])
const resources = ref([])
const students = ref([])
const submissions = ref([])
const submissionCounts = ref({})
const assignmentQuestions = ref([])

const showCreateAssignmentModal = ref(false)
const showCreateResourceModal = ref(false)
const showImportModal = ref(false)
const showImagePreview = ref(false)
const showReminderModal = ref(false)
const previewImageUrl = ref('')
const creating = ref(false)
const gradingId = ref(null)
const selectedAssignmentId = ref('')
const editingAssignment = ref(null)
const aiGradingKey = ref(null)

const loadingUnsubmitted = ref(false)
const sendingReminder = ref(false)
const unsubmittedData = ref({
  total_enrolled: 0,
  submitted_count: 0,
  unsubmitted_count: 0,
  unsubmitted_students: []
})
const reminderMessage = ref('')

const fileInputRefs = ref({})
const importFileInput = ref(null)
const importFile = ref(null)
const importing = ref(false)
const clearingQuestions = ref(false)
const importResult = ref(null)
const importTab = ref('excel')
const importText = ref('')
const importTxtFile = ref(null)
const txtFileInput = ref(null)
const aiParsing = ref(false)
const testingAI = ref(false)

const assignmentForm = ref({
  title: '',
  due_date: '',
  description: '',
  questions: []
})

const resourceForm = ref({
  title: '',
  description: '',
  url: '',
  file: null
})

const resourceUploadType = ref('file')
const resourceFileInput = ref(null)
const uploadProgress = ref(0)

const gradeForms = ref({})
const answerGradeForms = ref({})
const generatingCommentId = ref(null)

const gradingFilter = ref('pending')
const gradingPage = ref(1)
const gradingPageSize = 5

const courseIcon = computed(() => {
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
  return icons[course.value.name] || '📚'
})

const pendingSubmissionsCount = computed(() => {
  let count = 0
  for (const assignment of assignments.value) {
    count += (assignment.pending_count || 0)
  }
  return count
})

const pendingSubmissionsForAssignment = computed(() => {
  if (!selectedAssignmentId.value) return 0
  return submissions.value.filter(s => s.status === 'submitted').length
})

const gradedSubmissionsForAssignment = computed(() => {
  if (!selectedAssignmentId.value) return 0
  return submissions.value.filter(s => s.status === 'graded').length
})

const filteredSubmissions = computed(() => {
  let filtered = submissions.value
  if (gradingFilter.value === 'pending') {
    filtered = submissions.value.filter(s => s.status === 'submitted')
  } else if (gradingFilter.value === 'graded') {
    filtered = submissions.value.filter(s => s.status === 'graded')
  }
  return filtered
})

const paginatedSubmissions = computed(() => {
  const start = (gradingPage.value - 1) * gradingPageSize
  const end = start + gradingPageSize
  return filteredSubmissions.value.slice(start, end)
})

const totalGradingPages = computed(() => {
  return Math.ceil(filteredSubmissions.value.length / gradingPageSize)
})

const gradingTotalCount = computed(() => {
  return filteredSubmissions.value.length
})

watch(gradingFilter, () => {
  gradingPage.value = 1
})

watch(selectedAssignmentId, () => {
  gradingPage.value = 1
  gradingFilter.value = 'pending'
})

const goBack = () => {
  router.push('/teacher/home')
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const getSubmissionCount = (assignmentId) => {
  return submissionCounts.value[assignmentId] || 0
}

const getTotalScore = () => {
  const assignment = assignments.value.find(a => a.id === selectedAssignmentId.value)
  return assignment?.total_score || 100
}

const isImageFile = (url) => {
  if (!url) return false
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
  const lowerUrl = url.toLowerCase()
  return imageExtensions.some(ext => lowerUrl.includes(ext))
}

const openImagePreview = (url) => {
  previewImageUrl.value = url
  showImagePreview.value = true
}

const calculateTotalScore = () => {
  return assignmentForm.value.questions.reduce((sum, q) => sum + (q.score || 0), 0)
}

const getQuestionTypeName = (type) => {
  const names = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'fill_blank': '填空题',
    'true_false': '判断题',
    'text': '大题'
  }
  return names[type] || type
}

const getRecommendedScore = (type) => {
  const scores = {
    'single_choice': 2,
    'multiple_choice': 3,
    'fill_blank': 5,
    'true_false': 2,
    'text': 10
  }
  return scores[type] || 10
}

const openCreateAssignmentModal = () => {
  editingAssignment.value = null
  assignmentForm.value = {
    title: '',
    due_date: '',
    description: '',
    questions: []
  }
  showCreateAssignmentModal.value = true
}

const closeAssignmentModal = () => {
  showCreateAssignmentModal.value = false
  editingAssignment.value = null
}

const addQuestion = (type) => {
  const question = {
    question_type: type,
    content: '',
    score: getRecommendedScore(type),
    image_url: '',
    correct_answer: '',
    correct_answers: [],
    options: {
      A: '',
      B: '',
      C: '',
      D: ''
    },
    fill_answer: '',
    true_false_answer: ''
  }
  
  assignmentForm.value.questions.push(question)
}

const removeQuestion = (index) => {
  assignmentForm.value.questions.splice(index, 1)
}

const triggerImageUpload = (index) => {
  const input = fileInputRefs.value[index]
  if (input) {
    input.click()
  }
}

const handleQuestionImageUpload = async (event, index) => {
  const file = event.target.files[0]
  if (!file) return
  
  try {
    const res = await assignmentAPI.uploadQuestionImage(file)
    assignmentForm.value.questions[index].image_url = res.data.image_url
  } catch (error) {
    alert('上传图片失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const removeQuestionImage = (index) => {
  assignmentForm.value.questions[index].image_url = ''
}

const editAssignment = async (assignment) => {
  editingAssignment.value = assignment
  
  try {
    const res = await assignmentAPI.getQuestions(assignment.id)
    const questions = res.data.questions || []
    
    assignmentForm.value = {
      title: assignment.title,
      due_date: assignment.due_date ? assignment.due_date.slice(0, 16) : '',
      description: assignment.description || '',
      questions: questions.map(q => {
        let correctAnswers = []
        if (q.question_type === 'multiple_choice' && q.correct_answer) {
          correctAnswers = q.correct_answer.split(',').filter(a => a)
        }
        return {
          id: q.id,
          question_type: q.question_type,
          content: q.content,
          score: q.score,
          image_url: q.image_url,
          correct_answer: q.correct_answer || '',
          correct_answers: correctAnswers,
          options: q.options || { A: '', B: '', C: '', D: '' }
        }
      })
    }
    showCreateAssignmentModal.value = true
  } catch (error) {
    alert('加载题目失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const loadCourseData = async (retryCount = 0) => {
  loading.value = true
  try {
    const results = await Promise.allSettled([
      assignmentAPI.getCourseDetail(courseId.value),
      assignmentAPI.getCourseAssignments(courseId.value),
      assignmentAPI.getCourseResources(courseId.value),
      assignmentAPI.getStudentCount(courseId.value)
    ])
    
    const [courseRes, assignmentsRes, resourcesRes, studentsRes] = results
    
    if (courseRes.status === 'fulfilled') {
      course.value = courseRes.value.data.course
    } else {
      console.error('加载课程详情失败:', courseRes.reason)
      if (retryCount < 2) {
        await new Promise(resolve => setTimeout(resolve, 500))
        return loadCourseData(retryCount + 1)
      }
    }
    
    if (assignmentsRes.status === 'fulfilled') {
      assignments.value = assignmentsRes.value.data.assignments
      assignments.value.forEach(assignment => {
        submissionCounts.value[assignment.id] = assignment.submission_count || 0
        assignment.pending_count = assignment.pending_count || 0
      })
    } else {
      console.error('加载作业列表失败:', assignmentsRes.reason)
      assignments.value = []
    }
    
    if (resourcesRes.status === 'fulfilled') {
      resources.value = resourcesRes.value.data.resources
    } else {
      console.error('加载资源列表失败:', resourcesRes.reason)
      resources.value = []
    }
    
    if (studentsRes.status === 'fulfilled') {
      students.value = studentsRes.value.data.students || []
    } else {
      console.error('加载学生列表失败:', studentsRes.reason)
      students.value = []
    }
  } catch (error) {
    console.error('加载课程数据失败:', error)
    if (retryCount < 2) {
      await new Promise(resolve => setTimeout(resolve, 500))
      return loadCourseData(retryCount + 1)
    }
    alert('加载失败：' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

const loadSubmissions = async () => {
  if (!selectedAssignmentId.value) return
  
  loadingSubmissions.value = true
  try {
    const res = await assignmentAPI.getSubmissions(selectedAssignmentId.value)
    submissions.value = res.data.submissions || []
    assignmentQuestions.value = res.data.questions || []
    
    gradeForms.value = {}
    for (const submission of submissions.value) {
      if (submission.status !== 'graded') {
        const existingScore = submission.score || 0
        gradeForms.value[submission.id] = { 
          score: existingScore, 
          feedback: submission.feedback || '', 
          overall_comment: submission.overall_comment || '',
          comment_locked: submission.comment_locked || false
        }
        
        for (const question of assignmentQuestions.value) {
          const answer = submission.answers?.[question.id]
          if (answer && question.question_type === 'text') {
            const key = `${submission.id}_${question.id}`
            answerGradeForms.value[key] = { 
              score: answer.score || 0, 
              feedback: answer.feedback || '', 
              aiFeedback: '', 
              aiAnalysis: '' 
            }
          }
        }
      }
    }
  } catch (error) {
    console.error('加载提交失败:', error)
    alert('加载失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    loadingSubmissions.value = false
  }
}

const viewSubmissions = (assignment) => {
  selectedAssignmentId.value = assignment.id
  activeTab.value = 'grading'
}

const triggerImportFile = () => {
  importFileInput.value.click()
}

const handleImportFile = (event) => {
  const file = event.target.files[0]
  if (file) {
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      alert('请选择Excel文件（.xlsx或.xls格式）')
      return
    }
    importFile.value = file
    importResult.value = null
  }
}

const handleDropImport = (event) => {
  const file = event.dataTransfer.files[0]
  if (file) {
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      alert('请选择Excel文件（.xlsx或.xls格式）')
      return
    }
    importFile.value = file
    importResult.value = null
  }
}

const clearImportFile = () => {
  importFile.value = null
  importResult.value = null
  if (importFileInput.value) {
    importFileInput.value.value = ''
  }
}

const downloadTemplate = async () => {
  try {
    const response = await assignmentAPI.downloadQuestionsTemplate()
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '题目导入模板.xlsx')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    alert('下载模板失败')
  }
}

const handleImportQuestions = async () => {
  if (importTab.value === 'excel' && !importFile.value) return
  if (importTab.value === 'text' && !importText.value.trim()) return
  if (importTab.value === 'file' && !importTxtFile.value) return
  
  importing.value = true
  importResult.value = null
  
  try {
    let assignmentId = editingAssignment.value?.id
    
    if (!assignmentId) {
      if (!assignmentForm.value.title || !assignmentForm.value.due_date) {
        alert('请先填写作业标题和截止时间')
        importing.value = false
        return
      }
      
      const createRes = await assignmentAPI.createAssignmentForCourse(courseId.value, {
        title: assignmentForm.value.title,
        due_date: assignmentForm.value.due_date,
        description: '',
        total_score: 100
      })
      assignmentId = createRes.data.assignment.id
      editingAssignment.value = createRes.data.assignment
    }
    
    let response
    if (importTab.value === 'excel') {
      response = await assignmentAPI.importQuestions(assignmentId, importFile.value)
    } else if (importTab.value === 'text') {
      response = await assignmentAPI.importTextQuestions(assignmentId, importText.value)
    } else if (importTab.value === 'file') {
      response = await assignmentAPI.importFileQuestions(assignmentId, importTxtFile.value)
    }
    
    importResult.value = response.data
    
    if (response.data.success_count > 0) {
      for (const q of response.data.questions) {
        const questionData = {
          question_type: q.question_type,
          content: q.content,
          score: q.score,
          image_url: '',
          correct_answer: '',
          correct_answers: [],
          options: { A: '', B: '', C: '', D: '' },
          fill_answer: '',
          true_false_answer: ''
        }
        
        if (q.question_type === 'single_choice') {
          questionData.correct_answer = q.correct_answer || ''
          questionData.options = q.options || { A: '', B: '', C: '', D: '' }
        } else if (q.question_type === 'multiple_choice') {
          questionData.correct_answers = q.correct_answer ? q.correct_answer.split(',').map(s => s.trim()) : []
          questionData.options = q.options || { A: '', B: '', C: '', D: '' }
        } else if (q.question_type === 'fill_blank') {
          questionData.fill_answer = q.correct_answer || ''
        } else if (q.question_type === 'true_false') {
          questionData.true_false_answer = q.correct_answer || ''
        } else {
          questionData.correct_answer = q.correct_answer || ''
        }
        
        assignmentForm.value.questions.push(questionData)
      }
      
      if (importTab.value === 'excel') {
        clearImportFile()
      } else if (importTab.value === 'text') {
        importText.value = ''
      } else if (importTab.value === 'file') {
        clearTxtFile()
      }
    }
  } catch (error) {
    alert('导入失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    importing.value = false
  }
}

const triggerTxtFileUpload = () => {
  txtFileInput.value?.click()
}

const handleTxtFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) {
    if (!file.name.endsWith('.txt')) {
      alert('请选择文本文件（.txt格式）')
      return
    }
    importTxtFile.value = file
    importResult.value = null
  }
}

const handleTxtFileDrop = (event) => {
  event.preventDefault()
  const file = event.dataTransfer.files[0]
  if (file) {
    if (!file.name.endsWith('.txt')) {
      alert('请选择文本文件（.txt格式）')
      return
    }
    importTxtFile.value = file
    importResult.value = null
  }
}

const clearTxtFile = () => {
  importTxtFile.value = null
  importResult.value = null
  if (txtFileInput.value) {
    txtFileInput.value.value = ''
  }
}

const handleTestAI = async () => {
  testingAI.value = true
  
  try {
    const response = await assignmentAPI.testAIConnection()
    
    if (response.data.success) {
      alert('✅ AI服务连接正常！\n\n' + response.data.message)
    } else {
      const hint = response.data.hint ? '\n\n' + response.data.hint : ''
      alert('❌ AI服务连接失败\n\n' + response.data.error + hint)
    }
  } catch (error) {
    const errorMsg = error.response?.data?.error || error.message || '未知错误'
    const hint = error.response?.data?.hint ? '\n\n' + error.response.data.hint : ''
    alert('❌ 测试失败：' + errorMsg + hint)
  } finally {
    testingAI.value = false
  }
}

const handleAIParse = async () => {
  if (!importText.value.trim()) {
    alert('请输入要解析的题目文本')
    return
  }
  
  aiParsing.value = true
  importResult.value = null
  
  try {
    const statusRes = await assignmentAPI.checkAIStatus()
    if (!statusRes.data.configured) {
      alert('AI服务未配置\n\n' + (statusRes.data.hint || statusRes.data.message))
      aiParsing.value = false
      return
    }
    
    let assignmentId = editingAssignment.value?.id
    
    if (!assignmentId) {
      if (!assignmentForm.value.title || !assignmentForm.value.due_date) {
        alert('请先填写作业标题和截止时间')
        aiParsing.value = false
        return
      }
      
      const createRes = await assignmentAPI.createAssignmentForCourse(courseId.value, {
        title: assignmentForm.value.title,
        due_date: assignmentForm.value.due_date,
        description: '',
        total_score: 100
      })
      assignmentId = createRes.data.assignment.id
      editingAssignment.value = createRes.data.assignment
    }
    
    const response = await assignmentAPI.aiParseQuestions(assignmentId, importText.value)
    
    importResult.value = response.data
    
    if (response.data.success_count > 0) {
      for (const q of response.data.questions) {
        const questionData = {
          question_type: q.question_type,
          content: q.content,
          score: q.score,
          image_url: '',
          correct_answer: '',
          correct_answers: [],
          options: { A: '', B: '', C: '', D: '' },
          fill_answer: '',
          true_false_answer: ''
        }
        
        if (q.question_type === 'single_choice') {
          questionData.correct_answer = q.correct_answer || ''
          questionData.options = q.options || { A: '', B: '', C: '', D: '' }
        } else if (q.question_type === 'multiple_choice') {
          questionData.correct_answers = q.correct_answer ? q.correct_answer.split(',').map(s => s.trim()) : []
          questionData.options = q.options || { A: '', B: '', C: '', D: '' }
        } else if (q.question_type === 'fill_blank') {
          questionData.fill_answer = q.correct_answer || ''
        } else if (q.question_type === 'true_false') {
          questionData.true_false_answer = q.correct_answer || ''
        } else {
          questionData.correct_answer = q.correct_answer || ''
        }
        
        assignmentForm.value.questions.push(questionData)
      }
      
      importText.value = ''
      alert(`AI解析成功！共导入 ${response.data.success_count} 道题目`)
    }
  } catch (error) {
    const errorMsg = error.response?.data?.error || error.message || '未知错误'
    alert('AI解析失败：' + errorMsg)
  } finally {
    aiParsing.value = false
  }
}

const handleClearQuestions = async () => {
  if (!editingAssignment.value?.id) {
    alert('请先保存作业')
    return
  }
  
  if (!confirm('确定要清除本次作业的所有题目吗？此操作不可撤销！')) {
    return
  }
  
  clearingQuestions.value = true
  try {
    const response = await assignmentAPI.clearQuestions(editingAssignment.value.id)
    alert(response.data.message)
    assignmentForm.value.questions = []
    importResult.value = null
  } catch (error) {
    alert('清除失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    clearingQuestions.value = false
  }
}

const handleCreateAssignment = async () => {
  if (!assignmentForm.value.title || !assignmentForm.value.due_date) {
    alert('请填写作业标题和截止时间')
    return
  }
  
  creating.value = true
  try {
    let assignmentId = editingAssignment.value?.id
    
    if (assignmentId) {
      await assignmentAPI.updateAssignment(assignmentId, {
        title: assignmentForm.value.title,
        due_date: assignmentForm.value.due_date,
        description: assignmentForm.value.description,
        total_score: calculateTotalScore()
      })
      
      await assignmentAPI.createQuestionsBatch({
        assignment_id: assignmentId,
        questions: assignmentForm.value.questions.map((q, idx) => {
          let correctAnswer = ''
          
          if (q.question_type === 'multiple_choice') {
            correctAnswer = q.correct_answers.sort().join(',')
          } else if (q.question_type === 'fill_blank') {
            correctAnswer = q.fill_answer || ''
          } else if (q.question_type === 'true_false') {
            correctAnswer = q.true_false_answer || ''
          } else {
            correctAnswer = q.correct_answer || ''
          }
          
          return {
            question_type: q.question_type,
            content: q.content,
            score: q.score,
            image_url: q.image_url,
            correct_answer: correctAnswer,
            options: q.options
          }
        })
      })
    } else {
      const createRes = await assignmentAPI.createAssignmentForCourse(courseId.value, {
        title: assignmentForm.value.title,
        due_date: assignmentForm.value.due_date,
        description: assignmentForm.value.description,
        total_score: calculateTotalScore()
      })
      assignmentId = createRes.data.assignment.id
      
      if (assignmentForm.value.questions.length > 0) {
        await assignmentAPI.createQuestionsBatch({
          assignment_id: assignmentId,
          questions: assignmentForm.value.questions.map((q, idx) => {
            let correctAnswer = ''
            
            if (q.question_type === 'multiple_choice') {
              correctAnswer = q.correct_answers.sort().join(',')
            } else if (q.question_type === 'fill_blank') {
              correctAnswer = q.fill_answer || ''
            } else if (q.question_type === 'true_false') {
              correctAnswer = q.true_false_answer || ''
            } else {
              correctAnswer = q.correct_answer || ''
            }
            
            return {
              question_type: q.question_type,
              content: q.content,
              score: q.score,
              image_url: q.image_url,
              correct_answer: correctAnswer,
              options: q.options
            }
          })
        })
      }
    }
    
    const wasEditing = Boolean(editingAssignment.value)
    closeAssignmentModal()
    await loadCourseData()
    alert(wasEditing ? '作业修改成功！' : '作业发布成功！')
  } catch (error) {
    alert('发布失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    creating.value = false
  }
}

const gradeSubmission = async (submission) => {
  const form = gradeForms.value[submission.id]
  
  const answersData = []
  let calculatedScore = 0
  
  for (const question of assignmentQuestions.value) {
    const answer = submission.answers?.[question.id]
    
    if (question.question_type === 'text') {
      const answerForm = getAnswerGradeForm(submission.id, question.id)
      answersData.push({
        question_id: question.id,
        score: answerForm.score || 0,
        feedback: answerForm.feedback || ''
      })
      calculatedScore += answerForm.score || 0
    } else if (answer && answer.score !== null && answer.score !== undefined) {
      calculatedScore += answer.score
    }
  }
  
  let finalScore = calculatedScore
  if (form?.score !== undefined && form?.score !== null && form?.score !== '') {
    finalScore = form.score
  }
  
  gradingId.value = submission.id
  try {
    await assignmentAPI.gradeSubmission(submission.id, {
      score: finalScore,
      feedback: form?.feedback || '',
      overall_comment: form?.overall_comment || '',
      answers: answersData
    })
    await loadSubmissions()
    alert('批改成功！')
    
    if (gradingFilter.value === 'pending' && filteredSubmissions.value.length === 0) {
      gradingFilter.value = 'graded'
    }
  } catch (error) {
    alert('批改失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    gradingId.value = null
  }
}

const autoGradeSubmission = async (submission) => {
  if (!confirm('确定要自动批改客观题吗？系统将根据正确答案自动批改单选题、多选题、填空题和判断题。')) return
  
  gradingId.value = submission.id
  try {
    const res = await assignmentAPI.gradeSubmission(submission.id, {
      auto_grade: true
    })
    
    if (res.data.auto_score !== undefined) {
      const form = gradeForms.value[submission.id]
      if (form) {
        form.score = res.data.auto_score
      }
      
      if (res.data.answers) {
        for (const answerData of res.data.answers) {
          const answer = submission.answers?.[answerData.question_id]
          if (answer) {
            answer.score = answerData.score
            answer.is_correct = answerData.is_correct
          }
        }
      }
      
      submission.score = res.data.auto_score
    }
    
    alert(`自动批改完成！客观题得分：${res.data.auto_score} 分`)
  } catch (error) {
    alert('自动批改失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    gradingId.value = null
  }
}

const getQuestionInfo = (questionId) => {
  return assignmentQuestions.value.find(q => q.id === questionId)
}

const getAnswerGradeForm = (submissionId, questionId) => {
  const key = `${submissionId}_${questionId}`
  if (!answerGradeForms.value[key]) {
    answerGradeForms.value[key] = { score: 0, feedback: '', aiFeedback: '', aiAnalysis: '' }
  }
  return answerGradeForms.value[key]
}

const aiGradeQuestion = async (submission, question) => {
  const answer = submission.answers?.[question.id]
  if (!answer || (!answer.answer_text && !answer.answer_image_url)) {
    alert('学生未作答此题，无法使用AI评分')
    return
  }
  
  const key = `${submission.id}_${question.id}`
  aiGradingKey.value = key
  
  try {
    const res = await assignmentAPI.aiGradeQuestion({
      question_id: question.id,
      submission_id: submission.id
    })
    
    if (res.data.success) {
      const form = getAnswerGradeForm(submission.id, question.id)
      form.score = res.data.score
      form.feedback = res.data.feedback || ''
      form.aiFeedback = res.data.feedback || ''
      form.aiAnalysis = res.data.analysis || ''
      
      if (submission.answers?.[question.id]) {
        submission.answers[question.id].score = res.data.score
        submission.answers[question.id].feedback = res.data.feedback || ''
      }
      
      alert(`AI评分完成！推荐得分：${res.data.score}分`)
    } else {
      alert('AI评分失败：' + (res.data.error || '未知错误'))
    }
  } catch (error) {
    alert('AI评分失败：' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    aiGradingKey.value = null
  }
}

const calculateAutoScore = (submission) => {
  let score = 0
  for (const question of assignmentQuestions.value) {
    const answer = submission.answers?.[question.id]
    if (answer && answer.score !== null && question.question_type !== 'text') {
      score += answer.score
    }
  }
  return score
}

const calculateTextScore = (submission) => {
  let score = 0
  for (const question of assignmentQuestions.value) {
    if (question.question_type === 'text') {
      const form = answerGradeForms.value[`${submission.id}_${question.id}`]
      if (form && form.score) {
        score += form.score
      }
    }
  }
  return score
}

const generateOverallComment = async (submission) => {
  const form = gradeForms.value[submission.id]
  if (!form) return
  
  generatingCommentId.value = submission.id
  try {
    const res = await assignmentAPI.generateOverallComment(submission.id)
    
    if (res.data.success) {
      form.overall_comment = res.data.comment
      alert('AI总评生成成功！您可以修改后再锁定。')
    } else {
      alert('AI生成总评失败：' + (res.data.error || '未知错误'))
    }
  } catch (error) {
    alert('AI生成总评失败：' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    generatingCommentId.value = null
  }
}

const toggleCommentLock = async (submission) => {
  const form = gradeForms.value[submission.id]
  if (!form) return
  
  const newLockState = !form.comment_locked
  const action = newLockState ? 'lock' : 'unlock'
  
  try {
    const res = await assignmentAPI.lockComment(submission.id, action)
    
    if (res.data.success) {
      form.comment_locked = newLockState
      alert(newLockState ? '评语已锁定！' : '评语已解锁！')
    }
  } catch (error) {
    alert('操作失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const unlockAndEdit = async (submission) => {
  const form = gradeForms.value[submission.id]
  if (!form) return
  
  try {
    const res = await assignmentAPI.lockComment(submission.id, 'unlock')
    
    if (res.data.success) {
      form.comment_locked = false
    }
  } catch (error) {
    alert('解锁失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const getNextSubmission = (currentSubmission) => {
  const currentIndex = filteredSubmissions.value.findIndex(s => s.id === currentSubmission.id)
  if (currentIndex === -1 || currentIndex === filteredSubmissions.value.length - 1) {
    return null
  }
  return filteredSubmissions.value[currentIndex + 1]
}

const goToNextSubmission = (currentSubmission) => {
  const nextSubmission = getNextSubmission(currentSubmission)
  if (nextSubmission) {
    const nextElement = document.getElementById(`submission-${nextSubmission.id}`)
    if (nextElement) {
      nextElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
}

const openCreateResourceModal = () => {
  resourceForm.value = { title: '', description: '', url: '', file: null }
  resourceUploadType.value = 'file'
  uploadProgress.value = 0
  showCreateResourceModal.value = true
}

const triggerResourceFileUpload = () => {
  resourceFileInput.value?.click()
}

const handleResourceFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) {
    if (file.size === 0) {
      alert('无法上传空文件或文件夹，请选择具体的文件')
      event.target.value = ''
      return
    }
    if (file.size > 100 * 1024 * 1024) {
      alert('文件大小不能超过100MB')
      event.target.value = ''
      return
    }
    resourceForm.value.file = file
    if (!resourceForm.value.title) {
      resourceForm.value.title = file.name.replace(/\.[^/.]+$/, '')
    }
  }
}

const handleResourceFileDrop = (event) => {
  event.preventDefault()
  const items = event.dataTransfer.items
  
  if (items && items.length > 0) {
    const item = items[0]
    if (item.kind === 'file') {
      const file = item.getAsFile()
      if (file) {
        if (!file.name || file.name === '') {
          alert('无法上传文件夹，请选择具体的文件（如图片、文档、视频等）')
          return
        }
        if (file.size === 0) {
          alert('无法上传空文件，请选择有内容的文件')
          return
        }
        if (file.size > 100 * 1024 * 1024) {
          alert('文件大小不能超过100MB')
          return
        }
        resourceForm.value.file = file
        if (!resourceForm.value.title) {
          resourceForm.value.title = file.name.replace(/\.[^/.]+$/, '')
        }
      }
    } else {
      alert('请拖放文件，而不是文件夹')
    }
  } else {
    const file = event.dataTransfer.files[0]
    if (file) {
      if (file.size === 0) {
        alert('无法上传空文件或文件夹，请选择具体的文件')
        return
      }
      resourceForm.value.file = file
      if (!resourceForm.value.title) {
        resourceForm.value.title = file.name.replace(/\.[^/.]+$/, '')
      }
    }
  }
}

const clearResourceFile = () => {
  resourceForm.value.file = null
  if (resourceFileInput.value) {
    resourceFileInput.value.value = ''
  }
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

const getFileIcon = (filename) => {
  if (!filename) return '📄'
  const ext = filename.split('.').pop().toLowerCase()
  const icons = {
    'pdf': '📕',
    'doc': '📘', 'docx': '📘',
    'xls': '📗', 'xlsx': '📗',
    'ppt': '📙', 'pptx': '📙',
    'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️',
    'mp4': '🎬', 'avi': '🎬', 'mov': '🎬', 'mkv': '🎬',
    'mp3': '🎵', 'wav': '🎵', 'flac': '🎵',
    'txt': '📝',
    'zip': '📦', 'rar': '📦'
  }
  return icons[ext] || '📄'
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

const handleCreateResource = async () => {
  if (!resourceForm.value.title) {
    alert('请输入资源标题')
    return
  }
  
  creating.value = true
  uploadProgress.value = 0
  
  try {
    if (resourceUploadType.value === 'file' && resourceForm.value.file) {
      const formData = new FormData()
      formData.append('file', resourceForm.value.file)
      formData.append('title', resourceForm.value.title)
      formData.append('description', resourceForm.value.description)
      
      await assignmentAPI.createResource(courseId.value, formData)
    } else if (resourceUploadType.value === 'link' && resourceForm.value.url) {
      await assignmentAPI.createResource(courseId.value, {
        title: resourceForm.value.title,
        description: resourceForm.value.description,
        url: resourceForm.value.url,
        file_type: 'link'
      })
    } else {
      alert('请选择文件或输入链接')
      creating.value = false
      return
    }
    
    showCreateResourceModal.value = false
    resourceForm.value = { title: '', description: '', url: '', file: null }
    uploadProgress.value = 0
    await loadCourseData()
    alert('资源发布成功！')
  } catch (error) {
    alert('发布失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    creating.value = false
  }
}

const deleteResource = async (resourceId) => {
  if (!confirm('确定要删除这个资源吗？')) return
  
  try {
    await assignmentAPI.deleteResource(resourceId)
    await loadCourseData()
    alert('资源删除成功！')
  } catch (error) {
    alert('删除失败：' + (error.response?.data?.error || '未知错误'))
  }
}

const loadUnsubmittedStudents = async () => {
  if (!selectedAssignmentId.value) return
  
  loadingUnsubmitted.value = true
  try {
    const res = await assignmentAPI.getUnsubmittedStudents(selectedAssignmentId.value)
    unsubmittedData.value = res.data
  } catch (error) {
    console.error('加载未提交学生失败:', error)
    alert('加载失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    loadingUnsubmitted.value = false
  }
}

const sendReminder = async () => {
  if (!selectedAssignmentId.value) return
  
  sendingReminder.value = true
  try {
    const data = {}
    if (reminderMessage.value.trim()) {
      data.message = reminderMessage.value.trim()
    }
    
    const res = await assignmentAPI.sendAssignmentReminder(selectedAssignmentId.value, data)
    
    alert(res.data.message)
    showReminderModal.value = false
    reminderMessage.value = ''
  } catch (error) {
    alert('发送失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    sendingReminder.value = false
  }
}

const goToStatistics = () => {
  if (!selectedAssignmentId.value) return
  router.push(`/teacher/assignment/${selectedAssignmentId.value}/statistics`)
}

const syncAiContext = () => {
  window.__teacherAiContext = {
    course_id: courseId.value,
    assignment_id: selectedAssignmentId.value || null,
    page: activeTab.value
  }
}

const normalizeAiDueDate = (value) => {
  if (!value) return ''
  const normalized = String(value).replace('Z', '').replace(/\.\d+$/, '')
  return normalized.length >= 16 ? normalized.slice(0, 16) : normalized
}

const applyAiAssignmentDraft = (draft) => {
  if (!draft || (draft.course_id && String(draft.course_id) !== String(courseId.value))) return

  assignmentForm.value = {
    title: draft.title || '',
    due_date: normalizeAiDueDate(draft.due_date),
    description: draft.description || '',
    questions: (draft.questions || []).map((question) => ({
      question_type: question.question_type || 'text',
      content: question.content || '',
      score: question.score || getRecommendedScore(question.question_type || 'text'),
      image_url: question.image_url || '',
      correct_answer: question.correct_answer || '',
      correct_answers: question.question_type === 'multiple_choice'
        ? String(question.correct_answer || '').split(',').filter(Boolean)
        : [],
      options: question.options || { A: '', B: '', C: '', D: '' },
      fill_answer: question.question_type === 'fill_blank' ? (question.correct_answer || '') : '',
      true_false_answer: question.question_type === 'true_false' ? (question.correct_answer || '') : ''
    }))
  }
  editingAssignment.value = null
  activeTab.value = 'assignments'
  showCreateAssignmentModal.value = true
}

const handleAiAssignmentDraft = (event) => {
  applyAiAssignmentDraft(event.detail)
}

const applyStoredAiDraft = () => {
  const storedDraft = sessionStorage.getItem('teacher-ai-assignment-draft')
  if (!storedDraft) return
  try {
    applyAiAssignmentDraft(JSON.parse(storedDraft))
    sessionStorage.removeItem('teacher-ai-assignment-draft')
  } catch (error) {
    sessionStorage.removeItem('teacher-ai-assignment-draft')
  }
}

watch(selectedAssignmentId, () => {
  loadSubmissions()
})

watch([selectedAssignmentId, activeTab], syncAiContext)

watch(showReminderModal, (newVal) => {
  if (newVal) {
    loadUnsubmittedStudents()
  }
})

onMounted(() => {
  window.addEventListener('teacher-ai-apply-draft', handleAiAssignmentDraft)
  syncAiContext()
  loadCourseData()
  applyStoredAiDraft()
})

onUnmounted(() => {
  window.removeEventListener('teacher-ai-apply-draft', handleAiAssignmentDraft)
  if (window.__teacherAiContext?.course_id === courseId.value) {
    delete window.__teacherAiContext
  }
})
</script>

<style scoped>
.teacher-course-detail {
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
  overflow-x: auto;
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
  white-space: nowrap;
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

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid #f0f0f0;
}

.section-header h3 {
  margin: 0;
  color: #333;
  font-size: 18px;
}

.loading,
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: 12px;
  margin-top: 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 15px;
}

.empty-title {
  font-size: 18px;
  color: #333;
  margin: 0 0 10px 0;
  font-weight: 600;
}

.empty-hint {
  font-size: 14px;
  color: #999;
  margin: 0;
}

.pending-reminder {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
  padding: 12px 20px;
  border-radius: 25px;
  margin-top: 20px;
  font-size: 14px;
  color: #e65100;
  box-shadow: 0 2px 8px rgba(230, 81, 0, 0.15);
}

.reminder-badge {
  font-size: 18px;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}

.pending-reminder strong {
  font-size: 18px;
  font-weight: 700;
}

.grading-reminder {
  display: flex;
  align-items: center;
  gap: 15px;
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  padding: 15px 20px;
  border-radius: 10px;
  margin: 15px 0;
  border-left: 4px solid #2196f3;
}

.grading-reminder .reminder-icon {
  font-size: 28px;
}

.grading-reminder .reminder-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.grading-reminder .reminder-text {
  font-size: 15px;
  color: #1565c0;
  font-weight: 500;
}

.grading-reminder .reminder-text strong {
  font-size: 18px;
  font-weight: 700;
}

.grading-reminder .reminder-hint {
  font-size: 12px;
  color: #64b5f6;
}

.grading-filter-section {
  margin-bottom: 15px;
}

.filter-tabs {
  display: flex;
  gap: 10px;
  background: #f5f7fa;
  padding: 8px;
  border-radius: 10px;
}

.filter-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 14px;
  color: #666;
}

.filter-tab:hover {
  background: rgba(255, 255, 255, 0.8);
}

.filter-tab.active {
  background: white;
  color: #333;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  font-weight: 500;
}

.filter-tab .tab-icon {
  font-size: 16px;
}

.filter-tab .tab-count {
  background: #e0e0e0;
  color: #666;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}

.filter-tab.active .tab-count {
  background: #4a90d9;
  color: white;
}

.pagination-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 10px;
}

.pagination-info {
  font-size: 13px;
  color: #666;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-btn {
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 13px;
  color: #333;
  transition: all 0.2s ease;
}

.pagination-btn:hover:not(:disabled) {
  background: #4a90d9;
  color: white;
  border-color: #4a90d9;
}

.pagination-btn:disabled {
  background: #f5f5f5;
  color: #ccc;
  cursor: not-allowed;
}

.page-indicator {
  padding: 6px 12px;
  font-size: 13px;
  color: #666;
  font-weight: 500;
}

.assignment-list,
.resource-list,
.submission-list {
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
.submission-count,
.question-count {
  margin: 0 0 5px 0;
  color: #999;
  font-size: 14px;
}

.assignment-actions {
  display: flex;
  gap: 10px;
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

.student-count {
  color: #667eea;
  font-size: 14px;
}

.student-table {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.table-header,
.table-row {
  display: flex;
  padding: 15px 20px;
}

.table-header {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.table-row {
  border-bottom: 1px solid #f0f0f0;
}

.table-row:last-child {
  border-bottom: none;
}

.table-row:hover {
  background: #fafafa;
}

.col {
  flex: 1;
  color: #666;
}

.table-header .col {
  color: #333;
}

.assignment-select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  min-width: 200px;
}

.submission-item {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.submission-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.student-info {
  display: flex;
  gap: 15px;
  align-items: center;
}

.student-name {
  font-weight: 600;
  color: #333;
}

.submit-time {
  color: #999;
  font-size: 13px;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.status-badge.submitted {
  background: #fff3cd;
  color: #856404;
}

.status-badge.graded {
  background: #d4edda;
  color: #155724;
}

.questions-review-section {
  margin-bottom: 20px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.section-title {
  margin: 0;
  padding: 12px 15px;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
  font-size: 15px;
  color: #333;
}

.question-review-item {
  padding: 15px;
  border-bottom: 1px solid #f0f0f0;
}

.question-review-item:last-child {
  border-bottom: none;
}

.question-review-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.question-score-info {
  color: #999;
  font-size: 13px;
}

.question-review-content {
  margin-bottom: 12px;
}

.question-text {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 14px;
  line-height: 1.6;
}

.options-review {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-review-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #f9f9f9;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}

.option-review-item.correct-option {
  background: #e8f5e9;
  border-color: #a5d6a7;
}

.option-review-item.student-selected {
  background: #e3f2fd;
  border-color: #90caf9;
}

.option-review-item.correct-option.student-selected {
  background: #c8e6c9;
  border-color: #66bb6a;
}

.option-key {
  width: 24px;
  height: 24px;
  background: #667eea;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.correct-option .option-key {
  background: #4caf50;
}

.option-value {
  flex: 1;
  color: #333;
  font-size: 14px;
}

.correct-mark {
  color: #4caf50;
  font-size: 12px;
  font-weight: 500;
}

.student-mark {
  color: #2196f3;
  font-size: 12px;
  font-weight: 500;
}

.fill-blank-review,
.true-false-review {
  padding: 12px;
  background: #f5f5f5;
  border-radius: 6px;
}

.correct-answer-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.correct-answer-box .answer-label {
  color: #666;
  font-size: 14px;
}

.correct-answer-box .answer-value {
  font-weight: 600;
  color: #333;
  padding: 4px 12px;
  background: #e8f5e9;
  border-radius: 4px;
}

.correct-answer-box .answer-value.true {
  color: #28a745;
  background: #e8f5e9;
}

.correct-answer-box .answer-value.false {
  color: #dc3545;
  background: #ffebee;
}

.fill-answer {
  font-weight: 500;
  color: #17a2b8;
}

.tf-answer {
  font-weight: 600;
}

.tf-answer.true {
  color: #28a745;
}

.tf-answer.false {
  color: #dc3545;
}

.student-answer-section {
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  border-left: 3px solid #667eea;
}

.answer-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.student-answer-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.student-answer-content .answer-text {
  color: #333;
  font-size: 14px;
}

.answer-score-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.score-badge {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
}

.score-badge.correct {
  background: #e8f5e9;
  color: #2e7d32;
}

.score-badge.wrong {
  background: #ffebee;
  color: #c62828;
}

.correct-text {
  color: #4caf50;
  font-size: 13px;
}

.partial-text {
  color: #ff9800;
  font-size: 13px;
}

.no-answer {
  color: #999;
  font-style: italic;
}

.auto-grade-section {
  margin-bottom: 15px;
  padding: 15px;
  background: #e8f5e9;
  border-radius: 8px;
  text-align: center;
}

.btn-auto-grade {
  background: #4caf50;
  color: white;
  padding: 10px 20px;
  font-size: 14px;
}

.btn-auto-grade:hover:not(:disabled) {
  background: #43a047;
}

.auto-grade-hint {
  margin: 10px 0 0 0;
  color: #666;
  font-size: 12px;
}

.text-grade-section {
  margin-top: 12px;
  padding: 12px;
  background: #fff8e1;
  border-radius: 6px;
  border: 1px solid #ffe082;
}

.ai-grade-btn-section {
  margin-bottom: 15px;
  text-align: center;
}

.btn-ai-grade {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 10px 20px;
  font-size: 14px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
  transition: all 0.3s;
}

.btn-ai-grade:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-ai-grade:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.ai-grade-hint {
  margin: 8px 0 0 0;
  color: #888;
  font-size: 12px;
}

.ai-feedback-section {
  margin-top: 15px;
  padding: 12px;
  background: linear-gradient(135deg, #e8f5e9 0%, #f3e5f5 100%);
  border-radius: 8px;
  border-left: 4px solid #667eea;
}

.ai-feedback-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ai-feedback-icon {
  font-size: 18px;
}

.ai-feedback-title {
  font-weight: 600;
  color: #667eea;
  font-size: 14px;
}

.ai-feedback-text {
  margin: 0 0 8px 0;
  color: #333;
  font-size: 13px;
  line-height: 1.6;
}

.ai-analysis-text {
  margin: 0;
  padding-top: 8px;
  border-top: 1px dashed #ccc;
  color: #666;
  font-size: 12px;
  line-height: 1.6;
}

.text-grade-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.text-grade-label {
  font-size: 13px;
  color: #333;
  font-weight: 500;
  white-space: nowrap;
}

.text-score-input {
  width: 80px;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  text-align: center;
}

.max-score-hint {
  color: #999;
  font-size: 12px;
}

.text-feedback-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.text-feedback-label {
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

.text-feedback-input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}

.answer-feedback-text {
  margin: 8px 0 0 0;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
  color: #666;
  font-size: 13px;
}

.score-summary {
  margin: 15px 0;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.score-summary-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px dashed #e0e0e0;
}

.score-summary-row:last-child {
  border-bottom: none;
}

.score-summary-row.total {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 2px solid #667eea;
  border-bottom: none;
}

.score-label {
  color: #666;
  font-size: 14px;
}

.score-value {
  color: #333;
  font-weight: 500;
  font-size: 14px;
}

.score-value.highlight {
  color: #667eea;
  font-size: 18px;
  font-weight: 600;
}

.teacher-feedback-section {
  margin: 20px 0;
  padding: 15px;
  background: #f0f7ff;
  border-radius: 8px;
  border: 1px solid #b3d4fc;
}

.overall-comment-section {
  margin: 20px 0;
  padding: 15px;
  background: linear-gradient(135deg, #f0f7ff 0%, #f5f0ff 100%);
  border-radius: 8px;
  border: 1px solid #c8b8e8;
}

.comment-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 10px;
}

.comment-actions {
  display: flex;
  gap: 8px;
}

.btn-ai-comment {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 8px 16px;
  font-size: 13px;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(102, 126, 234, 0.3);
}

.btn-ai-comment:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(102, 126, 234, 0.4);
}

.btn-ai-comment:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-lock {
  background: #28a745;
  color: white;
  padding: 8px 16px;
  font-size: 13px;
}

.btn-lock:hover {
  background: #218838;
}

.btn-locked {
  background: #6c757d;
  color: white;
  padding: 8px 16px;
  font-size: 13px;
}

.textarea-locked {
  background: #f5f5f5;
  color: #666;
  cursor: not-allowed;
}

.comment-hint {
  margin: 10px 0 0 0;
  font-size: 12px;
  color: #888;
}

.graded-score-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.total-score-display {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.total-score-display strong {
  color: #667eea;
  font-size: 24px;
}

.graded-badge {
  background: #d4edda;
  color: #155724;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
}

.overall-comment-display {
  background: linear-gradient(135deg, #fff9e6 0%, #fff5f0 100%);
  padding: 15px;
  border-radius: 8px;
  border-left: 4px solid #ffc107;
  margin-top: 15px;
}

.comment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.comment-icon {
  font-size: 18px;
}

.comment-title {
  font-weight: 600;
  color: #333;
  font-size: 15px;
}

.locked-badge {
  background: #e9ecef;
  color: #495057;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.comment-content {
  margin: 0;
  color: #333;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.feedback-text {
  margin: 10px 0 0 0;
  color: #666;
  font-size: 14px;
}

.grade-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.btn-next {
  background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
  color: white;
  padding: 10px 20px;
  font-size: 14px;
  border-radius: 6px;
  box-shadow: 0 2px 6px rgba(17, 153, 142, 0.3);
}

.btn-next:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(17, 153, 142, 0.4);
}

.feedback-label {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 10px;
}

.feedback-textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  min-height: 100px;
}

.feedback-textarea:focus {
  outline: none;
  border-color: #667eea;
}

.answers-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.answer-item {
  background: #f9f9f9;
  padding: 15px;
  border-radius: 8px;
  border-left: 3px solid #667eea;
}

.answer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.question-num {
  font-weight: 600;
  color: #667eea;
}

.answer-score {
  color: #28a745;
  font-weight: 600;
}

.answer-content p {
  margin: 0;
  color: #333;
}

.answer-image {
  max-width: 200px;
  max-height: 150px;
  margin-top: 10px;
  border-radius: 6px;
}

.answer-feedback {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #ddd;
  color: #666;
  font-size: 13px;
}

.submission-content {
  padding: 15px;
  background: #f9f9f9;
  border-radius: 8px;
}

.submission-content p {
  margin: 0 0 10px 0;
  color: #333;
  line-height: 1.6;
}

.file-link {
  color: #667eea;
  text-decoration: none;
  font-size: 14px;
}

.file-link:hover {
  text-decoration: underline;
}

.graded-info {
  padding: 15px;
  background: #e8f5e9;
  border-radius: 8px;
}

.graded-info p {
  margin: 0 0 5px 0;
  color: #333;
}

.grade-form {
  padding: 15px;
  background: #f9f9f9;
  border-radius: 8px;
}

.form-row {
  display: flex;
  gap: 15px;
  margin-bottom: 15px;
}

.form-row .form-group {
  margin-bottom: 0;
}

.flex-1 {
  flex: 1;
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

.btn-edit {
  background: #17a2b8;
  color: white;
}

.btn-edit:hover {
  background: #138496;
}

.btn-add {
  background: #28a745;
  color: white;
  padding: 6px 12px;
  font-size: 13px;
}

.btn-add:hover {
  background: #218838;
}

.btn-single {
  background: #17a2b8;
}

.btn-single:hover {
  background: #138496;
}

.btn-multiple {
  background: #fd7e14;
}

.btn-multiple:hover {
  background: #e06c0a;
}

.btn-fill {
  background: #17a2b8;
}

.btn-fill:hover {
  background: #138496;
}

.btn-true-false {
  background: #20c997;
}

.btn-true-false:hover {
  background: #1aa179;
}

.btn-text {
  background: #6f42c1;
}

.btn-text:hover {
  background: #5e35b1;
}

.btn-import {
  background: #fd7e14;
}

.btn-import:hover {
  background: #e06c0a;
}

.btn-remove {
  background: #dc3545;
  color: white;
  padding: 2px 8px;
  font-size: 16px;
  line-height: 1;
}

.btn-remove:hover {
  background: #c82333;
}

.btn-upload {
  background: #6c757d;
  color: white;
  padding: 6px 12px;
  font-size: 13px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.resource-modal {
  max-width: 600px;
  padding: 0;
}

.resource-modal .modal-body {
  padding: 20px 30px;
}

.import-modal {
  max-width: 650px;
  padding: 0;
}

.import-modal .modal-body {
  padding: 25px;
}

.import-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  border-bottom: 2px solid #e0e0e0;
  padding-bottom: 10px;
}

.import-tab {
  padding: 10px 20px;
  border: none;
  background: #f8f9fa;
  border-radius: 8px 8px 0 0;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  transition: all 0.3s;
}

.import-tab:hover {
  background: #e9ecef;
  color: #333;
}

.import-tab.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.import-content {
  min-height: 200px;
}

.format-hint {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 15px;
}

.format-hint h4 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 14px;
}

.format-hint p {
  margin: 0 0 8px 0;
  color: #666;
  font-size: 13px;
}

.format-hint pre {
  background: #e9ecef;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.import-textarea {
  width: 100%;
  min-height: 200px;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}

.import-textarea:focus {
  outline: none;
  border-color: #667eea;
}

.ai-parse-section {
  text-align: center;
  padding: 20px;
  background: linear-gradient(135deg, #f0f7ff 0%, #f5f0ff 100%);
  border-radius: 12px;
  margin-bottom: 20px;
}

.btn-ai-parse {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 14px 32px;
  font-size: 16px;
  border-radius: 10px;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  transition: all 0.3s;
  border: none;
  cursor: pointer;
}

.btn-ai-parse:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.btn-ai-parse:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.ai-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.btn-test-ai {
  background: #f0f0f0;
  color: #333;
  padding: 14px 24px;
  font-size: 14px;
  border-radius: 10px;
  font-weight: 500;
  transition: all 0.3s;
  border: 1px solid #ddd;
  cursor: pointer;
}

.btn-test-ai:hover:not(:disabled) {
  background: #e0e0e0;
  border-color: #ccc;
}

.btn-test-ai:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ai-parse-hint {
  margin-top: 12px;
  color: #666;
  font-size: 13px;
}

.ai-parse-time-hint {
  margin-top: 8px;
  color: #e67e22;
  font-size: 12px;
}

.import-steps {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.import-step {
  display: flex;
  gap: 15px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 10px;
}

.step-num {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
}

.step-content h4 {
  margin: 0 0 5px 0;
  color: #333;
  font-size: 15px;
}

.step-content p {
  margin: 0 0 10px 0;
  color: #666;
  font-size: 13px;
}

.btn-download {
  background: #28a745;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.btn-download:hover {
  background: #218838;
}

.upload-area {
  border: 2px dashed #ddd;
  border-radius: 10px;
  padding: 25px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: white;
}

.upload-area:hover {
  border-color: #667eea;
  background: #f8f9ff;
}

.upload-placeholder {
  color: #999;
}

.upload-icon {
  font-size: 40px;
  display: block;
  margin-bottom: 10px;
}

.upload-hint {
  font-size: 12px;
  color: #bbb;
  margin-top: 5px;
}

.file-selected {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.file-icon {
  font-size: 28px;
}

.file-name {
  color: #333;
  font-weight: 500;
}

.clear-btn {
  background: #f5f5f5;
  border: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 16px;
  color: #999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.clear-btn:hover {
  background: #e0e0e0;
  color: #666;
}

.import-result {
  margin-top: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 10px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  margin-bottom: 15px;
}

.result-header.success {
  color: #28a745;
}

.result-icon {
  font-size: 20px;
}

.result-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.stat-item {
  padding: 10px 20px;
  border-radius: 8px;
  text-align: center;
}

.stat-item.success {
  background: #e8f5e9;
}

.stat-item.error {
  background: #ffebee;
}

.stat-num {
  display: block;
  font-size: 24px;
  font-weight: bold;
}

.stat-item.success .stat-num {
  color: #28a745;
}

.stat-item.error .stat-num {
  color: #dc3545;
}

.stat-label {
  font-size: 12px;
  color: #666;
}

.error-list {
  background: #fff5f5;
  padding: 12px;
  border-radius: 8px;
}

.error-list h5 {
  margin: 0 0 8px 0;
  color: #dc3545;
  font-size: 13px;
}

.error-list ul {
  margin: 0;
  padding-left: 18px;
}

.error-list li {
  color: #666;
  font-size: 12px;
  margin-bottom: 3px;
}

.upload-tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.tab-btn {
  flex: 1;
  padding: 10px 15px;
  border: 2px solid #e0e0e0;
  background: white;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.tab-btn:hover {
  border-color: #667eea;
}

.tab-btn.active {
  border-color: #667eea;
  background: #e8f0fe;
  color: #667eea;
}

.file-upload-section {
  margin-bottom: 15px;
}

.upload-area {
  border: 2px dashed #d0d0d0;
  border-radius: 12px;
  padding: 30px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #fafafa;
}

.upload-area:hover {
  border-color: #667eea;
  background: #f5f7ff;
}

.upload-placeholder {
  color: #666;
}

.upload-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 10px;
}

.upload-hint {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}

.upload-warning {
  font-size: 12px;
  color: #ff6b6b;
  margin-top: 5px;
}

.file-preview {
  text-align: left;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.file-icon {
  font-size: 32px;
}

.file-details {
  flex: 1;
}

.file-name {
  margin: 0;
  font-weight: 500;
  color: #333;
  word-break: break-all;
}

.file-size {
  margin: 5px 0 0 0;
  font-size: 12px;
  color: #999;
}

.clear-file-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: #ff4d4f;
  color: white;
  border-radius: 50%;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}

.upload-progress {
  margin-top: 15px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #667eea;
  transition: width 0.3s;
}

.link-input-section {
  margin-bottom: 15px;
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

.resource-actions {
  display: flex;
  gap: 8px;
}

.btn-danger {
  background: #dc3545;
  color: white;
}

.btn-danger:hover {
  background: #c82333;
}

.assignment-modal {
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

.basic-info {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
}

.basic-info .form-group {
  flex: 1;
}

.questions-section {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.questions-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f8f9fa;
  border-bottom: 1px solid #e0e0e0;
}

.questions-header h4 {
  margin: 0;
  color: #333;
}

.add-question-btns {
  display: flex;
  gap: 8px;
}

.score-tips {
  display: flex;
  gap: 15px;
  padding: 10px 15px;
  background: #fff8e1;
  border-bottom: 1px solid #ffe082;
  flex-wrap: wrap;
}

.tip-item {
  font-size: 12px;
  color: #f57c00;
}

.empty-questions {
  padding: 40px;
  text-align: center;
  color: #999;
}

.questions-list {
  max-height: 400px;
  overflow-y: auto;
}

.question-item {
  padding: 15px;
  border-bottom: 1px solid #f0f0f0;
}

.question-item:last-child {
  border-bottom: none;
}

.question-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.question-number {
  font-weight: 600;
  color: #667eea;
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

.question-type-badge.text {
  background: #f3e5f5;
  color: #7b1fa2;
}

.question-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.score-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: #666;
}

.score-input {
  width: 50px;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  text-align: center;
}

.score-hint {
  font-size: 11px;
  color: #999;
}

.question-content {
  padding-left: 10px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  color: #555;
  font-weight: 500;
  font-size: 14px;
}

.required {
  color: #dc3545;
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  box-sizing: border-box;
}

.form-group textarea {
  resize: vertical;
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
  outline: none;
  border-color: #667eea;
}

.choice-options {
  margin-top: 10px;
}

.choice-options > label {
  display: block;
  margin-bottom: 8px;
  color: #555;
  font-weight: 500;
  font-size: 14px;
}

.options-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 15px;
}

.option-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.option-label {
  width: 24px;
  height: 24px;
  background: #667eea;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}

.option-item input {
  flex: 1;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
}

.correct-answer {
  margin-top: 15px;
}

.correct-answer label {
  display: block;
  margin-bottom: 10px;
  color: #555;
  font-weight: 500;
  font-size: 14px;
}

.single-select,
.multi-select {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}

.radio-label,
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 8px 15px;
  background: #f8f9fa;
  border-radius: 6px;
  transition: all 0.2s;
}

.radio-label:hover,
.checkbox-label:hover {
  background: #e9ecef;
}

.radio-label input,
.checkbox-label input {
  display: none;
}

.radio-custom,
.checkbox-custom {
  width: 18px;
  height: 18px;
  border: 2px solid #667eea;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.radio-custom {
  border-radius: 50%;
}

.checkbox-custom {
  border-radius: 3px;
}

.radio-label input:checked + .radio-custom,
.checkbox-label input:checked + .checkbox-custom {
  background: #667eea;
}

.radio-label input:checked + .radio-custom::after,
.checkbox-label input:checked + .checkbox-custom::after {
  content: '✓';
  color: white;
  font-size: 12px;
}

.multi-hint {
  width: 100%;
  margin-top: 10px;
  padding: 8px 12px;
  background: #fff8e1;
  border-radius: 4px;
  font-size: 12px;
  color: #f57c00;
}

.fill-blank-question {
  margin-top: 10px;
}

.fill-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #17a2b8;
  background: #e3f7fa;
  padding: 8px 12px;
  border-radius: 4px;
}

.true-false-question {
  margin-top: 10px;
}

.true-false-options {
  display: flex;
  gap: 20px;
}

.true-false-options .radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: 2px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.true-false-options .radio-label:hover {
  border-color: #999;
}

.true-false-options .radio-label input[type="radio"] {
  display: none;
}

.true-false-options .radio-custom {
  width: 20px;
  height: 20px;
  border: 2px solid #ddd;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

.true-false-options .radio-label input[type="radio"]:checked + .radio-custom {
  border-color: currentColor;
  background: currentColor;
}

.true-false-options .radio-label input[type="radio"]:checked + .radio-custom::after {
  content: '';
  width: 8px;
  height: 8px;
  background: white;
  border-radius: 50%;
}

.true-false-options .true-option {
  color: #28a745;
}

.true-false-options .true-option input[type="radio"]:checked ~ span:last-child {
  font-weight: bold;
}

.true-false-options .true-option:has(input[type="radio"]:checked) {
  border-color: #28a745;
  background: #e8f5e9;
}

.true-false-options .false-option {
  color: #dc3545;
}

.true-false-options .false-option:has(input[type="radio"]:checked) {
  border-color: #dc3545;
  background: #ffebee;
}

.text-question {
  margin-top: 10px;
}

.image-upload {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.file-input {
  display: none;
}

.image-preview-inline {
  position: relative;
  display: inline-block;
}

.image-preview-inline img {
  max-width: 150px;
  max-height: 100px;
  border-radius: 4px;
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

.total-score {
  font-size: 16px;
  color: #333;
}

.total-score strong {
  color: #667eea;
  font-size: 20px;
}

.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.file-preview {
  margin-top: 10px;
}

.image-preview {
  text-align: center;
}

.preview-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.3s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.preview-image:hover {
  transform: scale(1.02);
}

.image-preview-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}

.image-preview-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
}

.image-preview-content img {
  max-width: 90vw;
  max-height: 90vh;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}

.image-preview-content .close-btn {
  position: absolute;
  top: -40px;
  right: 0;
  background: white;
  border: none;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 24px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #333;
  transition: all 0.3s;
}

.image-preview-content .close-btn:hover {
  background: #ff6b6b;
  color: white;
}

@media (max-width: 768px) {
  .tabs {
    padding: 0 10px;
  }
  
  .tab {
    padding: 12px 15px;
    font-size: 13px;
  }
  
  .form-row {
    flex-direction: column;
  }
  
  .basic-info {
    flex-direction: column;
  }
  
  .options-grid {
    grid-template-columns: 1fr;
  }
  
  .assignment-item {
    flex-direction: column;
    gap: 15px;
  }
  
  .assignment-actions {
    width: 100%;
    justify-content: flex-end;
  }
  
  .add-question-btns {
    flex-wrap: wrap;
  }
  
  .score-tips {
    flex-direction: column;
    gap: 5px;
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.btn-reminder {
  background: linear-gradient(135deg, #ff6b6b 0%, #ff8e53 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(255, 107, 107, 0.3);
}

.btn-reminder:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 107, 107, 0.4);
}

.btn-statistics {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.btn-statistics:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.reminder-modal {
  max-width: 600px;
}

.reminder-stats {
  display: flex;
  justify-content: space-around;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 10px;
  margin-bottom: 20px;
}

.reminder-stats .stat-item {
  text-align: center;
}

.reminder-stats .stat-label {
  display: block;
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.reminder-stats .stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.reminder-stats .stat-value.submitted {
  color: #28a745;
}

.reminder-stats .stat-value.unsubmitted {
  color: #ff6b6b;
}

.unsubmitted-section h4 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 15px;
}

.student-list-container {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  margin-bottom: 20px;
}

.student-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  border-bottom: 1px solid #f0f0f0;
}

.student-item:last-child {
  border-bottom: none;
}

.student-item .student-name {
  font-weight: 500;
  color: #333;
}

.student-item .student-info {
  font-size: 12px;
  color: #999;
}

.custom-message-section {
  margin-top: 15px;
}

.custom-message-section label {
  display: block;
  margin-bottom: 8px;
  color: #555;
  font-weight: 500;
  font-size: 14px;
}

.custom-message-section textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
}

.custom-message-section textarea:focus {
  outline: none;
  border-color: #667eea;
}

.all-submitted {
  text-align: center;
  padding: 40px 20px;
}

.all-submitted .check-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 15px;
}

.all-submitted p {
  margin: 0;
  color: #28a745;
  font-size: 16px;
  font-weight: 500;
}
</style>
