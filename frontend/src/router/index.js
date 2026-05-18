import { createRouter, createWebHistory } from 'vue-router'
import StockList from '../views/StockList.vue'
import Dashboard from '../views/Dashboard.vue'

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
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router