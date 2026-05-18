import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { stocksApi, filtersApi, systemApi } from '@/api'

export const useStocksStore = defineStore('stocks', () => {
  const stocks = ref([])
  const total = ref(0)
  const loading = ref(false)
  const stats = ref({
    total_stocks: 0,
    stocks_with_metrics: 0,
    latest_date: null,
    up_count: 0,
    limit_up_count: 0
  })

  const params = ref({
    page: 1,
    page_size: 50,
    sort_by: 'score',
    sort_order: 'desc'
  })

  async function fetchStocks() {
    loading.value = true
    try {
      const res = await stocksApi.getStocks(params.value)
      stocks.value = res.data.data
      total.value = res.data.total
    } catch (e) {
      console.error('获取股票列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const res = await stocksApi.getStats()
      stats.value = res.data
    } catch (e) {
      console.error('获取统计信息失败:', e)
    }
  }

  async function refreshData() {
    await systemApi.triggerRefresh()
    await fetchStocks()
    await fetchStats()
  }

  function setParams(newParams) {
    params.value = { ...params.value, ...newParams }
    fetchStocks()
  }

  return {
    stocks,
    total,
    loading,
    stats,
    params,
    fetchStocks,
    fetchStats,
    refreshData,
    setParams
  }
})