<template>
  <div class="schedule-page">
    <div class="page-header">
      <h2>授课计划</h2>
      <p class="teacher-info" v-if="teacherName">{{ teacherName }}（工号：{{ teacherId }}）</p>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else-if="schedules.length === 0" class="empty-schedule">
      <span class="empty-icon">📚</span>
      <p>暂无授课安排</p>
      <p class="hint">请联系管理员上传课表</p>
    </div>

    <div v-else class="schedule-wrapper">
      <div class="selector-bar">
        <div class="selector-item">
          <label>学年：</label>
          <select v-model="selectedYear">
            <option v-for="year in yearOptions" :key="year" :value="year">{{ year }}</option>
          </select>
        </div>
        <div class="selector-item">
          <label>学期：</label>
          <select v-model="selectedSemester">
            <option v-for="sem in semesterOptions" :key="sem" :value="sem">{{ sem }}</option>
          </select>
        </div>
        <div class="selector-item">
          <label>周次：</label>
          <select v-model="selectedWeek">
            <option v-for="w in 20" :key="w" :value="w">第{{ w }}周</option>
          </select>
        </div>
        <button class="download-btn" @click="downloadSchedule">
          📥 下载课表图片
        </button>
      </div>
      
      <div class="schedule-container" ref="scheduleRef">
        <div class="schedule-title">
          <span class="semester">{{ selectedYear }} {{ selectedSemester }}</span>
          <span class="teacher-name">{{ teacherName }} 授课计划 · 第{{ selectedWeek }}周</span>
        </div>
        
        <div class="schedule-table">
          <div class="schedule-header">
            <div class="time-column">节次</div>
            <div class="day-column" v-for="day in weekDays" :key="day.value">
              {{ day.label }}
            </div>
          </div>

          <div class="schedule-body">
            <div class="schedule-row" v-for="period in periods" :key="period.value">
              <div class="time-cell">
                <div class="period-number">{{ period.value }}</div>
                <div class="period-time">{{ period.time }}</div>
              </div>
              <div 
                class="day-cell" 
                v-for="day in weekDays" 
                :key="day.value"
              >
                <div 
                  v-for="(course, index) in getCoursesForDisplay(day.value, period.value)" 
                  :key="index"
                  class="course-card"
                  :style="getCourseStyle(course)"
                >
                  <div class="course-name">{{ course.course_name }}</div>
                  <div class="course-location">@{{ course.classroom || '待定' }}</div>
                  <div class="course-class" v-if="course.class_name">{{ course.class_name }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="schedule-summary">
        <h3>授课统计</h3>
        <div class="summary-stats">
          <div class="stat-item">
            <span class="stat-value">{{ filteredSchedules.length }}</span>
            <span class="stat-label">本周课时</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ uniqueCourses }}</span>
            <span class="stat-label">课程数</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ uniqueClasses }}</span>
            <span class="stat-label">班级数</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { scheduleAPI } from '@/api/schedule'

const loading = ref(true)
const teacherId = ref('')
const teacherName = ref('')
const schedules = ref([])
const scheduleGrid = ref({})
const scheduleRef = ref(null)

const currentYear = new Date().getFullYear()
const currentMonth = new Date().getMonth() + 1
const currentDate = new Date()

const startYear = 2018
const endYear = currentYear + 2

const yearOptions = []
for (let y = startYear; y <= endYear; y++) {
  yearOptions.push(`${y}-${y + 1}学年`)
}

const semesterOptions = ['第一学期', '第二学期']

const getCurrentSchoolYear = () => {
  if (currentMonth >= 9) {
    return `${currentYear}-${currentYear + 1}学年`
  } else if (currentMonth >= 1 && currentMonth <= 2) {
    return `${currentYear - 1}-${currentYear}学年`
  } else {
    return `${currentYear - 1}-${currentYear}学年`
  }
}

const getCurrentSemester = () => {
  if (currentMonth >= 9 && currentMonth <= 12) {
    return '第一学期'
  } else if (currentMonth >= 3 && currentMonth <= 7) {
    return '第二学期'
  } else if (currentMonth >= 1 && currentMonth <= 2) {
    return '第一学期'
  }
  return '第一学期'
}

const getCurrentWeek = () => {
  const semesterStart = currentMonth >= 9 
    ? new Date(currentYear, 8, 1)
    : new Date(currentYear, 2, 1)
  
  let startMonday = semesterStart
  const dayOfWeek = semesterStart.getDay()
  if (dayOfWeek !== 1) {
    startMonday = new Date(semesterStart)
    startMonday.setDate(semesterStart.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1))
  }
  
  const diffDays = Math.floor((currentDate - startMonday) / (1000 * 60 * 60 * 24))
  const weekNumber = Math.floor(diffDays / 7) + 1
  
  if (weekNumber >= 1 && weekNumber <= 20) {
    return weekNumber
  }
  return 1
}

const selectedYear = ref(getCurrentSchoolYear())
const selectedSemester = ref(getCurrentSemester())
const selectedWeek = ref(getCurrentWeek())

const weekDays = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

const periods = [
  { value: 1, time: '08:00-08:45' },
  { value: 2, time: '08:55-09:40' },
  { value: 3, time: '10:00-10:45' },
  { value: 4, time: '10:55-11:40' },
  { value: 5, time: '14:00-14:45' },
  { value: 6, time: '14:55-15:40' },
  { value: 7, time: '16:00-16:45' },
  { value: 8, time: '16:55-17:40' },
  { value: 9, time: '19:00-19:45' },
  { value: 10, time: '19:55-20:40' },
  { value: 11, time: '21:00-21:45' },
  { value: 12, time: '21:55-22:40' }
]

const defaultColors = [
  '#74b9ff',
  '#fd79a8',
  '#55efc4',
  '#ffeaa7',
  '#a29bfe',
  '#fab1a0',
  '#81ecec',
  '#ff7675',
  '#fdcb6e',
  '#00b894',
]
const courseColorMap = ref({})
let colorIndex = 0

const filteredSchedules = computed(() => {
  return schedules.value.filter(s => {
    const matchYear = !s.semester_year || s.semester_year === selectedYear.value
    const matchSemester = !s.semester || s.semester === selectedSemester.value
    const matchWeek = selectedWeek.value >= s.start_week && selectedWeek.value <= s.end_week
    return matchYear && matchSemester && matchWeek
  })
})

const filteredGrid = computed(() => {
  const grid = {}
  filteredSchedules.value.forEach(s => {
    const key = `${s.week_day}-${s.period}`
    if (!grid[key]) {
      grid[key] = []
    }
    grid[key].push(s)
  })
  return grid
})

const uniqueCourses = computed(() => {
  const courses = new Set(filteredSchedules.value.map(s => s.course_name))
  return courses.size
})

const uniqueClasses = computed(() => {
  const classes = new Set(filteredSchedules.value.map(s => s.class_name).filter(Boolean))
  return classes.size
})

const getCourseColor = (courseName, predefinedColor) => {
  if (predefinedColor) {
    return predefinedColor
  }
  if (!courseColorMap.value[courseName]) {
    courseColorMap.value[courseName] = defaultColors[colorIndex % defaultColors.length]
    colorIndex++
  }
  return courseColorMap.value[courseName]
}

const getCoursesForDisplay = (day, period) => {
  const key = `${day}-${period}`
  return filteredGrid.value[key] || []
}

const getCourseStyle = (course) => {
  const color = getCourseColor(course.course_name, course.color)
  return {
    background: color
  }
}

const loadSchedule = async () => {
  loading.value = true
  
  try {
    const response = await scheduleAPI.getTeacherSchedule()
    teacherId.value = response.data.teacher_id
    teacherName.value = response.data.teacher_name
    schedules.value = response.data.schedules
    scheduleGrid.value = response.data.schedule_grid
  } catch (err) {
    console.error('加载授课计划失败:', err)
    schedules.value = []
    scheduleGrid.value = {}
  } finally {
    loading.value = false
  }
}

const downloadSchedule = async () => {
  if (!scheduleRef.value) return
  
  try {
    const html2canvas = (await import('html2canvas')).default
    const canvas = await html2canvas(scheduleRef.value, {
      backgroundColor: '#ffffff',
      scale: 2,
      useCORS: true
    })
    
    const link = document.createElement('a')
    link.download = `授课计划_${teacherName.value}_${selectedYear.value}_${selectedSemester.value}_第${selectedWeek.value}周.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  } catch (err) {
    console.error('下载失败:', err)
    alert('下载失败，请稍后重试')
  }
}

onMounted(() => {
  loadSchedule()
})
</script>

<style scoped>
.schedule-page {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 8px 0;
  color: #333;
  font-size: 24px;
}

.teacher-info {
  color: #667eea;
  font-size: 14px;
  margin: 0;
}

.loading {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.selector-bar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.selector-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.selector-item label {
  font-size: 14px;
  color: #555;
  font-weight: 500;
}

.selector-item select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  background: white;
  cursor: pointer;
  min-width: 120px;
}

.selector-item select:focus {
  outline: none;
  border-color: #667eea;
}

.download-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: transform 0.2s, box-shadow 0.2s;
  margin-left: auto;
}

.download-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.schedule-container {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  padding: 20px;
}

.schedule-title {
  text-align: center;
  padding: 16px 0;
  border-bottom: 2px solid #f0f0f0;
  margin-bottom: 16px;
}

.schedule-title .semester {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  display: block;
  margin-bottom: 4px;
}

.schedule-title .teacher-name {
  font-size: 13px;
  color: #667eea;
}

.schedule-table {
  overflow-x: auto;
}

.schedule-header {
  display: flex;
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 8px;
}

.time-column, .day-column {
  flex: 1;
  min-width: 80px;
  padding: 12px 8px;
  text-align: center;
  font-weight: 600;
  font-size: 14px;
  color: #555;
}

.time-column {
  min-width: 60px;
  flex: 0 0 60px;
}

.schedule-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.schedule-row {
  display: flex;
  gap: 4px;
}

.time-cell {
  flex: 0 0 60px;
  min-width: 60px;
  padding: 8px 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  border-radius: 8px;
}

.period-number {
  font-size: 16px;
  font-weight: 700;
  color: #333;
  margin-bottom: 2px;
}

.period-time {
  font-size: 9px;
  color: #999;
  white-space: nowrap;
}

.day-cell {
  flex: 1;
  min-width: 80px;
  min-height: 60px;
  padding: 2px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.course-card {
  border-radius: 8px;
  padding: 6px;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  min-height: 50px;
}

.course-name {
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-align: center;
  line-height: 1.2;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.course-location {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.9);
  margin-top: 2px;
  text-align: center;
}

.course-class {
  font-size: 8px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 2px;
  text-align: center;
}

.empty-schedule {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.empty-icon {
  font-size: 60px;
  display: block;
  margin-bottom: 15px;
}

.empty-schedule p {
  margin: 5px 0;
}

.empty-schedule .hint {
  font-size: 12px;
  color: #bbb;
}

.schedule-summary {
  margin-top: 20px;
  padding: 20px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.schedule-summary h3 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
}

.summary-stats {
  display: flex;
  gap: 30px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #667eea;
}

.stat-label {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

@media (max-width: 768px) {
  .schedule-page {
    padding: 12px;
  }
  
  .selector-bar {
    gap: 12px;
  }
  
  .selector-item select {
    min-width: 100px;
    padding: 6px 8px;
    font-size: 13px;
  }
  
  .download-btn {
    padding: 8px 16px;
    font-size: 13px;
  }
  
  .time-column, .day-column {
    min-width: 60px;
    padding: 8px 4px;
    font-size: 12px;
  }
  
  .time-column {
    min-width: 50px;
    flex: 0 0 50px;
  }
  
  .time-cell {
    min-width: 50px;
    flex: 0 0 50px;
  }
  
  .period-number {
    font-size: 14px;
  }
  
  .period-time {
    display: none;
  }
  
  .day-cell {
    min-width: 60px;
    min-height: 50px;
  }
  
  .course-name {
    font-size: 10px;
  }
  
  .course-location {
    font-size: 8px;
  }
}
</style>
