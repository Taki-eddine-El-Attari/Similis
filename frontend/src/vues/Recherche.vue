<script setup>
// Recherche par le contenu. Deux états, selon l'adresse :
//   /recherche                        choisir une image requête dans GHIM-10K
//   /recherche?source=ghim&id=4012    résultats pour cette image requête, puis retour de pertinence :
//                                     on coche les résultats pertinents et on clique sur « Affiner »
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AnimateIcon } from '@animate-ui/vue/icons'
import { ArrowLeft, RefreshCw } from '@lucide/vue'
import { affinerRecherche, chercherSimilaires, listerCategoriesGhim, listerImagesGhim, urlImage } from '@/api'
import { DESCRIPTEURS } from '@/descripteurs' // les 5 descripteurs du graphique des poids
import Check from '@/components/animate-ui/icons/Check.vue'
import Search from '@/components/animate-ui/icons/Search.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const route = useRoute()
const router = useRouter()

const occupe = ref(false)
const erreur = ref('')

// Exécute un appel à l'API : indicateur de chargement, et message d'erreur s'il échoue.
async function executer(action) {
  occupe.value = true
  erreur.value = ''
  try {
    return await action()
  } catch (e) {
    erreur.value = e.message
  } finally {
    occupe.value = false
  }
}

// Image requête lue dans l'adresse ; null : aucune, on affiche le choix.
const requete = computed(() => {
  const { source, id } = route.query
  return source && id ? { source, id: Number(id) } : null
})

// Choisir une image requête, c'est changer l'adresse : le bouton Retour du navigateur revient au choix.
function choisir(image) {
  router.push({ path: '/recherche', query: { source: image.source, id: image.id } })
}

// --- État 1 : choisir une image requête dans GHIM-10K ---

const categories = ref([]) // [{ nom, nb_images }]
const categorie = ref(null) // nom de la catégorie ouverte
const page = ref(null) // { images, page, pages, total }

async function ouvrirCategorie(nom, numero = 1) {
  categorie.value = nom
  page.value = null // affiche les squelettes pendant la lecture
  page.value = (await executer(() => listerImagesGhim(nom, numero))) || null
}

// --- État 2 : résultats ---

const k = ref(50) // nombre de résultats demandé
const resultats = ref(null) // null : recherche en cours ; sinon liste classée, sans l'image requête
const PAR_PAGE = 50 // au-delà, les résultats sont découpés en pages
const pageResultats = ref(1)
const infoRequete = ref(null) // nom et catégorie de l'image requête, renvoyés par l'API

// Retour de pertinence FRE. Le serveur ne garde rien : à chaque « Affiner », on lui renvoie
// la requête d'origine et toutes les images cochées depuis le début.
const pertinentes = ref([]) // images cochées (cumul), notées 'source:id', par exemple 'ghim:4012'
const iteration = ref(0) // 0 : recherche simple ; +1 à chaque « Affiner »
const poids = ref(null) // part du poids total par descripteur, après un « Affiner »

const cle = (image) => image.source + ':' + image.id
// 'ghim:4012' → { source: 'ghim', id: 4012 }, la forme attendue par l'API
function designer(texte) {
  const [source, id] = texte.split(':')
  return { source, id: Number(id) }
}

// affinage = false : nouvelle recherche simple, on repart de zéro.
// affinage = true  : retour de pertinence avec les images cochées.
async function lancer(affinage = false) {
  const precedents = resultats.value
  resultats.value = null
  if (!affinage) {
    pertinentes.value = []
    iteration.value = 0
    poids.value = null
  }
  const nombreDemande = Number(k.value)
  const reponse = await executer(() =>
    affinage
      ? affinerRecherche(requete.value, pertinentes.value.map(designer), nombreDemande)
      : chercherSimilaires(requete.value, nombreDemande),
  )
  if (!reponse) {
    resultats.value = precedents || [] // en cas d'erreur, les résultats précédents restent affichés
    return
  }
  if (affinage) {
    iteration.value++
    poids.value = reponse.poids_par_descripteur
  }
  infoRequete.value = reponse?.requete || null
  // L'image requête est déjà affichée à gauche : on la retire de la liste.
  const estRequete = (image) => image.source === requete.value.source && image.id === requete.value.id
  // Le serveur renvoie une ligne de plus que demandé, pour la requête : on garde les k premières des autres.
  resultats.value = reponse.resultats.filter((image) => !estRequete(image)).slice(0, nombreDemande)
  pageResultats.value = 1
}

// Résultats de la page affichée, et nombre de pages.
const nbPages = computed(() => Math.ceil((resultats.value?.length || 0) / PAR_PAGE))
const visibles = computed(() => resultats.value.slice((pageResultats.value - 1) * PAR_PAGE, pageResultats.value * PAR_PAGE))

// Distance à 4 décimales, écrite à la française : 0,4127.
function nombre(valeur) {
  return valeur.toLocaleString('fr-FR', { minimumFractionDigits: 4, maximumFractionDigits: 4 })
}

// À chaque changement d'adresse (et au premier affichage) : on lance la recherche, ou on prépare le choix.
watch(
  requete,
  async () => {
    if (requete.value) return lancer()
    if (!categories.value.length) categories.value = (await executer(listerCategoriesGhim)) || []
  },
  { immediate: true },
)
</script>

<template>
  <section class="grid gap-4">
    <header class="flex flex-wrap items-end gap-x-3 gap-y-2">
      <div class="mr-auto min-w-0">
      <!-- Lien de retour : vers la page de l'image si la requête vient de la galerie, sinon vers le choix -->
      <nav class="flex items-center gap-x-1.5 text-sm text-muted-foreground" aria-label="Chemin">
        <RouterLink
          v-if="requete"
          :to="requete.source === 'galerie' ? '/images/' + requete.id : '/recherche'"
          class="flex items-center gap-1 rounded hover:text-foreground hover:underline"
        >
          <ArrowLeft class="size-3.5" />
          {{ requete.source === 'galerie' ? "Retour à l'image" : 'Retour au choix de l\'image' }}
        </RouterLink>
        <span v-else>Recherche</span>
      </nav>
      <h1 class="text-2xl font-semibold tracking-tight">
        {{ requete ? 'Images similaires' : 'Choisir une image requête' }}
      </h1>
      <p v-if="requete" class="mt-1 text-sm text-muted-foreground" aria-live="polite">
        <template v-if="resultats">
          <span class="font-mono">{{ resultats.length }}</span> résultats, du plus proche au plus éloigné,
          dans GHIM-10K et votre galerie. Cochez les images pertinentes, puis cliquez sur Affiner.
        </template>
        <template v-else>Recherche en cours</template>
      </p>
      </div>
      <!-- Itération et bouton Affiner : à droite du titre, toujours au même endroit -->
      <template v-if="requete">
        <span class="rounded-full bg-muted px-2.5 py-1.5 text-xs font-medium">
          Itération <span class="font-mono">{{ iteration }}</span>
        </span>
        <Button :disabled="occupe || !resultats" @click="lancer(true)">
          <RefreshCw />
          {{ pertinentes.length
            ? `Affiner avec ${pertinentes.length} image${pertinentes.length > 1 ? 's' : ''}`
            : 'Affiner' }}
        </Button>
      </template>
    </header>

    <Transition name="fondu">
      <p v-if="erreur" role="alert" class="text-sm text-destructive">{{ erreur }}</p>
    </Transition>

    <!-- État 1 : choix de l'image requête -->
    <template v-if="!requete">
      <p class="max-w-prose text-sm text-muted-foreground">
        Choisissez une image de la base GHIM-10K ci-dessous. Pour partir d'une de vos images, ouvrez-la depuis la
        <RouterLink to="/galerie" class="font-medium text-primary underline-offset-4 hover:underline">galerie</RouterLink>
        puis cliquez sur « Chercher les images similaires ».
      </p>

      <!-- Les 20 catégories de GHIM-10K -->
      <ul class="flex flex-wrap gap-2" aria-label="Catégories de GHIM-10K">
        <li v-for="c in categories" :key="c.nom">
          <button
            type="button"
            class="rounded-full border px-3 py-1 text-sm hover:bg-accent"
            :class="categorie === c.nom ? 'border-primary bg-primary-soft font-medium text-primary' : 'bg-card text-muted-foreground'"
            :aria-pressed="categorie === c.nom"
            @click="ouvrirCategorie(c.nom)"
          >
            {{ c.nom }}
          </button>
        </li>
      </ul>

      <template v-if="categorie">
        <!-- Squelettes pendant la lecture de la page -->
        <ul v-if="!page" class="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8" aria-busy="true">
          <li v-for="n in 24" :key="n" class="squelette aspect-square rounded-lg" />
        </ul>
        <template v-else>
          <ul class="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
            <li v-for="image in page.images" :key="image.id">
              <button
                type="button"
                class="squelette block aspect-square w-full overflow-hidden rounded-lg border outline-2 outline-offset-2 outline-transparent hover:outline-primary"
                :aria-label="'Choisir ' + image.nom + ' comme image requête'"
                @click="choisir(image)"
              >
                <img :src="urlImage(image)" :alt="image.nom" loading="lazy" class="size-full object-cover" />
              </button>
            </li>
          </ul>
          <nav class="flex items-center justify-center gap-3 text-sm" aria-label="Pages">
            <Button variant="outline" :disabled="page.page <= 1 || occupe" @click="ouvrirCategorie(categorie, page.page - 1)">
              Précédent
            </Button>
            <span class="text-muted-foreground">
              Page <span class="font-mono">{{ page.page }}</span> sur <span class="font-mono">{{ page.pages }}</span>
            </span>
            <Button variant="outline" :disabled="page.page >= page.pages || occupe" @click="ouvrirCategorie(categorie, page.page + 1)">
              Suivant
            </Button>
          </nav>
        </template>
      </template>
    </template>

    <!-- État 2 : résultats -->
    <div v-else class="grid gap-6 lg:grid-cols-[16rem_1fr] lg:items-start">
      <!-- Colonne de gauche : image requête, réglage, puis poids des descripteurs -->
      <div class="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Image requête</CardTitle>
          <CardDescription v-if="infoRequete">
            {{ infoRequete.nom }}
          </CardDescription>
        </CardHeader>
        <CardContent class="grid gap-4">
          <div class="squelette aspect-square overflow-hidden rounded-lg border">
            <img :src="urlImage(requete)" alt="Image requête" class="size-full object-cover" />
          </div>
          <div v-if="infoRequete" class="flex flex-wrap gap-2 text-xs">
            <span class="rounded-full bg-muted px-2 py-0.5 font-medium">
              {{ infoRequete.source === 'ghim' ? 'GHIM-10K' : 'Ma galerie' }}
            </span>
            <span v-if="infoRequete.categorie" class="rounded-full bg-muted px-2 py-0.5 font-medium">
              {{ infoRequete.categorie }}
            </span>
          </div>
          <form class="grid gap-2" @submit.prevent="lancer()">
            <Label for="k">Nombre de résultats</Label>
            <div class="flex gap-2">
              <Input id="k" v-model="k" type="number" min="5" max="500" required class="w-20" />
              <AnimateIcon animate-on-hover as-child>
                <Button type="submit" :disabled="occupe">
                  <Search :size="16" />
                  Rechercher
                </Button>
              </AnimateIcon>
            </div>
            <p class="text-xs text-muted-foreground">De 5 à 500.</p>
          </form>
          <Button variant="outline" @click="router.push('/recherche')">Changer d'image</Button>
        </CardContent>
      </Card>

      <!-- Après un « Affiner » : part du poids total portée par chaque descripteur -->
      <Transition name="fondu">
        <Card v-if="poids">
          <CardHeader>
            <CardTitle>Poids par descripteur</CardTitle>
            <CardDescription>Plus un descripteur est stable entre les images cochées, plus il pèse.</CardDescription>
          </CardHeader>
          <CardContent class="grid gap-2">
            <div v-for="d in DESCRIPTEURS" :key="d.cle" class="grid grid-cols-[6.5rem_1fr_3rem] items-center gap-2 text-xs">
              <span>{{ d.nom }}</span>
              <span class="h-2 overflow-hidden rounded-full bg-muted">
                <span
                  class="block h-full rounded-full transition-[width] duration-300"
                  :style="{ width: poids[d.cle] * 100 + '%', background: d.couleur }"
                />
              </span>
              <span class="text-right font-mono">{{ Math.round(poids[d.cle] * 100) }} %</span>
            </div>
          </CardContent>
        </Card>
      </Transition>
      </div>

      <!-- Résultats classés par distance croissante -->
      <div class="grid min-w-0 gap-3">

        <ul v-if="!resultats" class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5" aria-busy="true">
          <li v-for="n in Math.min(Number(k) || 20, 20)" :key="n" class="squelette aspect-square rounded-lg" />
        </ul>
        <ul v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
          <li
            v-for="(image, i) in visibles"
            :key="image.source + image.id"
            class="squelette relative aspect-square overflow-hidden rounded-lg border outline-2 outline-offset-2 outline-transparent"
            :class="{ '!outline-primary': pertinentes.includes(cle(image)) }"
          >
            <!-- Toute la vignette sert à cocher l'image comme pertinente -->
            <label class="block size-full cursor-pointer">
              <img :src="urlImage(image)" :alt="image.nom" loading="lazy" draggable="false" class="size-full object-cover" />
              <input
                v-model="pertinentes"
                type="checkbox"
                class="peer sr-only"
                :value="cle(image)"
                :aria-label="'Marquer ' + image.nom + ' comme pertinente'"
              />
              <span
                class="absolute top-1.5 left-1.5 grid size-5 place-items-center rounded-md border-[1.5px] border-white bg-black/25 text-transparent peer-checked:border-primary peer-checked:bg-primary peer-checked:text-primary-foreground peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50"
                aria-hidden="true"
              >
                <Check :size="13" :stroke-width="3" />
              </span>
            </label>
            <button
              type="button"
              class="absolute top-1.5 right-1.5 grid size-6 place-items-center rounded-md bg-black/40 text-white hover:bg-black/70"
              :aria-label="'Chercher à partir de ' + image.nom"
              :title="'Chercher à partir de ' + image.nom"
              @click="choisir(image)"
            >
              <Search :size="13" />
            </button>
            <!-- Rang dans le classement complet (toutes pages confondues), catégorie et distance -->
            <span class="pointer-events-none absolute inset-x-0 bottom-0 flex justify-between gap-2 bg-gradient-to-t from-black/70 px-2 pt-5 pb-1.5 text-[11px] text-white">
              <span class="truncate"><span class="font-mono">{{ (pageResultats - 1) * PAR_PAGE + i + 1 }}</span> · {{ image.categorie }}</span>
              <span class="shrink-0 font-mono">{{ nombre(image.distance) }}</span>
            </span>
            <span
              v-if="image.source === 'galerie'"
              class="pointer-events-none absolute right-1.5 bottom-7 rounded-md bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground"
            >
              Ma galerie
            </span>
          </li>
        </ul>

        <!-- Pages : seulement au-delà de 50 résultats -->
        <nav v-if="nbPages > 1" class="flex items-center justify-center gap-3 text-sm" aria-label="Pages de résultats">
          <Button variant="outline" :disabled="pageResultats <= 1" @click="pageResultats--">Précédent</Button>
          <span class="text-muted-foreground">
            Page <span class="font-mono">{{ pageResultats }}</span> sur <span class="font-mono">{{ nbPages }}</span>
          </span>
          <Button variant="outline" :disabled="pageResultats >= nbPages" @click="pageResultats++">Suivant</Button>
        </nav>
      </div>
    </div>
  </section>
</template>
