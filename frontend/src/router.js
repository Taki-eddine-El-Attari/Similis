import { createRouter, createWebHistory } from 'vue-router'
import Accueil from './vues/Accueil.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', component: Accueil }],
})
