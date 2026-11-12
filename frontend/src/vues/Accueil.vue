<script setup>
// Page d'accueil, publique. En haut : l'accroche et une démonstration de la recherche sur de vraies photos.
// En dessous : ce que la plateforme fait de la photo choisie dans la démonstration.
// Les entrées et les apparitions des blocs sont animées par Motion (motion-v).
import { computed, onMounted, ref } from 'vue'
import { ArrowRight } from '@lucide/vue'
import { MotionConfig, motion } from 'motion-v'
import { lireVitrine, urlVitrine } from '@/api'
import { DESCRIPTEURS } from '@/descripteurs'
import { cn } from '@/lib/utils'
import { utilisateur } from '@/session'
import BoutonTheme from '@/composants/BoutonTheme.vue'
import Demonstration from '@/composants/Demonstration.vue'
import Logo from '@/composants/Logo.vue'
import Mosaique from '@/composants/Mosaique.vue'
import Folder from '@/components/animate-ui/icons/Folder.vue'
import { buttonVariants } from '@/components/ui/button'

const vitrine = ref(undefined) // réponse de GET /api/vitrine ; undefined tant qu'elle n'est pas arrivée
const indisponible = ref('') // message affiché si la vitrine ne peut pas être lue
const requete = ref(null) // numéro de la photo requête choisie dans la démonstration

onMounted(async () => {
  try {
    vitrine.value = await lireVitrine()
  } catch (e) {
    // Index absent ou serveur arrêté : la page s'affiche quand même, sans la démonstration.
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

// --- La photo détaillée sous la démonstration ---

// La photo requête, ou la photo d'exemple tant qu'aucune n'est choisie.
const photo = computed(() => vitrine.value?.images[requete.value ?? vitrine.value.exemple])

// Son empreinte : ses 141 valeurs, rangées par descripteur. Chaque valeur est un écart à la moyenne
// de GHIM-10K, compté en écarts-types ; la barre est pleine à 3 écarts-types et ne va pas plus loin.
const empreinte = computed(() =>
  DESCRIPTEURS.map((d) => {
    const [debut, fin] = vitrine.value.groupes[d.cle]
    return { ...d, valeurs: photo.value.vecteur.slice(debut, fin).map((v) => Math.max(-1, Math.min(1, v / 3))) }
  }),
)

// Couleur dominante (canaux entre 0 et 1) écrite pour le CSS.
const couleurCss = (c) => `rgb(${c.r * 255} ${c.g * 255} ${c.b * 255})`
// Part de chaque couleur dominante dans la photo, en pourcentage : « 38 % »
const partsCouleurs = computed(() => photo.value.dominantes.map((c) => Math.round(c.proportion * 100) + '\u00a0%'))

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

// Nom français des catégories de GHIM-10K montrées dans la vitrine (les dossiers de la base sont en anglais).
const CATEGORIES = {
  sunset: 'Couchers de soleil',
  fireworks: "Feux d'artifice",
  trees: 'Arbres',
  'sea shores': 'Bords de mer',
}

// Les photos de la vitrine, rangées par catégorie comme dans une galerie.
const rangement = computed(() => {
  const dossiers = new Map() // catégorie → ses photos
  for (const image of vitrine.value.images) {
    dossiers.set(image.categorie, [...(dossiers.get(image.categorie) || []), image])
  }
  return [...dossiers].map(([categorie, images]) => ({ nom: CATEGORIES[categorie] || categorie, images }))
})

// --- L'évaluation ---

// Précision moyenne par itération, mesurée par backend/evaluer.py ; vide s'il n'a pas été lancé.
const evaluation = computed(() => vitrine.value?.evaluation ?? [])
const maximum = computed(() => Math.max(...evaluation.value))
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
// Deux réglages : colonne de gauche, puis colonne de droite avec un léger retard.
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
      <header class="mx-auto flex h-14 w-full max-w-7xl items-center justify-between px-4 sm:px-6">
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
      </header>

      <main class="flex-1">
        <!-- Haut de page : l'accroche, puis la démonstration sur toute la largeur -->
        <section class="mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 sm:pt-8">
          <div class="grid gap-x-12 gap-y-6 lg:grid-cols-12 lg:items-end">
            <div class="lg:col-span-7">
              <motion.p
                v-bind="ENTREES[0]"
                class="font-mono text-xs tracking-[0.14em] text-muted-foreground uppercase"
              >
                Recherche d'images par le contenu
              </motion.p>
              <motion.h1
                v-bind="ENTREES[1]"
                class="mt-4 text-[clamp(2rem,9vw,2.75rem)] leading-[1.05] font-semibold tracking-[-0.035em] sm:text-5xl xl:text-[3.5rem]"
              >
                <!-- Le blanc écrit entre les deux lignes sépare les mots dans le texte lu ou copié -->
                <span class="block">Qui se ressemble</span>{{ ' ' }}
                <span class="block text-primary">se retrouve.</span>
              </motion.h1>
            </div>
            <motion.div v-bind="ENTREES[2]" class="lg:col-span-5">
              <p class="max-w-md text-base text-pretty text-muted-foreground sm:text-lg">
                Similis décrit chaque photo par 141 valeurs de couleur et de texture, puis retrouve celles qui lui
                ressemblent.
              </p>
              <RouterLink :to="action.vers" :class="[BOUTON, 'mt-5']">
                {{ action.texte }}
                <ArrowRight class="transition-transform duration-200 group-hover:translate-x-0.5" />
              </RouterLink>
            </motion.div>
          </div>

          <motion.div v-bind="ENTREES[3]" class="mt-8">
            <Demonstration v-if="!indisponible" v-model:requete="requete" :vitrine="vitrine" :noms="CATEGORIES" />
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
          </motion.div>
        </section>

        <!-- Ce que la plateforme fait de la photo choisie : empreinte, transformations, mesure, galerie -->
        <section class="mx-auto w-full max-w-7xl px-4 pt-16 pb-20 sm:px-6 sm:pt-20">
          <motion.div v-if="photo" v-bind="APPARITIONS[0]" class="mb-8 max-w-2xl">
            <h2 class="text-2xl font-semibold tracking-tight sm:text-3xl">
              Ce que Similis fait de
              <img
                :src="urlVitrine(photo.n)"
                alt=""
                class="mx-0.5 inline-block h-[0.95em] w-[1.27em] rounded-[0.2em] object-cover align-[-0.08em]"
              />
              cette photo
            </h2>
            <p class="mt-2 text-muted-foreground">
              Choisissez-en une autre dans la démonstration&nbsp;: tout ce qui suit change avec elle.
            </p>
          </motion.div>

          <div class="grid gap-4 lg:grid-cols-12">
            <template v-if="photo">
              <!-- Empreinte : la photo, ses couleurs dominantes et ses 141 valeurs -->
              <motion.article
                v-bind="APPARITIONS[0]"
                class="flex flex-col rounded-2xl border bg-card p-5 sm:p-6 lg:col-span-7"
              >
                <div class="grid gap-5 sm:grid-cols-2 sm:items-center">
                  <div class="squelette aspect-[4/3] overflow-hidden rounded-lg border">
                    <img
                      :src="urlVitrine(photo.n)"
                      alt="Photo choisie dans la démonstration"
                      class="size-full object-cover"
                    />
                  </div>
                  <div>
                    <h3 class="text-lg font-semibold tracking-tight">Une empreinte de 141 valeurs</h3>
                    <p class="mt-1 text-sm text-muted-foreground">
                      Trois descripteurs de couleur, deux de texture. C'est ce vecteur que la recherche compare d'une
                      photo à l'autre.
                    </p>
                    <p class="mt-4 text-xs font-medium">Couleurs dominantes</p>
                    <!-- Une bande partagée en 5 : la largeur de chaque couleur est sa part dans la photo -->
                    <div
                      class="mt-1.5 flex h-7 gap-0.5 overflow-hidden rounded-md"
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
                    <p class="mt-1.5 flex gap-3 font-mono text-[11px] text-muted-foreground" aria-hidden="true">
                      <span v-for="(part, i) in partsCouleurs" :key="i">{{ part }}</span>
                    </p>
                  </div>
                </div>

                <!-- mt-auto : si le bloc voisin est plus haut, l'empreinte reste en bas du cadre -->
                <div class="mt-auto pt-6">
                  <div
                    class="empreinte"
                    role="img"
                    aria-label="Les 141 valeurs de la photo, comparées à la moyenne de GHIM-10K"
                  >
                    <span
                      v-for="d in empreinte"
                      :key="d.cle"
                      :style="{ color: d.couleur, flexGrow: d.valeurs.length }"
                    >
                      <i
                        v-for="(v, i) in d.valeurs"
                        :key="i"
                        :style="{ '--haut': Math.max(v, 0), '--bas': Math.max(-v, 0) }"
                      />
                    </span>
                  </div>
                  <ul class="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <li v-for="d in empreinte" :key="d.cle" class="flex items-center gap-1.5">
                      <i class="size-2 rounded-[3px]" :style="{ background: d.couleur }" />
                      {{ d.nom }}
                      <span class="font-mono text-foreground">{{ d.valeurs.length }}</span>
                    </li>
                  </ul>
                  <p class="mt-2 text-xs text-muted-foreground">
                    Une barre par valeur. Vers le haut&nbsp;: plus que la moyenne des
                    {{ vitrine.total.toLocaleString('fr-FR') }} images de la base. Vers le bas&nbsp;: moins.
                  </p>
                </div>
              </motion.article>

              <!-- Transformations : l'originale, puis cinq aperçus de la même photo -->
              <motion.article
                v-bind="APPARITIONS[1]"
                class="flex flex-col rounded-2xl border bg-card p-5 sm:p-6 lg:col-span-5"
              >
                <h3 class="text-lg font-semibold tracking-tight">Cinq transformations</h3>
                <p class="mt-1 text-sm text-muted-foreground">
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
                  <span class="font-mono text-foreground">plage_rotation_90.jpg</span>
                </p>
              </motion.article>

              <!-- Mesure : précision moyenne à chaque itération, lue dans le tableau de l'évaluation -->
              <motion.article
                v-if="evaluation.length"
                v-bind="APPARITIONS[0]"
                class="flex flex-col rounded-2xl border bg-card p-5 sm:p-6 lg:col-span-5"
              >
                <h3 class="text-lg font-semibold tracking-tight">Un retour de pertinence mesuré</h3>
                <p class="mt-1 text-sm text-muted-foreground">
                  Précision moyenne sur 25 résultats, pour 100 requêtes tirées de GHIM-10K.
                </p>
                <!-- Écrit sur une seule ligne : les blancs autour de la flèche sont ainsi gardés -->
                <p class="mt-5 font-mono text-3xl font-medium tracking-tight">
                  {{ nombre(evaluation[0]) }} <span class="text-muted-foreground">→</span> <span class="text-primary">{{ nombre(evaluation.at(-1)) }}</span>
                </p>
                <!-- Une barre par itération : sa hauteur est la précision, comptée à partir de zéro -->
                <ol class="mt-4 flex h-20 items-end gap-1.5" aria-label="Précision moyenne à chaque itération">
                  <li
                    v-for="(valeur, i) in evaluation"
                    :key="i"
                    class="flex-1"
                    :style="{ height: (valeur / maximum) * 100 + '%' }"
                    :aria-label="'Itération ' + (i + 1) + ' : ' + nombre(valeur)"
                    :title="'Itération ' + (i + 1) + ' : ' + nombre(valeur)"
                  >
                    <motion.i
                      class="block size-full origin-bottom rounded-t-[3px]"
                      :class="i ? 'bg-primary' : 'bg-muted-foreground/45'"
                      :initial="{ scaleY: 0.02 }"
                      :while-in-view="{ scaleY: 1 }"
                      :in-view-options="{ once: true }"
                      :transition="{ duration: 0.7, delay: 0.25 + i * 0.07, ease: DOUX }"
                    />
                  </li>
                </ol>
                <ol class="mt-1.5 flex gap-1.5 font-mono text-[10px] text-muted-foreground" aria-hidden="true">
                  <li v-for="(valeur, i) in evaluation" :key="i" class="flex-1 text-center">{{ i + 1 }}</li>
                </ol>
                <p class="mt-auto pt-4 text-xs text-muted-foreground">
                  Itération 1&nbsp;: recherche simple. Chaque itération suivante ajoute un tour de retour de
                  pertinence.
                </p>
              </motion.article>
            </template>

            <!-- Galerie : le dernier bloc mène à l'inscription -->
            <motion.article
              v-bind="APPARITIONS[photo && evaluation.length ? 1 : 0]"
              class="grid gap-6 rounded-2xl border border-primary/15 bg-primary-soft p-5 sm:p-6"
              :class="[
                photo && evaluation.length ? 'lg:col-span-7' : 'lg:col-span-12',
                { 'md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]': photo },
              ]"
            >
              <div class="flex flex-col justify-between gap-6">
                <div class="max-w-xl">
                  <h3 class="text-lg font-semibold tracking-tight">Votre galerie, vos catégories</h3>
                  <p class="mt-1 text-sm text-foreground/75">
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

              <!-- Les photos de la démonstration, rangées par catégorie comme dans une galerie.
                   @container : la disposition suit la largeur de ce bloc, pas celle de la fenêtre. -->
              <div v-if="photo" class="@container self-center">
                <ul
                  class="grid gap-x-3 gap-y-4 @xs:grid-cols-2"
                  aria-label="Les photos de la démonstration, rangées par catégorie"
                >
                  <li v-for="dossier in rangement" :key="dossier.nom">
                    <p class="flex items-center gap-1.5 text-xs font-medium">
                      <Folder :size="14" class="shrink-0 text-primary" />
                      <span class="truncate">{{ dossier.nom }}</span>{{ ' ' }}
                      <span class="font-mono font-normal text-foreground/60">{{ dossier.images.length }}</span>
                    </p>
                    <div class="mt-1.5 grid grid-cols-6 gap-1 @xs:grid-cols-3">
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
              </div>
            </motion.article>
          </div>
        </section>
      </main>

      <footer class="border-t">
        <div
          class="mx-auto flex w-full max-w-7xl flex-wrap justify-between gap-x-8 gap-y-1 px-4 py-6 text-sm text-muted-foreground sm:px-6"
        >
          <p>Similis, mini-projet de Multimedia Mining, groupe 1.</p>
          <p>Base GHIM-10K. Retour de pertinence&nbsp;: Feature Relevance Estimation.</p>
        </div>
      </footer>
    </div>
  </MotionConfig>
</template>

<style scoped>
/* Empreinte : une barre par valeur du vecteur, groupées par descripteur (un <span> par groupe).
   La ligne du milieu est la moyenne de GHIM-10K : la barre monte si la valeur est au-dessus
   de la moyenne (--haut), descend si elle est en dessous (--bas). */
.empreinte {
  position: relative;
  display: flex;
  gap: 3px;
  height: 5.5rem;
}
.empreinte::before {
  content: '';
  position: absolute;
  top: 50%;
  right: 0;
  left: 0;
  border-top: 1px solid var(--border);
}
.empreinte > span {
  display: flex;
  flex-basis: 0;
  min-width: 0;
}
.empreinte i {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
}
.empreinte i::before,
.empreinte i::after {
  content: '';
  position: absolute;
  right: 0;
  left: 0;
  height: 50%;
  background: currentColor;
  /* Changement de photo : les barres glissent vers leurs nouvelles hauteurs. */
  transition: transform 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}
.empreinte i::before {
  bottom: 50%;
  transform: scaleY(var(--haut));
  transform-origin: bottom;
}
.empreinte i::after {
  top: 50%;
  opacity: 0.5;
  transform: scaleY(var(--bas));
  transform-origin: top;
}
/* À partir de la tablette, un fin espace sépare les barres. */
@media (min-width: 640px) {
  .empreinte > span {
    gap: 1px;
  }
}

/* Couleurs dominantes : au changement de photo, les parts et les teintes glissent. */
.palette {
  transition:
    flex-grow 0.6s cubic-bezier(0.22, 1, 0.36, 1),
    background-color 0.6s ease;
}
</style>
