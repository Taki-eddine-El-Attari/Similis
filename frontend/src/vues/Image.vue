<script setup>
// Page d'une image : aperçu, téléchargement, descripteurs et transformations.
// Chaque transformation crée une nouvelle image ; on ouvre alors la page de cette nouvelle image.
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AnimateIcon } from '@animate-ui/vue/icons'
import { ArrowLeft, Contrast, Crop, FlipHorizontal2, FlipVertical2, RotateCw, Scaling } from '@lucide/vue'
import { lireDescripteurs, lireImage, transformerImage, urlFichier } from '@/api'
import Barres from '@/composants/Barres.vue'
import Download from '@/components/animate-ui/icons/Download.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()

const image = ref(null) // { id, categorie_id, nom, largeur, hauteur }
const descripteurs = ref(null) // { histogrammes, moments, dominantes, glcm, lbp }
const onglet = ref('descripteurs') // 'descripteurs' | 'transformations'
const occupe = ref(false)
const erreur = ref('')

onMounted(async () => {
  try {
    image.value = await lireImage(route.params.id)
    // Le service accepte plusieurs images ; ici on n'en demande qu'une.
    const reponse = await lireDescripteurs([{ source: 'galerie', id: image.value.id }])
    descripteurs.value = reponse[0]
  } catch (e) {
    erreur.value = e.message
  }
})

// --- Affichage des descripteurs (valeurs brutes, non normalisées) ---

// Histogrammes de couleur : un graphique par canal, avec la couleur du canal.
const CANAUX = [
  { cle: 'r', nom: 'Rouge', couleur: '--canal-r' },
  { cle: 'g', nom: 'Vert', couleur: '--canal-g' },
  { cle: 'b', nom: 'Bleu', couleur: '--canal-b' },
]
// 32 cases de 8 niveaux chacune : « 0 à 7 », « 8 à 15 », ... « 248 à 255 ».
const CASES = Array.from({ length: 32 }, (_, i) => `${i * 8} à ${i * 8 + 7}`)
const MOTIFS = Array.from({ length: 10 }, (_, i) => 'Motif ' + i)
const MOMENTS = [
  { cle: 'h', nom: 'Teinte (H)' },
  { cle: 's', nom: 'Saturation (S)' },
  { cle: 'v', nom: 'Valeur (V)' },
]
const GLCM = [
  { cle: 'contraste', nom: 'Contraste' },
  { cle: 'correlation', nom: 'Corrélation' },
  { cle: 'energie', nom: 'Énergie' },
  { cle: 'homogeneite', nom: 'Homogénéité' },
  { cle: 'dissimilarite', nom: 'Dissimilarité' },
  { cle: 'asm', nom: 'ASM' },
]

// Nombre à 4 décimales, écrit à la française : 0,9412.
function nombre(valeur) {
  return valeur.toLocaleString('fr-FR', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
}

// Couleur CSS d'une couleur dominante (ses composantes sont entre 0 et 1).
function couleurCss(c) {
  return `rgb(${c.r * 255} ${c.g * 255} ${c.b * 255})`
}

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

    <div v-if="image" class="grid gap-6 lg:grid-cols-[1fr_24rem] lg:items-start">
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

      <!-- Colonne de droite : deux onglets -->
      <div class="grid min-w-0 gap-4">
      <Tabs v-model="onglet">
        <TabsList class="w-full">
          <TabsTrigger value="descripteurs">Descripteurs</TabsTrigger>
          <TabsTrigger value="transformations">Transformations</TabsTrigger>
        </TabsList>
      </Tabs>

      <!-- Onglet Descripteurs -->
      <div v-if="onglet === 'descripteurs'" class="grid gap-4">
        <p v-if="!descripteurs && !erreur" class="text-sm text-muted-foreground">Calcul des descripteurs en cours</p>
        <template v-if="descripteurs">
          <Card>
            <CardHeader>
              <CardTitle>Histogrammes de couleur</CardTitle>
              <CardDescription>Part des pixels par niveau, de 0 (sombre) à 255 (clair), en 32 cases.</CardDescription>
            </CardHeader>
            <CardContent class="grid gap-3">
              <div v-for="canal in CANAUX" :key="canal.cle">
                <span class="text-xs text-muted-foreground">{{ canal.nom }}</span>
                <Barres
                  :valeurs="descripteurs.histogrammes[canal.cle]"
                  :etiquettes="CASES"
                  :couleur="canal.couleur"
                  :description="'Histogramme du canal ' + canal.nom"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Couleurs dominantes</CardTitle>
              <CardDescription>Les 5 couleurs les plus présentes (k-means).</CardDescription>
            </CardHeader>
            <CardContent>
              <ul class="flex flex-wrap gap-3">
                <li v-for="(c, i) in descripteurs.dominantes" :key="i" class="grid justify-items-center gap-1">
                  <span class="size-10 rounded-lg border" :style="{ background: couleurCss(c) }" />
                  <span class="font-mono text-xs">{{ Math.round(c.proportion * 100) }} %</span>
                </li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Moments de couleur</CardTitle>
              <CardDescription>En HSV, chaque canal ramené entre 0 et 1.</CardDescription>
            </CardHeader>
            <CardContent>
              <table class="w-full text-xs">
                <thead>
                  <tr class="border-b text-muted-foreground">
                    <th class="py-1.5 text-left font-medium">Canal</th>
                    <th class="py-1.5 text-right font-medium">Moyenne</th>
                    <th class="py-1.5 text-right font-medium">Écart-type</th>
                    <th class="py-1.5 text-right font-medium">Asymétrie</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="canal in MOMENTS" :key="canal.cle" class="border-b last:border-0">
                    <th class="py-1.5 text-left font-medium">{{ canal.nom }}</th>
                    <td v-for="(valeur, i) in descripteurs.moments[canal.cle]" :key="i" class="py-1.5 text-right font-mono">
                      {{ nombre(valeur) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Texture (GLCM)</CardTitle>
              <CardDescription>Moyenne des 4 directions, à 1 pixel de distance.</CardDescription>
            </CardHeader>
            <CardContent>
              <table class="w-full text-xs">
                <tbody>
                  <tr v-for="propriete in GLCM" :key="propriete.cle" class="border-b last:border-0">
                    <th class="py-1.5 text-left font-medium text-muted-foreground">{{ propriete.nom }}</th>
                    <td class="py-1.5 text-right font-mono">{{ nombre(descripteurs.glcm[propriete.cle]) }}</td>
                  </tr>
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Texture (LBP)</CardTitle>
              <CardDescription>Part des pixels pour chacun des 10 motifs uniformes.</CardDescription>
            </CardHeader>
            <CardContent>
              <Barres
                :valeurs="descripteurs.lbp"
                :etiquettes="MOTIFS"
                couleur="--chart-5"
                description="Histogramme des motifs LBP"
              />
            </CardContent>
          </Card>
        </template>
      </div>

      <!-- Onglet Transformations -->
      <Card v-else>
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
    </div>
  </section>
</template>
