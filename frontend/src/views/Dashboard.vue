<template>
  <div class="dashboard">
    <div class="stats-row">
      <div class="stat-card" v-for="card in statCards" :key="card.label"
        :style="{ '--card-color': card.color }">
        <div class="stat-icon">
          <el-icon :size="28"><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-body">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </div>
      </div>
    </div>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>快捷筛选</span>
        </div>
      </template>
      <div class="quick-filters">
        <el-button @click="goStocks({ sort_by: 'score', sort_order: 'desc' })" round>按评分排序</el-button>
        <el-button type="danger" @click="goStocks({ min_pct_change: 9.9 })" round>涨停股票</el-button>
        <el-button type="warning" @click="goStocks({ min_pct_change: 5 })" round>涨幅 ≥5%</el-button>
        <el-button @click="goStocks({ min_pct_change: 0 })" round>上涨股票</el-button>
        <el-button @click="goStocks({})" round>全部股票</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { DataLine, TrendCharts, WarnTriangleFilled, Calendar } from '@element-plus/icons-vue'
import { stocksApi } from '@/api'

const router = useRouter()
const stats = ref({
  total_stocks: 0, up_count: 0, limit_up_count: 0, latest_date: null
})

const statCards = ref([
  { icon: DataLine, label: '股票总数', value: '-', color: '#409eff' },
  { icon: TrendCharts, label: '上涨股票', value: '-', color: '#67c23a' },
  { icon: WarnTriangleFilled, label: '涨停股票', value: '-', color: '#f56c6c' },
  { icon: Calendar, label: '最新交易日', value: '-', color: '#e6a23c' },
])

onMounted(async () => {
  try {
    const res = await stocksApi.getStats()
    stats.value = res.data
    statCards.value = [
      { icon: DataLine, label: '股票总数', value: stats.value.total_stocks ?? '-', color: '#409eff' },
      { icon: TrendCharts, label: '上涨股票', value: stats.value.up_count ?? '-', color: '#67c23a' },
      { icon: WarnTriangleFilled, label: '涨停股票', value: stats.value.limit_up_count ?? '-', color: '#f56c6c' },
      { icon: Calendar, label: '最新交易日', value: stats.value.latest_date || '-', color: '#e6a23c' },
    ]
  } catch (e) {}
})

function goStocks(q) {
  router.push({ path: '/stocks', query: q })
}
</script>

<style scoped>
.dashboard { max-width: 1200px; margin: 0 auto; }

.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 24px; }

.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  border-left: 4px solid var(--card-color);
}
.stat-icon {
  width: 48px; height: 48px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  color: var(--card-color);
  background: color-mix(in srgb, var(--card-color) 10%, transparent);
}
.stat-value { font-size: 26px; font-weight: 700; color: #303133; line-height: 1.2; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }

.section-card { border-radius: 12px; }
.section-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: 1px solid #f0f2f5; }
.section-header { font-size: 15px; font-weight: 600; color: #303133; }

.quick-filters { display: flex; gap: 10px; flex-wrap: wrap; padding: 4px 0; }
</style>
