// Apparence de l'interface : mode clair ou sombre, et couleur d'accent.
// Les deux choix sont mémorisés dans le navigateur (localStorage).
import { computed, watchEffect } from 'vue'
import { useColorMode, useStorage } from '@vueuse/core'

// Pose la classe « dark » ou « light » sur <html>. Sans choix, suit le système.
const mode = useColorMode({ storageKey: 'similis-theme' })

// Choix enregistré : 'auto' (système), 'light' ou 'dark'.
export const theme = mode.store

export const estSombre = computed(() => mode.value === 'dark')

export function basculerTheme() {
  theme.value = estSombre.value ? 'light' : 'dark'
}

// Accent : 'sarcelle' (défaut) ou 'indigo'. Lu par style.css via l'attribut data-accent.
export const ACCENTS = ['sarcelle', 'indigo']
export const accent = useStorage('similis-accent', 'sarcelle')

watchEffect(() => {
  // Une valeur inconnue dans le stockage retombe sur l'accent par défaut.
  if (!ACCENTS.includes(accent.value)) accent.value = 'sarcelle'
  document.documentElement.dataset.accent = accent.value
})
