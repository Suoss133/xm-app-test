<template>
  <el-row :gutter="16">
    <el-col :span="8">
      <el-card header="套件列表">
        <el-menu :default-active="active" @select="onSelect">
          <el-menu-item v-for="s in suites" :key="s.name" :index="s.name">
            {{ suiteLabel(s.name) }}
            <el-tag size="small" style="margin-left: 8px">{{ s.current_app }}</el-tag>
          </el-menu-item>
        </el-menu>
      </el-card>
    </el-col>
    <el-col :span="16">
      <el-card v-if="current">
        <template #header>
          <div class="hd">
            <span>编辑：{{ current.name }}</span>
            <el-button type="primary" :loading="saving" @click="save">保存</el-button>
          </div>
        </template>
        <el-form label-width="140px">
          <el-form-item label="目标 App">
            <el-select v-model="form.current_app" style="width: 260px">
              <el-option v-for="a in apps" :key="a" :label="a" :value="a" />
            </el-select>
          </el-form-item>
          <el-form-item label="默认设备 UDID">
            <el-input v-model="form.device_udid" placeholder="可空，执行时再选" />
          </el-form-item>
          <el-divider>业务参数</el-divider>
          <el-form-item
            v-for="(val, key) in form.parameter"
            :key="key"
            :label="paramLabel(key)"
          >
            <el-input v-model="form.parameter[key]" />
          </el-form-item>
        </el-form>
      </el-card>
      <el-empty v-else description="请选择左侧套件" />
    </el-col>
  </el-row>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSuites, updateSuite } from '@/api/modules'
import { paramLabel } from '@/utils/paramLabels'
import { suiteLabel } from '@/utils/suiteLabels'

const apps = ['Humbirdy', 'Koocam', 'Koobird', 'baseus', 'SoliomHome']
const suites = ref([])
const active = ref('')
const current = ref(null)
const form = ref({ current_app: '', device_udid: '', parameter: {} })
const saving = ref(false)

async function load() {
  const res = await getSuites()
  suites.value = res.suites || []
}

function onSelect(name) {
  active.value = name
  const s = suites.value.find((i) => i.name === name)
  current.value = s
  form.value = {
    current_app: s.current_app || '',
    device_udid: s.device_udid || '',
    parameter: { ...(s.parameter || {}) },
  }
}

async function save() {
  saving.value = true
  try {
    await updateSuite(current.value.name, {
      current_app: form.value.current_app,
      device_udid: form.value.device_udid,
      parameter: form.value.parameter,
    })
    ElMessage.success('已保存')
    await load()
    onSelect(current.value.name)
  } finally {
    saving.value = false
  }
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