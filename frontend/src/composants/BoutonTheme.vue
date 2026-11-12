<script setup>
// Bouton qui bascule entre le mode clair et le mode sombre.
import { computed } from 'vue'
import { AnimateIcon } from '@animate-ui/vue/icons'
import { basculerTheme, estSombre } from '@/apparence'
import Moon from '@/components/animate-ui/icons/Moon.vue'
import Sun from '@/components/animate-ui/icons/Sun.vue'
import { Button } from '@/components/ui/button'

// sansTexte : l'icône seule, pour la barre de la page d'accueil.
// Le nom du bouton reste alors donné aux lecteurs d'écran et à l'infobulle.
defineProps({ sansTexte: Boolean })

const texte = computed(() => (estSombre.value ? 'Mode clair' : 'Mode sombre'))
</script>

<template>
  <AnimateIcon animate-on-hover as-child>
    <Button
      variant="ghost"
      :size="sansTexte ? 'icon' : 'sm'"
      :class="sansTexte ? '' : 'justify-start'"
      :aria-label="sansTexte ? texte : undefined"
      :title="sansTexte ? texte : undefined"
      @click="basculerTheme"
    >
      <component :is="estSombre ? Sun : Moon" :size="16" />
      <template v-if="!sansTexte">{{ texte }}</template>
    </Button>
  </AnimateIcon>
</template>
