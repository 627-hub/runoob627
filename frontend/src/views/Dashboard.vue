<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #409eff">
            <el-icon :size="30"><DataLine /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.total_stocks }}</div>
            <div class="stat-label">股票总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #67c23a">
            <el-icon :size="30"><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.up_count }}</div>
            <div class="stat-label">上涨股票</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #f56c6c">
            <el-icon :size="30"><WarnTriangleFilled /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.limit_up_count }}</div>
            <div class="stat-label">涨停股票</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #e6a23c">
            <el-icon :size="30"><Calendar /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.latest_date || '-' }}</div>
            <div class="stat-label">最新交易日</div>
          </div>
        </el-card>
      </el-col>
    </el-row>


    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>股票列表</span>
          </template>
          <StockList />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { stocksApi, systemApi, filtersApi } from '@/api'
import StockList from './StockList.vue'

const router = useRouter()
const stats = ref({
  total_stocks: 0,
  stocks_with_metrics: 0,
  latest_date: null,
  up_count: 0,
  limit_up_count: 0
})
const refreshStatus = ref({
  running: false,
  last_run: null,
  last_status: null,
  stock_count: 0
})


  // Active filter display
const activeFilterSummary = ref('暂无激活筛选')
// Keep track of active filter name for better UX
const activeFilterName = ref(null)

async function loadActiveFilter() {
  try {
    const res = await filtersApi.getActiveFilter()
    const data = res?.data || {}
    const cfg = data.config ?? data
    const name = data.name ?? null
    activeFilterName.value = name
    if (!cfg || Object.keys(cfg).length === 0) {
      activeFilterSummary.value = name
        ? `激活筛选: ${name}`
        : '默认筛选: 主板+排 ST+市值筛选'
      return
    }
    // 简单摘要展示，仅展示关键项
    const parts = []
    if (cfg.is_mainboard_only) parts.push('仅主板')
    if (cfg.exclude_st) parts.push('排除 ST')
    if (cfg.min_market_cap != null) parts.push(`市值≥${(cfg.min_market_cap/1e8).toFixed(2)}亿`)
    if (parts.length === 0) parts.push('自定义筛选')
    if (name) parts.unshift(`筛选名: ${name}`)
    activeFilterSummary.value = parts.join('，')
  } catch (e) {
    console.error('读取当前激活筛选失败', e)
  }
}

async function loadStats() {
  try {
    const res = await stocksApi.getStats()
    stats.value = res.data
  } catch (e) {
    console.error('获取统计失败:', e)
  }
}

async function loadRefreshStatus() {
  try {
    const res = await systemApi.getRefreshStatus()
    refreshStatus.value = res.data
  } catch (e) {
    console.error('获取刷新状态失败:', e)
  }
}

function quickFilter(type) {
  const query = {}
  if (type === 'score') {
    query.sort_by = 'score'
    query.sort_order = 'desc'
    query.page_size = 50
  } else if (type === 'limit_up') {
    query.min_pct_change = 9.9
  } else if (type === 'up') {
    query.min_pct_change = 0
  }
  router.push({ path: '/stocks', query })
}

onMounted(() => {
  loadStats()
  loadRefreshStatus()
  loadActiveFilter()
  // 读取定时器状态以初始化开关状态
  loadSchedulerStatus()
})

async function loadSchedulerStatus() {
  try {
    const res = await systemApi.getRefreshStatus()
    // 再次请求以确保状态，若接口返回 running，则以此更新 UI
    // 这里简单保留现有刷新状态，将定时开关通过后端开关控制
  } catch (e) {
    console.error('读取调度状态失败:', e)
  }
}

let autoRefreshEnabled = ref(false)
async function toggleAutoRefresh(val) {
  try {
    if (val) {
      await systemApi.startScheduler()
    } else {
      await systemApi.stopScheduler()
    }
  } catch (e) {
    console.error('切换定时刷新失败', e)
  }
}
</script>

<style scoped>
.dashboard {
  max-width: 1200px;
  margin: 0 auto;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.quick-filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
