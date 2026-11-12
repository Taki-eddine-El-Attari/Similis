// Vérification du calcul FRE fait dans le navigateur (src/fre.js). Lancer : node frontend/test_fre.mjs
// Les valeurs attendues sont calculées à la main, à partir des formules du cahier des charges.
import assert from 'node:assert/strict'
import { EPSILON, classer, distance, partsParDescripteur, retourDePertinence } from './src/fre.js'

const proche = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} au lieu de ${b}`)

// --- Retour de pertinence : moyenne des images pertinentes, poids = 1 / (ε + écart-type) ---
const retour = retourDePertinence([[1, 2], [3, 2]])
assert.deepEqual(retour.requete, [2, 2])
proche(retour.poids[0], 1 / (EPSILON + 1)) // la première valeur varie : écart-type 1
proche(retour.poids[1], 1 / EPSILON) // la seconde ne varie pas : poids maximal

// Une seule image pertinente : la requête ne change pas et tous les poids sont égaux
const seule = retourDePertinence([[5, 7, 9]])
assert.deepEqual(seule.requete, [5, 7, 9])
assert.ok(seule.poids.every((w) => w === 1 / EPSILON))

// --- Distance pondérée : Σ w (x − y)² / Σ w ---
proche(distance([0, 0], [3, 4], [1, 1]), 12.5) // (9 + 16) / 2
proche(distance([0, 0], [3, 4], [3, 1]), 10.75) // (27 + 16) / 4
proche(distance([1, 2], [1, 2], [1, 1]), 0)

// --- Recherche simple : la requête d'abord, puis les autres par distance croissante ---
const base = [[0, 0], [1, 0], [5, 5], [0.9, 0.1], [1, 0]]
const simple = classer(base, 0)
// distances à l'image 0 : 0,5 ; 25 ; 0,41 ; 0,5. Les images 1 et 4, à égalité, gardent leur ordre.
assert.deepEqual(simple.ordre, [0, 3, 1, 4, 2])
proche(simple.distances[3], 0.41)
proche(simple.distances[2], 25)
proche(simple.distances[0], 0)
// La requête reste en tête même si une autre image lui est identique
assert.deepEqual(classer([[1, 1], [1, 1], [2, 2]], 1).ordre, [1, 0, 2])

// --- Retour de pertinence : l'ordre change ---
// Requête A = (0, 0). Sans retour, C = (2, 3) est plus proche que D = (9, 0,05).
const images = [[0, 0], [4, 0.1], [2, 3], [9, 0.05]]
assert.deepEqual(classer(images, 0).ordre, [0, 2, 1, 3])
// On coche B = (4, 0,1) : la seconde valeur est stable entre A et B, elle pèse donc beaucoup,
// et D, qui a la même, passe devant C.
const affine = classer(images, 0, [1])
assert.deepEqual(affine.ordre, [0, 1, 3, 2])
proche(affine.poids[0], 1 / (EPSILON + 2)) // écart-type de (0, 4)
proche(affine.poids[1], 1 / (EPSILON + 0.05)) // écart-type de (0, 0,1)
// distance de D à la nouvelle requête (2, 0,05) : w0 × 49 / (w0 + w1)
proche(affine.distances[3], (affine.poids[0] * 49) / (affine.poids[0] + affine.poids[1]))
// Sans image cochée, « affiner » redonne la recherche simple
assert.deepEqual(classer(images, 0, []).ordre, classer(images, 0).ordre)

// --- Part du poids par descripteur ---
const parts = partsParDescripteur([1, 1, 2, 4], { a: [0, 2], b: [2, 3], c: [3, 4] })
assert.deepEqual(parts, { a: 0.25, b: 0.25, c: 0.5 })

console.log('FRE (navigateur) : toutes les vérifications passent.')
