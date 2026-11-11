// Tous les appels au backend passent par ce fichier : une fonction par service.

// Envoie une requête à l'API et renvoie la réponse décodée.
// « corps » : un objet (envoyé en JSON) ou un FormData (envoi de fichiers).
// En cas d'erreur, lève une Error avec le message renvoyé par l'API.
async function appeler(methode, chemin, corps) {
  // Pour un FormData, le navigateur écrit lui-même l'en-tête Content-Type.
  const fichiers = corps instanceof FormData
  const reponse = await fetch('/api' + chemin, {
    method: methode,
    headers: corps && !fichiers ? { 'Content-Type': 'application/json' } : {},
    body: fichiers ? corps : corps ? JSON.stringify(corps) : undefined,
  })
  // Une archive ZIP est renvoyée telle quelle, sous forme de Blob.
  if (reponse.ok && reponse.headers.get('Content-Type') === 'application/zip') {
    return reponse.blob()
  }
  // 204 : réponse sans contenu
  const donnees = reponse.status === 204 ? null : await reponse.json().catch(() => null)
  if (!reponse.ok) {
    throw new Error(donnees?.erreur || `Erreur ${reponse.status}`)
  }
  return donnees
}

// --- Authentification ---

// POST /api/auth/inscription — crée un compte et ouvre la session
export function inscription(nom, motDePasse) {
  return appeler('POST', '/auth/inscription', { nom, mot_de_passe: motDePasse })
}

// POST /api/auth/connexion — ouvre la session
export function connexion(nom, motDePasse) {
  return appeler('POST', '/auth/connexion', { nom, mot_de_passe: motDePasse })
}

// POST /api/auth/deconnexion — ferme la session
export function deconnexion() {
  return appeler('POST', '/auth/deconnexion')
}

// GET /api/auth/moi — utilisateur connecté (erreur s'il n'y a pas de session)
export function moi() {
  return appeler('GET', '/auth/moi')
}

// --- Catégories ---

// GET /api/categories — liste à plat : id, parent_id, nom, nb_images
export function listerCategories() {
  return appeler('GET', '/categories')
}

// POST /api/categories — crée une catégorie (parentId nul : à la racine)
export function creerCategorie(nom, parentId) {
  return appeler('POST', '/categories', { nom, parent_id: parentId })
}

// PUT /api/categories/<id> — renomme une catégorie
export function renommerCategorie(id, nom) {
  return appeler('PUT', '/categories/' + id, { nom })
}

// DELETE /api/categories/<id> — supprime une catégorie vide
export function supprimerCategorie(id) {
  return appeler('DELETE', '/categories/' + id)
}

// --- Images ---

// GET /api/images?categorie_id= — images d'une catégorie (categorieId nul : sans catégorie)
export function listerImages(categorieId) {
  return appeler('GET', '/images' + (categorieId === null ? '' : '?categorie_id=' + categorieId))
}

// GET /api/images/<id> — une image : nom, catégorie, dimensions
export function lireImage(id) {
  return appeler('GET', '/images/' + id)
}

// POST /api/images/<id>/transformations — crée une nouvelle image
// type : 'recadrage', 'echelle', 'rotation', 'miroir' ou 'gris' ; parametres : ceux du type
export function transformerImage(id, type, parametres = {}) {
  return appeler('POST', `/images/${id}/transformations`, { type, ...parametres })
}

// POST /api/images — charge des fichiers ; renvoie { creees, refusees }
export function chargerImages(fichiers, categorieId) {
  const formulaire = new FormData()
  for (const fichier of fichiers) formulaire.append('fichiers', fichier)
  if (categorieId !== null) formulaire.append('categorie_id', categorieId)
  return appeler('POST', '/images', formulaire)
}

// PUT /api/images/<id> — déplace une image (categorieId nul : sans catégorie)
export function deplacerImage(id, categorieId) {
  return appeler('PUT', '/images/' + id, { categorie_id: categorieId })
}

// POST /api/images/suppression — supprime plusieurs images
export function supprimerImages(ids) {
  return appeler('POST', '/images/suppression', { ids })
}

// POST /api/images/zip — renvoie l'archive ZIP (Blob) des images demandées
export function zipImages(ids) {
  return appeler('POST', '/images/zip', { ids })
}

// GET /api/images/<id>/fichier — adresse du fichier, pour <img> ou pour un téléchargement
export function urlFichier(id, telecharger = false) {
  return `/api/images/${id}/fichier` + (telecharger ? '?telecharger=1' : '')
}
