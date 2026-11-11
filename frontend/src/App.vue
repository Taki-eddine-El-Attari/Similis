<script setup>
// Cadre de l'application : barre de navigation (si connecté) et page courante.
import { useRouter } from 'vue-router'
import { AnimateIcon } from '@animate-ui/vue/icons'
import { deconnexion } from '@/api'
import { utilisateur } from '@/router'
import LogOut from '@/components/animate-ui/icons/LogOut.vue'
import { Button } from '@/components/ui/button'

const router = useRouter()

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

  <div v-else class="min-h-screen bg-muted">
    <header class="border-b bg-background">
      <nav class="mx-auto flex h-14 max-w-6xl items-center gap-6 px-6" aria-label="Navigation principale">
        <RouterLink to="/galerie" class="text-lg font-semibold tracking-tight">Similis</RouterLink>
        <RouterLink
          to="/galerie"
          class="text-sm text-muted-foreground hover:text-foreground"
          active-class="font-medium text-foreground"
        >
          Galerie
        </RouterLink>
        <span class="ml-auto text-sm text-muted-foreground">{{ utilisateur.nom }}</span>
        <AnimateIcon animate-on-hover as-child>
          <Button variant="outline" size="sm" @click="seDeconnecter">
            <LogOut :size="16" />
            Déconnexion
          </Button>
        </AnimateIcon>
      </nav>
    </header>
    <main class="mx-auto max-w-6xl p-6">
      <RouterView />
    </main>
  </div>
</template>
