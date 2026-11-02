import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '总览' } },
      { path: 'devices', name: 'Devices', component: () => import('@/views/Devices.vue'), meta: { title: '设备' } },
      { path: 'suites', name: 'Suites', component: () => import('@/views/Suites.vue'), meta: { title: '套件' } },
      { path: 'jobs', name: 'Jobs', component: () => import('@/views/Jobs.vue'), meta: { title: '执行任务' } },
      { path: 'history', name: 'History', component: () => import('@/views/JobHistory.vue'), meta: { title: '任务历史' } },
      { path: 'reports', name: 'Reports', component: () => import('@/views/Reports.vue'), meta: { title: '报告' } },
    ],
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})