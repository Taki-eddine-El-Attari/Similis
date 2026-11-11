<script setup>
// Profil : compte connecté et réglages d'apparence (mémorisés dans ce navigateur).
import { accent, enFondu, theme } from '@/apparence'
import { utilisateur } from '@/session'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const themes = [
  { valeur: 'auto', texte: 'Système' },
  { valeur: 'light', texte: 'Clair' },
  { valeur: 'dark', texte: 'Sombre' },
]

// Les pastilles montrent la teinte de chaque accent dans le mode affiché.
const accents = [
  { valeur: 'sarcelle', texte: 'Sarcelle', pastille: 'bg-[#0F766E] dark:bg-[#2DD4BF]' },
  { valeur: 'indigo', texte: 'Indigo', pastille: 'bg-[#4338CA] dark:bg-[#A5B4FC]' },
]
</script>

<template>
  <section class="grid max-w-xl gap-6">
    <div>
      <h1 class="text-2xl font-semibold tracking-tight">Profil</h1>
      <p class="mt-1 text-muted-foreground">Votre compte et l'apparence de Similis.</p>
    </div>

    <Card>
      <CardHeader>
        <CardTitle>Compte</CardTitle>
        <CardDescription>Nom d'utilisateur</CardDescription>
      </CardHeader>
      <CardContent class="font-medium">{{ utilisateur?.nom }}</CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle>Apparence</CardTitle>
        <CardDescription>Ces choix sont enregistrés dans ce navigateur.</CardDescription>
      </CardHeader>
      <CardContent class="grid gap-5">
        <div class="grid gap-2">
          <span id="titre-theme" class="text-sm font-medium">Thème</span>
          <Tabs :model-value="theme" @update:model-value="(v) => enFondu(() => (theme = v))">
            <TabsList aria-labelledby="titre-theme">
              <TabsTrigger v-for="t in themes" :key="t.valeur" :value="t.valeur" class="px-4">
                {{ t.texte }}
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
        <div class="grid gap-2">
          <span id="titre-accent" class="text-sm font-medium">Couleur d'accent</span>
          <Tabs :model-value="accent" @update:model-value="(v) => enFondu(() => (accent = v))">
            <TabsList aria-labelledby="titre-accent">
              <TabsTrigger v-for="a in accents" :key="a.valeur" :value="a.valeur" class="px-4">
                <i class="size-3 rounded-full" :class="a.pastille" aria-hidden="true" />
                {{ a.texte }}
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </CardContent>
    </Card>
  </section>
</template>
