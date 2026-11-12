<script setup>
// Démonstration de la page d'accueil : la recherche par le contenu et le retour de pertinence FRE,
// en miniature, sur les photos de la vitrine. Le calcul est fait dans le navigateur (fre.js),
// avec les mêmes vecteurs et les mêmes formules que le serveur.
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { usePreferredReducedMotion } from '@vueuse/core'
import { RefreshCw } from '@lucide/vue'
import { animate } from 'motion-v'
import { urlVitrine } from '@/api'
import { DESCRIPTEURS } from '@/descripteurs'
import { classer, partsParDescripteur } from '@/fre'
import Check from '@/components/animate-ui/icons/Check.vue'
import { Button } from '@/components/ui/button'

const props = defineProps({
  // Réponse de GET /api/vitrine. Absente tant qu'elle n'est pas arrivée : des squelettes la remplacent.
  vitrine: { type: Object, default: undefined },
  // Nom français des catégories montrées : il décrit chaque photo aux lecteurs d'écran.
  noms: { type: Object, default: () => ({}) },
})
// Numéro de la photo requête, partagé avec la page. null : aucune, la planche garde son ordre de départ.
const requete = defineModel('requete', { default: null })

const images = computed(() => props.vitrine?.images ?? [])
const vecteurs = computed(() => images.value.map((image) => image.vecteur))

const cochees = ref([]) // numéros des photos marquées pertinentes (cumul, comme dans la plateforme)
const iteration = ref(0) // 0 : recherche simple ; +1 à chaque « Affiner »
const classement = ref(null) // { ordre, distances, poids } ; null : pas encore de requête
const aAffiner = ref(false) // une photo a été cochée ou décochée depuis le dernier classement
const pondere = ref(false) // le classement affiché tient compte de photos cochées
const chargees = reactive(new Set()) // numéros des photos déjà affichées : leur squelette s'arrête

// Le système demande moins d'animations : ni attente, ni décalage entre les photos.
const mouvement = usePreferredReducedMotion()
const calme = computed(() => mouvement.value === 'reduce')

// --- Les trois actions ---

let attente // minuterie du choix automatique de la photo d'exemple

// Fixe la photo requête et lance une recherche simple. n nul : retour à la planche de départ.
function choisir(n) {
  clearTimeout(attente)
  requete.value = n
  cochees.value = []
  iteration.value = 0
  aAffiner.value = false
  pondere.value = false
  classement.value = n === null ? null : classer(vecteurs.value, n)
}

// Clic sur une photo : sans requête, elle devient la requête ; ensuite, le clic la coche ou la décoche.
function cliquer(n) {
  if (requete.value === null) return choisir(n)
  cochees.value = cochees.value.includes(n) ? cochees.value.filter((c) => c !== n) : [...cochees.value, n]
  aAffiner.value = true
}

// Retour de pertinence : nouveau classement d'après la requête et toutes les photos cochées.
// Sans photo cochée, c'est de nouveau la recherche simple.
function affiner() {
  classement.value = classer(vecteurs.value, requete.value, cochees.value)
  iteration.value++
  aAffiner.value = false
  pondere.value = cochees.value.length > 0
}

// À l'arrivée des photos, la démonstration choisit d'elle-même la photo d'exemple après un court instant :
// le classement se montre sans attendre un clic. Si le visiteur clique avant, c'est son choix qui compte.
watch(
  () => props.vitrine,
  (vitrine) => {
    if (vitrine && requete.value === null) {
      attente = setTimeout(() => choisir(vitrine.exemple), calme.value ? 0 : 1400)
    }
  },
  { immediate: true },
)

// --- Ce qui est affiché ---

// Photos dans l'ordre d'affichage : classées s'il y a une requête, sinon dans l'ordre de la vitrine.
const rangees = computed(() => (classement.value ? classement.value.ordre.map((n) => images.value[n]) : images.value))

const consigne = computed(() => {
  const n = cochees.value.length
  if (!props.vitrine) return 'Chargement des photos…'
  if (requete.value === null) return 'Cliquez sur une photo\u00a0: elle devient la requête.'
  if (aAffiner.value) {
    return n
      ? `${n > 1 ? n + ' photos cochées' : 'Une photo cochée'}. Cliquez sur Affiner pour reclasser.`
      : 'Plus aucune photo cochée. Cliquez sur Affiner pour revenir à la recherche simple.'
  }
  if (pondere.value) {
    return `Reclassées d'après ${n > 1 ? `vos ${n} photos cochées` : 'votre photo cochée'}. Cochez-en d'autres ou changez de photo.`
  }
  return 'Les plus proches viennent en premier. Cochez celles qui vous conviennent.'
})

// Distance à 2 décimales, écrite à la française : 0,54
const nombre = (valeur) => valeur.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// Nom lu par les lecteurs d'écran pour le bouton d'une photo, selon ce que fait le clic.
function decrire(image, rang) {
  const nom = props.noms[image.categorie] || image.categorie
  if (requete.value === null) return `Prendre comme requête une photo de la catégorie ${nom}`
  if (image.n === requete.value) return `Photo requête, catégorie ${nom}`
  return `Rang ${rang}, catégorie ${nom} : marquer comme pertinente`
}

// --- Poids des descripteurs ---

// Part du poids total portée par chaque descripteur. Sans requête, toutes les valeurs pèsent autant.
const parts = computed(() =>
  props.vitrine
    ? partsParDescripteur(classement.value?.poids ?? vecteurs.value[0].map(() => 1), props.vitrine.groupes)
    : null,
)

// Parts affichées : à chaque nouveau classement, elles glissent de l'ancienne valeur à la nouvelle.
const affichees = ref(null)
let glissement
watch(
  parts,
  (nouvelles) => {
    const anciennes = affichees.value
    glissement?.stop()
    // Pas d'animation au premier affichage, ni si rien ne change (nouvelle recherche simple).
    const identiques = anciennes && nouvelles && DESCRIPTEURS.every((d) => anciennes[d.cle] === nouvelles[d.cle])
    if (!anciennes || !nouvelles || identiques || calme.value) {
      affichees.value = nouvelles
      return
    }
    // animate (Motion) fait passer t de 0 à 1 ; chaque part suit t entre son ancienne et sa nouvelle valeur.
    glissement = animate(0, 1, {
      duration: 0.7,
      ease: [0.22, 1, 0.36, 1],
      onUpdate(t) {
        affichees.value = Object.fromEntries(
          DESCRIPTEURS.map((d) => [d.cle, anciennes[d.cle] + (nouvelles[d.cle] - anciennes[d.cle]) * t]),
        )
      },
    })
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  clearTimeout(attente)
  glissement?.stop()
})

// Grille de la planche : 4 photos par ligne sur téléphone, 12 sur grand écran (deux lignes de 12).
const GRILLE = 'grid grid-cols-4 gap-2 p-4 sm:grid-cols-6 md:grid-cols-8 xl:grid-cols-12'
</script>

<template>
  <section class="rounded-2xl border bg-card" aria-label="Démonstration de la recherche">
    <!-- Consigne, puis les deux actions -->
    <header class="flex flex-wrap items-center gap-x-4 gap-y-3 border-b px-4 py-3">
      <p class="min-h-10 basis-full text-sm font-medium md:min-h-0 xl:flex-1 xl:text-base" aria-live="polite">
        {{ consigne }}
      </p>
      <div class="flex w-full flex-wrap gap-2 sm:w-auto">
        <Button variant="outline" class="flex-1 sm:flex-none" :disabled="requete === null" @click="choisir(null)">
          Autre photo
        </Button>
        <Button class="flex-1 sm:flex-none" :disabled="!aAffiner" @click="affiner">
          <RefreshCw />
          {{ cochees.length ? `Affiner avec ${cochees.length} photo${cochees.length > 1 ? 's' : ''}` : 'Affiner' }}
        </Button>
      </div>
    </header>

    <!-- En attendant les photos : des squelettes aux mêmes dimensions -->
    <ul v-if="!vitrine" :class="GRILLE" aria-busy="true">
      <li v-for="n in 24" :key="n">
        <div class="squelette aspect-[4/3] rounded-md" />
        <p class="mt-1 h-3.5" />
      </li>
    </ul>

    <!-- La planche. TransitionGroup anime le reclassement : chaque photo glisse de son ancienne place
         à la nouvelle, les mieux classées en premier (transition-delay). -->
    <TransitionGroup v-else tag="ul" name="glisse" :class="GRILLE">
      <li
        v-for="(image, rang) in rangees"
        :key="image.n"
        class="relative"
        :class="{ 'z-10': image.n === requete }"
        :style="{ transitionDelay: calme ? '0ms' : rang * 18 + 'ms' }"
      >
        <button
          type="button"
          class="relative block aspect-[4/3] w-full overflow-hidden rounded-md outline-2 outline-offset-2 focus-visible:ring-3 focus-visible:ring-ring/50 enabled:cursor-pointer"
          :class="[
            image.n === requete || cochees.includes(image.n)
              ? 'outline-primary'
              : 'outline-transparent hover:outline-primary/50',
            { squelette: !chargees.has(image.n) },
          ]"
          :disabled="image.n === requete"
          :aria-pressed="requete !== null && image.n !== requete ? cochees.includes(image.n) : undefined"
          :aria-label="decrire(image, rang)"
          @click="cliquer(image.n)"
        >
          <img
            :src="urlVitrine(image.n)"
            alt=""
            draggable="false"
            class="size-full object-cover"
            @load="chargees.add(image.n)"
          />
          <!-- Case à cocher, une fois la requête choisie -->
          <span
            v-if="requete !== null && image.n !== requete"
            class="absolute top-1 left-1 grid size-4 place-items-center rounded-[5px] border-[1.5px] transition-colors duration-200"
            :class="
              cochees.includes(image.n)
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-white bg-black/25 text-transparent'
            "
            aria-hidden="true"
          >
            <Check :size="11" :stroke-width="3" :animate="cochees.includes(image.n)" />
          </span>
        </button>
        <!-- Sous la photo, comme sur une planche contact : son rang et sa distance à la requête -->
        <p class="mt-1 flex h-3.5 items-center justify-between gap-1 font-mono text-[10px] leading-none text-muted-foreground">
          <template v-if="classement">
            <span v-if="image.n === requete" class="font-medium text-primary">Requête</span>
            <template v-else>
              <span class="text-foreground">{{ String(rang).padStart(2, '0') }}</span>{{ ' ' }}
              <span>{{ nombre(classement.distances[image.n]) }}</span>
            </template>
          </template>
        </p>
      </li>
    </TransitionGroup>

    <!-- Poids des descripteurs : parts égales en recherche simple, déplacées par le retour de pertinence -->
    <footer class="grid gap-2.5 border-t px-4 py-3">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p class="text-xs font-medium">Poids par descripteur</p>
        <p class="order-last basis-full text-xs text-muted-foreground sm:order-none sm:basis-auto">
          {{
            pondere
              ? 'Plus un descripteur est stable entre vos photos, plus il pèse.'
              : 'Recherche simple\u00a0: les 141 valeurs pèsent autant.'
          }}
        </p>
        <span class="ml-auto rounded-full bg-muted px-2.5 py-1 text-xs font-medium">
          Itération <span class="font-mono">{{ iteration }}</span>
        </span>
      </div>
      <template v-if="affichees">
        <!-- Une barre partagée en 5 : la largeur de chaque morceau est la part du descripteur -->
        <div class="flex h-2 gap-0.5" aria-hidden="true">
          <i
            v-for="d in DESCRIPTEURS"
            :key="d.cle"
            class="min-w-1 rounded-full"
            :style="{ flex: affichees[d.cle] * 100 + ' 1 0%', background: d.couleur }"
          />
        </div>
        <ul class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <li v-for="d in DESCRIPTEURS" :key="d.cle" class="flex items-center gap-1.5">
            <i class="size-2 rounded-[3px]" :style="{ background: d.couleur }" />
            {{ d.nom }}
            <span class="font-mono text-foreground">{{ Math.round(affichees[d.cle] * 100) }}&nbsp;%</span>
          </li>
        </ul>
      </template>
      <template v-else>
        <div class="squelette h-2 rounded-full" />
        <div class="h-4" />
      </template>
    </footer>
  </section>
</template>

<style scoped>
/* Reclassement : TransitionGroup pose cette classe sur chaque photo qui change de place.
   La photo part de son ancienne place et glisse jusqu'à la nouvelle. */
.glisse-move {
  transition: transform 0.65s cubic-bezier(0.22, 1, 0.36, 1);
}
</style>
