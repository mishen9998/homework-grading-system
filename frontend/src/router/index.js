import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { cancelPendingReads } from '@/api/index'

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/loading',
    name: 'Loading',
    component: () => import('@/views/Loading.vue')
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue')
  },
  {
    path: '/student',
    name: 'StudentDashboard',
    component: () => import('@/views/StudentDashboard.vue'),
    meta: { requiresAuth: true, role: 'student' },
    redirect: '/student/home',
    children: [
      { path: 'knowledge', name: 'StudentKnowledge', component: () => import('@/views/KnowledgeLibrary.vue') },
      {
        path: 'home',
        name: 'StudentHome',
        component: () => import('@/views/StudentHome.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'course/:id',
        name: 'CourseDetail',
        component: () => import('@/views/CourseDetail.vue')
      },
      {
        path: 'messages',
        name: 'StudentMessages',
        component: () => import('@/views/StudentMessages.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'profile',
        name: 'StudentProfile',
        component: () => import('@/views/StudentProfile.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'schedule',
        name: 'StudentSchedule',
        component: () => import('@/views/StudentSchedule.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'chat',
        name: 'StudentChat',
        component: () => import('@/views/Chat.vue')
      }
    ]
  },
  {
    path: '/teacher',
    name: 'TeacherDashboard',
    component: () => import('@/views/TeacherDashboard.vue'),
    meta: { requiresAuth: true, role: 'teacher' },
    redirect: '/teacher/home',
    children: [
      { path: 'knowledge', name: 'TeacherKnowledge', component: () => import('@/views/KnowledgeLibrary.vue') },
      {
        path: 'home',
        name: 'TeacherHome',
        component: () => import('@/views/TeacherHome.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'messages',
        name: 'TeacherMessages',
        component: () => import('@/views/TeacherMessages.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'profile',
        name: 'TeacherProfile',
        component: () => import('@/views/TeacherProfile.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'teaching-plan',
        name: 'TeacherSchedule',
        component: () => import('@/views/TeacherSchedule.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'course/:id',
        name: 'TeacherCourseDetail',
        component: () => import('@/views/TeacherCourseDetail.vue')
      },
      {
        path: 'assignment/:assignmentId/statistics',
        name: 'AssignmentStatistics',
        component: () => import('@/views/AssignmentStatistics.vue')
      },
      {
        path: 'chat',
        name: 'TeacherChat',
        component: () => import('@/views/Chat.vue')
      }
    ]
  },
  {
    path: '/admin',
    name: 'AdminDashboard',
    component: () => import('@/views/AdminDashboard.vue'),
    meta: { requiresAuth: true, role: 'admin' },
    redirect: '/admin/home',
    children: [
      { path: 'knowledge', name: 'AdminKnowledge', component: () => import('@/views/KnowledgeLibrary.vue') },
      {
        path: 'home',
        name: 'AdminHome',
        component: () => import('@/views/AdminHome.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/AdminUsers.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'import',
        name: 'AdminImport',
        component: () => import('@/views/AdminImport.vue')
      },
      {
        path: 'schedule',
        name: 'AdminSchedule',
        component: () => import('@/views/AdminSchedule.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'profile',
        name: 'AdminProfile',
        component: () => import('@/views/AdminProfile.vue'),
        meta: { keepAlive: true }
      },
      {
        path: 'chat',
        name: 'AdminChat',
        component: () => import('@/views/Chat.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  cancelPendingReads()
  
  const authStore = useAuthStore()
  
  if (to.meta.requiresAuth) {
    if (!authStore.isAuthenticated || !authStore.user) {
      next('/login')
    } else if (to.meta.role && authStore.user.role !== to.meta.role) {
      if (authStore.user.role === 'student') {
        next('/student')
      } else if (authStore.user.role === 'teacher') {
        next('/teacher')
      } else if (authStore.user.role === 'admin') {
        next('/admin')
      } else {
        next('/login')
      }
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
