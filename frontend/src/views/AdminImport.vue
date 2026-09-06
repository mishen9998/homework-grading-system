<template>
  <div class="import-page">
    <div class="import-card">
      <h2>批量导入用户</h2>
      <p class="description">通过Excel文件批量导入学生和教师账号</p>
      
      <div class="steps">
        <div class="step">
          <div class="step-number">1</div>
          <div class="step-content">
            <h3>下载模板</h3>
            <p>下载Excel模板文件，按照模板格式填写用户信息</p>
            <button @click="downloadTemplate" class="btn btn-outline">
              📥 下载模板
            </button>
          </div>
        </div>
        
        <div class="step">
          <div class="step-number">2</div>
          <div class="step-content">
            <h3>填写信息</h3>
            <p>在Excel中填写用户信息，必填字段：账号、密码、邮箱、角色、姓名</p>
          </div>
        </div>
        
        <div class="step">
          <div class="step-number">3</div>
          <div class="step-content">
            <h3>上传文件</h3>
            <p>选择填好的Excel文件并上传</p>
            <div class="upload-area" @click="triggerUpload" @dragover.prevent @drop.prevent="handleDrop">
              <input 
                ref="fileInput" 
                type="file" 
                accept=".xlsx,.xls" 
                @change="handleFileChange"
                hidden
              >
              <div v-if="!selectedFile" class="upload-placeholder">
                <span class="upload-icon">📁</span>
                <p>点击或拖拽文件到此处</p>
                <p class="upload-hint">支持 .xlsx 和 .xls 格式</p>
              </div>
              <div v-else class="file-info">
                <span class="file-icon">📄</span>
                <span class="file-name">{{ selectedFile.name }}</span>
                <button @click.stop="clearFile" class="clear-btn">&times;</button>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <button 
        @click="handleImport" 
        class="btn btn-primary"
        :disabled="!selectedFile || importing"
      >
        {{ importing ? '导入中...' : '开始导入' }}
      </button>
    </div>

    <div v-if="importResult" class="result-card">
      <h3>导入结果</h3>
      <div class="result-stats">
        <div class="stat success">
          <span class="stat-value">{{ importResult.success_count }}</span>
          <span class="stat-label">成功导入</span>
        </div>
        <div class="stat error" v-if="importResult.error_count > 0">
          <span class="stat-value">{{ importResult.error_count }}</span>
          <span class="stat-label">导入失败</span>
        </div>
      </div>
      <div v-if="importResult.errors && importResult.errors.length > 0" class="error-list">
        <h4>错误详情：</h4>
        <ul>
          <li v-for="(error, index) in importResult.errors" :key="index">{{ error }}</li>
        </ul>
      </div>
      <p class="result-message">{{ importResult.message }}</p>
    </div>

    <div class="template-guide">
      <h3>模板说明</h3>
      <table>
        <thead>
          <tr>
            <th>列名</th>
            <th>是否必填</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>账号</td>
            <td class="required">必填</td>
            <td>登录账号（学号/工号），必须唯一</td>
          </tr>
          <tr>
            <td>密码</td>
            <td class="required">必填</td>
            <td>用户登录密码</td>
          </tr>
          <tr>
            <td>邮箱</td>
            <td class="required">必填</td>
            <td>用户邮箱，必须唯一</td>
          </tr>
          <tr>
            <td>角色</td>
            <td class="required">必填</td>
            <td>student（学生）或 teacher（教师）</td>
          </tr>
          <tr>
            <td>姓名</td>
            <td class="required">必填</td>
            <td>用户真实姓名</td>
          </tr>
          <tr>
            <td>学号</td>
            <td>选填</td>
            <td>学生学号</td>
          </tr>
          <tr>
            <td>电话</td>
            <td>选填</td>
            <td>联系电话</td>
          </tr>
          <tr>
            <td>QQ</td>
            <td>选填</td>
            <td>QQ号码</td>
          </tr>
          <tr>
            <td>班级</td>
            <td>选填</td>
            <td>班级名称</td>
          </tr>
          <tr>
            <td>学院</td>
            <td>选填</td>
            <td>所属学院</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { adminAPI } from '@/api/admin'

const fileInput = ref(null)
const selectedFile = ref(null)
const importing = ref(false)
const importResult = ref(null)

const triggerUpload = () => {
  fileInput.value.click()
}

const handleFileChange = (event) => {
  const file = event.target.files[0]
  if (file) {
    validateAndSetFile(file)
  }
}

const handleDrop = (event) => {
  const file = event.dataTransfer.files[0]
  if (file) {
    validateAndSetFile(file)
  }
}

const validateAndSetFile = (file) => {
  if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
    alert('请选择Excel文件（.xlsx或.xls格式）')
    return
  }
  selectedFile.value = file
  importResult.value = null
}

const clearFile = () => {
  selectedFile.value = null
  fileInput.value.value = ''
}

const downloadTemplate = async () => {
  try {
    const response = await adminAPI.downloadTemplate()
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', '用户导入模板.xlsx')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    alert('下载模板失败')
  }
}

const handleImport = async () => {
  if (!selectedFile.value) return
  
  importing.value = true
  importResult.value = null
  
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    
    const response = await adminAPI.importUsers(formData)
    importResult.value = response.data
    
    if (response.data.success_count > 0) {
      clearFile()
    }
  } catch (error) {
    alert('导入失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.import-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.import-card {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.import-card h2 {
  margin: 0 0 10px 0;
  color: #333;
}

.description {
  color: #999;
  margin-bottom: 30px;
}

.steps {
  margin-bottom: 30px;
}

.step {
  display: flex;
  gap: 20px;
  margin-bottom: 25px;
  padding-bottom: 25px;
  border-bottom: 1px solid #f0f0f0;
}

.step:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.step-number {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
}

.step-content h3 {
  margin: 0 0 8px 0;
  color: #333;
  font-size: 16px;
}

.step-content p {
  margin: 0 0 15px 0;
  color: #999;
  font-size: 14px;
}

.upload-area {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 30px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-area:hover {
  border-color: #667eea;
  background: #f8f9ff;
}

.upload-placeholder {
  color: #999;
}

.upload-icon {
  font-size: 48px;
  display: block;
  margin-bottom: 10px;
}

.upload-hint {
  font-size: 12px;
  color: #bbb;
  margin-top: 5px;
}

.file-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.file-icon {
  font-size: 32px;
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

.btn {
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  width: 100%;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-outline {
  background: white;
  border: 1px solid #667eea;
  color: #667eea;
}

.btn-outline:hover {
  background: #667eea;
  color: white;
}

.result-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 20px;
}

.result-card h3 {
  margin: 0 0 15px 0;
  color: #333;
}

.result-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.result-stats .stat {
  padding: 15px 25px;
  border-radius: 8px;
  text-align: center;
}

.result-stats .stat.success {
  background: #e8f5e9;
}

.result-stats .stat.error {
  background: #ffebee;
}

.result-stats .stat-value {
  display: block;
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.result-stats .stat.success .stat-value {
  color: #4CAF50;
}

.result-stats .stat.error .stat-value {
  color: #f44336;
}

.result-stats .stat-label {
  font-size: 14px;
  color: #999;
}

.error-list {
  background: #fff3f3;
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 15px;
}

.error-list h4 {
  margin: 0 0 10px 0;
  color: #f44336;
  font-size: 14px;
}

.error-list ul {
  margin: 0;
  padding-left: 20px;
}

.error-list li {
  color: #666;
  font-size: 13px;
  margin-bottom: 5px;
}

.result-message {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.template-guide {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.template-guide h3 {
  margin: 0 0 15px 0;
  color: #333;
}

.template-guide table {
  width: 100%;
  border-collapse: collapse;
}

.template-guide th,
.template-guide td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #f0f0f0;
}

.template-guide th {
  background: #f8f9fa;
  color: #666;
  font-weight: 500;
}

.template-guide td {
  color: #666;
  font-size: 14px;
}

.template-guide td.required {
  color: #f44336;
  font-weight: 500;
}
</style>
