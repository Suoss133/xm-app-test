<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">压测调度台</div>
      <el-menu :default-active="route.path" router background-color="#1d1e2c" text-color="#bbb" active-text-color="#409eff">
        <el-menu-item index="/dashboard"><el-icon><Odometer /></el-icon>总览</el-menu-item>
        <el-menu-item index="/devices"><el-icon><Iphone /></el-icon>设备</el-menu-item>
        <el-menu-item index="/suites"><el-icon><SetUp /></el-icon>套件配置</el-menu-item>
        <el-menu-item index="/jobs"><el-icon><VideoPlay /></el-icon>执行任务</el-menu-item>
        <el-menu-item index="/history"><el-icon><List /></el-icon>任务历史</el-menu-item>
        <el-menu-item index="/reports"><el-icon><Document /></el-icon>报告</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span>{{ route.meta.title || '控制台' }}</span>
        <el-tag type="success" size="small">API: {{ apiBase }}</el-tag>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
const apiBase = import.meta.env.VITE_API_BASE || ''
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #1d1e2c; }
.logo { color: #fff; font-weight: 700; padding: 20px 16px; font-size: 16px; }
.header {
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid #eee; background: #fff;
}
.main { background: #f5f7fa; }
</style>