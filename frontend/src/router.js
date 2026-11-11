import { ref } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { moi } from './api'
import Connexion from './vues/Connexion.vue'
import Galerie from './vues/Galerie.vue'

// Utilisateur connecté, partagé par toute l'application.
// undefined : pas encore vérifié ; null : non connecté ; objet : connecté.
export const utilisateur = ref(undefined)

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/galerie' },
    { path: '/connexion', component: Connexion, meta: { publique: true } },
    { path: '/galerie', component: Galerie },
    { path: '/:inconnu(.*)', redirect: '/galerie' },
  ],
})

// Avant chaque changement de page : une route non publique exige d'être connecté.
router.beforeEach(async (destination) => {
  if (utilisateur.value === undefined) {
    // Premier affichage (ou rechargement) : on demande à l'API si la session existe encore.
    utilisateur.value = await moi().catch(() => null)
  }
  if (!destination.meta.publique && !utilisateur.value) {
    return { path: '/connexion', query: { suite: destination.fullPath } }
  }
  if (destination.path === '/connexion' && utilisateur.value) {
    return '/galerie'
  }
})

export default router
