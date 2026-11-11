<script setup>
// Bouton qui bascule entre le mode clair et le mode sombre.
import { AnimateIcon } from '@animate-ui/vue/icons'
import { basculerTheme, estSombre } from '@/apparence'
import Moon from '@/components/animate-ui/icons/Moon.vue'
import Sun from '@/components/animate-ui/icons/Sun.vue'
import { Button } from '@/components/ui/button'
</script>

<template>
  <AnimateIcon animate-on-hover as-child>
    <Button variant="ghost" size="sm" class="justify-start" @click="basculerTheme">
      <component :is="estSombre ? Sun : Moon" :size="16" />
      {{ estSombre ? 'Mode clair' : 'Mode sombre' }}
    </Button>
  </AnimateIcon>
</template>
