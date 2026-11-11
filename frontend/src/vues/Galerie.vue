<script setup>
// Galerie : arbre des catégories à gauche, images de la catégorie choisie à droite.
import { computed, onMounted, ref } from 'vue'
import { AnimateIcon } from '@animate-ui/vue/icons'
import { FolderPlus } from '@lucide/vue'
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

const categories = ref([]) // liste à plat renvoyée par l'API
const courante = ref(null) // id de la catégorie affichée ; null : « Sans catégorie »
const images = ref([])
const selection = ref([]) // ids des images cochées
const occupe = ref(false) // une action longue est en cours
const erreur = ref('')
const message = ref('') // compte rendu du dernier chargement
const survol = ref(false) // des fichiers sont glissés au-dessus de la page
const champFichiers = ref(null)

// --- Arbre des catégories ---

// Transforme la liste à plat en liste ordonnée : chaque catégorie est suivie de ses enfants,
// avec son niveau de profondeur (0 pour une racine). Sert à l'arbre et au menu « Déplacer ».
function descendants(parentId, niveau) {
  return categories.value
    .filter((c) => c.parent_id === parentId)
    .flatMap((c) => [{ ...c, niveau }, ...descendants(c.id, niveau + 1)])
}
const arbre = computed(() => descendants(null, 0))

const categorie = computed(() => categories.value.find((c) => c.id === courante.value) || null)

// Chemin de la catégorie affichée, de la racine jusqu'à elle : « Voyages / Maroc ».
const chemin = computed(() => {
  const noms = []
  for (let c = categorie.value; c; c = categories.value.find((p) => p.id === c.parent_id)) {
    noms.unshift(c.nom)
  }
  return noms.join(' / ')
})

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
    const [listeCategories, listeImages] = await Promise.all([listerCategories(), listerImages(courante.value)])
    categories.value = listeCategories
    images.value = listeImages
    // On ne garde cochées que les images encore affichées.
    selection.value = selection.value.filter((id) => listeImages.some((image) => image.id === id))
  })
}

function ouvrir(id) {
  courante.value = id
  selection.value = []
  message.value = ''
  actualiser()
}

onMounted(actualiser)

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

// null : fermée. Sinon { type, nom, erreur } avec type parmi :
// 'creer' (parent = dialogue.parent), 'renommer', 'supprimer-categorie', 'supprimer-images'.
const dialogue = ref(null)

const TEXTES = {
  creer: { titre: 'Nouvelle catégorie', bouton: 'Créer' },
  renommer: { titre: 'Renommer la catégorie', bouton: 'Renommer' },
  'supprimer-categorie': { titre: 'Supprimer la catégorie', bouton: 'Supprimer' },
  'supprimer-images': { titre: 'Supprimer les images', bouton: 'Supprimer' },
}

function demander(type, parent = null) {
  dialogue.value = { type, parent, nom: type === 'renommer' ? categorie.value.nom : '', erreur: '' }
}

const description = computed(() => {
  const d = dialogue.value
  if (d?.type === 'creer') {
    const parent = categories.value.find((c) => c.id === d.parent)
    return parent ? `Elle sera créée dans « ${parent.nom} ».` : 'Elle sera créée à la racine.'
  }
  if (d?.type === 'renommer') return `Nom actuel : « ${categorie.value?.nom} ».`
  if (d?.type === 'supprimer-categorie') return `« ${categorie.value?.nom} » sera supprimée. Elle doit être vide.`
  const n = selection.value.length
  return (n === 1 ? 'Cette image sera supprimée' : `Ces ${n} images seront supprimées`) + ' définitivement.'
})

async function confirmer() {
  const d = dialogue.value
  d.erreur = ''
  occupe.value = true
  try {
    if (d.type === 'creer') {
      await creerCategorie(d.nom, d.parent)
    } else if (d.type === 'renommer') {
      await renommerCategorie(courante.value, d.nom)
    } else if (d.type === 'supprimer-categorie') {
      const parent = categorie.value.parent_id
      await supprimerCategorie(courante.value)
      courante.value = parent // on remonte à la catégorie parente
    } else {
      await supprimerImages(selection.value)
    }
    dialogue.value = null
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
      <ul class="grid gap-0.5">
        <li>
          <button
            type="button"
            class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            :class="{ 'bg-accent font-medium !text-accent-foreground': courante === null }"
            :aria-current="courante === null ? 'true' : undefined"
            @click="ouvrir(null)"
          >
            Sans catégorie
          </button>
        </li>
        <li v-for="c in arbre" :key="c.id">
          <AnimateIcon animate-on-hover as-child>
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-md py-1.5 pr-2 text-left text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              :class="{ 'bg-accent font-medium !text-accent-foreground': courante === c.id }"
              :style="{ paddingLeft: 0.5 + c.niveau * 0.9 + 'rem' }"
              :aria-current="courante === c.id ? 'true' : undefined"
              @click="ouvrir(c.id)"
            >
              <Folder :size="15" class="shrink-0" />
              <span class="min-w-0 flex-1 truncate">{{ c.nom }}</span>
              <span class="font-mono text-xs text-muted-foreground">{{ c.nb_images }}</span>
            </button>
          </AnimateIcon>
        </li>
      </ul>
    </nav>

    <!-- Images de la catégorie affichée -->
    <div class="grid min-w-0 gap-4">
      <header class="flex flex-wrap items-end gap-2">
        <div class="mr-auto min-w-0">
          <p class="truncate text-sm text-muted-foreground">Galerie{{ chemin && ' / ' + chemin }}</p>
          <h1 class="truncate text-2xl font-semibold tracking-tight">{{ categorie?.nom || 'Sans catégorie' }}</h1>
        </div>
        <template v-if="categorie">
          <Button variant="outline" @click="demander('creer', courante)">
            <FolderPlus />
            Sous-catégorie
          </Button>
          <AnimateIcon animate-on-hover as-child>
            <Button variant="outline" @click="demander('renommer')">
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

      <p v-if="message" role="status" class="text-sm text-muted-foreground">{{ message }}</p>
      <p v-if="erreur" role="alert" class="text-sm text-destructive">{{ erreur }}</p>

      <!-- Zone de dépôt : visible quand la catégorie est vide ou quand on glisse des fichiers -->
      <button
        v-if="!images.length || survol"
        type="button"
        class="grid place-items-center gap-1 rounded-xl border border-dashed px-6 py-12 text-center text-sm text-muted-foreground hover:border-primary hover:text-foreground"
        :class="{ 'border-primary bg-primary-soft text-foreground': survol }"
        @click="champFichiers.click()"
      >
        <Upload :size="20" />
        <span class="font-medium text-foreground">
          {{ occupe ? 'Chargement en cours' : 'Déposez vos images ici, ou cliquez pour les choisir' }}
        </span>
        <span>JPG ou PNG, 10 Mo maximum par fichier</span>
      </button>

      <TransitionGroup
        v-if="images.length"
        tag="ul"
        name="grille"
        class="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5"
        :aria-busy="occupe"
      >
        <li v-for="image in images" :key="image.id">
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
            <option v-for="c in arbre" :key="c.id" :value="c.id">{{ '  '.repeat(c.niveau) + c.nom }}</option>
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
    <Dialog :open="dialogue !== null" @update:open="dialogue = null">
      <DialogContent v-if="dialogue" :show-close-button="false">
        <form class="grid gap-4" @submit.prevent="confirmer">
          <DialogHeader>
            <DialogTitle>{{ TEXTES[dialogue.type].titre }}</DialogTitle>
            <DialogDescription>{{ description }}</DialogDescription>
          </DialogHeader>
          <div v-if="dialogue.type === 'creer' || dialogue.type === 'renommer'" class="grid gap-2">
            <Label for="nom-categorie">Nom de la catégorie</Label>
            <Input id="nom-categorie" v-model.trim="dialogue.nom" required maxlength="50" autocomplete="off" />
          </div>
          <p v-if="dialogue.erreur" role="alert" class="text-sm text-destructive">{{ dialogue.erreur }}</p>
          <DialogFooter>
            <Button type="button" variant="outline" @click="dialogue = null">Annuler</Button>
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

/* Apparition et disparition des images de la grille, et de la barre d'actions. */
.grille-enter-active,
.grille-leave-active,
.barre-enter-active,
.barre-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.grille-enter-from,
.grille-leave-to {
  opacity: 0;
  transform: scale(0.96);
}
.barre-enter-from,
.barre-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
