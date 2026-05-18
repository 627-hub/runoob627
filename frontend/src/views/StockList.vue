<template>
  <div class="stock-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>股票列表 (共 {{ total }} 只)</span>
          <div class="header-actions">
            <span class="refresh-status">{{ refreshStatus }}</span>
            <el-switch v-model="autoRefresh" active-text="自动刷新" @change="toggleAutoRefresh" />
          </div>
        </div>
      </template>

      <!-- 当前激活筛选信息 -->
      <div class="active-filter-info">
        <el-alert :closable="false" type="info">
          <template #title>
            当前筛选: {{ activeFilterName }} 
            <el-tag size="small">仅主板</el-tag>
            <el-tag size="small">排除ST</el-tag>
            <el-tag size="small">市值≥{{ minMarketCapYuan }}亿</el-tag>
          </template>
        </el-alert>
      </div>

      <!-- 筛选工具栏 -->
      <div class="filter-bar">
        <div class="formula-section">
          <span class="label">公式:</span>
          <el-checkbox-group v-model="selectedFormulas" class="formula-checkboxes">
            <el-checkbox v-for="f in availableFormulas" :key="f" :label="f" border size="small">{{ f }}</el-checkbox>
          </el-checkbox-group>
          <el-button type="primary" :loading="applying" @click="applyFormulas">应用筛选</el-button>
        </div>
        
        <el-divider />
        
        <el-form inline>
          <el-form-item label="搜索">
            <el-input v-model="params.search" placeholder="代码/名称" clearable @change="loadData" style="width: 90px" />
          </el-form-item>
          <el-form-item label="市场">
            <el-select v-model="params.market" clearable @change="loadData" style="70px">
              <el-option label="上海" value="SH" />
              <el-option label="深圳" value="SZ" />
            </el-select>
          </el-form-item>
          <el-form-item label="板块">
            <el-select v-model="params.sector" clearable filterable placeholder="全部板块" @change="loadData" style="140px">
              <el-option v-for="s in sectorsList" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="板块类型">
            <el-select v-model="params.block_type" clearable placeholder="全部类型" @change="loadData" style="90px">
              <el-option v-for="t in sectorTypes" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="仅主板">
            <el-switch v-model="params.is_mainboard_only" @change="loadData" />
          </el-form-item>
          <el-form-item label="排除ST">
            <el-switch v-model="params.exclude_st" @change="loadData" />
          </el-form-item>
          <el-form-item label="流通市值(亿)">
            <el-input-number v-model="params.min_market_cap_yi" :min="0" :step="1" controls-position="right" style="80px" @change="loadData" placeholder="不限" />
          </el-form-item>
          <el-form-item label="最小涨幅%">
            <el-input-number v-model="params.min_pct_change" :min="0" :max="20" :step="0.5" controls-position="right" style="70px" @change="loadData" />
          </el-form-item>
          <el-form-item>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 股票表格 -->
      <el-table v-loading="loading" :data="stocks" stripe height="520" style="width: 100%" :header-cell-style="{background:'#f5f7fa',color:'#333',fontWeight:'bold'}">
        <el-table-column prop="code" label="代码" width="110" sortable fixed />
        <el-table-column prop="name" label="名称" width="100" show-overflow-tooltip />
        <el-table-column prop="market" label="市场" width="70">
          <template #default="{ row }"><el-tag size="small">{{ row.market }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="pct_change" label="涨跌幅%" width="100" sortable>
          <template #default="{ row }">
            <span :class="row.pct_change > 9 ? 'text-success' : row.pct_change > 0 ? 'text-warning' : 'text-danger'">
              {{ row.pct_change?.toFixed(2) || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="close" label="现价" width="90">
          <template #default="{ row }">{{ row.close?.toFixed(2) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="成交额(亿)" width="105">
          <template #default="{ row }">{{ row.amount ? (row.amount/1e8).toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="volume" label="成交量(万)" width="110">
          <template #default="{ row }">{{ row.volume ? (row.volume/1e4).toFixed(0) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="score" label="今日评分" width="90" sortable>
          <template #default="{ row }">
            <el-tag :type="row.score >= 80 ? 'success' : row.score >= 60 ? 'warning' : 'danger'" size="small">
              {{ row.score?.toFixed(0) || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="avg_score_8d" label="8日评分" width="90" sortable>
          <template #default="{ row }">
            <el-tag :type="row.avg_score_8d >= 80 ? 'success' : row.avg_score_8d >= 60 ? 'warning' : 'danger'" size="small">
              {{ row.avg_score_8d?.toFixed(0) || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sectors" label="板块" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-popover placement="bottom" :width="300" trigger="hover">
              <template #reference>
                <div class="sector-preview">
                  <el-tag v-for="s in (row.sectors||'').split(',').filter(Boolean).slice(0,3)" :key="s" size="small" type="success" class="tag">{{ s }}</el-tag>
                  <span v-if="(row.sectors||'').split(',').filter(Boolean).length > 3" class="more-tag">+{{ (row.sectors||'').split(',').filter(Boolean).length - 3 }}</span>
                </div>
              </template>
              <div v-for="s in (row.sectors||'').split(',').filter(Boolean)" :key="s" class="sector-item">{{ s }}</div>
              <div v-if="row.block_types && row.block_types.length" class="sector-types-divider">
                <el-tag v-for="t in row.block_types" :key="t" size="small" :type="typeTagType(t)" class="tag">{{ t }}</el-tag>
              </div>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column prop="formulas" label="公式来源" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="f in (row.formulas||[])" :key="f" size="small" type="info" class="tag">{{ f }}</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.page_size"
          :total="total"
          :page-sizes="[20,50,100,200]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="loadData"
          @size-change="loadData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { stocksApi, formulasApi, systemApi, filtersApi } from '@/api'
import { ElMessage } from 'element-plus'

const stocks = ref([])
const total = ref(0)
const loading = ref(false)
const applying = ref(false)
const autoRefresh = ref(false)

// 激活筛选信息
const activeFilterName = ref('默认筛选')
const minMarketCapYuan = computed(() => params.min_market_cap_yi || 20)
const refreshStatus = ref('就绪')

const availableFormulas = ref([])
const selectedFormulas = ref([])
const sectorsList = ref([])  // 板块列表
const sectorsByType = ref({})  // 按类型分组的板块
const sectorTypes = ref([])  // 板块类型列表（行业/概念/地区/风格/指数/其他）

const params = reactive({
  page: 1, page_size: 50, sort_by: 'score', sort_order: 'desc',
  search: '', market: '', sector: '', block_type: '', is_mainboard_only: true, exclude_st: true,
  min_market_cap_yi: 20, min_pct_change: null,
  formulas: []  // 按公式筛选（多选）
})

async function loadActiveFilter() {
  try {
    const res = await filtersApi.getActiveFilter()
    if (res.data?.config) {
      const cfg = res.data.config
      params.is_mainboard_only = cfg.is_mainboard_only ?? true
      params.exclude_st = cfg.exclude_st ?? true
      params.min_market_cap_yi = cfg.min_market_cap ? (cfg.min_market_cap / 1e8) : 20
      activeFilterName.value = res.data.name || '默认筛选'
    }
  } catch (e) { console.error(e) }
}

async function loadFormulas() {
  try {
    const res = await formulasApi.getCategories()
    const cats = res.data || {}
    availableFormulas.value = [...new Set(Object.values(cats).flat())]
  } catch (e) { console.error(e) }
}

async function loadSectors() {
  try {
    const res = await stocksApi.getSectors()
    sectorsList.value = res.data?.sectors || []
    sectorsByType.value = res.data?.by_type || {}
    sectorTypes.value = res.data?.types || []
  } catch (e) { console.error('加载板块列表失败', e) }
}

function typeTagType(blockType) {
  const map = { '行业': 'success', '概念': 'warning', '地区': 'primary', '风格': 'info', '指数': 'danger' }
  return map[blockType] || 'info'
}

async function applyFormulas() {
  if (applying.value) return
  if (!selectedFormulas.value.length) { ElMessage.warning('请选择公式'); return }
  applying.value = true
  try {
    // 仅保存公式配置到后端
    await formulasApi.saveUserFormulas({ formulas: selectedFormulas.value, combine_mode: 'or' })
    // 设置公式筛选参数，从 DB 过滤（不调 TDX）
    params.formulas = selectedFormulas.value
    params.page = 1
    await loadData()
    ElMessage.success(`已按 ${selectedFormulas.value.length} 个公式筛选，共 ${total.value} 只股票`)
  } catch (e) { 
    ElMessage.error('操作失败: ' + e.message) 
  }
  finally { applying.value = false }
}

async function loadData() {
  loading.value = true
  try {
    const queryParams = { ...params }
    if (queryParams.min_market_cap_yi > 0) {
      queryParams.min_market_cap = queryParams.min_market_cap_yi * 100000000
    }
    delete queryParams.min_market_cap_yi
    // formulas 数组转为逗号分隔字符串（方便 Axios 序列化）
    if (Array.isArray(queryParams.formulas) && queryParams.formulas.length > 0) {
      queryParams.formulas = queryParams.formulas.join(',')
    } else if (!queryParams.formulas || queryParams.formulas.length === 0) {
      delete queryParams.formulas
    }
    const res = await stocksApi.getStocks(queryParams)
    stocks.value = res.data.data || []
    total.value = res.data.total || 0
  } catch (e) { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

function resetFilters() {
  Object.assign(params, {
    page: 1, search: '', market: '', sector: '', block_type: '',
    is_mainboard_only: true, exclude_st: true,
    min_market_cap_yi: 20, min_pct_change: null,
    formulas: []
  })
  selectedFormulas.value = []
  loadData()
}

async function toggleAutoRefresh(val) {
  try {
    if (val) {
      await systemApi.startScheduler()
      ElMessage.success('已开启自动刷新')
    } else {
      await systemApi.stopScheduler()
      ElMessage.success('已关闭自动刷新')
    }
  } catch (e) { ElMessage.error('操作失败') }
}

function exportData() {
  const csv = '代码,名称,市场,板块,涨跌幅,现价,成交额,成交量,今日评分,8日评分,公式\n' + stocks.value.map(s => 
    `${s.code},${s.name},${s.market},"${(s.sectors||'').replace(/"/g, '""')}",${s.pct_change},${s.close},${s.amount},${s.volume},${s.score},${(s.avg_score_8d || '-')},${(s.formulas||[]).join(';')}`).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `stocks_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

onMounted(() => { loadActiveFilter(); loadFormulas(); loadSectors(); loadData() })
</script>

<style scoped>
.stock-list { max-width: 1500px; margin: 0 auto; }
.header { display: flex; justify-content: space-between; align-items: center; }
.header-actions { display: flex; align-items: center; gap: 15px; }
.refresh-status { font-size: 12px; color: #909399; margin-right: 10px; }

.active-filter-info { margin-bottom: 10px; }
.active-filter-info .el-alert { padding: 8px 12px; }
.active-filter-info .el-tag { margin-left: 8px; }

.filter-bar { padding: 12px; background: #f8f9fa; border-radius: 4px; margin-bottom: 12px; }
.formula-section { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.formula-section .label { font-weight: bold; font-size: 13px; }
.formula-checkboxes { display: flex; flex-wrap: wrap; gap: 4px; }
.formula-checkboxes .el-checkbox { margin: 2px; }

.text-success { color: #67c23a; font-weight: bold; }
.text-warning { color: #e6a23c; }
.text-danger { color: #f56c6c; }
.tag { margin: 1px; }

.pagination { margin-top: 12px; display: flex; justify-content: flex-end; }

.sector-preview { display: inline-flex; align-items: center; gap: 2px; flex-wrap: wrap; }
.more-tag { font-size: 12px; color: #909399; cursor: pointer; }
.sector-item { padding: 2px 0; font-size: 13px; }
.sector-types-divider { border-top: 1px solid #eee; margin-top: 6px; padding-top: 6px; display: flex; gap: 4px; flex-wrap: wrap; }
</style>