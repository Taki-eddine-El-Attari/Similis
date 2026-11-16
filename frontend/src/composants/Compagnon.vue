<script setup>
// La photo compagnon de la page d'accueil, dessinée en WebGL (three.js) à partir de ses vrais pixels.
// Une particule par cellule de la photo. Chaque particule connaît sa place dans chaque état
// (photo, histogrammes, dominantes, empreinte, case « Requête ») ; le shader passe de l'une à l'autre
// selon l'étape, qui ne dépend que du défilement. Le canevas couvre la fenêtre et ne reçoit aucun clic.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Camera,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  LinearFilter,
  Mesh,
  PlaneGeometry,
  Scene,
  ShaderMaterial,
  Texture,
  WebGLRenderer,
} from 'three'
import { placeFenetre, placerParticules } from '@/compagnon'

const props = defineProps({
  pixels: { type: Object, required: true }, // résultat de lirePixels
  photo: { type: Object, required: true }, // la photo de la vitrine : vecteur, dominantes
  groupes: { type: Object, required: true }, // bornes des descripteurs dans le vecteur
  etape: { type: Object, required: true }, // valeur Motion : 0 photo, 1 histogrammes, 2 dominantes, 3 texture, 4 empreinte, 5 requête, 6 éteint
  repere: { type: Object, default: null }, // élément de la page qui donne le centre et la largeur de la scène
  fige: { type: Number, default: null }, // temps imposé par ?t=, en secondes
})
// fenetre : la fenêtre LBP s'est posée sur une autre cellule. lent : l'écran ne suit pas, moins de particules.
// absent : WebGL ne démarre pas.
const emit = defineEmits(['fenetre', 'lent', 'absent'])

const toile = ref(null)

// --- Shaders ---

// Rotation de la scène puis perspective, communes aux particules et au tirage papier.
const PROJETER = /* glsl */ `
  uniform vec2 uVue;      // taille de la fenêtre, en pixels
  uniform vec2 uCentre;   // centre de la scène, en pixels depuis le centre de la fenêtre
  uniform float uEchelle; // pixels par unité de scène
  uniform vec2 uIncl;     // inclinaison de la scène, en radians
  // Renvoie la place à l'écran (xy, en pixels) et le grossissement dû à la perspective (z).
  vec3 projeter(vec3 p) {
    float cy = cos(uIncl.y), sy = sin(uIncl.y), cx = cos(uIncl.x), sx = sin(uIncl.x);
    p = vec3(p.x * cy + p.z * sy, p.y, p.z * cy - p.x * sy);
    p = vec3(p.x, p.y * cx - p.z * sx, p.y * sx + p.z * cx);
    float loupe = 1.0 / (1.0 - p.z * uEchelle / 1500.0);
    return vec3(uCentre + p.xy * uEchelle * loupe, loupe);
  }
`

const SOMMETS = /* glsl */ `
  attribute vec2 aUv;    // centre de la cellule dans la photo, v vers le bas
  attribute vec3 aAlea;  // deux nombres au hasard, puis le niveau de gris
  attribute vec3 aHisto; // place dans les histogrammes ; z : canal
  attribute vec3 aDom;   // place dans la bande des dominantes ; z : numéro de la couleur
  attribute vec3 aEmp;   // place dans l'empreinte ; z : numéro du descripteur
  uniform vec2 uPhoto;   // largeur et hauteur de la photo, en unités de scène
  uniform vec2 uGrille;  // nombre de cellules : colonnes, lignes
  uniform float uT[6];   // avancement de chaque passage, entre 0 et 1 ; le dernier éteint tout
  uniform vec4 uFin;     // case « Requête » : centre et taille, en pixels
  uniform float uTemps;
  uniform float uBalayage; // hauteur de la ligne de balayage dans la photo
  uniform vec3 uCanaux[3];
  uniform vec3 uDominantes[5];
  uniform vec3 uDescripteurs[5];
  varying vec2 vUv;
  varying vec2 vCellule; // place dans la grille, en cellules
  varying vec3 vPlat;    // part de couleur unie
  varying vec4 vParts;   // part de la photo, part du gris, opacité, éclat du balayage
  ${PROJETER}

  // Chaque particule part avec son propre retard, puis glisse sans à-coup.
  float passage(float avance, float retard) {
    float t = clamp(avance * 1.7 - retard * 0.7, 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
  }

  void main() {
    float t01 = passage(uT[0], 0.5 * aAlea.x + 0.5 * (1.0 - aUv.y));
    float t12 = passage(uT[1], 0.45 * aAlea.y + 0.55 * aDom.z / 4.0);
    float t23 = passage(uT[2], 0.5 * aAlea.x + 0.5 * aUv.x);
    float t34 = passage(uT[3], 0.4 * aAlea.y + 0.6 * aUv.x);
    float t45 = passage(uT[4], 0.7 * aAlea.x + 0.3 * aUv.y);
    // « entiere » vaut 1 quand la particule est à sa place dans la photo (dans la scène ou dans la case).
    float entiere = (1.0 - t01) + t23 * (1.0 - t34) + t45;

    // La photo a un léger relief : les zones claires sont un peu plus près de l'œil.
    float onde = exp(-pow((aUv.y - uBalayage) * 12.0, 2.0));
    vec3 photo = vec3((aUv - 0.5) * vec2(uPhoto.x, -uPhoto.y), (aAlea.z - 0.5) * 0.008 + onde * 0.004);
    vec3 p = photo;
    p = mix(p, vec3(aHisto.xy, 0.0), t01);
    p = mix(p, vec3(aDom.xy, 0.0), t12);
    p = mix(p, photo, t23);
    p = mix(p, vec3(aEmp.xy, 0.0), t34);
    // En vol, le nuage se gonfle en profondeur et tourne un peu, puis se repose.
    float vol = sin(3.14159 * t01) + sin(3.14159 * t12) + sin(3.14159 * t23) + sin(3.14159 * t34);
    float angle = aAlea.x * 6.2832 + uTemps * 0.4;
    p += vol * vec3(0.035 * cos(angle), 0.035 * sin(angle), (aAlea.y - 0.5) * 0.45);
    // Avant de partir vers la case « Requête », l'empreinte se resserre.
    p.xy *= mix(1.0, 0.55, uT[4]);

    vec3 ecran = projeter(p);
    vec2 cellule = uPhoto / uGrille * uEchelle * ecran.z;
    float taille = mix(1.0, 0.92, t01);
    taille = mix(taille, 0.82, t12);
    taille = mix(taille, 1.0, t23);
    taille = mix(taille, 0.5, t34);
    // Dans la photo, les cellules se recouvrent un peu : aucun jour entre elles.
    float bord = 1.0 + 0.08 * entiere;

    // Case « Requête » : la photo la remplit comme le fait « object-fit: cover ».
    float forme = uPhoto.x / uPhoto.y;
    float large = max(uFin.z, uFin.w * forme);
    vec2 affichee = vec2(large, large / forme);
    vec2 fin = uFin.xy + (aUv - 0.5) * vec2(affichee.x, -affichee.y);
    float dedans = step(abs(fin.x - uFin.x), uFin.z * 0.5) * step(abs(fin.y - uFin.y), uFin.w * 0.5);
    vec2 place = mix(ecran.xy, fin, t45);
    place += sin(3.14159 * t45) * (aAlea.xy - 0.5) * 90.0;
    vec2 cote = mix(cellule * taille * bord, affichee / uGrille * 1.08, t45);

    vec2 coin = vec2(position.x, -position.y);
    gl_Position = vec4((place + position.xy * cote) * 2.0 / uVue, 0.0, 1.0);
    vUv = aUv + coin * bord * entiere / uGrille;
    vCellule = aUv * uGrille - 0.5 + coin;

    // Couleur : part de la photo (a), part du gris (g) et couleur unie, mélangées passage après passage.
    float a = 1.0, g = 0.0;
    vec3 plat = vec3(0.0);
    float m = t01 * 0.82; // histogrammes : la couleur du canal
    a *= 1.0 - m; plat = uCanaux[int(aHisto.z)] * m;
    a *= 1.0 - t12; plat = mix(plat, uDominantes[int(aDom.z)], t12); // dominantes
    a *= 1.0 - t23; plat *= 1.0 - t23; g = t23; // texture : niveaux de gris
    a *= 1.0 - t34; g *= 1.0 - t34; plat = mix(plat, uDescripteurs[int(aEmp.z)], t34); // empreinte
    g *= 1.0 - t45; plat *= 1.0 - t45; a = mix(a, 1.0, t45); // retour à la photo
    vPlat = plat;
    // Sous la moyenne, les barres de l'empreinte sont plus pâles.
    float pale = mix(1.0, aEmp.y < 0.0 ? 0.5 : 1.0, t34 * (1.0 - t45));
    vParts = vec4(a, g, pale * mix(1.0, dedans, t45) * (1.0 - uT[5]), onde * (1.0 - t01));
  }
`

const FRAGMENTS = /* glsl */ `
  uniform sampler2D uImage;
  uniform vec3 uAccent;
  uniform vec3 uFenetre; // fenêtre LBP : colonne, ligne, visibilité
  varying vec2 vUv;
  varying vec2 vCellule;
  varying vec3 vPlat;
  varying vec4 vParts;

  void main() {
    vec3 photo = texture2D(uImage, vUv).rgb;
    float gris = dot(photo, vec3(0.299, 0.587, 0.114));
    vec3 couleur = photo * vParts.x + vec3(gris) * vParts.y + vPlat;
    // Ligne de balayage : un trait de lumière qui traverse la photo.
    couleur += (1.0 - couleur) * vParts.w * 0.1;
    // Fenêtre LBP : un cadre de 3 cellules de côté, et la ligne et la colonne du pixel observé.
    vec2 ecart = abs(vCellule - uFenetre.xy);
    float loin = max(ecart.x, ecart.y);
    float croix = (1.0 - step(0.5, min(ecart.x, ecart.y))) * 0.42 * step(1.5, loin);
    float cadre = step(1.5, loin) * (1.0 - step(2.7, loin));
    couleur = mix(couleur, uAccent, max(croix, cadre) * uFenetre.z);
    gl_FragColor = vec4(couleur, vParts.z);
  }
`

// Le tirage papier sous la photo : un rectangle aux coins ronds, sa bordure et son ombre.
const SOMMETS_TIRAGE = /* glsl */ `
  uniform vec2 uPhoto;
  uniform float uMarge; // marge blanche du tirage, en pixels
  varying vec2 vPlace;  // place dans le tirage, en pixels depuis son centre
  varying vec2 vDemi;   // demi-taille du tirage, en pixels
  ${PROJETER}
  void main() {
    vDemi = uPhoto * uEchelle * 0.5 + uMarge;
    vPlace = position.xy * 2.0 * (vDemi + 70.0);
    vec3 ecran = projeter(vec3(vPlace / uEchelle, -0.012));
    gl_Position = vec4(ecran.xy * 2.0 / uVue, 0.0, 1.0);
  }
`
const FRAGMENTS_TIRAGE = /* glsl */ `
  uniform vec3 uCarte;
  uniform vec3 uBordure;
  uniform float uOpacite;
  uniform float uOmbre;
  varying vec2 vPlace;
  varying vec2 vDemi;
  // Distance au bord d'un rectangle aux coins ronds : négative à l'intérieur.
  float auBord(vec2 p, vec2 demi, float rayon) {
    vec2 d = abs(p) - demi + rayon;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - rayon;
  }
  void main() {
    float d = auBord(vPlace, vDemi, 10.0);
    float dedans = 1.0 - smoothstep(-0.5, 0.5, d);
    float trait = 1.0 - smoothstep(0.5, 1.5, abs(d + 0.5));
    // Ombre douce, décalée vers le bas : le tirage est posé sur la table.
    float ombre = uOmbre * exp(-max(auBord(vPlace + vec2(0.0, 14.0), vDemi, 10.0), 0.0) / 22.0);
    vec3 couleur = mix(uCarte, uBordure, trait);
    float opacite = max(dedans, trait);
    // Hors du tirage, il ne reste que l'ombre : du noir, presque transparent.
    float total = max(opacite, ombre);
    gl_FragColor = vec4(couleur * opacite / max(total, 0.001), total * uOpacite);
  }
`

// --- Scène three.js ---

let rendu // WebGLRenderer
let scene
let particules // Mesh des particules
let tirage // Mesh du tirage papier
let boucle // numéro de la prochaine image demandée au navigateur
let observateur // suit les changements de thème et d'accent
let guetteur // suit la taille du canevas
const camera = new Camera() // les shaders font eux-mêmes la projection

const uniformes = {
  uVue: { value: [1, 1] },
  uCentre: { value: [0, 0] },
  uEchelle: { value: 1 },
  uIncl: { value: [0, 0] },
  uPhoto: { value: [1, 0.75] },
  uGrille: { value: [1, 1] },
  uT: { value: [0, 0, 0, 0, 0, 0] },
  uFin: { value: [0, 0, 1, 1] },
  uTemps: { value: 0 },
  uBalayage: { value: 0 },
  uCanaux: { value: new Float32Array(9) },
  uDominantes: { value: new Float32Array(15) },
  uDescripteurs: { value: new Float32Array(15) },
  uImage: { value: null },
  uAccent: { value: [0, 0, 0] },
  uFenetre: { value: [0, 0, 0] },
  uCarte: { value: [1, 1, 1] },
  uBordure: { value: [0, 0, 0] },
  uMarge: { value: 12 },
  uOpacite: { value: 1 },
  uOmbre: { value: 0.12 },
}

// Lit une couleur du thème (variable CSS) et la rend en trois nombres entre 0 et 1.
function couleurTheme(nom) {
  const sonde = document.createElement('i')
  sonde.style.color = `var(${nom})`
  document.body.append(sonde)
  const [r, g, b] = getComputedStyle(sonde).color.match(/[\d.]+/g).map(Number)
  sonde.remove()
  return [r / 255, g / 255, b / 255]
}

// Couleurs du shader : elles viennent des variables CSS et suivent le thème et l'accent.
function lireCouleurs() {
  uniformes.uCanaux.value.set(['--canal-r', '--canal-g', '--canal-b'].flatMap(couleurTheme))
  uniformes.uDescripteurs.value.set([1, 2, 3, 4, 5].flatMap((n) => couleurTheme(`--chart-${n}`)))
  uniformes.uAccent.value = couleurTheme('--primary')
  uniformes.uCarte.value = couleurTheme('--card')
  uniformes.uBordure.value = couleurTheme('--border')
  uniformes.uOmbre.value = document.documentElement.classList.contains('dark') ? 0.45 : 0.12
}

// Construit (ou reconstruit, au changement de photo) le nuage de particules et la texture.
function chargerPhoto() {
  const { pixels, photo } = props
  const places = placerParticules(pixels, photo, props.groupes)
  const geometrie = new InstancedBufferGeometry()
  const carre = new PlaneGeometry(1, 1)
  geometrie.index = carre.index
  geometrie.setAttribute('position', carre.getAttribute('position'))
  geometrie.setAttribute('aUv', new InstancedBufferAttribute(places.uv, 2))
  geometrie.setAttribute('aAlea', new InstancedBufferAttribute(places.alea, 3))
  geometrie.setAttribute('aHisto', new InstancedBufferAttribute(places.histo, 3))
  geometrie.setAttribute('aDom', new InstancedBufferAttribute(places.dom, 3))
  geometrie.setAttribute('aEmp', new InstancedBufferAttribute(places.emp, 3))
  geometrie.instanceCount = places.nombre

  const texture = new Texture(pixels.image)
  texture.flipY = false // v = 0 en haut de la photo, comme dans la grille
  texture.generateMipmaps = false
  texture.minFilter = LinearFilter
  texture.needsUpdate = true

  particules.geometry.dispose()
  uniformes.uImage.value?.dispose()
  particules.geometry = geometrie
  uniformes.uImage.value = texture
  uniformes.uGrille.value = [pixels.cols, pixels.lignes]
  // La photo tient dans la boîte de la scène : toute la largeur en paysage, presque toute la hauteur en portrait.
  const forme = pixels.largeur / pixels.hauteur
  uniformes.uPhoto.value = forme >= 1 ? [1, 1 / forme] : [0.88 * forme, 0.88]
  uniformes.uDominantes.value.set(photo.dominantes.flatMap((c) => [c.r, c.g, c.b]))
}

// Taille du canevas à l'écran, en pixels CSS. Ce n'est pas innerWidth : la barre de défilement
// prend une part de la fenêtre, et un canevas plus large que sa place décalerait tout vers la gauche.
let large = 1
let haute = 1
function dimensionner() {
  large = toile.value.clientWidth
  haute = toile.value.clientHeight
  rendu.setSize(large, haute, false)
  uniformes.uVue.value = [large, haute]
  // Changer la taille vide le canevas : on redessine tout de suite, sans attendre la prochaine image.
  if (uniformes.uImage.value) rendu.render(scene, camera)
}

// --- Entrées : le pointeur incline la scène ---

const pointeur = [0, 0] // place du pointeur, entre -1 et 1 ; (0, 0) : centre de la fenêtre
const incl = [0, 0] // inclinaison affichée, qui rejoint celle demandée en douceur
function suivre(e) {
  pointeur[0] = (e.clientX / large) * 2 - 1
  pointeur[1] = (e.clientY / haute) * 2 - 1
}

// --- Une image ---

const marche = (debut, fin, x) => {
  const t = Math.max(0, Math.min(1, (x - debut) / (fin - debut)))
  return t * t * (3 - 2 * t)
}

let depart // heure de la première image
let avant // heure de l'image précédente
let lenteur = 0 // durée moyenne d'une image, en ms
let comptees = 0 // images comptées depuis le dernier réglage de qualité
let cellule = '' // dernière cellule annoncée pour la fenêtre LBP
let eteint = false // rien à dessiner : le canevas est déjà vide

function dessiner(maintenant) {
  boucle = requestAnimationFrame(dessiner)
  depart ??= maintenant
  const ecoule = Math.min(100, maintenant - (avant ?? maintenant))
  avant = maintenant
  const temps = props.fige ?? (maintenant - depart) / 1000
  const etape = props.etape.get()
  const u = uniformes

  // Passages : chaque étape reste en place un moment (début et fin de chaque intervalle), puis se transforme.
  for (let k = 0; k < 4; k++) u.uT.value[k] = marche(0.16, 0.84, etape - k)
  u.uT.value[4] = marche(0.1, 1, etape - 4)
  u.uT.value[5] = marche(0.05, 0.6, etape - 5)
  if (u.uT.value[5] >= 1) {
    if (!eteint) rendu.clear()
    eteint = true
    return
  }
  eteint = false

  // Place de la scène et de la case « Requête », lues dans la page.
  if (props.repere) {
    const r = props.repere.getBoundingClientRect()
    u.uCentre.value = [r.left + r.width / 2 - large / 2, haute / 2 - (r.top + r.height / 2)]
    u.uEchelle.value = r.width
    u.uMarge.value = Math.max(6, r.width * 0.018)
  }
  if (etape > 3.9) {
    const r = document.querySelector('[data-case-requete]')?.getBoundingClientRect()
    if (r) u.uFin.value = [r.left + r.width / 2 - large / 2, haute / 2 - (r.top + r.height / 2), r.width, r.height]
  }

  // Vie propre : la scène dérive lentement, et s'incline vers le pointeur. Plus calme hors de la photo.
  const [t01, , t23, t34, t45] = u.uT.value
  const entiere = 1 - t01 + t23 * (1 - t34)
  const ampleur = (0.035 + 0.125 * entiere) * (1 - t45)
  const suivi = 1 - Math.exp(-ecoule / 180)
  incl[0] += (pointeur[1] - incl[0]) * suivi
  incl[1] += (pointeur[0] - incl[1]) * suivi
  // Hors de la photo, la dérive est plus faible : les blocs et les barres gardent des bords droits.
  const derive = 0.3 + 0.7 * entiere
  u.uIncl.value = [
    (incl[0] * ampleur + 0.03 * derive * Math.sin(temps * 0.5)) * (1 - t45),
    (incl[1] * ampleur + 0.045 * derive * Math.sin(temps * 0.37 + 1)) * (1 - t45),
  ]
  u.uCentre.value[1] += Math.sin(temps * 0.6) * 5 * entiere
  // La perspective grossit le côté le plus proche : inclinée, la scène glisserait vers ce côté.
  // On la décale d'autant dans l'autre sens, pour qu'elle reste au milieu de sa table.
  // 1500 : la distance de l'œil, la même que dans le shader (projeter).
  const glisse = (demi, angle) => (demi ** 2 * Math.sin(angle) * Math.cos(angle)) / 1500
  const [rx, ry] = u.uIncl.value
  u.uCentre.value[0] += glisse((u.uPhoto.value[0] * u.uEchelle.value) / 2, ry)
  u.uCentre.value[1] -= glisse((u.uPhoto.value[1] * u.uEchelle.value) / 2, rx)
  u.uTemps.value = temps
  u.uBalayage.value = ((temps / 5.5) % 1) * 1.5 - 0.25
  // Le tirage papier ne paraît que lorsque presque toutes les particules sont à leur place.
  u.uOpacite.value = Math.max(0, entiere * 4 - 3)

  // Fenêtre LBP : visible seulement à l'étape « texture ».
  const [col, ligne] = placeFenetre(temps, props.pixels.cols, props.pixels.lignes)
  u.uFenetre.value = [col, ligne, t23 * (1 - t34)]
  const posee = Math.round(col) + ' ' + Math.round(ligne)
  if (posee !== cellule) {
    cellule = posee
    emit('fenetre', Math.round(col), Math.round(ligne))
  }

  rendu.render(scene, camera)
  if (toile.value.dataset.pret !== String(props.photo.n)) toile.value.dataset.pret = props.photo.n

  // Qualité : si une image prend trop de temps, on baisse d'abord la finesse du canevas, puis le nombre de particules.
  lenteur += (ecoule - lenteur) * 0.05
  if (++comptees > 90 && lenteur > 24 && props.fige === null) {
    comptees = 0
    if (rendu.getPixelRatio() > 1) rendu.setPixelRatio(Math.max(1, rendu.getPixelRatio() - 0.5))
    else emit('lent')
  }
}

onMounted(() => {
  try {
    rendu = new WebGLRenderer({ canvas: toile.value, alpha: true, antialias: true, powerPreference: 'high-performance' })
  } catch {
    return emit('absent')
  }
  rendu.setPixelRatio(Math.min(devicePixelRatio, 2))
  rendu.setClearColor(0x000000, 0)
  scene = new Scene()
  const commun = { uniforms: uniformes, transparent: true, depthTest: false, depthWrite: false }
  tirage = new Mesh(
    new PlaneGeometry(1, 1),
    new ShaderMaterial({ ...commun, vertexShader: SOMMETS_TIRAGE, fragmentShader: FRAGMENTS_TIRAGE }),
  )
  particules = new Mesh(
    new InstancedBufferGeometry(),
    new ShaderMaterial({ ...commun, vertexShader: SOMMETS, fragmentShader: FRAGMENTS }),
  )
  tirage.frustumCulled = particules.frustumCulled = false
  particules.renderOrder = 1
  scene.add(tirage, particules)

  lireCouleurs()
  chargerPhoto()
  dimensionner()
  // Le canevas change de taille avec la fenêtre, et aussi quand la barre de défilement paraît.
  guetteur = new ResizeObserver(dimensionner)
  guetteur.observe(toile.value)
  addEventListener('pointermove', suivre, { passive: true })
  observateur = new MutationObserver(lireCouleurs)
  observateur.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-accent'] })
  boucle = requestAnimationFrame(dessiner)
})

// Autre photo (ou autre nombre de particules) : le nuage est reconstruit.
watch(() => props.pixels, () => rendu && chargerPhoto())

// La page est quittée : on arrête la boucle et on rend la mémoire de la carte graphique.
onBeforeUnmount(() => {
  cancelAnimationFrame(boucle)
  guetteur?.disconnect()
  removeEventListener('pointermove', suivre)
  observateur?.disconnect()
  if (!rendu) return
  particules.geometry.dispose()
  particules.material.dispose()
  tirage.geometry.dispose()
  tirage.material.dispose()
  uniformes.uImage.value?.dispose()
  rendu.dispose()
  rendu.forceContextLoss()
})
</script>

<template>
  <!-- Décor : tout ce que le canevas montre est aussi écrit dans la page -->
  <canvas ref="toile" class="pointer-events-none fixed inset-0 z-30 size-full" aria-hidden="true" />
</template>
