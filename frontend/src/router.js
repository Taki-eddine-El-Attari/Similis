import { createRouter, createWebHistory } from 'vue-router'
import { moi } from './api'
import { utilisateur } from './session'
import Connexion from './vues/Connexion.vue'
import Galerie from './vues/Galerie.vue'
import PageImage from './vues/Image.vue'
import Profil from './vues/Profil.vue'
import Recherche from './vues/Recherche.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/galerie' },
    { path: '/connexion', component: Connexion, meta: { publique: true } },
    { path: '/galerie', component: Galerie },
    // (\\d+) : l'identifiant doit être un nombre
    { path: '/images/:id(\\d+)', component: PageImage },
    { path: '/recherche', component: Recherche },
    { path: '/profil', component: Profil },
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
