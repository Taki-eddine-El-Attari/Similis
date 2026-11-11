<script setup>
// Cadre de l'application : barre latérale (si connecté) et page courante.
import { useRouter } from 'vue-router'
import { AnimateIcon } from '@animate-ui/vue/icons'
import { deconnexion } from '@/api'
import '@/apparence' // applique le thème et l'accent dès le démarrage
import { utilisateur } from '@/session'
import BoutonTheme from '@/composants/BoutonTheme.vue'
import Logo from '@/composants/Logo.vue'
import Image from '@/components/animate-ui/icons/Image.vue'
import LogOut from '@/components/animate-ui/icons/LogOut.vue'
import Search from '@/components/animate-ui/icons/Search.vue'
import User from '@/components/animate-ui/icons/User.vue'
import { Button } from '@/components/ui/button'

const router = useRouter()

// Liens de la barre latérale.
const liens = [
  { chemin: '/galerie', texte: 'Galerie', icone: Image },
  { chemin: '/recherche', texte: 'Recherche', icone: Search },
  { chemin: '/profil', texte: 'Profil', icone: User },
]

async function seDeconnecter() {
  // Même si l'appel échoue, on revient à l'écran de connexion.
  await deconnexion().catch(() => {})
  utilisateur.value = null
  router.push('/connexion')
}
</script>

<template>
  <!-- Pages publiques (connexion) : pas de barre -->
  <RouterView v-if="!utilisateur" />

  <!-- Petit écran : la barre passe en haut. À partir de md : à gauche, fixe. -->
  <div v-else class="flex min-h-screen flex-col md:flex-row">
    <aside
      class="flex shrink-0 flex-wrap items-center gap-1 border-b bg-sidebar p-3 text-sidebar-foreground md:sticky md:top-0 md:h-screen md:w-56 md:flex-col md:flex-nowrap md:items-stretch md:border-r md:border-b-0"
    >
      <RouterLink to="/galerie" class="mr-auto rounded-md px-2 py-1 md:mr-0 md:mb-3">
        <Logo />
      </RouterLink>

      <nav class="flex gap-1 md:flex-col" aria-label="Navigation principale">
        <AnimateIcon v-for="lien in liens" :key="lien.chemin" animate-on-hover as-child>
          <RouterLink
            :to="lien.chemin"
            class="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            active-class="bg-sidebar-accent font-medium !text-sidebar-accent-foreground"
            :class="{ 'bg-sidebar-accent font-medium !text-sidebar-accent-foreground': lien.chemin === '/galerie' && $route.path.startsWith('/images/') }"
          >
            <component :is="lien.icone" :size="16" />
            {{ lien.texte }}
          </RouterLink>
        </AnimateIcon>
      </nav>

      <div class="flex items-center gap-1 md:mt-auto md:flex-col md:items-stretch md:border-t md:pt-3">
        <p class="hidden truncate px-2 pb-1 text-xs text-muted-foreground md:block">
          Connecté : <span class="font-medium text-foreground">{{ utilisateur.nom }}</span>
        </p>
        <BoutonTheme />
        <AnimateIcon animate-on-hover as-child>
          <Button variant="ghost" size="sm" class="justify-start" @click="seDeconnecter">
            <LogOut :size="16" />
            Déconnexion
          </Button>
        </AnimateIcon>
      </div>
    </aside>

    <main class="min-w-0 flex-1 p-6 md:p-8">
      <!-- Changement de page : l'ancienne s'efface, puis la nouvelle apparaît -->
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" :key="$route.path" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>
