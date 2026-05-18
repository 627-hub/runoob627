<template>
  <div class="filter-config">
    <el-row :gutter="20">
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>选股公式配置</span>
              <el-button type="primary" size="small" @click="saveFormulas" :loading="saving">
                保存配置
              </el-button>
            </div>
          </template>

          <div class="combine-mode">
            <span>组合模式：</span>
            <el-radio-group v-model="combineMode">
              <el-radio label="or">或（任一公式选中即可）</el-radio>
              <el-radio label="and">与（需同时满足多个公式）</el-radio>
            </el-radio-group>
          </div>

          <el-tabs v-model="activeCategory">
            <el-tab-pane
              v-for="(formulas, category) in formulaCategories"
              :key="category"
              :label="category"
              :name="category"
            >
              <el-checkbox-group v-model="selectedFormulas">
                <el-checkbox
                  v-for="f in formulas"
                  :key="f"
                  :label="f"
                  class="formula-checkbox"
                />
              </el-checkbox-group>
            </el-tab-pane>
          </el-tabs>

          <div class="selected-info">
            已选择 {{ selectedFormulas.length }} 个公式
            <el-button size="small" link type="primary" @click="testFormulas">
              测试公式
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card>
          <template #header>
            <span>默认筛选条件</span>
          </template>
          <el-form label-width="120px">
            <el-form-item label="最小涨幅%">
              <el-input-number v-model="defaultConfig.min_pct_change" :min="0" :max="20" :step="0.5" controls-position="right" style="width: 150px" />
            </el-form-item>
            <el-form-item label="最大涨幅%">
              <el-input-number v-model="defaultConfig.max_pct_change" :min="0" :max="20" :step="0.5" controls-position="right" style="width: 150px" />
            </el-form-item>
            <el-form-item label="最小成交额(元)">
              <el-input-number v-model="defaultConfig.min_amount" :min="0" :step="100000000" controls-position="right" style="width: 150px" />
            </el-form-item>
            <el-form-item label="最小评分">
              <el-input-number v-model="defaultConfig.min_score" :min="0" :max="100" :step="5" controls-position="right" style="width: 150px" />
            </el-form-item>
            <el-form-item label="市场">
              <el-checkbox-group v-model="defaultConfig.market">
                <el-checkbox label="SH">上海</el-checkbox>
                <el-checkbox label="SZ">深圳</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="仅主板">
              <el-switch v-model="defaultConfig.is_mainboard_only" />
            </el-form-item>
            <el-form-item label="最小上市天数">
              <el-input-number v-model="defaultConfig.min_listing_days" :min="0" :step="30" controls-position="right" style="width: 150px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveDefaultConfig">保存为默认配置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="testDialogVisible" title="公式测试结果" width="500px">
      <div v-if="testResult">
        <p>公式：{{ testResult.formula_name }}</p>
        <p>选出股票数：{{ testResult.stock_count }}</p>
        <div v-if="testResult.stocks && testResult.stocks.length > 0">
          <p>股票列表（前20只）：</p>
          <div class="stock-list">
            <el-tag v-for="s in testResult.stocks" :key="s" size="small" class="stock-tag">
              {{ s }}
            </el-tag>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="testDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { formulasApi, filtersApi } from '@/api'

const formulaCategories = ref({})
const selectedFormulas = ref([])
const combineMode = ref('or')
const activeCategory = ref('涨停类')
const saving = ref(false)

const testDialogVisible = ref(false)
const testResult = ref(null)

const defaultConfig = ref({
  min_pct_change: null,
  max_pct_change: null,
  min_amount: null,
  min_score: null,
  market: ['SH', 'SZ'],
  is_mainboard_only: false,
  min_listing_days: 0
})

async function loadFormulaCategories() {
  try {
    const res = await formulasApi.getCategories()
    formulaCategories.value = res.data || {}
  } catch (e) {
    console.error('加载公式分类失败:', e)
  }
}

async function loadUserFormulas() {
  try {
    const res = await formulasApi.getUserFormulas()
    if (res.data) {
      selectedFormulas.value = res.data.active_formulas || []
      combineMode.value = res.data.combine_mode || 'or'
    }
  } catch (e) {
    console.error('加载用户公式失败:', e)
  }
}

async function saveFormulas() {
  if (selectedFormulas.value.length === 0) {
    ElMessage.warning('请至少选择一个公式')
    return
  }
  saving.value = true
  try {
    await formulasApi.saveUserFormulas({
      formulas: selectedFormulas.value,
      combine_mode: combineMode.value
    })
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function testFormulas() {
  if (selectedFormulas.value.length === 0) {
    ElMessage.warning('请至少选择一个公式')
    return
  }
  try {
    const res = await formulasApi.testFormula(selectedFormulas.value[0])
    testResult.value = res.data
    testDialogVisible.value = true
  } catch (e) {
    ElMessage.error('测试失败')
  }
}

async function loadDefaultConfig() {
  try {
    const res = await filtersApi.getDefaultConfig()
    if (res.data) {
      defaultConfig.value = { ...defaultConfig.value, ...res.data }
    }
  } catch (e) {
    console.error('加载默认配置失败:', e)
  }
}

async function saveDefaultConfig() {
  ElMessage.success('默认配置已保存（前端暂存）')
}

onMounted(() => {
  loadFormulaCategories()
  loadUserFormulas()
  loadDefaultConfig()
})
</script>

<style scoped>
.filter-config {
  max-width: 1400px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.combine-mode {
  margin-bottom: 15px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.combine-mode span {
  font-weight: 500;
  margin-right: 10px;
}

.formula-checkbox {
  margin-right: 15px;
  margin-bottom: 8px;
}

.selected-info {
  margin-top: 15px;
  padding: 10px;
  background: #ecf5ff;
  border-radius: 4px;
  color: #409eff;
}

.stock-list {
  max-height: 200px;
  overflow-y: auto;
}

.stock-tag {
  margin: 3px;
}
</style>