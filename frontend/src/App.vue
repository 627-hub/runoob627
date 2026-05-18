<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-left">
        <h2>股票选股系统</h2>
        <el-menu mode="horizontal" :default-active="route.path" router class="header-menu">
          <el-menu-item index="/">股票列表</el-menu-item>
        </el-menu>
      </div>
      <div class="header-right">
        <el-tag :type="refreshStatus.running ? 'warning' : 'success'" class="status-tag">
          {{ refreshStatus.running ? '刷新中' : '就绪' }}
        </el-tag>
        <span class="last-update">更新: {{ refreshStatus.last_run || '-' }}</span>
      </div>
    </el-header>

    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { systemApi } from '@/api'

const route = useRoute()
const refreshStatus = ref({ running: false, last_run: null })

let statusTimer = null

async function loadRefreshStatus() {
  try {
    const res = await systemApi.getRefreshStatus()
    refreshStatus.value = res.data || {}
  } catch (e) { console.error(e) }
}

onMounted(() => {
  loadRefreshStatus()
  statusTimer = setInterval(loadRefreshStatus, 30000)
})

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer)
})
</script>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }

.app-container { min-height: 100vh; flex-direction: column; }
.app-header { display: flex; justify-content: space-between; align-items: center; background: #fff; border-bottom: 1px solid #e4e7ed; padding: 0 20px; }
.header-left { display: flex; align-items: center; gap: 20px; }
.header-left h2 { margin: 0; color: #303133; }
.header-menu { border: none; background: transparent; }
.header-right { display: flex; align-items: center; gap: 15px; }
.status-tag { margin-right: 5px; }
.last-update { font-size: 12px; color: #909399; }
.app-main { padding: 15px; background: #f5f7fa; }
</style>