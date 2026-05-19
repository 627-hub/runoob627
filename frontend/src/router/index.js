import { createRouter, createWebHistory } from 'vue-router'
import StockList from '../views/StockList.vue'
import Dashboard from '../views/Dashboard.vue'
import FilterConfig from '../views/FilterConfig.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard
  },
  {
    path: '/stocks',
    name: 'StockList',
    component: StockList
  },
  {
    path: '/filters',
    name: 'FilterConfig',
    component: FilterConfig
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router