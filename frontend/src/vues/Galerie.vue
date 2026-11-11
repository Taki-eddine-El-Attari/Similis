<script setup>
// Galerie : arbre des catégories à gauche, images de la catégorie choisie à droite.
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AnimateIcon } from '@animate-ui/vue/icons'
import { ChevronRight, FolderPlus, Maximize2 } from '@lucide/vue'
import {
  chargerImages, creerCategorie, deplacerImage, listerCategories, listerImages,
  renommerCategorie, supprimerCategorie, supprimerImages, urlFichier, zipImages,
} from '@/api'
import Check from '@/components/animate-ui/icons/Check.vue'
import Download from '@/components/animate-ui/icons/Download.vue'
import Folder from '@/components/animate-ui/icons/Folder.vue'
import Pencil from '@/components/animate-ui/icons/Pencil.vue'
import Plus from '@/components/animate-ui/icons/Plus.vue'
import Trash2 from '@/components/animate-ui/icons/Trash2.vue'
import Upload from '@/components/animate-ui/icons/Upload.vue'
import X from '@/components/animate-ui/icons/X.vue'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const route = useRoute()
const router = useRouter()

const categories = ref([]) // liste à plat renvoyée par l'API
// id de la catégorie affichée ; null : « Sans catégorie ». Valeur de départ lue dans l'adresse.
const courante = ref(Number(route.query.categorie) || null)
const images = ref([])
const selection = ref([]) // ids des images cochées
const occupe = ref(false) // une action longue est en cours
const erreur = ref('')
const message = ref('') // compte rendu du dernier chargement
const survol = ref(false) // des fichiers sont glissés au-dessus de la page
const champFichiers = ref(null)

// --- Arbre des catégories ---

const fermees = ref([]) // ids des catégories repliées dans l'arbre ; par défaut tout est ouvert
const nbSansCategorie = ref(0)

// Transforme la liste à plat en liste ordonnée : chaque catégorie est suivie de ses enfants,
// avec son niveau de profondeur (0 pour une racine) et « parente » si elle a des enfants.
// replier = true : les enfants d'une catégorie repliée sont laissés de côté.
function descendants(parentId, niveau, replier) {
  return categories.value
    .filter((c) => c.parent_id === parentId)
    .flatMap((c) => {
      const enfants = replier && fermees.value.includes(c.id) ? [] : descendants(c.id, niveau + 1, replier)
      return [{ ...c, niveau, parente: categories.value.some((e) => e.parent_id === c.id) }, ...enfants]
    })
}
const arbre = computed(() => descendants(null, 0, true)) // lignes visibles de l'arbre
const toutes = computed(() => descendants(null, 0, false)) // menu « Déplacer vers »

// Replie ou déplie une catégorie de l'arbre.
function basculer(id) {
  fermees.value = fermees.value.includes(id) ? fermees.value.filter((f) => f !== id) : [...fermees.value, id]
}

const categorie = computed(() => categories.value.find((c) => c.id === courante.value) || null)

// Chemin de la catégorie affichée, de la racine jusqu'à elle : [Voyages, Maroc].
const chemin = computed(() => {
  const etapes = []
  for (let c = categorie.value; c; c = categories.value.find((p) => p.id === c.parent_id)) {
    etapes.unshift(c)
  }
  return etapes
})

// --- Renommer dans le titre ---

const nouveauNom = ref(null) // null : titre normal ; texte : le titre est un champ de saisie
const champNom = ref(null)

async function renommer() {
  nouveauNom.value = categorie.value.nom
  await nextTick() // le champ n'existe qu'après le prochain affichage
  champNom.value.select()
}

// Entrée ou clic ailleurs : enregistre. Échap : annule (nouveauNom repasse à null avant).
async function validerNom() {
  const nom = nouveauNom.value?.trim()
  if (nouveauNom.value === null) return
  nouveauNom.value = null
  if (!nom || nom === categorie.value.nom) return
  await executer(() => renommerCategorie(courante.value, nom))
  const echec = erreur.value
  await actualiser()
  erreur.value = echec
}

// --- Chargement des données ---

// Exécute une action de l'API : indicateur de chargement, et message d'erreur si elle échoue.
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

// Relit les catégories et les images de la catégorie affichée.
function actualiser() {
  return executer(async () => {
    // Le nombre d'images sans catégorie n'est pas dans la liste des catégories : on le demande à part.
    const [listeCategories, listeImages, sansCategorie] = await Promise.all([
      listerCategories(),
      listerImages(courante.value),
      courante.value === null ? null : listerImages(null),
    ])
    categories.value = listeCategories
    images.value = listeImages
    nbSansCategorie.value = (sansCategorie || listeImages).length
    // On ne garde cochées que les images encore affichées.
    selection.value = selection.value.filter((id) => listeImages.some((image) => image.id === id))
  })
}

function ouvrir(id) {
  nouveauNom.value = null
  courante.value = id
  selection.value = []
  message.value = ''
  // La catégorie affichée est notée dans l'adresse (/galerie?categorie=3) :
  // on la retrouve après un rechargement ou en revenant de la page d'une image.
  router.replace({ query: id === null ? {} : { categorie: id } })
  actualiser()
}

onMounted(async () => {
  await actualiser()
  // Catégorie de l'adresse introuvable (supprimée, ou d'un autre compte) : retour à « Sans catégorie ».
  if (courante.value !== null && !categorie.value) ouvrir(null)
})

// --- Chargement d'images ---

async function envoyer(fichiers) {
  if (!fichiers.length) return
  message.value = ''
  const reponse = await executer(() => chargerImages(fichiers, courante.value))
  if (!reponse) return
  const n = reponse.creees.length
  message.value = n === 1 ? '1 image chargée.' : `${n} images chargées.`
  if (reponse.refusees.length) {
    erreur.value = 'Fichiers refusés : ' + reponse.refusees.map((r) => `${r.nom} : ${r.raison}`).join(' ')
  }
  const refus = erreur.value
  await actualiser()
  erreur.value = refus // actualiser() efface l'erreur : on remet la liste des refus
}

function choisirFichiers(evenement) {
  envoyer([...evenement.target.files])
  evenement.target.value = '' // permet de rechoisir les mêmes fichiers
}

function deposer(evenement) {
  survol.value = false
  envoyer([...evenement.dataTransfer.files])
}

// --- Actions sur les images cochées ---

// Fait télécharger une adresse par le navigateur, sans quitter la page.
function declencher(adresse, nom) {
  const lien = document.createElement('a')
  lien.href = adresse
  lien.download = nom
  lien.click()
}

// Une image : le fichier lui-même. Plusieurs : une archive ZIP.
async function telecharger() {
  if (selection.value.length === 1) {
    const image = images.value.find((i) => i.id === selection.value[0])
    declencher(urlFichier(image.id, true), image.nom)
    return
  }
  const archive = await executer(() => zipImages(selection.value))
  if (!archive) return
  const adresse = URL.createObjectURL(archive)
  declencher(adresse, 'similis.zip')
  URL.revokeObjectURL(adresse)
}

async function deplacer(evenement) {
  // Dans le menu, la valeur vide désigne « Sans catégorie ».
  const cible = evenement.target.value === '' ? null : Number(evenement.target.value)
  evenement.target.selectedIndex = 0 // le menu revient sur son titre
  await executer(() => Promise.all(selection.value.map((id) => deplacerImage(id, cible))))
  const echec = erreur.value
  await actualiser()
  erreur.value = echec
}

// --- Boîte de dialogue : créer, renommer, supprimer ---

// dialogue : contenu de la boîte, { type, parent, nom, erreur, description } avec type parmi
// 'creer' (parent = dialogue.parent), 'supprimer-categorie', 'supprimer-images'.
// dialogueOuvert : boîte visible ou non. Les deux sont séparés pour que le contenu
// reste affiché pendant l'animation de fermeture.
const dialogue = ref({ type: 'creer', parent: null, nom: '', erreur: '', description: '' })
const dialogueOuvert = ref(false)

const TEXTES = {
  creer: { titre: 'Nouvelle catégorie', bouton: 'Créer' },
  'supprimer-categorie': { titre: 'Supprimer la catégorie', bouton: 'Supprimer' },
  'supprimer-images': { titre: 'Supprimer les images', bouton: 'Supprimer' },
}

function demander(type, parent = null) {
  dialogue.value = { type, parent, nom: '', erreur: '', description: decrire(type, parent) }
  dialogueOuvert.value = true
}

// Phrase d'explication de la boîte. Calculée à l'ouverture : elle ne change pas pendant la fermeture.
function decrire(type, parent) {
  if (type === 'creer') {
    const nom = categories.value.find((c) => c.id === parent)?.nom
    return nom ? `Elle sera créée dans « ${nom} ».` : 'Elle sera créée à la racine.'
  }
  if (type === 'supprimer-categorie') return `« ${categorie.value.nom} » sera supprimée. Elle doit être vide.`
  const n = selection.value.length
  return (n === 1 ? 'Cette image sera supprimée' : `Ces ${n} images seront supprimées`) + ' définitivement.'
}

async function confirmer() {
  const d = dialogue.value
  d.erreur = ''
  occupe.value = true
  try {
    if (d.type === 'creer') {
      await creerCategorie(d.nom, d.parent)
      // La catégorie parente est dépliée, pour que la nouvelle soit visible.
      fermees.value = fermees.value.filter((f) => f !== d.parent)
    } else if (d.type === 'supprimer-categorie') {
      const parent = categorie.value.parent_id
      await supprimerCategorie(courante.value)
      courante.value = parent // on remonte à la catégorie parente
    } else {
      await supprimerImages(selection.value)
    }
    dialogueOuvert.value = false
    await actualiser()
  } catch (e) {
    d.erreur = e.message // l'erreur reste affichée dans la boîte
  } finally {
    occupe.value = false
  }
}
</script>

<template>
  <section
    class="grid gap-6 lg:grid-cols-[15rem_1fr] lg:items-start"
    @dragover.prevent="survol = true"
    @dragleave="survol = $event.currentTarget.contains($event.relatedTarget)"
    @drop.prevent="deposer"
  >
    <!-- Arbre des catégories -->
    <nav class="rounded-xl border bg-card p-2" aria-label="Catégories">
      <div class="flex items-center justify-between py-1 pr-1 pl-2">
        <h2 class="text-xs font-medium text-muted-foreground">Catégories</h2>
        <AnimateIcon animate-on-hover as-child>
          <Button variant="ghost" size="icon-sm" aria-label="Nouvelle catégorie à la racine" @click="demander('creer')">
            <Plus :size="16" />
          </Button>
        </AnimateIcon>
      </div>
      <!-- Lignes serrées, comme un explorateur de fichiers : flèche pour replier, puis le nom -->
      <TransitionGroup tag="ul" name="branche">
        <li key="sans">
          <button
            type="button"
            class="ligne flex w-full items-center gap-1.5 rounded-md py-1 pr-2 pl-7 text-left text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            :class="{ active: courante === null }"
            :aria-current="courante === null ? 'true' : undefined"
            @click="ouvrir(null)"
          >
            <span class="min-w-0 flex-1 truncate">Sans catégorie</span>
            <span v-if="nbSansCategorie" class="font-mono text-xs text-muted-foreground">{{ nbSansCategorie }}</span>
          </button>
        </li>
        <li
          v-for="c in arbre"
          :key="c.id"
          class="ligne flex items-center rounded-md text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          :class="{ active: courante === c.id }"
          :style="{ paddingLeft: 0.25 + c.niveau * 0.75 + 'rem' }"
        >
          <!-- La flèche n'existe que si la catégorie a des sous-catégories ; sinon un espace de même largeur -->
          <button
            v-if="c.parente"
            type="button"
            class="grid size-5 shrink-0 place-items-center rounded hover:bg-foreground/10"
            :aria-expanded="!fermees.includes(c.id)"
            :aria-label="(fermees.includes(c.id) ? 'Déplier ' : 'Replier ') + c.nom"
            @click="basculer(c.id)"
          >
            <ChevronRight class="size-3.5 transition-transform duration-200" :class="{ 'rotate-90': !fermees.includes(c.id) }" />
          </button>
          <span v-else class="size-5 shrink-0" />
          <AnimateIcon animate-on-hover as-child>
            <button
              type="button"
              class="flex min-w-0 flex-1 items-center gap-1.5 py-1 pr-2 pl-0.5 text-left"
              :aria-current="courante === c.id ? 'true' : undefined"
              @click="ouvrir(c.id)"
            >
              <Folder :size="15" class="shrink-0" />
              <span class="min-w-0 flex-1 truncate">{{ c.nom }}</span>
              <span class="font-mono text-xs text-muted-foreground">{{ c.nb_images }}</span>
            </button>
          </AnimateIcon>
        </li>
      </TransitionGroup>
    </nav>

    <!-- Images de la catégorie affichée -->
    <div class="grid min-w-0 gap-4">
      <header class="flex flex-wrap items-end gap-2">
        <div class="mr-auto min-w-0">
          <!-- Chemin : chaque étape est un lien, sauf la catégorie affichée -->
          <nav class="flex flex-wrap items-center gap-x-1.5 text-sm text-muted-foreground" aria-label="Chemin">
            <button type="button" class="rounded hover:text-foreground hover:underline" @click="ouvrir(null)">Galerie</button>
            <template v-for="etape in chemin" :key="etape.id">
              <span aria-hidden="true">/</span>
              <span v-if="etape.id === courante" aria-current="page">{{ etape.nom }}</span>
              <button v-else type="button" class="rounded hover:text-foreground hover:underline" @click="ouvrir(etape.id)">
                {{ etape.nom }}
              </button>
            </template>
          </nav>
          <!-- Renommer : le titre devient un champ. Entrée ou clic ailleurs enregistre, Échap annule. -->
          <input
            v-if="nouveauNom !== null"
            ref="champNom"
            v-model="nouveauNom"
            class="-ml-1.5 w-full max-w-md rounded-md border bg-background px-1.5 text-2xl font-semibold tracking-tight outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            maxlength="50"
            aria-label="Nouveau nom de la catégorie"
            @keydown.enter="validerNom"
            @keydown.esc="nouveauNom = null"
            @blur="validerNom"
          />
          <h1 v-else class="truncate border border-transparent text-2xl font-semibold tracking-tight">
            {{ categorie?.nom || 'Sans catégorie' }}
          </h1>
        </div>
        <template v-if="categorie">
          <Button variant="outline" @click="demander('creer', courante)">
            <FolderPlus />
            Sous-catégorie
          </Button>
          <AnimateIcon animate-on-hover as-child>
            <Button variant="outline" @click="renommer">
              <Pencil :size="16" />
              Renommer
            </Button>
          </AnimateIcon>
          <AnimateIcon animate-on-hover as-child>
            <Button variant="outline" @click="demander('supprimer-categorie')">
              <Trash2 :size="16" />
              Supprimer
            </Button>
          </AnimateIcon>
        </template>
        <AnimateIcon animate-on-hover as-child>
          <Button :disabled="occupe" @click="champFichiers.click()">
            <Upload :size="16" />
            Charger des images
          </Button>
        </AnimateIcon>
        <input
          ref="champFichiers"
          type="file"
          class="hidden"
          multiple
          accept=".jpg,.jpeg,.png,image/jpeg,image/png"
          @change="choisirFichiers"
        />
      </header>

      <Transition name="fondu">
        <p v-if="message" role="status" class="text-sm text-muted-foreground">{{ message }}</p>
      </Transition>
      <Transition name="fondu">
        <p v-if="erreur" role="alert" class="text-sm text-destructive">{{ erreur }}</p>
      </Transition>

      <!-- Zone de dépôt : visible quand la catégorie est vide ou quand on glisse des fichiers -->
      <Transition name="fondu">
      <button
        v-if="!images.length || survol"
        type="button"
        class="grid min-h-[60vh] place-items-center content-center gap-1 rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground hover:border-primary hover:text-foreground"
        :class="{ 'border-primary bg-primary-soft text-foreground': survol }"
        @click="champFichiers.click()"
      >
        <Upload :size="20" />
        <span class="font-medium text-foreground">
          {{ occupe ? 'Chargement en cours' : 'Déposez vos images ici, ou cliquez pour les choisir' }}
        </span>
        <span>JPG ou PNG, 10 Mo maximum par fichier</span>
      </button>
      </Transition>

      <TransitionGroup
        v-if="images.length"
        tag="ul"
        name="grille"
        class="relative grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5"
        :aria-busy="occupe"
      >
        <li v-for="image in images" :key="image.id" class="relative">
          <!-- Ouvre la page de l'image (aperçu et transformations) ; le reste de la vignette sert à cocher -->
          <RouterLink
            :to="'/images/' + image.id"
            class="absolute top-1.5 right-1.5 z-10 grid size-6 place-items-center rounded-md bg-black/40 text-white hover:bg-black/70"
            :aria-label="'Ouvrir ' + image.nom"
            :title="'Ouvrir ' + image.nom"
          >
            <Maximize2 class="size-3.5" />
          </RouterLink>
          <label
            class="vignette relative block aspect-square cursor-pointer overflow-hidden rounded-lg border bg-muted outline-2 outline-offset-2 outline-transparent"
          >
            <!-- ponytail: la vignette est le fichier complet ; créer des miniatures si la grille devient lente -->
            <img :src="urlFichier(image.id)" :alt="image.nom" loading="lazy" draggable="false" class="size-full object-cover" />
            <input v-model="selection" type="checkbox" class="peer sr-only" :value="image.id" :aria-label="'Sélectionner ' + image.nom" />
            <span
              class="absolute top-1.5 left-1.5 grid size-5 place-items-center rounded-md border-[1.5px] border-white bg-black/25 text-transparent peer-checked:border-primary peer-checked:bg-primary peer-checked:text-primary-foreground peer-focus-visible:ring-3 peer-focus-visible:ring-ring/50"
              aria-hidden="true"
            >
              <Check :size="13" :stroke-width="3" />
            </span>
            <span class="absolute inset-x-0 bottom-0 flex justify-between gap-2 bg-gradient-to-t from-black/65 px-2 pt-4 pb-1.5 text-[11px] text-white">
              <span class="truncate">{{ image.nom }}</span>
              <span class="shrink-0 font-mono">{{ image.largeur }}×{{ image.hauteur }}</span>
            </span>
          </label>
        </li>
      </TransitionGroup>

      <!-- Barre d'actions : apparaît dès qu'une image est cochée -->
      <Transition name="barre">
        <div
          v-if="selection.length"
          class="sticky bottom-4 mx-auto flex w-fit max-w-full flex-wrap items-center gap-2 rounded-xl border bg-card py-2 pr-2 pl-4 text-sm shadow-lg"
          role="toolbar"
          aria-label="Actions sur les images sélectionnées"
        >
          <span>
            <b class="font-mono">{{ selection.length }}</b>
            {{ selection.length === 1 ? 'image sélectionnée' : 'images sélectionnées' }}
          </span>
          <AnimateIcon animate-on-hover as-child>
            <Button variant="outline" size="sm" :disabled="occupe" @click="telecharger">
              <Download :size="14" />
              {{ selection.length === 1 ? 'Télécharger' : 'ZIP' }}
            </Button>
          </AnimateIcon>
          <select
            class="h-7 max-w-40 rounded-md border bg-background px-2 text-[0.8rem] font-medium hover:bg-muted"
            aria-label="Déplacer vers une catégorie"
            :disabled="occupe"
            @change="deplacer"
          >
            <option disabled selected>Déplacer vers</option>
            <option value="">Sans catégorie</option>
            <option v-for="c in toutes" :key="c.id" :value="c.id">{{ '  '.repeat(c.niveau) + c.nom }}</option>
          </select>
          <AnimateIcon animate-on-hover as-child>
            <Button variant="destructive" size="sm" :disabled="occupe" @click="demander('supprimer-images')">
              <Trash2 :size="14" />
              Supprimer
            </Button>
          </AnimateIcon>
          <AnimateIcon animate-on-hover as-child>
            <Button variant="ghost" size="icon-sm" aria-label="Tout désélectionner" @click="selection = []">
              <X :size="14" />
            </Button>
          </AnimateIcon>
        </div>
      </Transition>
    </div>

    <!-- Une seule boîte de dialogue pour créer, renommer et confirmer une suppression -->
    <Dialog v-model:open="dialogueOuvert">
      <DialogContent :show-close-button="false">
        <form class="grid gap-4" @submit.prevent="confirmer">
          <DialogHeader>
            <DialogTitle>{{ TEXTES[dialogue.type].titre }}</DialogTitle>
            <DialogDescription>{{ dialogue.description }}</DialogDescription>
          </DialogHeader>
          <div v-if="dialogue.type === 'creer'" class="grid gap-2">
            <Label for="nom-categorie">Nom de la catégorie</Label>
            <Input id="nom-categorie" v-model.trim="dialogue.nom" required maxlength="50" autocomplete="off" />
          </div>
          <p v-if="dialogue.erreur" role="alert" class="text-sm text-destructive">{{ dialogue.erreur }}</p>
          <DialogFooter>
            <Button type="button" variant="outline" @click="dialogueOuvert = false">Annuler</Button>
            <Button type="submit" :variant="dialogue.type.startsWith('supprimer') ? 'destructive' : 'default'" :disabled="occupe">
              {{ TEXTES[dialogue.type].bouton }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </section>
</template>

<style scoped>
/* Contour d'accent sur une image cochée (maquette : « vignette cochée »). */
.vignette:has(:checked) {
  outline-color: var(--primary);
}

/* Ligne de l'arbre correspondant à la catégorie affichée. */
.ligne.active {
  background: var(--accent);
  color: var(--accent-foreground);
  font-weight: 500;
}

/* Arbre : une ligne qui apparaît ou disparaît (flèche, ajout, suppression) se déplie en hauteur. */
.branche-enter-active,
.branche-leave-active {
  overflow: hidden;
  transition: max-height 0.2s ease, opacity 0.2s ease;
}
.branche-enter-from,
.branche-leave-to {
  max-height: 0;
  opacity: 0;
}
.branche-enter-to,
.branche-leave-from {
  max-height: 2rem; /* un peu plus que la hauteur d'une ligne */
}

/* Grille : une image qui arrive grossit légèrement ; quand une image part,
   les autres glissent vers leur nouvelle place (classe -move de TransitionGroup). */
.grille-enter-active,
.grille-move,
.barre-enter-active,
.barre-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.grille-enter-from {
  opacity: 0;
  transform: scale(0.96);
}
/* L'image qui part sort de la grille tout de suite, pour laisser sa place aux autres. */
.grille-leave-active {
  position: absolute;
  opacity: 0;
}
.barre-enter-from,
.barre-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
