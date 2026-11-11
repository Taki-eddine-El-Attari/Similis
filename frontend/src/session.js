// Utilisateur connecté, partagé par toute l'application.
// undefined : pas encore vérifié ; null : non connecté ; objet : connecté.
// Fichier à part : le routeur et les vues le lisent sans s'importer l'un l'autre.
import { ref } from 'vue'

export const utilisateur = ref(undefined)
