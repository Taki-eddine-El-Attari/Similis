<script setup>
// Page provisoire de l'étape 1 : montre que le frontend joint l'API à travers le proxy.
// Elle sera remplacée par la vraie page d'accueil à la fin du projet.
import { ref, onMounted } from 'vue'
import { sante } from '@/api'
import { AnimateIcon } from '@animate-ui/vue/icons'
import RefreshCw from '@/components/animate-ui/icons/RefreshCw.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const etat = ref('chargement') // 'chargement' | 'ok' | 'erreur'
const message = ref('')

async function verifier() {
  etat.value = 'chargement'
  try {
    const reponse = await sante()
    message.value = reponse.etat
    etat.value = 'ok'
  } catch (erreur) {
    message.value = erreur.message
    etat.value = 'erreur'
  }
}

onMounted(verifier)
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-muted p-6">
    <Card class="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Similis</CardTitle>
        <CardDescription>Recherche d'images par le contenu</CardDescription>
      </CardHeader>
      <CardContent class="flex items-center justify-between gap-4">
        <p role="status" :class="etat === 'erreur' ? 'text-destructive' : 'text-muted-foreground'">
          <template v-if="etat === 'chargement'">Connexion à l'API…</template>
          <template v-else-if="etat === 'ok'">API : {{ message }}</template>
          <template v-else>API injoignable : {{ message }}</template>
        </p>
        <!-- AnimateIcon : l'icône s'anime quand on survole tout le bouton -->
        <AnimateIcon animate-on-hover as-child>
          <Button variant="outline" @click="verifier">
            <RefreshCw :size="16" />
            Réessayer
          </Button>
        </AnimateIcon>
      </CardContent>
    </Card>
  </main>
</template>
