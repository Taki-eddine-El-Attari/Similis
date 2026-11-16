// Les 5 descripteurs d'une image, dans l'ordre du vecteur de 141 valeurs, avec leur couleur du thème.
// « cle » est le nom employé par l'API (poids_par_descripteur, groupes).
export const DESCRIPTEURS = [
  { cle: 'histogrammes', nom: 'Histogrammes', couleur: 'var(--chart-1)' },
  { cle: 'moments', nom: 'Moments', couleur: 'var(--chart-2)' },
  { cle: 'dominantes', nom: 'Dominantes', couleur: 'var(--chart-3)' },
  { cle: 'glcm', nom: 'GLCM', couleur: 'var(--chart-4)' },
  { cle: 'lbp', nom: 'LBP', couleur: 'var(--chart-5)' },
]

// Range un vecteur normalisé par descripteur, pour le dessiner : chaque valeur (un écart à la moyenne
// de GHIM-10K, en écarts-types) devient une hauteur entre -1 et 1, pleine à 3 écarts-types.
// groupes : { cle: [début, fin[ } dans le vecteur. Renvoie [{ cle, nom, couleur, valeurs }].
export function rangerParDescripteur(vecteur, groupes) {
  return DESCRIPTEURS.map((d) => {
    const [debut, fin] = groupes[d.cle]
    return { ...d, valeurs: vecteur.slice(debut, fin).map((v) => Math.max(-1, Math.min(1, v / 3))) }
  })
}
