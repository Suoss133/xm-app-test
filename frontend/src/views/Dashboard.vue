<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="6" v-for="c in cards" :key="c.label">
        <el-card shadow="hover"><el-statistic :title="c.label" :value="c.value" /></el-card>
      </el-col>
    </el-row>
    <el-card class="mt" header="最近任务">
      <el-table :data="recent" size="small" stripe>
        <el-table-column prop="id" label="ID" width="100" />
        <el-table-column prop="suite" label="套件" width="160">
            <template #default="{ row }">
                {{ suiteLabel(row.suite) }}
            </template>
        </el-table-column>
        <el-table-column prop="device_udid" label="设备" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getDevices, jobsSummary } from '@/api/modules'
import { suiteLabel } from '@/utils/suiteLabels'

const devices = ref([])
const summary = ref({ total: 0, by_status: {}, recent: [] })

const cards = computed(() => [
  { label: '在线设备', value: devices.value.filter(d => d.status === 'device').length },
  { label: '任务总数', value: summary.value.total || 0 },
  { label: '运行中', value: summary.value.by_status?.running || 0 },
  { label: '成功', value: summary.value.by_status?.success || 0 },
])
const recent = computed(() => summary.value.recent || [])

function statusType(s) {
  return { success: 'success', failed: 'danger', running: 'warning', pending: 'info', stopped: 'info' }[s] || ''
}

onMounted(async () => {
  try {
    const d = await getDevices()
    devices.value = d.devices || []
  } catch {}
  try {
    summary.value = await jobsSummary()
  } catch {}
})
</script>

<style scoped>
.mt { margin-top: 16px; }
</style>