<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>任务历史</span>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>
    </template>
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="100" />
      <el-table-column prop="suite" label="套件" width="160">
        <template #default="{ row }">
            {{ suiteLabel(row.suite) }}
        </template>
      </el-table-column>
      <el-table-column prop="device_udid" label="设备" min-width="180" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="message" label="信息" show-overflow-tooltip />
      <el-table-column prop="created_at" label="创建" width="170" />
      <el-table-column prop="finished_at" label="结束" width="170" />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goLog(row.id)">查看日志</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listJobs } from '@/api/modules'
import { suiteLabel } from '@/utils/suiteLabels'

const router = useRouter()
const list = ref([])
const loading = ref(false)

function statusType(s) {
  return (
    {
      success: 'success',
      failed: 'danger',
      running: 'warning',
      pending: 'info',
      stopped: 'info',
    }[s] || 'info'
  )
}

async function load() {
  loading.value = true
  try {
    list.value = await listJobs(50)
  } finally {
    loading.value = false
  }
}

function goLog(id) {
  router.push({ path: '/jobs', query: { job_id: id } })
}

onMounted(load)
</script>

<style scoped>
.hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>