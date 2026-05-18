import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

export const stocksApi = {
  getStocks(params) {
    return api.get('/stocks/', { params })
  },
  getStock(code) {
    return api.get(`/stocks/${code}`)
  },
  getFilterOptions() {
    return api.get('/stocks/filter-options/options')
  },
  getSectors() {
    return api.get('/stocks/sectors/list')
  },
  getStats() {
    return api.get('/stocks/stats/summary')
  }
}

export const filtersApi = {
  getFilters() {
    return api.get('/filters/')
  },
  createFilter(data) {
    return api.post('/filters/', data)
  },
  updateFilter(id, data) {
    return api.put(`/filters/${id}`, data)
  },
  deleteFilter(id) {
    return api.delete(`/filters/${id}`)
  },
  activateFilter(id) {
    return api.post(`/filters/${id}/activate`)
  },
  getDefaultConfig() {
    return api.get('/filters/default')
  }
  ,
  getActiveFilter() {
    return api.get('/filters/active')
  }
}

export const systemApi = {
  healthCheck() {
    return api.get('/health')
  },
  getRefreshStatus() {
    return api.get('/refresh/status')
  },
  triggerRefresh() {
    return api.post('/refresh/trigger')
  },
  triggerFormulaRefresh() {
    return api.post('/refresh/formula-trigger')
  },
  getSchedulerStatus() {
    return api.get('/refresh/scheduler/status')
  },
  startScheduler() {
    return api.post('/refresh/scheduler/start')
  },
  stopScheduler() {
    return api.post('/refresh/scheduler/stop')
  },
  testTdx() {
    return api.get('/tdx/test')
  }
}

export const formulasApi = {
  getCategories() {
    return api.get('/formulas/categories')
  },
  getCombineModes() {
    return api.get('/formulas/combine-modes')
  },
  getUserFormulas() {
    return api.get('/formulas/user')
  },
  saveUserFormulas(data) {
    return api.post('/formulas/user', data)
  },
  testFormula(formulaName) {
    return api.get(`/formulas/test/${formulaName}`)
  }
}

export default api
