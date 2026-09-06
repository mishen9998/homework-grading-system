<template>
  <div class="user-management">
    <div class="search-bar">
      <input 
        v-model="searchText" 
        type="text" 
        placeholder="搜索账号、姓名、邮箱或学号..."
        @input="handleSearch"
      >
      <select v-model="roleFilter" @change="loadUsers">
        <option value="">全部角色</option>
        <option value="student">学生</option>
        <option value="teacher">教师</option>
      </select>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    
    <div v-else class="content-area">
      <div v-if="users.length === 0" class="empty">暂无用户数据</div>
      
      <template v-else>
        <div v-if="showStudentSection" class="section">
          <h2 class="section-title">
            <span class="icon">🎓</span>
            学生列表
            <span class="count">共 {{ totalStudentCount }} 人</span>
          </h2>
          
          <div class="class-groups">
            <div 
              v-for="(group, className) in studentGroups" 
              :key="className"
              class="class-box"
            >
              <div class="class-header" @click="toggleClass(className)">
                <div class="class-info">
                  <span class="class-icon">📚</span>
                  <span class="class-name">{{ className || '未分配班级' }}</span>
                  <span class="student-count">{{ group.length }} 人</span>
                </div>
                <span :class="['expand-icon', { expanded: expandedClasses.has(className) }]">
                  ▼
                </span>
              </div>
              
              <div v-if="expandedClasses.has(className)" class="students-list">
                <div 
                  v-for="student in group" 
                  :key="student.id" 
                  class="student-card"
                  @click="openEditModal(student)"
                >
                  <div class="student-avatar">
                    {{ student.name.charAt(0) }}
                  </div>
                  <div class="student-info">
                    <div class="student-name">{{ student.name }}</div>
                    <div class="student-details">
                      <span v-if="student.student_id">学号：{{ student.student_id }}</span>
                      <span>{{ student.email }}</span>
                    </div>
                  </div>
                  <div class="student-actions">
                    <button @click.stop="openEditModal(student)" class="edit-btn">编辑</button>
                    <button @click.stop="handleDelete(student)" class="delete-btn">删除</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="showTeacherSection" class="section">
          <h2 class="section-title">
            <span class="icon">👨‍🏫</span>
            教师列表
            <span class="count">共 {{ teachers.length }} 人</span>
          </h2>
          
          <div class="teachers-list">
            <div 
              v-for="teacher in teachers" 
              :key="teacher.id" 
              class="teacher-card"
              @click="openEditModal(teacher)"
            >
              <div class="teacher-avatar">
                {{ teacher.name.charAt(0) }}
              </div>
              <div class="teacher-info">
                <div class="teacher-name">
                  {{ teacher.name }}
                  <span class="role-badge teacher">教师</span>
                </div>
                <div class="teacher-details">
                  <span v-if="teacher.teacher_id">工号：{{ teacher.teacher_id }}</span>
                  <span>邮箱：{{ teacher.email }}</span>
                </div>
                <div v-if="teacher.college" class="teacher-details">
                  <span>学院：{{ teacher.college }}</span>
                </div>
              </div>
              <div class="teacher-actions">
                <button @click.stop="openEditModal(teacher)" class="edit-btn">编辑</button>
                <button @click.stop="handleDelete(teacher)" class="delete-btn">删除</button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div v-if="showEditModal" class="modal-overlay" @click="closeEditModal">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>编辑用户信息</h3>
          <button @click="closeEditModal" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>账号</label>
            <input v-model="editForm.username" type="text">
          </div>
          <div class="form-group">
            <label>姓名</label>
            <input v-model="editForm.name" type="text">
          </div>
          <div class="form-group">
            <label>邮箱</label>
            <input v-model="editForm.email" type="email">
          </div>
          <div class="form-group">
            <label>角色</label>
            <select v-model="editForm.role">
              <option value="student">学生</option>
              <option value="teacher">教师</option>
            </select>
          </div>
          <div class="form-group" v-if="editForm.role === 'student'">
            <label>学号</label>
            <input v-model="editForm.student_id" type="text">
          </div>
          <div class="form-group" v-else>
            <label>工号</label>
            <input v-model="editForm.teacher_id" type="text">
          </div>
          <div class="form-group">
            <label>电话</label>
            <input v-model="editForm.phone" type="text">
          </div>
          <div class="form-group">
            <label>QQ</label>
            <input v-model="editForm.qq" type="text">
          </div>
          <div class="form-group">
            <label>班级</label>
            <input v-model="editForm.class_name" type="text">
          </div>
          <div class="form-group">
            <label>学院</label>
            <input v-model="editForm.college" type="text">
          </div>
          <div class="form-group">
            <label>新密码（留空则不修改）</label>
            <input v-model="editForm.password" type="password" placeholder="留空则不修改">
          </div>
        </div>
        <div class="modal-footer">
          <button @click="closeEditModal" class="btn btn-secondary">取消</button>
          <button @click="handleUpdate" class="btn btn-primary" :disabled="updating">
            {{ updating ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { adminAPI } from '@/api/admin'

const loading = ref(false)
const updating = ref(false)
const users = ref([])
const searchText = ref('')
const roleFilter = ref('')
const showEditModal = ref(false)
const currentUser = ref(null)
const expandedClasses = ref(new Set())

const editForm = ref({
  username: '',
  name: '',
  email: '',
  role: '',
  student_id: '',
  teacher_id: '',
  phone: '',
  qq: '',
  class_name: '',
  college: '',
  password: ''
})

const students = computed(() => {
  return users.value.filter(user => user.role === 'student')
})

const teachers = computed(() => {
  return users.value.filter(user => user.role === 'teacher')
})

const studentGroups = computed(() => {
  const groups = {}
  students.value.forEach(student => {
    const className = student.class_name || '未分配班级'
    if (!groups[className]) {
      groups[className] = []
    }
    groups[className].push(student)
  })
  return groups
})

const totalStudentCount = computed(() => students.value.length)

const showStudentSection = computed(() => {
  return roleFilter.value === '' || roleFilter.value === 'student'
})

const showTeacherSection = computed(() => {
  return roleFilter.value === '' || roleFilter.value === 'teacher'
})

const toggleClass = (className) => {
  if (expandedClasses.value.has(className)) {
    expandedClasses.value.delete(className)
  } else {
    expandedClasses.value.add(className)
  }
}

const loadUsers = async () => {
  loading.value = true
  try {
    const response = await adminAPI.getUsers({
      role: roleFilter.value,
      search: searchText.value
    })
    users.value = response.data.users
    expandedClasses.value.clear()
  } catch (error) {
    console.error('加载用户失败:', error)
  } finally {
    loading.value = false
  }
}

let searchTimeout = null
const handleSearch = () => {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    loadUsers()
  }, 300)
}

const openEditModal = (user) => {
  if (user.role === 'admin') {
    alert('不能编辑管理员账号')
    return
  }
  
  currentUser.value = user
  editForm.value = {
    username: user.username,
    name: user.name,
    email: user.email,
    role: user.role,
    student_id: user.student_id || '',
    teacher_id: user.teacher_id || '',
    phone: user.phone || '',
    qq: user.qq || '',
    class_name: user.class_name || '',
    college: user.college || '',
    password: ''
  }
  showEditModal.value = true
}

const closeEditModal = () => {
  showEditModal.value = false
  currentUser.value = null
  editForm.value = {
    username: '',
    name: '',
    email: '',
    role: '',
    student_id: '',
    teacher_id: '',
    phone: '',
    qq: '',
    class_name: '',
    college: '',
    password: ''
  }
}

const handleUpdate = async () => {
  if (!currentUser.value) return
  
  updating.value = true
  try {
    const data = { ...editForm.value }
    if (!data.password) {
      delete data.password
    }
    
    await adminAPI.updateUser(currentUser.value.id, data)
    alert('更新成功')
    closeEditModal()
    loadUsers()
  } catch (error) {
    alert('更新失败：' + (error.response?.data?.error || '未知错误'))
  } finally {
    updating.value = false
  }
}

const handleDelete = async (user) => {
  if (user.role === 'admin') {
    alert('不能删除管理员账号')
    return
  }
  
  if (!confirm(`确定要删除用户 ${user.name} 吗？`)) {
    return
  }
  
  try {
    await adminAPI.deleteUser(user.id)
    alert('删除成功')
    loadUsers()
  } catch (error) {
    alert('删除失败：' + (error.response?.data?.error || '未知错误'))
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.user-management {
  padding: 20px;
}

.search-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.search-bar input {
  flex: 1;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
}

.search-bar select {
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  background: white;
  min-width: 120px;
}

.content-area {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #333;
  padding-bottom: 15px;
  border-bottom: 2px solid #f0f0f0;
}

.section-title .icon {
  font-size: 24px;
}

.section-title .count {
  font-size: 14px;
  color: #999;
  font-weight: normal;
  margin-left: auto;
}

.class-groups {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.class-box {
  background: #f8f9fa;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e9ecef;
}

.class-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  cursor: pointer;
  transition: background 0.3s;
}

.class-header:hover {
  background: #e9ecef;
}

.class-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.class-icon {
  font-size: 20px;
}

.class-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.student-count {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
}

.expand-icon {
  color: #999;
  font-size: 12px;
  transition: transform 0.3s;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.students-list {
  padding: 15px;
  background: white;
  border-top: 1px solid #e9ecef;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.student-card {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 12px 15px;
  background: #fafafa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.student-card:hover {
  background: #f0f0f0;
  transform: translateX(5px);
}

.student-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: bold;
}

.student-info {
  flex: 1;
}

.student-name {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.student-details {
  font-size: 12px;
  color: #999;
  display: flex;
  gap: 15px;
}

.student-actions {
  display: flex;
  gap: 8px;
}

.edit-btn {
  background: #e3f2fd;
  color: #2196F3;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s;
}

.edit-btn:hover {
  background: #bbdefb;
}

.delete-btn {
  background: #ffebee;
  color: #f44336;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s;
}

.delete-btn:hover {
  background: #ffcdd2;
}

.teachers-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.teacher-card {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s;
}

.teacher-card:hover {
  background: #e9ecef;
  transform: translateX(5px);
}

.teacher-avatar {
  width: 45px;
  height: 45px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: bold;
}

.teacher-info {
  flex: 1;
}

.teacher-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.role-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: normal;
}

.role-badge.teacher {
  background: #e3f2fd;
  color: #2196F3;
}

.teacher-details {
  font-size: 13px;
  color: #999;
  display: flex;
  gap: 15px;
}

.teacher-actions {
  display: flex;
  gap: 8px;
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
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  color: #555;
  font-weight: 500;
  font-size: 14px;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.modal-footer {
  padding: 20px;
  border-top: 1px solid #eee;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn {
  padding: 10px 20px;
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
  background: #f5f5f5;
  color: #666;
}

.btn-secondary:hover {
  background: #e0e0e0;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading,
.empty {
  text-align: center;
  padding: 40px;
  color: #999;
  background: white;
  border-radius: 12px;
}
</style>
