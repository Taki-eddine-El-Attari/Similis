<script setup>
// Page d'accueil, publique. Une photo de la vitrine accompagne la lecture : au fil du défilement,
// elle se décompose en histogrammes, en couleurs dominantes, en texture, puis en une empreinte de
// 141 valeurs, et va se poser dans la case « Requête » de la démonstration.
// La photo est dessinée par composants/Compagnon.vue (WebGL) ; tout le reste est animé par Motion.
// ?t=<secondes> fige l'animation de repos à cet instant ; ?p=<0 à 1> place la page à ce défilement.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMediaQuery, usePreferredReducedMotion } from '@vueuse/core'
import { ArrowDown, ArrowRight } from '@lucide/vue'
import { MotionConfig, motion, useInView, useMotionValue, useMotionValueEvent, useScroll, useSpring } from 'motion-v'
import { lireVitrine, urlVitrine } from '@/api'
import { BASES, CASES, HAUT_BANDE, HAUT_BARRE, barresEmpreinte, blocsDominantes, fenetreLbp, lirePixels } from '@/compagnon'
import { DESCRIPTEURS, rangerParDescripteur } from '@/descripteurs'
import { cn } from '@/lib/utils'
import { utilisateur } from '@/session'
import BoutonTheme from '@/composants/BoutonTheme.vue'
import Compagnon from '@/composants/Compagnon.vue'
import Demonstration from '@/composants/Demonstration.vue'
import Empreinte from '@/composants/Empreinte.vue'
import Logo from '@/composants/Logo.vue'
import Mosaique from '@/composants/Mosaique.vue'
import Folder from '@/components/animate-ui/icons/Folder.vue'
import { buttonVariants } from '@/components/ui/button'

const vitrine = ref(undefined) // réponse de GET /api/vitrine ; undefined tant qu'elle n'est pas arrivée
const indisponible = ref('') // message affiché si la vitrine ne peut pas être lue
const requete = ref(null) // numéro de la photo requête choisie dans la démonstration
const derniere = ref(null) // dernière photo choisie : elle reste la compagne pendant qu'on en cherche une autre
watch(requete, (n) => n !== null && (derniere.value = n))

// Réglages de l'adresse : ?t= et ?p=
const route = useRoute()
const fige = route.query.t === undefined ? null : Number(route.query.t) || 0

onMounted(async () => {
  try {
    vitrine.value = await lireVitrine()
  } catch (e) {
    // Index absent ou serveur arrêté : la page s'affiche quand même, sans la photo ni la démonstration.
    indisponible.value = e instanceof TypeError ? 'Le serveur ne répond pas.' : e.message
  }
})

// Bouton principal : vers l'inscription, ou vers la galerie si la session est déjà ouverte.
const action = computed(() =>
  utilisateur.value
    ? { texte: 'Ouvrir ma galerie', vers: '/galerie' }
    : { texte: 'Créer un compte', vers: { path: '/connexion', query: { mode: 'inscription' } } },
)
// Classes du bouton principal : celles du composant Button, en plus grand.
const BOUTON = cn(buttonVariants(), 'group h-10 gap-2 px-4 text-[0.9375rem]')
// Étiquette : petit texte en chasse fixe, en capitales espacées.
const ETIQUETTE = 'font-mono text-xs tracking-[0.14em] text-muted-foreground uppercase'

// --- La photo compagnon ---

// La photo requête, ou la photo d'exemple tant qu'aucune n'est choisie.
const photo = computed(() => vitrine.value?.images[derniere.value ?? vitrine.value.exemple])

// Le système demande moins d'animations, ou WebGL ne démarre pas : pas de photo animée,
// chaque chapitre montre son état final, immobile.
const mouvement = usePreferredReducedMotion()
const sansWebgl = ref(false)
const anime = computed(() => mouvement.value !== 'reduce' && !sansWebgl.value && !indisponible.value)

// Ses pixels, lus dans le navigateur. Moins de particules sur un petit écran, ou si l'affichage ne suit pas.
const grand = useMediaQuery('(min-width: 1024px)')
const lent = ref(false)
const cote = computed(() => (grand.value ? 192 : 128) * (lent.value ? 0.66 : 1))
const pixels = shallowRef(null)
watch(
  [photo, cote],
  async ([choisie]) => {
    if (!choisie) return
    const lus = await lirePixels(urlVitrine(choisie.n), Math.round(cote.value)).catch(() => null)
    // Une autre photo a pu être choisie pendant la lecture : on ne garde que la bonne.
    if (lus && choisie === photo.value) pixels.value = { ...lus, n: choisie.n }
    else if (!lus) sansWebgl.value = true
  },
  { immediate: true },
)

// Nom français des catégories de GHIM-10K montrées dans la vitrine (les dossiers de la base sont en anglais).
const CATEGORIES = {
  sunset: 'Couchers de soleil',
  fireworks: "Feux d'artifice",
  trees: 'Arbres',
  'sea shores': 'Bords de mer',
}

// --- Ce que les chapitres écrivent de la photo ---

// String.fromCharCode(160) : l'espace insécable, écrit sans caractère invisible dans le fichier.
const pourcent = (part) => Math.round(part * 100) + String.fromCharCode(160) + '%'
// Couleur dominante (canaux entre 0 et 1) écrite pour le CSS.
const couleurCss = (c) => `rgb(${c.r * 255} ${c.g * 255} ${c.b * 255})`
// Part de chaque couleur dominante dans la photo : « 38 % »
const partsCouleurs = computed(() => photo.value.dominantes.map((c) => pourcent(c.proportion)))
const blocs = computed(() => blocsDominantes(photo.value.dominantes))

// Histogrammes : pour chaque canal, ses 32 cases (comptées sur les pixels) et la plus remplie.
const CANAUX = [
  { nom: 'Rouge', lettre: 'R', couleur: 'var(--canal-r)' },
  { nom: 'Vert', lettre: 'V', couleur: 'var(--canal-g)' },
  { nom: 'Bleu', lettre: 'B', couleur: 'var(--canal-b)' },
]
const histogrammes = computed(() => {

  return CANAUX.map((canal, i) => {
    const cases = [...pixels.value.histos[i]]
    const pleine = cases.indexOf(Math.max(...cases))
    return { ...canal, cases: cases.map((part) => part / cases[pleine]), pleine, part: pourcent(cases[pleine]) }
  })
})

// L'empreinte : les 141 valeurs, rangées par descripteur ; chacune est une hauteur de barre entre -1 et 1.
const empreinte = computed(() => rangerParDescripteur(photo.value.vecteur, vitrine.value.groupes))
// Texture : les 6 valeurs GLCM et les 10 valeurs LBP du vecteur.
const texture = computed(() => empreinte.value.filter((d) => d.cle === 'glcm' || d.cle === 'lbp'))
// Dans la scène : sous l'empreinte, le début et la largeur de chaque descripteur, en pourcentage.
const reperes = computed(() => {
  const { barres, largeur } = barresEmpreinte(photo.value.vecteur, vitrine.value.groupes)
  return DESCRIPTEURS.map((d, rang) => {
    const siennes = barres.filter((b) => b.groupe === rang)
    const debut = siennes[0].x - largeur / 2
    return { ...d, nombre: siennes.length, gauche: (debut + 0.5) * 100, large: (siennes.at(-1).x + largeur / 2 - debut) * 100 }
  })
})

// Fenêtre LBP : la cellule observée (donnée par la photo animée, ou fixe) et ses 8 voisins.
const cellule = ref(null)
const loupe = computed(() => {
  const p = pixels.value
  const [col, ligne] = cellule.value ?? [Math.round(p.cols * 0.42), Math.round(p.lignes * 0.6)]
  const lue = fenetreLbp(p, Math.max(1, Math.min(p.cols - 2, col)), Math.max(1, Math.min(p.lignes - 2, ligne)))
  // Les 9 cases de la fenêtre, ligne par ligne ; celle du milieu est le pixel observé.
  const cases = Array(9).fill({ gris: lue.centre, bit: null })
  for (const v of lue.voisins) cases[(v.dl + 1) * 3 + v.dc + 1] = v
  return { ...lue, cases }
})

// Hauteur dans la scène (0,375 en haut, -0,375 en bas) écrite en pourcentage depuis le haut.
const haut = (y) => ((0.375 - y) / 0.75) * 100 + '%'

// --- Le fil de la page : l'étape suit le défilement ---

const histoire = ref(null) // le bloc des chapitres
const scene = ref(null) // la zone collante où vit la photo
const repere = ref(null) // la boîte de la scène : centre et largeur de la photo

// Hauteurs de défilement où chaque étape est atteinte : 0 photo, 1 histogrammes, 2 dominantes,
// 3 texture, 4 empreinte, 5 la photo est posée dans la case « Requête », 6 elle s'efface.
let ancres = [0, 1, 2, 3, 4, 5, 6]
function mesurer() {
  if (!histoire.value) return
  const hautDe = (element) => element.getBoundingClientRect().top + scrollY
  // Ligne de lecture : le milieu de ce qui reste visible sous l'en-tête (et sous la bande de la photo, sur téléphone).
  const bande = grand.value || !scene.value ? 0 : scene.value.offsetHeight
  const lecture = (56 + bande + innerHeight) / 2
  const blocs = [...histoire.value.querySelectorAll('[data-etape]')]
  ancres = blocs.map((bloc) => hautDe(bloc) + bloc.offsetHeight / 2 - lecture)
  ancres[0] = 0
  const emplacement = document.querySelector('[data-case-requete]')
  const pose = emplacement
    ? hautDe(emplacement) + emplacement.offsetHeight / 2 - innerHeight * (grand.value ? 0.42 : 0.32)
    : ancres.at(-1) + innerHeight
  ancres.push(pose, pose + innerHeight * 0.25)
  // Les étapes se suivent toujours dans l'ordre, même sur un écran très haut.
  for (let i = 1; i < ancres.length; i++) ancres[i] = Math.max(ancres[i], ancres[i - 1] + 1)
}
// Étape (entre 0 et 6) à une hauteur de défilement donnée : fonction de cette seule hauteur.
function etapeA(y) {
  let i = 0
  while (i < ancres.length - 2 && y >= ancres[i + 1]) i++
  return Math.max(0, Math.min(ancres.length - 1, i + (y - ancres[i]) / (ancres[i + 1] - ancres[i])))
}

// Défilement natif. L'étape affichée rejoint l'étape visée par un ressort sans rebond :
// la photo ne saute jamais, même avec une molette à crans.
const { scrollY: defilement } = useScroll()
const visee = useMotionValue(0)
const etape = useSpring(visee, { stiffness: 170, damping: 30, mass: 1 })
const viser = () => visee.set(etapeA(scrollY))
useMotionValueEvent(defilement, 'change', viser)
// Les légendes de la scène lisent l'étape dans la variable CSS --e.
useMotionValueEvent(etape, 'change', (e) => scene.value?.style.setProperty('--e', e))

// La mise en page change (photos arrivées, fenêtre redimensionnée) : on reprend les mesures.
let guetteur
onMounted(() => {
  guetteur = new ResizeObserver(() => {
    mesurer()
    viser()
  })
  guetteur.observe(document.body)
})
onBeforeUnmount(() => guetteur?.disconnect())

// ?p= : une fois la page en place, on va droit à ce défilement, sans animation.
let place = route.query.p === undefined
watch([pixels, indisponible], async () => {
  if (place) return
  place = true
  await nextTick()
  requestAnimationFrame(() => {
    const p = Math.max(0, Math.min(1, Number(route.query.p) || 0))
    scrollTo(0, p * (document.documentElement.scrollHeight - innerHeight))
    mesurer()
    viser()
    etape.jump(visee.get())
    scene.value?.style.setProperty('--e', visee.get())
  })
})

// --- Transformations ---

// L'originale et les cinq transformations, rejouées en CSS sur la photo : Motion anime chaque aperçu
// de « depart » à « arrivee » quand il entre dans la fenêtre. Dans la plateforme, le vrai calcul est fait
// par le serveur. Rotation : la photo tournée est plus haute que large, on la réduit pour la voir entière.
const TRANSFORMATIONS = [
  { nom: 'Originale' },
  { nom: 'Recadrage', depart: { scale: 1 }, arrivee: { scale: 1.8 } },
  { nom: 'Échelle 0,5', depart: { scale: 1 }, arrivee: { scale: 0.5 } },
  { nom: 'Rotation 90°', depart: { rotate: 0, scale: 1 }, arrivee: { rotate: 90, scale: 0.75 } },
  { nom: 'Miroir', depart: { scaleX: 1 }, arrivee: { scaleX: -1 } },
  { nom: 'Niveaux de gris', depart: { filter: 'grayscale(0)' }, arrivee: { filter: 'grayscale(1)' } },
]

// --- La galerie ---

// Les photos de la vitrine, rangées par catégorie comme dans une galerie.
const rangement = computed(() => {
  const dossiers = new Map() // catégorie → ses photos
  for (const image of vitrine.value.images) {
    dossiers.set(image.categorie, [...(dossiers.get(image.categorie) || []), image])
  }
  return [...dossiers].map(([categorie, images]) => ({ nom: CATEGORIES[categorie] || categorie, images }))
})

// --- La mesure ---

// Précision moyenne par itération, mesurée par backend/evaluer.py ; vide s'il n'a pas été lancé.
const evaluation = computed(() => vitrine.value?.evaluation ?? [])
// Haut du graphique : la dizaine de points au-dessus de la meilleure précision.
const plafond = computed(() => Math.ceil((Math.max(...evaluation.value) + 0.05) * 10) / 10)
// Les points de la courbe, en pourcentage de la largeur et de la hauteur du graphique.
const points = computed(() =>
  evaluation.value.map((valeur, i) => ({
    valeur,
    x: ((i + 0.5) / evaluation.value.length) * 100,
    y: (1 - valeur / plafond.value) * 100,
  })),
)
const trace = computed(() => points.value.map((p) => `${p.x},${p.y}`).join(' '))
// La courbe se trace quand le graphique entre dans la fenêtre, une seule fois.
const graphique = ref(null)
const graphiqueVu = useInView(graphique, { once: true, amount: 0.6 })
// Nombre à 2 décimales, écrit à la française : 0,31
const nombre = (valeur) => valeur.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// --- Animations (Motion) ---

const DOUX = [0.22, 1, 0.36, 1] // courbe commune : départ vif, arrivée douce

// Haut de page : les blocs entrent l'un après l'autre, dès l'affichage.
const ENTREES = [0, 1, 2, 3].map((rang) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, delay: 0.08 * rang, ease: DOUX },
}))

// Suite de la page : un bloc apparaît quand il entre dans la fenêtre, une seule fois.
// Deux réglages : d'abord, puis avec un léger retard.
const APPARITIONS = [0, 0.08].map((retard) => ({
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  inViewOptions: { once: true, amount: 0.2 },
  transition: { duration: 0.6, delay: retard, ease: DOUX },
}))
</script>

<template>
  <!-- reduced-motion="user" : si le système demande moins d'animations, Motion ne déplace plus les blocs -->
  <MotionConfig reduced-motion="user">
    <div class="flex min-h-screen flex-col">
      <header class="sticky top-0 z-40 bg-background">
        <div class="mx-auto flex h-14 w-full max-w-[100rem] items-center justify-between px-4 sm:px-6 lg:px-10 xl:px-16">
          <Logo />
          <nav class="flex items-center gap-1" aria-label="Compte">
            <BoutonTheme sans-texte />
            <RouterLink
              :to="utilisateur ? '/galerie' : '/connexion'"
              :class="cn(buttonVariants({ variant: 'outline', size: 'lg' }), 'px-3.5')"
            >
              {{ utilisateur ? 'Ma galerie' : 'Se connecter' }}
            </RouterLink>
          </nav>
        </div>
      </header>

      <main class="flex-1">
        <!-- La photo compagnon : un canevas posé sur toute la fenêtre, qui ne reçoit aucun clic -->
        <Compagnon
          v-if="anime && pixels"
          :pixels="pixels"
          :photo="vitrine.images[pixels.n]"
          :groupes="vitrine.groupes"
          :etape="etape"
          :repere="repere"
          :fige="fige"
          @fenetre="(col, ligne) => (cellule = [col, ligne])"
          @lent="lent = true"
          @absent="sansWebgl = true"
        />

        <!-- L'histoire : les chapitres d'un côté, la scène de la photo de l'autre (au-dessus, sur téléphone) -->
        <div ref="histoire" class="histoire mx-auto w-full max-w-[100rem] sm:px-6 lg:px-10 xl:px-16" :class="{ calme: !anime }">
          <div v-if="anime" ref="scene" class="scene" aria-hidden="true">
            <div class="etabli">
              <!-- Légende de l'étape en cours, en haut de la table -->
              <p v-if="photo" :class="[ETIQUETTE, 'titre']">
                <span class="legende" style="--i: 0">
                  Photo {{ photo.n + 1 }} sur {{ vitrine.images.length }} · {{ CATEGORIES[photo.categorie] || photo.categorie }}
                </span>
                <span class="legende" style="--i: 1">Histogrammes · 3 × {{ CASES }} cases</span>
                <span class="legende" style="--i: 2">Couleurs dominantes · {{ photo.dominantes.length }}</span>
                <span class="legende" style="--i: 3">Niveaux de gris · fenêtre 3 × 3</span>
                <span class="legende" style="--i: 4">Empreinte · {{ photo.vecteur.length }} valeurs</span>
              </p>
              <div ref="repere" class="repere">
                <div v-if="!pixels" class="squelette absolute inset-0 rounded-lg" />
                <template v-else-if="photo">
                  <!-- Histogrammes : la ligne de base de chaque canal -->
                  <div class="legende absolute inset-0 font-mono text-[10px] text-muted-foreground" style="--i: 1">
                    <p
                      v-for="(canal, i) in CANAUX"
                      :key="canal.nom"
                      class="absolute inset-x-0 flex justify-between border-t border-muted-foreground/40 pt-1"
                      :style="{ top: haut(BASES[i]) }"
                    >
                      <span :style="{ color: canal.couleur }">{{ canal.lettre }}</span>
                      <span v-if="i === 2" class="max-lg:hidden">0 → 255</span>
                    </p>
                  </div>
                  <!-- Dominantes : la part de chaque couleur, sous son bloc -->
                  <div class="legende absolute inset-0 font-mono text-[10px] text-muted-foreground" style="--i: 2">
                    <span
                      v-for="(bloc, i) in blocs"
                      :key="i"
                      class="absolute -translate-x-1/2 pt-2 whitespace-nowrap"
                      :style="{ left: (bloc.x + bloc.largeur / 2 + 0.5) * 100 + '%', top: haut(-HAUT_BANDE / 2) }"
                    >
                      {{ partsCouleurs[i] }}
                    </span>
                  </div>
                  <!-- Empreinte : la moyenne, les bornes, et le nom de chaque descripteur -->
                  <div class="legende absolute inset-0 font-mono text-[10px] text-muted-foreground" style="--i: 4">
                    <span class="absolute right-full pr-2 max-lg:hidden" :style="{ top: haut(HAUT_BARRE) }">+3&nbsp;σ</span>
                    <span class="absolute right-full -translate-y-full pr-2 max-lg:hidden" :style="{ top: haut(-HAUT_BARRE) }">−3&nbsp;σ</span>
                    <span class="absolute inset-x-0 border-t border-muted-foreground/40" :style="{ top: haut(0) }" />
                    <span
                      v-for="(d, i) in reperes"
                      :key="d.cle"
                      class="absolute border-t-2 whitespace-nowrap"
                      :style="{
                        left: d.gauche + '%',
                        width: d.large + '%',
                        top: `calc(${haut(-HAUT_BARRE)} + 0.75rem)`,
                        borderColor: d.couleur,
                      }"
                    >
                      <!-- Un nom sur deux est écrit une ligne plus bas : les descripteurs étroits ne se chevauchent pas -->
                      <span class="block max-lg:hidden" :class="i % 2 ? 'pt-5' : 'pt-1'">
                        {{ d.nom }} <span class="text-foreground">{{ d.nombre }}</span>
                      </span>
                    </span>
                  </div>
                </template>
              </div>
            </div>
          </div>

          <div class="chapitres px-4 sm:px-0">
            <!-- Accroche -->
            <section class="bloc premier" data-etape>
              <div>
                <motion.p v-bind="ENTREES[0]" :class="ETIQUETTE">Recherche d'images par le contenu</motion.p>
                <motion.h1
                  v-bind="ENTREES[1]"
                  class="mt-4 text-[clamp(2.25rem,10vw,3rem)] leading-[1.02] font-semibold tracking-[-0.04em] lg:text-[clamp(3rem,4.2vw,4.75rem)] lg:whitespace-nowrap"
                >
                  <!-- Le blanc écrit entre les deux lignes sépare les mots dans le texte lu ou copié -->
                  <span class="block">Qui se ressemble</span>{{ ' ' }}
                  <span class="block text-primary">se retrouve.</span>
                </motion.h1>
                <motion.p v-bind="ENTREES[2]" class="mt-5 max-w-lg text-base text-pretty text-muted-foreground sm:text-lg lg:text-xl">
                  Similis décrit chaque photo par 141 valeurs de couleur et de texture, puis retrouve celles qui lui
                  ressemblent.
                </motion.p>
                <motion.div v-bind="ENTREES[3]" class="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3">
                  <RouterLink :to="action.vers" :class="BOUTON">
                    {{ action.texte }}
                    <ArrowRight class="transition-transform duration-200 group-hover:translate-x-0.5" />
                  </RouterLink>
                  <p v-if="photo" class="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <ArrowDown class="size-4" />
                    Faites défiler&nbsp;: cette photo se décompose.
                  </p>
                </motion.div>
              </div>
              <figure v-if="!anime" class="fixe">
                <img
                  v-if="photo"
                  :src="urlVitrine(photo.n)"
                  alt="Photo d'exemple de la démonstration"
                  class="w-full rounded-lg border object-cover"
                />
                <Mosaique v-else class="mx-auto w-full max-w-sm" />
              </figure>
            </section>

            <!-- 01 Couleur : histogrammes -->
            <section class="bloc" data-etape>
              <motion.div v-bind="APPARITIONS[0]">
                <p :class="ETIQUETTE"><span class="text-primary">01</span> · Couleur</p>
                <h2 class="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">D'abord, la couleur.</h2>
                <h3 class="mt-6 text-lg font-semibold tracking-tight lg:text-xl">Trois histogrammes</h3>
                <p class="mt-1 max-w-lg text-pretty text-muted-foreground lg:text-lg">
                  Chaque pixel tombe dans une case selon son niveau de rouge, de vert et de bleu. {{ CASES }} cases par
                  canal&nbsp;: {{ 3 * CASES }} valeurs.
                </p>
                <template v-if="pixels && photo">
                  <ul class="mt-5 grid max-w-md gap-1.5 font-mono text-xs">
                    <li v-for="canal in histogrammes" :key="canal.nom" class="flex items-center gap-2">
                      <i class="size-2 rounded-[3px]" :style="{ background: canal.couleur }" />
                      <span class="w-12 text-foreground">{{ canal.nom }}</span>
                      <span class="text-muted-foreground">
                        niveaux {{ canal.pleine * 8 }} à {{ canal.pleine * 8 + 7 }}&nbsp;: {{ canal.part }} des pixels
                      </span>
                    </li>
                  </ul>
                  <p class="mt-3 max-w-md text-xs text-muted-foreground">
                    Compté dans votre navigateur sur les
                    {{ (pixels.largeur * pixels.hauteur).toLocaleString('fr-FR') }} pixels de la photo. Pour chaque
                    canal, la case la plus remplie.
                  </p>
                </template>
              </motion.div>
              <figure v-if="!anime && pixels" class="fixe grid gap-3">
                <div
                  v-for="canal in histogrammes"
                  :key="canal.nom"
                  class="flex h-24 items-end gap-px border-b"
                  role="img"
                  :aria-label="'Histogramme du canal ' + canal.nom"
                >
                  <i
                    v-for="(part, i) in canal.cases"
                    :key="i"
                    class="flex-1 rounded-t-[2px]"
                    :style="{ height: part * 100 + '%', background: canal.couleur }"
                  />
                </div>
              </figure>
            </section>

            <!-- 01 Couleur : dominantes et moments -->
            <section class="bloc" data-etape>
              <motion.div v-bind="APPARITIONS[0]">
                <h3 class="text-lg font-semibold tracking-tight lg:text-xl">Cinq couleurs dominantes</h3>
                <p class="mt-1 max-w-lg text-pretty text-muted-foreground lg:text-lg">
                  Les pixels se regroupent en 5 couleurs. Chaque bloc est aussi large que la part de sa couleur dans
                  la photo. Couleurs et parts&nbsp;: 20 valeurs.
                </p>
                <ul v-if="photo" class="mt-5 flex flex-wrap gap-x-4 gap-y-2 font-mono text-xs">
                  <li v-for="(c, i) in photo.dominantes" :key="i" class="flex items-center gap-1.5">
                    <i class="palette size-4 rounded-[5px] border" :style="{ background: couleurCss(c) }" />
                    {{ partsCouleurs[i] }}
                  </li>
                </ul>
                <p class="mt-5 max-w-lg text-sm text-pretty text-muted-foreground lg:text-base">
                  S'y ajoutent 9 moments&nbsp;: moyenne, écart-type et asymétrie de la teinte, de la saturation et de
                  la valeur.
                </p>
              </motion.div>
              <figure v-if="!anime && photo" class="fixe">
                <div
                  class="flex h-28 gap-1 overflow-hidden rounded-lg"
                  role="img"
                  :aria-label="'Parts des 5 couleurs dominantes : ' + partsCouleurs.join(', ')"
                >
                  <i
                    v-for="(c, i) in photo.dominantes"
                    :key="i"
                    class="palette min-w-1"
                    :style="{ flex: c.proportion * 100 + ' 1 0%', background: couleurCss(c) }"
                  />
                </div>
              </figure>
            </section>

            <!-- 02 Texture -->
            <section class="bloc" data-etape>
              <motion.div v-bind="APPARITIONS[0]">
                <p :class="ETIQUETTE"><span class="text-primary">02</span> · Texture</p>
                <h2 class="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">Ensuite, la texture.</h2>
                <p class="mt-4 max-w-lg text-pretty text-muted-foreground lg:text-lg">
                  La photo passe en niveaux de gris. Une fenêtre de 3 × 3 compare un pixel à ses 8 voisins&nbsp;: 1 si
                  le voisin est au moins aussi clair, 0 sinon. Les 8 réponses forment un motif (LBP).
                </p>
                <template v-if="pixels && photo">
                  <!-- La fenêtre : à gauche les niveaux de gris lus, à droite les 8 réponses -->
                  <div class="mt-5 flex flex-wrap items-center gap-x-4 gap-y-3">
                    <div
                      class="grid grid-cols-3 gap-0.5 font-mono text-[11px]"
                      role="img"
                      :aria-label="'Niveaux de gris de la fenêtre. Centre : ' + loupe.centre"
                    >
                      <!-- Texte clair sur gris sombre, sombre sur gris clair : toujours lisible -->
                      <span
                        v-for="(c, i) in loupe.cases"
                        :key="i"
                        class="grid size-10 place-items-center rounded-[5px]"
                        :class="{ 'outline-2 -outline-offset-2 outline-primary': c.bit === null }"
                        :style="{ background: `rgb(${c.gris} ${c.gris} ${c.gris})`, color: c.gris > 140 ? '#16191D' : '#EDEEF0' }"
                      >
                        {{ c.gris }}
                      </span>
                    </div>
                    <ArrowRight class="size-4 text-muted-foreground" />
                    <div class="grid grid-cols-3 gap-0.5 font-mono text-sm" aria-hidden="true">
                      <span
                        v-for="(c, i) in loupe.cases"
                        :key="i"
                        class="grid size-10 place-items-center rounded-[5px] border"
                        :class="
                          c.bit === null
                            ? 'border-transparent text-[10px] text-muted-foreground'
                            : c.bit
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'bg-muted text-muted-foreground'
                        "
                      >
                        {{ c.bit === null ? '≥ ' + c.gris : c.bit }}
                      </span>
                    </div>
                    <p class="font-mono text-xs text-muted-foreground">
                      Motif<br />
                      <span class="text-base tracking-[0.18em] text-foreground">{{ loupe.motif }}</span>
                    </p>
                  </div>
                  <p class="mt-3 max-w-md text-xs text-muted-foreground">
                    Calculé ici sur les carrés affichés. Similis le fait sur chaque pixel, range les motifs en 10
                    familles, et ajoute 6 mesures de cooccurrence (GLCM).
                  </p>
                  <!-- Les valeurs de texture du vecteur, en écarts à la moyenne -->
                  <div class="mt-5 flex max-w-md gap-5">
                    <div v-for="d in texture" :key="d.cle" :style="{ flex: d.valeurs.length }">
                      <Empreinte
                        :groupes="[d]"
                        class="h-14"
                        :aria-label="`Les ${d.valeurs.length} valeurs ${d.nom} de la photo, comparées à la moyenne de GHIM-10K`"
                      />
                      <p class="mt-1.5 font-mono text-[11px] text-muted-foreground">
                        {{ d.nom }} <span class="text-foreground">{{ d.valeurs.length }}</span>
                      </p>
                    </div>
                  </div>
                </template>
              </motion.div>
              <figure v-if="!anime && photo" class="fixe">
                <img
                  :src="urlVitrine(photo.n)"
                  alt="La photo en niveaux de gris"
                  class="w-full rounded-lg border object-cover grayscale"
                />
              </figure>
            </section>

            <!-- 03 Empreinte -->
            <section class="bloc" data-etape>
              <motion.div v-bind="APPARITIONS[0]">
                <p :class="ETIQUETTE"><span class="text-primary">03</span> · Empreinte</p>
                <h2 class="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
                  141 valeurs&nbsp;: l'empreinte.
                </h2>
                <p class="mt-4 max-w-lg text-pretty text-muted-foreground lg:text-lg">
                  Tout se range sur une seule ligne, une barre par valeur. Vers le haut&nbsp;: plus que la moyenne
                  <template v-if="vitrine">des {{ vitrine.total.toLocaleString('fr-FR') }} images</template>
                  de la base. Vers le bas&nbsp;: moins. Une barre est pleine à 3 écarts-types.
                </p>
                <ul v-if="photo" class="mt-5 flex max-w-md flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
                  <li v-for="d in empreinte" :key="d.cle" class="flex items-center gap-1.5">
                    <i class="size-2 rounded-[3px]" :style="{ background: d.couleur }" />
                    {{ d.nom }}
                    <span class="font-mono text-foreground">{{ d.valeurs.length }}</span>
                  </li>
                </ul>
                <p class="mt-5 max-w-lg text-sm text-pretty text-muted-foreground lg:text-base">
                  C'est ce vecteur que la recherche compare d'une photo à l'autre.
                </p>
              </motion.div>
              <figure v-if="!anime && photo" class="fixe">
                <Empreinte
                  :groupes="empreinte"
                  class="h-36"
                  aria-label="Les 141 valeurs de la photo, comparées à la moyenne de GHIM-10K"
                />
              </figure>
            </section>
          </div>
        </div>

        <!-- 04 Recherche et retour de pertinence : la démonstration -->
        <section class="mx-auto w-full max-w-[100rem] px-4 pt-10 sm:px-6 lg:px-10 lg:pt-4 xl:px-16">
          <motion.div v-bind="APPARITIONS[0]" class="grid gap-x-6 gap-y-3 lg:grid-cols-12 lg:items-end">
            <div class="lg:col-span-7">
              <p :class="ETIQUETTE"><span class="text-primary">04</span> · Recherche et retour de pertinence</p>
              <h2 class="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">Chercher, cocher, affiner.</h2>
            </div>
            <p class="max-w-lg text-pretty text-muted-foreground lg:col-span-5 lg:text-lg">
              La photo devient la requête. Les autres sont classées par distance entre empreintes. Cochez celles qui
              conviennent&nbsp;: le retour de pertinence repondère les 141 valeurs.
            </p>
          </motion.div>

          <div class="mt-8">
            <Demonstration
              v-if="!indisponible"
              v-model:requete="requete"
              :vitrine="vitrine"
              :noms="CATEGORIES"
              :attrait="fige === null"
            />
            <!-- Index absent ou serveur arrêté : la page reste présentable -->
            <div v-else class="grid items-center gap-6 rounded-2xl border bg-card p-6 sm:grid-cols-[1fr_auto]">
              <div>
                <p class="font-medium">Démonstration indisponible</p>
                <p class="mt-1 text-sm text-muted-foreground">{{ indisponible }}</p>
              </div>
              <Mosaique class="w-44" />
            </div>
            <p class="mt-2.5 min-h-4 text-xs text-muted-foreground">
              <template v-if="vitrine">
                Calcul réel, refait dans votre navigateur sur {{ vitrine.images.length }} des
                {{ vitrine.total.toLocaleString('fr-FR') }} photos de GHIM-10K.
              </template>
            </p>
          </div>
        </section>

        <!-- 05 Mesure, 06 Plateforme : transformations et galerie -->
        <section class="mx-auto w-full max-w-[100rem] px-4 pt-20 pb-20 sm:px-6 sm:pt-28 lg:px-10 xl:px-16">
          <div class="grid gap-6 lg:grid-cols-12">
            <!-- Mesure : précision moyenne à chaque itération, lue dans le tableau de l'évaluation -->
            <motion.article
              v-if="evaluation.length"
              v-bind="APPARITIONS[0]"
              class="flex flex-col rounded-2xl border bg-card p-5 sm:p-6 lg:col-span-7"
            >
              <p :class="ETIQUETTE"><span class="text-primary">05</span> · Mesure</p>
              <div class="mt-3 flex flex-wrap items-end justify-between gap-x-8 gap-y-2">
                <h2 class="text-2xl font-semibold tracking-tight sm:text-3xl">Un retour de pertinence mesuré.</h2>
                <!-- Écrit sur une seule ligne : les blancs autour de la flèche sont ainsi gardés -->
                <p class="font-mono text-3xl font-medium tracking-tight">
                  {{ nombre(evaluation[0]) }} <span class="text-muted-foreground">→</span> <span class="text-primary">{{ nombre(evaluation.at(-1)) }}</span>
                </p>
              </div>
              <!-- La courbe : précision moyenne (de 0 au plafond) à chaque itération. Elle se trace à l'entrée. -->
              <div ref="graphique" class="relative mt-10 mb-6 min-h-44 flex-1 border-b" role="img" aria-label="Précision moyenne à chaque itération">
                <span class="absolute inset-x-0 top-0 border-t border-dashed" />
                <span class="absolute inset-x-0 top-1/2 border-t border-dashed" />
                <span class="absolute -top-4 right-0 font-mono text-[10px] text-muted-foreground">{{ nombre(plafond) }}</span>
                <motion.div
                  class="absolute inset-0"
                  :initial="false"
                  :animate="{ clipPath: graphiqueVu ? 'inset(-20% 0% -20% 0%)' : 'inset(-20% 100% -20% 0%)' }"
                  :transition="{ duration: 1.6, delay: 0.2, ease: DOUX }"
                >
                  <svg class="absolute inset-0 size-full overflow-visible" viewBox="0 0 100 100" preserveAspectRatio="none">
                    <polygon :points="`${points[0].x},100 ${trace} ${points.at(-1).x},100`" class="fill-primary-soft" />
                    <polyline
                      :points="trace"
                      fill="none"
                      class="stroke-primary"
                      stroke-width="2"
                      stroke-linejoin="round"
                      vector-effect="non-scaling-stroke"
                    />
                  </svg>
                  <span
                    v-for="(p, i) in points"
                    :key="i"
                    class="absolute -translate-x-1/2 -translate-y-1/2"
                    :style="{ left: p.x + '%', top: p.y + '%' }"
                  >
                    <i class="block size-2 rounded-full border-2 border-primary bg-card" />
                    <span class="absolute bottom-3 left-1/2 -translate-x-1/2 font-mono text-[10px]">{{ nombre(p.valeur) }}</span>
                  </span>
                </motion.div>
                <ol class="absolute inset-x-0 top-full flex pt-1.5 font-mono text-[10px] text-muted-foreground" aria-hidden="true">
                  <li v-for="(p, i) in points" :key="i" class="flex-1 text-center">{{ i + 1 }}</li>
                </ol>
              </div>
              <ol class="sr-only">
                <li v-for="(p, i) in points" :key="i">Itération {{ i + 1 }} : {{ nombre(p.valeur) }}</li>
              </ol>
              <p class="max-w-2xl pt-3 text-xs text-pretty text-muted-foreground">
                Précision moyenne sur 25 résultats, pour 100 requêtes&nbsp;: 5 images par catégorie de GHIM-10K,
                tirées avec une graine fixe. Une image est pertinente si elle vient du même dossier que la requête.
                Itération 1&nbsp;: recherche simple. Ensuite, à chaque itération, les bons résultats sont cochés,
                comme le ferait un utilisateur.
              </p>
            </motion.article>

            <!-- Transformations : l'originale, puis cinq aperçus de la même photo -->
            <motion.article
              v-if="photo"
              v-bind="APPARITIONS[1]"
              class="flex flex-col rounded-2xl border bg-card p-5 sm:p-6"
              :class="evaluation.length ? 'lg:col-span-5' : 'lg:col-span-12'"
            >
              <p :class="ETIQUETTE"><span class="text-primary">06</span> · Transformations</p>
              <h2 class="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">Cinq transformations.</h2>
              <p class="mt-2 text-sm text-pretty text-muted-foreground">
                Recadrage, échelle, rotation, miroir, niveaux de gris. Le résultat est une nouvelle image&nbsp;:
                l'originale reste intacte.
              </p>
              <ul class="mt-5 grid grid-cols-3 gap-x-2 gap-y-3">
                <li v-for="(t, i) in TRANSFORMATIONS" :key="t.nom">
                  <div class="aspect-[4/3] overflow-hidden rounded-md border bg-muted">
                    <motion.img
                      :src="urlVitrine(photo.n)"
                      alt=""
                      class="size-full object-cover"
                      :initial="t.depart"
                      :while-in-view="t.arrivee"
                      :in-view-options="{ once: true, amount: 0.6 }"
                      :transition="{ duration: 0.9, delay: 0.25 + i * 0.1, ease: DOUX }"
                    />
                  </div>
                  <p class="mt-1.5 truncate text-center text-[11px] text-muted-foreground">{{ t.nom }}</p>
                </li>
              </ul>
              <p class="mt-auto pt-5 text-xs text-muted-foreground">
                Le nom du fichier garde la trace de l'opération&nbsp;:
                <span class="font-mono text-foreground">{{ photo.categorie.replace(' ', '_') }}_rotation_90.jpg</span>
              </p>
            </motion.article>

            <!-- Galerie : le dernier bloc mène à l'inscription -->
            <motion.article
              v-bind="APPARITIONS[0]"
              class="grid gap-6 rounded-2xl border border-primary/15 bg-primary-soft p-5 sm:p-6 lg:col-span-12"
              :class="{ 'md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]': photo }"
            >
              <div class="flex flex-col justify-between gap-6">
                <div class="max-w-xl">
                  <p :class="[ETIQUETTE, 'text-foreground/60']"><span class="text-primary">07</span> · Galerie</p>
                  <h2 class="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">Votre galerie, vos catégories.</h2>
                  <p class="mt-2 text-sm text-pretty text-foreground/75">
                    Chargez vos photos, rangez-les en catégories et sous-catégories, puis lancez la recherche à
                    partir de n'importe laquelle.
                    <template v-if="photo">Ici, les photos de la démonstration, chacune dans sa catégorie.</template>
                  </p>
                </div>
                <div class="flex flex-wrap items-center gap-x-5 gap-y-2">
                  <RouterLink :to="action.vers" :class="BOUTON">
                    {{ action.texte }}
                    <ArrowRight class="transition-transform duration-200 group-hover:translate-x-0.5" />
                  </RouterLink>
                  <RouterLink
                    v-if="!utilisateur"
                    to="/connexion"
                    class="rounded-sm text-sm font-medium text-primary underline-offset-4 hover:underline"
                  >
                    J'ai déjà un compte
                  </RouterLink>
                </div>
              </div>

              <!-- Les photos de la démonstration, rangées par catégorie comme dans une galerie -->
              <ul
                v-if="photo"
                class="grid grid-cols-2 gap-x-4 gap-y-4 self-center xl:grid-cols-4"
                aria-label="Les photos de la démonstration, rangées par catégorie"
              >
                <li v-for="dossier in rangement" :key="dossier.nom">
                  <p class="flex items-center gap-1.5 text-xs font-medium">
                    <Folder :size="14" class="shrink-0 text-primary" />
                    <span class="truncate">{{ dossier.nom }}</span>{{ ' ' }}
                    <span class="font-mono font-normal text-foreground/60">{{ dossier.images.length }}</span>
                  </p>
                  <div class="mt-1.5 grid grid-cols-3 gap-1">
                    <img
                      v-for="image in dossier.images"
                      :key="image.n"
                      :src="urlVitrine(image.n)"
                      alt=""
                      class="aspect-[4/3] w-full rounded-[4px] object-cover"
                    />
                  </div>
                </li>
              </ul>
            </motion.article>
          </div>
        </section>
      </main>

      <footer class="border-t">
        <div
          class="mx-auto flex w-full max-w-[100rem] flex-wrap justify-between gap-x-8 gap-y-1 px-4 py-6 text-sm text-muted-foreground sm:px-6 lg:px-10 xl:px-16"
        >
          <p>Similis, mini-projet de Multimedia Mining, groupe 1.</p>
          <p>Base GHIM-10K. Retour de pertinence&nbsp;: Feature Relevance Estimation.</p>
        </div>
      </footer>
    </div>
  </MotionConfig>
</template>

<style scoped>
/* --- L'histoire : la scène de la photo et les chapitres ---
   Téléphone : la scène est une bande collante en haut (40 % de la hauteur), le texte défile dessous.
   Grand écran : la scène tient la colonne de droite, les chapitres celle de gauche. */
.scene {
  position: sticky;
  top: 3.5rem; /* sous l'en-tête */
  z-index: 20;
  height: 40svh;
  --e: 0; /* étape en cours, écrite par la page à chaque image */
}
.etabli {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  container-type: size;
  border-bottom: 1px solid var(--border);
  /* Une table de travail : un fond uni, et un point tous les 20 pixels. */
  background:
    radial-gradient(circle, var(--border) 1px, transparent 1.5px) 0 0 / 20px 20px,
    var(--background);
}
/* La boîte de la scène, au format 4 / 3 : la photo en paysage la remplit. */
.repere {
  position: relative;
  width: min(100cqw - 2.5rem, (100cqh - 3.5rem) / 0.78);
  aspect-ratio: 4 / 3;
}
.titre {
  position: absolute;
  top: 0.6rem;
  left: 1rem;
  font-size: 10px;
}
.titre .legende {
  position: absolute;
  white-space: nowrap;
}
/* Une légende n'est visible qu'autour de son étape (--i) : pleine à moins d'un quart d'étape, éteinte à 0,42. */
.legende {
  opacity: clamp(0, (0.42 - max(var(--e) - var(--i), var(--i) - var(--e))) * 6, 1);
}
.bloc {
  display: flex;
  min-height: 60svh;
  flex-direction: column;
  justify-content: center;
  padding-block: 2.5rem;
}
/* Téléphone : l'accroche vient juste sous la bande de la photo. */
.bloc.premier {
  min-height: 0;
  justify-content: flex-start;
  padding-block: 2rem 4rem;
}

/* Grand écran : toute la page suit une grille de 12 colonnes, séparées de 1,5 rem.
   La scène tient les colonnes 7 à 12 ; les chapitres, les colonnes 1 à 6, puis 2 à 6 sur un écran large. */
@media (min-width: 1024px) {
  .histoire {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    column-gap: 1.5rem;
  }
  .scene {
    grid-row: 1;
    grid-column: 7 / -1;
    align-self: start;
    display: grid;
    align-items: center; /* la table est centrée dans la hauteur de la fenêtre */
    height: calc(100svh - 3.5rem);
  }
  /* La table n'occupe plus toute la hauteur : elle garde une forme proche de celle de la photo
     (hauteur = 92 % de sa largeur), sans jamais dépasser la fenêtre. */
  .etabli {
    position: relative;
    inset: auto;
    width: 100%;
    aspect-ratio: 1 / 0.92;
    max-height: calc(100% - 2rem);
    border: 1px solid var(--border);
    border-radius: calc(var(--radius) * 1.8);
    background:
      radial-gradient(circle, var(--border) 1px, transparent 1.5px) 0 0 / 24px 24px,
      var(--card);
  }
  .repere {
    width: min(100cqw - 5rem, (100cqh - 7rem) / 0.75);
  }
  .titre {
    top: 1.1rem;
    left: 1.25rem;
    font-size: 11px;
  }
  .chapitres {
    grid-row: 1;
    grid-column: 1 / 7;
  }
  .bloc {
    min-height: 100svh;
  }
  .bloc.premier {
    min-height: calc(100svh - 3.5rem);
    justify-content: center;
    padding-block: 2.5rem;
  }
}
@media (min-width: 1280px) {
  .chapitres {
    grid-column: 2 / 7;
  }
}

/* Sans animation : plus de scène. Chaque chapitre montre son texte et, à côté, son état final. */
.histoire.calme {
  display: block;
}
.calme .bloc {
  min-height: 0;
  gap: 2rem;
  padding-block: 3rem;
}
.fixe {
  width: 100%;
  max-width: 34rem;
}
@media (min-width: 1024px) {
  /* La même grille de 12 colonnes : le texte à gauche, la figure dans les colonnes 7 à 12. */
  .calme .bloc {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    align-items: center;
    column-gap: 1.5rem;
    padding-block: 5rem;
  }
  .calme .bloc > :first-child {
    grid-column: 1 / 7;
  }
  .calme .bloc.premier {
    min-height: calc(100svh - 3.5rem);
  }
  .fixe {
    grid-column: 7 / -1;
    justify-self: center;
  }
}
@media (min-width: 1280px) {
  .calme .bloc > :first-child {
    grid-column: 2 / 7;
  }
}

/* Couleurs dominantes : au changement de photo, les parts et les teintes glissent. */
.palette {
  transition:
    flex-grow 0.6s cubic-bezier(0.22, 1, 0.36, 1),
    background-color 0.6s ease;
}
</style>
