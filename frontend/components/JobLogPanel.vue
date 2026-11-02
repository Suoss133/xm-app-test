<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>实时日志</span>
        <el-button size="small" @click="clear">清空</el-button>
      </div>
    </template>
    <pre ref="preRef" class="log">{{ text }}</pre>
  </el-card>
</template>

<script setup>
import { ref, nextTick } from 'vue'

const text = ref('')
const preRef = ref(null)
let ws = null

function append(line) {
  text.value += line + '\n'
  nextTick(() => {
    if (preRef.value) preRef.value.scrollTop = preRef.value.scrollHeight
  })
}
function clear() {
  text.value = ''
}
function connect(url) {
  if (ws) {
    ws.close()
    ws = null
  }
  ws = new WebSocket(url)
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'log') append(msg.line)
      if (msg.type === 'done') append('—— 任务日志结束 ——')
    } catch {
      append(ev.data)
    }
  }
  ws.onerror = () => append('[WS] 连接错误')
  ws.onclose = () => append('[WS] 已断开')
}

defineExpose({ connect, clear, append })
</script>

<style scoped>
.hd { display: flex; justify-content: space-between; align-items: center; }
.log {
  height: 520px; overflow: auto; margin: 0;
  background: #0d1117; color: #c9d1d9;
  padding: 12px; font-size: 12px; line-height: 1.5;
  border-radius: 4px;
}
</style>