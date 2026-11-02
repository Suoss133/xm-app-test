<!-- Reports.vue -->
<template>
  <el-card header="测试报告">
    <el-button @click="load" :loading="loading">刷新</el-button>
    <el-divider />
    <h4>Allure</h4>
    <pre v-if="data.allure_results">{{ data.allure_results }}</pre>
    <el-empty v-else description="暂无 Allure 结果" />
    <h4>Excel</h4>
    <el-table :data="data.excel || []" size="small">
      <el-table-column prop="name" label="文件" />
      <el-table-column prop="mtime" label="时间" width="180" />
      <el-table-column prop="size" label="大小" width="100" />
    </el-table>
    <h4>最近截图</h4>
    <el-table :data="data.screenshots || []" size="small">
      <el-table-column prop="name" label="文件" />
      <el-table-column prop="mtime" label="时间" width="180" />
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getReports } from '@/api/modules'
const data = ref({})
const loading = ref(false)
async function load() {
  loading.value = true
  try { data.value = await getReports() } finally { loading.value = false }
}
onMounted(load)
</script>