<template>
  <el-row :gutter="16">
    <el-col :span="8">
      <el-card header="提交任务">
        <el-form label-width="110px">
          <el-form-item label="设备" required>
            <el-select v-model="form.device_udid" filterable style="width: 100%">
              <el-option
                v-for="d in devices"
                :key="d.udid"
                :label="d.udid + (d.model ? ` (${d.model})` : '')"
                :value="d.udid"
                :disabled="d.status !== 'device'"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="套件" required>
            <el-select v-model="form.suite" style="width: 100%" @change="onSuiteChange">
              <el-option
                v-for="s in suites"
                :key="s.name"
                :label="`${suiteLabel(s.name)} [${s.current_app}]`"
                :value="s.name"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="目标 App">
            <el-input v-model="form.current_app" disabled />
          </el-form-item>
          <el-divider>参数（可改本次）</el-divider>
          <el-form-item
            v-for="(v, k) in form.params"
            :key="k"
            :label="paramLabel(k)"
          >
            <el-input v-model="form.params[k]" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="starting" @click="start">开始执行</el-button>
            <el-button type="danger" :disabled="!jobId" @click="stop">停止</el-button>
          </el-form-item>
        </el-form>
        <el-descriptions v-if="jobId" :column="1" size="small" border class="mt">
          <el-descriptions-item label="Job ID">{{ jobId }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(statusRaw)">{{ status }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
    <el-col :span="16">
      <JobLogPanel ref="logRef" />
    </el-col>
  </el-row>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getDevices,
  getSuites,
  createJob,
  stopJob,
  getJob,
} from '@/api/modules'
import { paramLabel } from '@/utils/paramLabels'
import JobLogPanel from '@/components/JobLogPanel.vue'
import { suiteLabel } from '@/utils/suiteLabels'

const route = useRoute()
const router = useRouter()

const devices = ref([])
const suites = ref([])
const form = ref({
  device_udid: '',
  suite: '',
  current_app: '',
  params: {},
})
const jobId = ref('')
const status = ref('-')
const statusRaw = ref('')
const starting = ref(false)
const logRef = ref(null)
let timer = null

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

function onSuiteChange(name) {
  const s = suites.value.find((i) => i.name === name)
  if (!s) return
  form.value.current_app = s.current_app || ''
  form.value.params = { ...(s.parameter || {}) }
  if (s.device_udid && !form.value.device_udid) {
    form.value.device_udid = s.device_udid
  }
}

function normalizeParams(raw) {
  const out = {}
  for (const [k, v] of Object.entries(raw || {})) {
    if (v === null || v === undefined) continue
    const s = String(v).trim()
    if (s === '') {
      out[k] = s
      continue
    }
    // 纯数字 -> number（test_count / sleep_control 等）
    if (/^-?\d+$/.test(s)) {
      out[k] = parseInt(s, 10)
    } else if (/^-?\d+\.\d+$/.test(s)) {
      out[k] = parseFloat(s)
    } else {
      out[k] = s
    }
  }
  return out
}

async function start() {
  if (!form.value.device_udid || !form.value.suite) {
    return ElMessage.warning('请选择设备和套件')
  }
  starting.value = true
  try {
    const payload = {
      suite: form.value.suite,
      device_udid: form.value.device_udid,
      current_app: form.value.current_app || undefined,
      params: normalizeParams({ ...form.value.params }),
    }
    console.log('[Jobs] 提交参数', payload)

    const res = await createJob(payload)
    jobId.value = res.id
    statusRaw.value = res.status
    status.value = res.status
    await logRef.value?.openJob(res.id)
    router.replace({ query: { job_id: res.id } })
    pollStatus()
    ElMessage.success('任务已提交')
  } finally {
    starting.value = false
  }
}

async function stop() {
  if (!jobId.value) return
  await stopJob(jobId.value)
  ElMessage.info('已请求停止')
}

function pollStatus() {
  clearInterval(timer)
  timer = setInterval(async () => {
    if (!jobId.value) return
    try {
      const j = await getJob(jobId.value)
      statusRaw.value = j.status
      status.value = j.status + (j.message ? ` (${j.message})` : '')
      if (['success', 'failed', 'stopped'].includes(j.status)) {
        clearInterval(timer)
      }
    } catch (e) {}
  }, 2000)
}

onMounted(async () => {
  const [d, s] = await Promise.all([getDevices(), getSuites()])
  devices.value = d.devices || []
  suites.value = s.suites || []

  const qid = route.query.job_id
  if (qid) {
    jobId.value = String(qid)
    await logRef.value?.openJob(String(qid))
    pollStatus()
  }
})

onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.mt {
  margin-top: 12px;
}
</style>