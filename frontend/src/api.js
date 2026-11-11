// Tous les appels au backend passent par ce fichier : une fonction par service.

// Envoie une requête JSON à l'API et renvoie la réponse décodée.
// En cas d'erreur, lève une Error avec le message renvoyé par l'API.
async function appeler(methode, chemin, corps) {
  const reponse = await fetch('/api' + chemin, {
    method: methode,
    headers: corps ? { 'Content-Type': 'application/json' } : {},
    body: corps ? JSON.stringify(corps) : undefined,
  })
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
