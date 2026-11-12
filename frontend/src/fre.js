// Recherche et retour de pertinence FRE, calculés dans le navigateur pour la démonstration
// de la page d'accueil. Mêmes formules que backend/recherche.py : modifier l'un, c'est modifier l'autre.
// Vérification : node frontend/test_fre.mjs

export const EPSILON = 0.0001 // ε de la formule 4

// Retour de pertinence. La nouvelle requête est la moyenne des images pertinentes ;
// chaque valeur pèse d'autant plus qu'elle varie peu entre ces images : w = 1 / (ε + écart-type).
// Avec une seule image pertinente, tous les poids sont égaux : c'est la recherche simple.
export function retourDePertinence(pertinents) {
  const nombre = pertinents.length
  const requete = pertinents[0].map((_, i) => pertinents.reduce((somme, v) => somme + v[i], 0) / nombre)
  const poids = requete.map((moyenne, i) => {
    const variance = pertinents.reduce((somme, v) => somme + (v[i] - moyenne) ** 2, 0) / nombre
    return 1 / (EPSILON + Math.sqrt(variance))
  })
  return { requete, poids }
}

// Distance pondérée entre deux vecteurs : Σ w (x − y)² / Σ w
export function distance(x, y, poids) {
  let somme = 0
  let total = 0
  for (let i = 0; i < x.length; i++) {
    somme += poids[i] * (x[i] - y[i]) ** 2
    total += poids[i]
  }
  return somme / total
}

// Classe toutes les images par rapport à l'image requête.
//   vecteurs : un vecteur normalisé par image ; requete : numéro de l'image requête ;
//   cochees  : numéros des images marquées pertinentes (aucune : recherche simple).
// Renvoie { ordre, distances, poids } : la requête d'abord, puis les autres par distance croissante.
export function classer(vecteurs, requete, cochees = []) {
  const { requete: cible, poids } = retourDePertinence([requete, ...cochees].map((n) => vecteurs[n]))
  const distances = vecteurs.map((vecteur) => distance(vecteur, cible, poids))
  const autres = vecteurs.map((_, n) => n).filter((n) => n !== requete)
  // À distance égale, l'ordre de départ est gardé, comme le tri stable du serveur.
  autres.sort((a, b) => distances[a] - distances[b] || a - b)
  return { ordre: [requete, ...autres], distances, poids }
}

// Part du poids total portée par chaque descripteur. groupes : { nom: [début, fin[ } dans le vecteur.
export function partsParDescripteur(poids, groupes) {
  const somme = (valeurs) => valeurs.reduce((total, w) => total + w, 0)
  const total = somme(poids)
  return Object.fromEntries(
    Object.entries(groupes).map(([nom, [debut, fin]]) => [nom, somme(poids.slice(debut, fin)) / total]),
  )
}
