<script setup>
// Écran de connexion et d'inscription : deux onglets, un seul formulaire.
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { connexion, inscription } from '@/api'
import { utilisateur } from '@/session'
import BoutonTheme from '@/composants/BoutonTheme.vue'
import Logo from '@/composants/Logo.vue'
import Mosaique from '@/composants/Mosaique.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()

// 'connexion' | 'inscription'. La page d'accueil ouvre directement l'inscription : /connexion?mode=inscription
const mode = ref(route.query.mode === 'inscription' ? 'inscription' : 'connexion')
const nom = ref('')
const motDePasse = ref('')
const erreur = ref('')
const envoi = ref(false)

async function envoyer() {
  erreur.value = ''
  envoi.value = true
  try {
    const service = mode.value === 'connexion' ? connexion : inscription
    utilisateur.value = await service(nom.value, motDePasse.value)
    // Retour à la page demandée avant la connexion, si c'est bien une page de l'application.
    const suite = String(route.query.suite || '')
    router.push(suite.startsWith('/') && !suite.startsWith('//') ? suite : '/galerie')
  } catch (e) {
    erreur.value = e.message
  } finally {
    envoi.value = false
  }
}
</script>

<template>
  <main class="grid min-h-screen lg:grid-cols-2">
    <!-- Colonne du formulaire -->
    <div class="flex flex-col bg-card p-6 sm:p-10">
      <div class="flex items-center justify-between">
        <RouterLink to="/" class="rounded-md" aria-label="Similis, retour à l'accueil">
          <Logo />
        </RouterLink>
        <BoutonTheme />
      </div>

      <div class="m-auto w-full max-w-sm py-10">
        <h1 class="text-2xl font-semibold tracking-tight">
          {{ mode === 'connexion' ? 'Bon retour' : 'Créer un compte' }}
        </h1>
        <p class="mt-1 text-muted-foreground">
          {{ mode === 'connexion'
            ? 'Connectez-vous pour retrouver votre galerie.'
            : 'Quelques secondes suffisent pour commencer.' }}
        </p>

        <Tabs v-model="mode" class="my-6" @update:model-value="erreur = ''">
          <TabsList class="w-full">
            <TabsTrigger value="connexion">Connexion</TabsTrigger>
            <TabsTrigger value="inscription">Inscription</TabsTrigger>
          </TabsList>
        </Tabs>

        <form class="grid gap-4" @submit.prevent="envoyer">
          <div class="grid gap-2">
            <Label for="nom">Nom d'utilisateur</Label>
            <Input id="nom" v-model="nom" class="h-10" required minlength="3" maxlength="30" autocomplete="username" />
          </div>
          <div class="grid gap-2">
            <Label for="mot-de-passe">Mot de passe</Label>
            <Input
              id="mot-de-passe"
              v-model="motDePasse"
              class="h-10"
              type="password"
              required
              minlength="8"
              maxlength="128"
              :autocomplete="mode === 'connexion' ? 'current-password' : 'new-password'"
              :aria-describedby="mode === 'inscription' ? 'aide-mot-de-passe' : undefined"
            />
            <p v-if="mode === 'inscription'" id="aide-mot-de-passe" class="text-xs text-muted-foreground">
              8 caractères minimum.
            </p>
          </div>

          <p v-if="erreur" role="alert" class="text-sm text-destructive">{{ erreur }}</p>

          <Button type="submit" class="h-10" :disabled="envoi">
            <template v-if="envoi">Envoi…</template>
            <template v-else>{{ mode === 'connexion' ? 'Se connecter' : 'Créer mon compte' }}</template>
          </Button>
        </form>
      </div>
    </div>

    <!-- Colonne décorative, masquée sur petit écran -->
    <div class="hidden place-items-center border-l p-12 lg:grid">
      <Mosaique class="w-full max-w-md" />
    </div>
  </main>
</template>
