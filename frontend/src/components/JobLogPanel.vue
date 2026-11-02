<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>
          任务日志
          <el-tag v-if="jobId" size="small" style="margin-left: 8px">{{ jobId }}</el-tag>
        </span>
        <div>
          <el-button size="small" @click="reload">重新加载</el-button>
          <el-button size="small" @click="clear">清空显示</el-button>
        </div>
      </div>
    </template>
    <pre ref="preRef" class="log">{{ text }}</pre>
  </el-card>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { getJobLogs, jobLogWsUrl } from '@/api/modules'

const text = ref('')
const preRef = ref(null)
const jobId = ref('')
let ws = null

function append(line) {
  text.value += (line ?? '') + '\n'
  nextTick(() => {
    if (preRef.value) preRef.value.scrollTop = preRef.value.scrollHeight
  })
}

function clear() {
  text.value = ''
}

async function loadHistory(id) {
  try {
    const res = await getJobLogs(id)
    const lines = res.lines || []
    text.value = lines.length ? lines.join('\n') + '\n' : ''
    nextTick(() => {
      if (preRef.value) preRef.value.scrollTop = preRef.value.scrollHeight
    })
  } catch (e) {
    append('[系统] 加载历史日志失败')
  }
}

function connectWs(id) {
  if (ws) {
    try {
      ws.close()
    } catch (e) {}
    ws = null
  }
  ws = new WebSocket(jobLogWsUrl(id))
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'history') {
        const lines = msg.lines || []
        if (lines.length) {
          text.value = lines.join('\n') + '\n'
          nextTick(() => {
            if (preRef.value) preRef.value.scrollTop = preRef.value.scrollHeight
          })
        }
      } else if (msg.type === 'log') {
        append(msg.line)
      } else if (msg.type === 'done') {
        append('—— 任务日志结束 ——')
      }
    } catch (e) {
      append(ev.data)
    }
  }
  ws.onerror = () => append('[WS] 连接错误')
}

async function openJob(id) {
  jobId.value = id
  clear()
  await loadHistory(id)
  connectWs(id)
}

async function reload() {
  if (!jobId.value) return
  await openJob(jobId.value)
}

defineExpose({ openJob, clear, append, reload })
</script>

<style scoped>
.hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.log {
  height: 520px;
  overflow: auto;
  margin: 0;
  background: #0d1117;
  color: #c9d1d9;
  padding: 12px;
  font-size: 12px;
  line-height: 1.5;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>