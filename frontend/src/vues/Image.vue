<script setup>
// Page d'une image : aperçu, téléchargement et transformations.
// Chaque transformation crée une nouvelle image ; on ouvre alors la page de cette nouvelle image.
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AnimateIcon } from '@animate-ui/vue/icons'
import { ArrowLeft, Contrast, Crop, FlipHorizontal2, FlipVertical2, RotateCw, Scaling } from '@lucide/vue'
import { lireImage, transformerImage, urlFichier } from '@/api'
import Download from '@/components/animate-ui/icons/Download.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const route = useRoute()
const router = useRouter()

const image = ref(null) // { id, categorie_id, nom, largeur, hauteur }
const occupe = ref(false)
const erreur = ref('')

onMounted(async () => {
  try {
    image.value = await lireImage(route.params.id)
  } catch (e) {
    erreur.value = e.message
  }
})

// Lien de retour : la galerie, ouverte sur la catégorie de l'image.
const retour = computed(() => ({
  path: '/galerie',
  query: image.value?.categorie_id ? { categorie: image.value.categorie_id } : {},
}))

// --- Recadrage à la souris ---

// Zone choisie, en pixels de l'image d'origine : { x, y, largeur, hauteur }. null : aucune zone.
const zone = ref(null)
let depart = null // point où le tracé a commencé, en pixels de l'image ; null hors tracé

// Convertit la position de la souris en pixels de l'image.
// L'aperçu est plus petit que l'image : on multiplie par le rapport des deux largeurs.
function position(evenement) {
  const cadre = evenement.currentTarget.getBoundingClientRect()
  const rapport = image.value.largeur / cadre.width
  const borner = (valeur, max) => Math.min(Math.max(Math.round(valeur), 0), max)
  return {
    x: borner((evenement.clientX - cadre.left) * rapport, image.value.largeur),
    y: borner((evenement.clientY - cadre.top) * rapport, image.value.hauteur),
  }
}

function commencer(evenement) {
  // La souris reste suivie même si elle sort de l'image pendant le tracé.
  evenement.currentTarget.setPointerCapture(evenement.pointerId)
  depart = position(evenement)
  zone.value = null
}

function tracer(evenement) {
  if (!depart) return
  const point = position(evenement)
  // Le tracé peut partir dans n'importe quel sens : on prend le coin en haut à gauche et la taille.
  zone.value = {
    x: Math.min(depart.x, point.x),
    y: Math.min(depart.y, point.y),
    largeur: Math.abs(point.x - depart.x),
    hauteur: Math.abs(point.y - depart.y),
  }
}

function terminer() {
  depart = null
  // Un simple clic, ou une zone sans surface, efface la sélection.
  if (zone.value && (zone.value.largeur < 1 || zone.value.hauteur < 1)) zone.value = null
}

// Place le rectangle sur l'aperçu, en pourcentages de la taille de l'image.
const styleZone = computed(() => {
  const z = zone.value
  const pourcent = (valeur, total) => (valeur / total) * 100 + '%'
  return {
    left: pourcent(z.x, image.value.largeur),
    top: pourcent(z.y, image.value.hauteur),
    width: pourcent(z.largeur, image.value.largeur),
    height: pourcent(z.hauteur, image.value.hauteur),
  }
})

// --- Transformations ---

const facteur = ref(0.5)

// Taille de l'image après changement d'échelle, affichée avant de valider.
const tailleFuture = computed(() => {
  const f = Number(facteur.value)
  if (!(f >= 0.1 && f <= 4)) return null
  return Math.max(1, Math.round(image.value.largeur * f)) + ' × ' + Math.max(1, Math.round(image.value.hauteur * f))
})

async function transformer(type, parametres) {
  occupe.value = true
  erreur.value = ''
  try {
    const nouvelle = await transformerImage(image.value.id, type, parametres)
    router.push('/images/' + nouvelle.id)
  } catch (e) {
    erreur.value = e.message
  } finally {
    occupe.value = false
  }
}
</script>

<template>
  <section class="grid gap-4">
    <header class="flex flex-wrap items-end gap-2">
      <div class="mr-auto min-w-0">
        <nav class="flex items-center gap-x-1.5 text-sm text-muted-foreground" aria-label="Chemin">
          <RouterLink :to="retour" class="flex items-center gap-1 rounded hover:text-foreground hover:underline">
            <ArrowLeft class="size-3.5" />
            Galerie
          </RouterLink>
          <template v-if="image">
            <span aria-hidden="true">/</span>
            <span class="truncate" aria-current="page">{{ image.nom }}</span>
          </template>
        </nav>
        <h1 class="truncate text-2xl font-semibold tracking-tight">{{ image?.nom || 'Image' }}</h1>
      </div>
      <AnimateIcon v-if="image" animate-on-hover as-child>
        <Button as="a" variant="outline" :href="urlFichier(image.id, true)" :download="image.nom">
          <Download :size="16" />
          Télécharger
        </Button>
      </AnimateIcon>
    </header>

    <Transition name="fondu">
      <p v-if="erreur" role="alert" class="text-sm text-destructive">{{ erreur }}</p>
    </Transition>

    <div v-if="image" class="grid gap-6 lg:grid-cols-[1fr_20rem] lg:items-start">
      <!-- Aperçu : on trace la zone de recadrage directement sur l'image -->
      <div class="grid justify-items-start gap-2">
        <div
          class="relative w-fit cursor-crosshair touch-none overflow-hidden rounded-lg border bg-muted select-none"
          @pointerdown="commencer"
          @pointermove="tracer"
          @pointerup="terminer"
          @pointercancel="terminer"
        >
          <img
            :src="urlFichier(image.id)"
            :alt="image.nom"
            :width="image.largeur"
            :height="image.hauteur"
            draggable="false"
            class="block h-auto max-h-[70vh] w-auto max-w-full"
          />
          <!-- L'ombre très large assombrit tout ce qui est hors de la zone -->
          <div
            v-if="zone"
            class="pointer-events-none absolute border-2 border-primary shadow-[0_0_0_9999px_rgb(0_0_0/0.5)]"
            :style="styleZone"
          />
        </div>
        <p class="font-mono text-xs text-muted-foreground">{{ image.largeur }} × {{ image.hauteur }} pixels</p>
      </div>

      <!-- Panneau des transformations -->
      <Card>
        <CardHeader>
          <CardTitle>Transformations</CardTitle>
          <CardDescription>Chacune crée une nouvelle image. L'originale est conservée.</CardDescription>
        </CardHeader>
        <CardContent class="grid gap-5">
          <div class="grid gap-2">
            <span class="text-sm font-medium">Recadrage</span>
            <p class="text-xs text-muted-foreground">
              <template v-if="zone">
                Zone : <span class="font-mono">{{ zone.largeur }} × {{ zone.hauteur }}</span> pixels, à partir de
                <span class="font-mono">({{ zone.x }}, {{ zone.y }})</span>
              </template>
              <template v-else>Tracez un rectangle sur l'image avec la souris.</template>
            </p>
            <div class="flex gap-2">
              <Button variant="outline" :disabled="!zone || occupe" @click="transformer('recadrage', zone)">
                <Crop />
                Recadrer
              </Button>
              <Button v-if="zone" variant="ghost" @click="zone = null">Effacer la zone</Button>
            </div>
          </div>

          <form class="grid gap-2" @submit.prevent="transformer('echelle', { facteur: Number(facteur) })">
            <Label for="facteur">Échelle</Label>
            <div class="flex gap-2">
              <Input id="facteur" v-model="facteur" type="number" min="0.1" max="4" step="0.1" required class="w-24" />
              <Button type="submit" variant="outline" :disabled="occupe">
                <Scaling />
                Redimensionner
              </Button>
            </div>
            <p class="text-xs text-muted-foreground">
              Facteur entre 0,1 et 4.
              <template v-if="tailleFuture">Nouvelle taille : <span class="font-mono">{{ tailleFuture }}</span></template>
            </p>
          </form>

          <div class="grid gap-2">
            <span class="text-sm font-medium">Rotation</span>
            <div class="flex flex-wrap gap-2">
              <Button
                v-for="angle in [90, 180, 270]"
                :key="angle"
                variant="outline"
                :disabled="occupe"
                @click="transformer('rotation', { angle })"
              >
                <RotateCw />
                {{ angle }}°
              </Button>
            </div>
          </div>

          <div class="grid gap-2">
            <span class="text-sm font-medium">Miroir</span>
            <div class="flex flex-wrap gap-2">
              <Button variant="outline" :disabled="occupe" title="Retourne l'image de haut en bas" @click="transformer('miroir', { axe: 'horizontal' })">
                <FlipHorizontal2 />
                Horizontal
              </Button>
              <Button variant="outline" :disabled="occupe" title="Retourne l'image de gauche à droite" @click="transformer('miroir', { axe: 'vertical' })">
                <FlipVertical2 />
                Vertical
              </Button>
            </div>
          </div>

          <div class="grid gap-2">
            <span class="text-sm font-medium">Couleur</span>
            <div>
              <Button variant="outline" :disabled="occupe" @click="transformer('gris')">
                <Contrast />
                Niveaux de gris
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </section>
</template>
