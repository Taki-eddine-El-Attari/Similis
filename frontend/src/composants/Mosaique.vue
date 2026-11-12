<script setup>
// Mosaïque décorative : 36 carreaux aux teintes du thème. Sert à l'écran de connexion,
// et à la page d'accueil quand la démonstration n'est pas disponible.
// Chaque chiffre du motif choisit une teinte ci-dessous.
const MOTIF = '032410421304103242013410230143204132'
const TEINTES = ['bg-primary', 'bg-primary-soft', 'bg-border', 'bg-muted', 'bg-card']
</script>

<template>
  <div class="grid grid-cols-6 gap-2" aria-hidden="true">
    <i
      v-for="(chiffre, i) in MOTIF"
      :key="i"
      class="aspect-square rounded-lg border"
      :class="TEINTES[chiffre]"
      :style="chiffre === '0' ? { opacity: 0.35 + ((i * 5) % 7) / 10 } : null"
    />
  </div>
</template>
