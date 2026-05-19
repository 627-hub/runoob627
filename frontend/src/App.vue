<template>
  <div class="app-layout">
    <header class="app-header">
      <div class="header-inner">
        <div class="header-left">
          <router-link to="/" class="logo">股票选股系统</router-link>
          <nav class="nav">
            <router-link to="/" class="nav-item" active-class="nav-active">概览</router-link>
            <router-link to="/stocks" class="nav-item" active-class="nav-active">股票列表</router-link>
            <router-link to="/filters" class="nav-item" active-class="nav-active">公式配置</router-link>
          </nav>
        </div>
        <div class="header-right">
          <el-tag :type="statusColor" size="small" effect="dark">
            {{ refreshStatus.running ? '刷新中' : '就绪' }}
          </el-tag>
          <span class="update-time">更新: {{ refreshStatus.last_run ? refreshStatus.last_run.slice(0, 16).replace('T', ' ') : '-' }}</span>
        </div>
      </div>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { systemApi } from '@/api'

const refreshStatus = ref({ running: false, last_run: null })
const statusColor = computed(() => refreshStatus.value.running ? 'warning' : 'success')
let timer = null

async function load() {
  try {
    const res = await systemApi.getRefreshStatus()
    refreshStatus.value = res.data || {}
  } catch (e) {}
}
onMounted(() => { load(); timer = setInterval(load, 30000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  background: #f0f2f5;
  color: #303133;
}
.app-layout { min-height: 100vh; display: flex; flex-direction: column; }

.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
  position: sticky; top: 0; z-index: 100;
}
.header-inner {
  max-width: 1500px; margin: 0 auto;
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 24px; height: 56px;
}
.header-left { display: flex; align-items: center; gap: 32px; }
.logo {
  font-size: 18px; font-weight: 700; color: #303133;
  text-decoration: none;
}
.logo:hover { color: #409eff; }
.nav { display: flex; gap: 4px; }
.nav-item {
  padding: 6px 16px; border-radius: 6px;
  font-size: 14px; color: #606266; text-decoration: none;
  transition: all .2s;
}
.nav-item:hover { background: #f0f2f5; color: #303133; }
.nav-active { background: #ecf5ff; color: #409eff; font-weight: 600; }

.header-right { display: flex; align-items: center; gap: 12px; }
.update-time { font-size: 12px; color: #909399; }

.app-main {
  flex: 1;
  max-width: 1500px; width: 100%;
  margin: 20px auto 40px;
  padding: 0 24px;
}
</style>
