// Données de la photo compagnon de la page d'accueil : lecture de ses pixels dans le navigateur,
// et place de chaque particule dans chacun des états (histogrammes, dominantes, empreinte).
// Unités : la scène est une boîte de 1 de large sur 0,75 de haut, centrée sur (0, 0), y vers le haut.
import { DESCRIPTEURS } from '@/descripteurs'

export const CASES = 32 // cases par histogramme, comme backend/descripteurs.py

// --- Mise en page de la scène, partagée par le shader et les légendes ---

export const HAUT_HISTO = 0.19 // hauteur de la case la plus remplie
// Ligne de base des trois histogrammes : R en haut, puis G, puis B.
export const BASES = [0, 1, 2].map((canal) => 0.375 - HAUT_HISTO - canal * 0.25)
export const HAUT_BANDE = 0.34 // hauteur de la bande des couleurs dominantes
export const HAUT_BARRE = 0.32 // hauteur d'une barre de l'empreinte à 3 écarts-types
const ECART_BLOCS = 0.008 // blanc entre deux couleurs dominantes
const ECART_GROUPES = 2 // blanc entre deux descripteurs de l'empreinte, en largeurs de barre

// Bande des couleurs dominantes : début et largeur de chaque bloc. La largeur est la part de la couleur.
export function blocsDominantes(dominantes) {
  const total = dominantes.reduce((somme, c) => somme + c.proportion, 0)
  const utile = 1 - ECART_BLOCS * (dominantes.length - 1)
  let x = -0.5
  return dominantes.map((c) => {
    const bloc = { x, largeur: (c.proportion / total) * utile }
    x += bloc.largeur + ECART_BLOCS
    return bloc
  })
}

// Empreinte : pour chaque valeur du vecteur, son descripteur, le centre de sa barre et sa hauteur
// entre -1 et 1 (pleine à 3 écarts-types). Renvoie { barres, largeur } ; largeur : celle d'une barre.
export function barresEmpreinte(vecteur, groupes) {
  const pas = 1 / (vecteur.length + ECART_GROUPES * (DESCRIPTEURS.length - 1))
  const barres = []
  DESCRIPTEURS.forEach((d, rang) => {
    const [debut, fin] = groupes[d.cle]
    for (let i = debut; i < fin; i++) {
      barres.push({
        groupe: rang,
        x: -0.5 + (i + ECART_GROUPES * rang + 0.5) * pas,
        hauteur: Math.max(-1, Math.min(1, vecteur[i] / 3)),
      })
    }
  })
  return { barres, largeur: pas * 0.72 }
}

// --- Pixels ---

// Lit la photo. cote : nombre de cellules de la grille sur le plus grand côté.
// Renvoie l'image, la grille (cols × lignes cellules, couleurs rvb et niveaux de gris),
// et les trois histogrammes comptés sur tous les pixels du fichier.
export async function lirePixels(url, cote) {
  const image = new Image()
  image.src = url
  await image.decode()
  const largeur = image.naturalWidth
  const hauteur = image.naturalHeight
  const toile = document.createElement('canvas')
  const dessin = toile.getContext('2d', { willReadFrequently: true })

  // Histogrammes R, G, B : chaque pixel du fichier tombe dans une des 32 cases (256 / 32 = 8 niveaux par case).
  toile.width = largeur
  toile.height = hauteur
  dessin.drawImage(image, 0, 0)
  const complet = dessin.getImageData(0, 0, largeur, hauteur).data
  const histos = [0, 1, 2].map(() => new Float32Array(CASES))
  for (let i = 0; i < complet.length; i += 4) {
    for (let canal = 0; canal < 3; canal++) histos[canal][complet[i + canal] >> 3]++
  }
  histos.forEach((h) => h.forEach((compte, i) => (h[i] = compte / (largeur * hauteur))))

  // Grille : la photo réduite à une cellule par particule.
  const rapport = cote / Math.max(largeur, hauteur)
  const cols = Math.round(largeur * rapport)
  const lignes = Math.round(hauteur * rapport)
  toile.width = cols
  toile.height = lignes
  dessin.drawImage(image, 0, 0, cols, lignes)
  const rvb = dessin.getImageData(0, 0, cols, lignes).data
  const gris = new Uint8Array(cols * lignes)
  for (let i = 0; i < gris.length; i++) {
    // Même formule que OpenCV pour passer en niveaux de gris.
    gris[i] = Math.round(0.299 * rvb[i * 4] + 0.587 * rvb[i * 4 + 1] + 0.114 * rvb[i * 4 + 2])
  }
  return { image, largeur, hauteur, cols, lignes, rvb, gris, histos }
}

// --- Fenêtre LBP ---

// Les 8 voisins, dans le sens des aiguilles d'une montre à partir du coin haut gauche : [colonne, ligne].
const VOISINS = [[-1, -1], [0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0]]

// Principe du LBP sur la cellule (col, ligne) : chaque voisin vaut 1 s'il est au moins aussi clair que le centre.
// Renvoie { centre, voisins: [{ dc, dl, gris, bit }], motif } ; motif : les 8 réponses à la suite.
export function fenetreLbp(pixels, col, ligne) {
  const lire = (c, l) => pixels.gris[l * pixels.cols + c]
  const centre = lire(col, ligne)
  const voisins = VOISINS.map(([dc, dl]) => {
    const gris = lire(col + dc, ligne + dl)
    return { dc, dl, gris, bit: gris >= centre ? 1 : 0 }
  })
  return { centre, voisins, motif: voisins.map((v) => v.bit).join('') }
}

// Balayage de la fenêtre : elle avance par bonds le long d'une ligne, puis passe à la ligne suivante.
// Fonction du temps seul : le même instant donne toujours la même place. Renvoie [col, ligne], non entiers
// pendant un bond.
const BOND = 1.5 // secondes par arrêt : un glissement, puis une pause
export function placeFenetre(temps, cols, lignes) {
  const arret = (k) => {
    const parLigne = 9
    const rang = ((k % (parLigne * 6)) + parLigne * 6) % (parLigne * 6)
    const c = rang % parLigne
    const l = Math.floor(rang / parLigne)
    // Décalage d'une ligne sur deux, pour ne pas repasser sur les mêmes colonnes.
    return [
      Math.round(cols * (0.1 + (0.8 * (c + (l % 2) * 0.5)) / parLigne)),
      Math.round(lignes * (0.14 + (0.72 * ((l * 5) % 6)) / 5)),
    ]
  }
  const k = Math.floor(temps / BOND)
  const t = Math.min(1, (temps / BOND - k) / 0.38)
  const doux = 1 - (1 - t) ** 3
  const [a, b] = [arret(k - 1), arret(k)]
  return [a[0] + (b[0] - a[0]) * doux, a[1] + (b[1] - a[1]) * doux]
}

// --- Places des particules ---

// Suite pseudo-aléatoire à graine fixe : la même photo donne toujours le même nuage.
function hasard(graine) {
  return () => {
    graine = (graine + 0x6d2b79f5) | 0
    let t = Math.imul(graine ^ (graine >>> 15), 1 | graine)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// Une particule par cellule de la grille. Pour chacune : sa place dans la photo (uv), dans les
// histogrammes, dans la bande des dominantes et dans l'empreinte. Le 3e nombre de chaque place est
// le numéro du canal, de la couleur dominante ou du descripteur : le shader en tire la couleur.
export function placerParticules(pixels, photo, groupes) {
  const { cols, lignes, rvb, gris, histos } = pixels
  const nombre = cols * lignes
  const tirer = hasard(photo.n + 1)
  const uv = new Float32Array(nombre * 2)
  const alea = new Float32Array(nombre * 3) // deux nombres au hasard, puis le niveau de gris
  const histo = new Float32Array(nombre * 3)
  const dom = new Float32Array(nombre * 3)
  const emp = new Float32Array(nombre * 3)

  for (let i = 0; i < nombre; i++) {
    uv[i * 2] = ((i % cols) + 0.5) / cols
    uv[i * 2 + 1] = (Math.floor(i / cols) + 0.5) / lignes
    alea[i * 3] = tirer()
    alea[i * 3 + 1] = tirer()
    alea[i * 3 + 2] = gris[i] / 255
  }

  // Histogrammes : un tiers des particules par canal. Chacune tombe dans la case de son niveau ;
  // la pile d'une case monte jusqu'à la hauteur comptée sur tous les pixels de la photo.
  const canalDe = (i) => ((i % cols) + Math.floor(i / cols)) % 3
  const caseDe = (i) => rvb[i * 4 + canalDe(i)] >> 3
  const piles = new Uint32Array(3 * CASES)
  for (let i = 0; i < nombre; i++) piles[canalDe(i) * CASES + caseDe(i)]++
  const sommets = histos.map((h) => Math.max(...h)) // chaque canal a sa propre échelle : sa case la plus remplie touche le haut
  const rangs = new Uint32Array(3 * CASES)
  const COLONNES = 5 // particules côte à côte dans une case
  for (let i = 0; i < nombre; i++) {
    const canal = canalDe(i)
    const c = caseDe(i)
    const rang = rangs[canal * CASES + c]++
    const etages = Math.ceil(piles[canal * CASES + c] / COLONNES)
    const hauteur = (histos[canal][c] / sommets[canal]) * HAUT_HISTO
    histo[i * 3] = -0.5 + (c + 0.14 + (0.72 * ((rang % COLONNES) + 0.5)) / COLONNES) / CASES
    histo[i * 3 + 1] = BASES[canal] + ((Math.floor(rang / COLONNES) + 0.5) / etages) * hauteur
    histo[i * 3 + 2] = canal
  }

  // Dominantes : chaque particule rejoint la couleur dominante la plus proche de la sienne, tant que
  // ce bloc a de la place. Le nombre de places d'un bloc est sa part réelle de la photo.
  const blocs = blocsDominantes(photo.dominantes)
  const places = blocs.map((b) => Math.round(b.largeur * nombre))
  const prises = blocs.map(() => 0)
  const choix = new Uint8Array(nombre)
  const PAS = 7919 // nombre premier : parcourt toutes les particules dans un ordre dispersé
  for (let k = 0; k < nombre; k++) {
    const i = (k * PAS) % nombre
    let meilleur = -1
    let proche = Infinity
    photo.dominantes.forEach((c, j) => {
      const ecart =
        (rvb[i * 4] / 255 - c.r) ** 2 + (rvb[i * 4 + 1] / 255 - c.g) ** 2 + (rvb[i * 4 + 2] / 255 - c.b) ** 2
      if (prises[j] < places[j] && ecart < proche) [meilleur, proche] = [j, ecart]
    })
    if (meilleur < 0) meilleur = 0 // arrondis : les dernières particules vont au bloc le plus large
    choix[i] = meilleur
    prises[meilleur]++
  }
  const poses = blocs.map(() => 0)
  for (let i = 0; i < nombre; i++) {
    const j = choix[i]
    const { x, largeur } = blocs[j]
    const parRang = Math.max(1, Math.round(Math.sqrt((prises[j] * largeur) / HAUT_BANDE)))
    // Seules les rangées complètes comptent : le bloc est un rectangle net, sans rangée entamée en bas.
    const etages = Math.max(1, Math.floor(prises[j] / parRang))
    const rang = poses[j]++
    // Les quelques particules en trop se glissent dans la dernière rangée, sous leurs voisines.
    const etage = Math.min(Math.floor(rang / parRang), etages - 1)
    dom[i * 3] = x + (((rang % parRang) + 0.5) / parRang) * largeur
    dom[i * 3 + 1] = HAUT_BANDE / 2 - ((etage + 0.5) / etages) * HAUT_BANDE
    dom[i * 3 + 2] = j
  }

  // Empreinte : les particules se partagent les 141 barres, plus nombreuses dans les barres hautes.
  // Elles sont prises colonne par colonne : la gauche de la photo va vers la gauche de l'empreinte.
  const { barres, largeur } = barresEmpreinte(photo.vecteur, groupes)
  const parts = barres.map((b) => Math.max(Math.abs(b.hauteur), 0.04))
  const total = parts.reduce((somme, p) => somme + p, 0)
  let barre = 0
  let debut = 0 // première particule de la barre en cours
  let fin = (parts[0] / total) * nombre
  for (let k = 0; k < nombre; k++) {
    while (k >= fin && barre < barres.length - 1) {
      barre++
      debut = fin
      fin += (parts[barre] / total) * nombre
    }
    const i = (k % lignes) * cols + Math.floor(k / lignes)
    const b = barres[barre]
    emp[i * 3] = b.x + ((k % 2) - 0.5) * largeur * 0.5 // deux colonnes de particules par barre
    emp[i * 3 + 1] = ((k - debut + 0.5) / (fin - debut)) * b.hauteur * HAUT_BARRE
    emp[i * 3 + 2] = b.groupe
  }

  return { nombre, uv, alea, histo, dom, emp }
}
