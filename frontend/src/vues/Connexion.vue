<script setup>
// Écran de connexion et d'inscription : deux onglets, un seul formulaire.
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { connexion, inscription } from '@/api'
import { utilisateur } from '@/router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()

const mode = ref('connexion') // 'connexion' | 'inscription'
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
  <main class="flex min-h-screen items-center justify-center bg-muted p-6">
    <Card class="w-full max-w-sm">
      <CardHeader>
        <CardTitle class="text-xl">Similis</CardTitle>
        <CardDescription>Recherche d'images par le contenu</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs v-model="mode" class="mb-5" @update:model-value="erreur = ''">
          <TabsList class="w-full">
            <TabsTrigger value="connexion">Connexion</TabsTrigger>
            <TabsTrigger value="inscription">Inscription</TabsTrigger>
          </TabsList>
        </Tabs>

        <form class="grid gap-4" @submit.prevent="envoyer">
          <div class="grid gap-2">
            <Label for="nom">Nom d'utilisateur</Label>
            <Input id="nom" v-model="nom" required minlength="3" maxlength="30" autocomplete="username" />
          </div>
          <div class="grid gap-2">
            <Label for="mot-de-passe">Mot de passe</Label>
            <Input
              id="mot-de-passe"
              v-model="motDePasse"
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

          <Button type="submit" :disabled="envoi">
            <template v-if="envoi">Envoi…</template>
            <template v-else>{{ mode === 'connexion' ? 'Se connecter' : 'Créer mon compte' }}</template>
          </Button>
        </form>
      </CardContent>
    </Card>
  </main>
</template>
