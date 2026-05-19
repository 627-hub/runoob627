<template>
  <div class="stock-list">
    <!-- 公式筛选面板（可折叠） -->
    <el-card shadow="never" class="filter-card">
      <div class="filter-header" @click="formulaOpen = !formulaOpen">
        <div class="filter-header-left">
          <span class="filter-title">公式筛选</span>
          <el-tag v-if="selectedFormulas.length" type="primary" size="small" effect="plain">
            {{ selectedFormulas.length }} 个已选
          </el-tag>
          <el-tag v-else size="small" type="info" effect="plain">全部</el-tag>
        </div>
        <div class="filter-header-right">
          <el-button size="small" type="primary" :loading="applying" @click.stop.prevent="applyFormulas">
            应用筛选
          </el-button>
          <el-button size="small" :icon="formulaOpen ? 'ArrowUp' : 'ArrowDown'" @click.stop.prevent="formulaOpen = !formulaOpen" circle />
        </div>
      </div>
      <el-collapse-transition>
        <div v-show="formulaOpen" class="formula-body">
          <div v-for="(names, cat) in formulaByCategory" :key="cat" class="formula-group">
            <div class="formula-cat">{{ cat }}</div>
            <div class="formula-items">
              <el-checkbox-group v-model="selectedFormulas">
                <el-checkbox v-for="f in names" :key="f" :label="f" size="small" class="formula-cb">
                  {{ f }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>
        </div>
      </el-collapse-transition>
    </el-card>

    <!-- 工具栏 -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="params.search" placeholder="代码/名称" clearable
            @change="loadData" style="width:120px" size="small" />
          <el-select v-model="params.market" clearable placeholder="市场"
            @change="loadData" style="width:80px" size="small">
            <el-option label="上海" value="SH" />
            <el-option label="深圳" value="SZ" />
          </el-select>
          <el-cascader v-model="sectorCascade" :options="sectorCascadeOptions"
            placeholder="板块筛选" clearable filterable style="width:180px" size="small"
            :props="{ expandTrigger: 'hover' }"
            @change="onSectorChange" />
          <el-input-number v-model="params.min_pct_change" :min="0" :max="20" :step="0.5"
            controls-position="right" style="width:80px" size="small" placeholder="涨幅"
            @change="loadData" />
          <el-input-number v-model="params.min_market_cap_yi" :min="0" :step="1"
            controls-position="right" style="width:80px" size="small" placeholder="市值"
            @change="loadData" />
        </div>
        <div class="toolbar-right">
          <el-switch v-model="params.is_mainboard_only" active-text="主板" @change="loadData" size="small" />
          <el-switch v-model="params.exclude_st" active-text="排除ST" @change="loadData" size="small" />
          <el-button size="small" @click="resetFilters">重置</el-button>
          <el-button size="small" @click="exportData">导出CSV</el-button>
        </div>
      </div>
      <div class="toolbar-meta">
        <span class="result-count">共 <strong>{{ total }}</strong> 只股票</span>
        <span v-if="selectedFormulas.length" class="tag-group">
          <el-tag v-for="f in selectedFormulas" :key="f" size="small" closable
            @close="removeFormula(f)" type="info" effect="plain">{{ f }}</el-tag>
        </span>
      </div>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card" :body-style="{ padding: '0' }">
      <el-table v-loading="loading" :data="stocks" stripe
        style="width:100%" :header-cell-style="{background:'#fafafa',color:'#303133',fontWeight:600,fontSize:'12px'}">
        <el-table-column label="代码/名称" width="140" sortable>
          <template #default="{ row }">
            <div class="cell-code">{{ row.code }}</div>
            <div class="cell-name">{{ row.name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="market" label="市场" width="56" sortable>
          <template #default="{ row }">
            <el-tag :type="row.market === 'SH' ? 'primary' : 'warning'" size="small" effect="plain">{{ row.market }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pct_change" label="涨幅" width="72" sortable>
          <template #default="{ row }">
            <span :class="pctClass(row.pct_change)">
              {{ row.pct_change != null ? row.pct_change.toFixed(1) + '%' : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="close" label="现价" width="72" sortable>
          <template #default="{ row }">{{ row.close?.toFixed(2) ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="成交额" width="88" sortable>
          <template #default="{ row }">
            <span class="num">{{ row.amount ? (row.amount/1e8).toFixed(2) + '亿' : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="market_cap" label="流通市值" width="100" sortable>
          <template #default="{ row }">
            <span v-if="row.market_cap">{{ (row.market_cap/1e8).toFixed(1) }}亿</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="score" label="评分" width="80" sortable>
          <template #default="{ row }">
            <div class="score-cell">
              <el-progress :percentage="row.score ?? 0" :stroke-width="10" :color="scoreColor(row.score)"
                :format="() => row.score != null ? row.score.toFixed(0) : '-'" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="行业" min-width="100">
          <template #default="{ row }">
            <el-tag v-for="s in (row.sectors_by_type?.['行业'] || []).slice(0, 1)"
              :key="s" size="small" effect="plain" type="success" class="sector-tag">{{ s }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="概念" min-width="140">
          <template #default="{ row }">
            <el-popover placement="bottom" :width="280" trigger="hover">
              <template #reference>
                <div class="sector-preview">
                  <el-tag v-for="s in (row.sectors_by_type?.['概念'] || []).slice(0, 2)"
                    :key="s" size="small" effect="plain" type="warning" class="sector-tag">{{ s }}</el-tag>
                  <span v-if="(row.sectors_by_type?.['概念'] || []).length > 2" class="more">
                    +{{ (row.sectors_by_type?.['概念'] || []).length - 2 }}
                  </span>
                </div>
              </template>
              <div v-for="s in (row.sectors_by_type?.['概念'] || [])" :key="s" style="padding:2px 0;font-size:13px">{{ s }}</div>
            </el-popover>
          </template>
        </el-table-column>
        <el-table-column label="地区" width="80">
          <template #default="{ row }">
            <span v-if="row.sectors_by_type?.['地区']?.[0]" class="region">{{ row.sectors_by_type['地区'][0] }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="风格" min-width="100">
          <template #default="{ row }">
            <el-tag v-for="s in (row.sectors_by_type?.['风格'] || []).slice(0, 1)"
              :key="s" size="small" effect="plain" type="info" class="sector-tag">{{ s }}</el-tag>
            <span v-if="(row.sectors_by_type?.['风格'] || []).length > 1" class="more">
              +{{ (row.sectors_by_type?.['风格'] || []).length - 1 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="公式" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-for="f in (row.formulas||[]).slice(0, 2)" :key="f"
              size="small" type="" effect="plain" class="sector-tag">{{ f }}</el-tag>
            <span v-if="(row.formulas||[]).length > 2" class="more">+{{ row.formulas.length - 2 }}</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination v-model:current-page="params.page" v-model:page-size="params.page_size"
          :total="total" :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="loadData" @size-change="loadData" background small />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { stocksApi, formulasApi, filtersApi } from '@/api'
import { ElMessage } from 'element-plus'

const stocks = ref([])
const total = ref(0)
const loading = ref(false)
const applying = ref(false)
const formulaOpen = ref(true)

const formulaByCategory = ref({})
const formulaNames = computed(() => Object.values(formulaByCategory.value).flat())
const selectedFormulas = ref([])
const sectorsList = ref([])
const sectorTypes = ref([])
const sectorsByType = ref({})
const sectorCascade = ref([])
const sectorCascadeOptions = computed(() => {
  return Object.entries(sectorsByType.value).map(([type, names]) => ({
    value: type,
    label: type,
    children: names.map(n => ({ value: n, label: n })),
  }))
})

const params = reactive({
  page: 1, page_size: 50, sort_by: 'score', sort_order: 'desc',
  search: '', market: '', sector: '', block_type: '',
  is_mainboard_only: true, exclude_st: true,
  min_market_cap_yi: 20, min_pct_change: null,
  formulas: []
})

function pctClass(v) {
  if (v == null) return ''
  if (v >= 9.5) return 'pct-limitup'
  if (v >= 5) return 'pct-hot'
  if (v >= 0) return 'pct-up'
  if (v >= -3) return 'pct-down'
  return 'pct-crash'
}
function scoreColor(s) {
  if (s == null) return '#dcdfe6'
  if (s >= 80) return '#67c23a'
  if (s >= 60) return '#e6a23c'
  return '#f56c6c'
}

function onSectorChange(val) {
  if (val && val.length === 2) {
    params.block_type = val[0]
    params.sector = val[1]
  } else {
    params.block_type = ''
    params.sector = ''
  }
  params.page = 1
  loadData()
}

async function loadFormulas() {
  try {
    const res = await formulasApi.getCategories()
    formulaByCategory.value = res.data || {}
  } catch (e) {}
}
async function loadSectors() {
  try {
    const res = await stocksApi.getSectors()
    sectorsList.value = res.data?.sectors || []
    sectorTypes.value = res.data?.types || []
    sectorsByType.value = res.data?.by_type || {}
  } catch (e) {}
}
async function applyFormulas() {
  if (applying.value) return
  applying.value = true
  try {
    await formulasApi.saveUserFormulas({ formulas: selectedFormulas.value, combine_mode: 'or' })
    params.formulas = [...selectedFormulas.value]
    params.page = 1
    await loadData()
  } catch (e) { ElMessage.error('操作失败') }
  finally { applying.value = false }
}
function removeFormula(f) {
  selectedFormulas.value = selectedFormulas.value.filter(x => x !== f)
  params.formulas = [...selectedFormulas.value]
  loadData()
}
async function loadData() {
  loading.value = true
  try {
    const q = { ...params }
    if (q.min_market_cap_yi > 0) q.min_market_cap = q.min_market_cap_yi * 100000000
    delete q.min_market_cap_yi
    if (Array.isArray(q.formulas) && q.formulas.length) q.formulas = q.formulas.join(',')
    else delete q.formulas
    const res = await stocksApi.getStocks(q)
    stocks.value = res.data.data || []
    total.value = res.data.total || 0
  } catch (e) { ElMessage.error('加载失败') }
  finally { loading.value = false }
}
function resetFilters() {
  Object.assign(params, {
    page: 1, search: '', market: '', sector: '', block_type: '',
    is_mainboard_only: true, exclude_st: true,
    min_market_cap_yi: 20, min_pct_change: null, formulas: []
  })
  selectedFormulas.value = []
  sectorCascade.value = []
  loadData()
}
function exportData() {
  const csv = '代码,名称,市场,涨幅,现价,成交额,流通市值,评分,行业,概念,地区,风格,公式\n' +
    stocks.value.map(s =>
      `${s.code},${s.name},${s.market},${s.pct_change ?? ''},${s.close ?? ''},${s.amount ?? ''},${s.market_cap ?? ''},${s.score ?? ''},"${(s.sectors_by_type?.['行业']||[]).join(';')}","${(s.sectors_by_type?.['概念']||[]).join(';')}","${(s.sectors_by_type?.['地区']||[]).join(';')}","${(s.sectors_by_type?.['风格']||[]).join(';')}","${(s.formulas||[]).join(';')}"`
    ).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `stocks_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

onMounted(() => { loadFormulas(); loadSectors(); loadData() })
</script>

<style scoped>
.stock-list { display: flex; flex-direction: column; gap: 16px; }

/* Formula filter card */
.filter-card { border-radius: 12px; }
.filter-card :deep(.el-card__body) { padding: 0; }
.filter-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; cursor: pointer; user-select: none;
}
.filter-header:hover { background: #fafafa; }
.filter-header-left { display: flex; align-items: center; gap: 10px; }
.filter-title { font-size: 15px; font-weight: 600; color: #303133; }
.filter-header-right { display: flex; align-items: center; gap: 8px; }
.formula-body { padding: 0 20px 14px; border-top: 1px solid #f0f2f5; }
.formula-group { margin-top: 12px; }
.formula-cat { font-size: 12px; font-weight: 600; color: #909399; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .5px; }
.formula-items { display: flex; flex-wrap: wrap; gap: 4px; }
.formula-cb { margin: 0; }

/* Toolbar */
.toolbar-card { border-radius: 12px; }
.toolbar-card :deep(.el-card__body) { padding: 14px 20px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }
.toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-meta {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-top: 10px; padding-top: 10px; border-top: 1px solid #f0f2f5;
}
.result-count { font-size: 13px; color: #606266; margin-right: 8px; }
.result-count strong { color: #303133; }
.tag-group { display: flex; flex-wrap: wrap; gap: 4px; }

/* Table card */
.table-card { border-radius: 12px; overflow: hidden; }

/* Cell styles */
.cell-code { font-weight: 600; font-size: 13px; color: #303133; }
.cell-name { font-size: 11px; color: #909399; margin-top: 1px; }

.pct-limitup { color: #cf1322; font-weight: 700; font-size: 14px; }
.pct-hot { color: #f5222d; font-weight: 600; }
.pct-up { color: #f56c6c; }
.pct-down { color: #67c23a; }
.pct-crash { color: #389e0d; font-weight: 600; }

.num { font-variant-numeric: tabular-nums; }

.score-cell { padding: 4px 0; }
.score-cell :deep(.el-progress__text) { font-size: 12px !important; }

.sector-preview { display: inline-flex; align-items: center; gap: 2px; flex-wrap: wrap; }
.sector-tag { margin: 1px; max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
.more { font-size: 11px; color: #909399; cursor: pointer; margin-left: 2px; }
.region { font-size: 13px; color: #606266; }

.pagination-wrap {
  display: flex; justify-content: flex-end;
  padding: 14px 20px; border-top: 1px solid #f0f2f5;
}

@media (max-width: 900px) {
  .toolbar { flex-direction: column; align-items: stretch; }
  .toolbar-left, .toolbar-right { flex-wrap: wrap; }
}
</style>
