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

// GET /api/sante — vérifie que l'API répond
export function sante() {
  return appeler('GET', '/sante')
}
