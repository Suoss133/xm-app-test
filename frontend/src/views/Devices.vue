<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>设备列表</span>
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>
    </template>
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="udid" label="UDID" min-width="220" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.status === 'device' ? 'success' : 'danger'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="model" label="型号" width="160" />
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDevices } from '@/api/modules'

const list = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await getDevices()
    list.value = res.devices || []
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.hd { display: flex; justify-content: space-between; align-items: center; }
</style>