// Les 5 descripteurs d'une image, dans l'ordre du vecteur de 141 valeurs, avec leur couleur du thème.
// « cle » est le nom employé par l'API (poids_par_descripteur, groupes).
export const DESCRIPTEURS = [
  { cle: 'histogrammes', nom: 'Histogrammes', couleur: 'var(--chart-1)' },
  { cle: 'moments', nom: 'Moments', couleur: 'var(--chart-2)' },
  { cle: 'dominantes', nom: 'Dominantes', couleur: 'var(--chart-3)' },
  { cle: 'glcm', nom: 'GLCM', couleur: 'var(--chart-4)' },
  { cle: 'lbp', nom: 'LBP', couleur: 'var(--chart-5)' },
]
