<script setup>
// Empreinte d'une photo : une barre par valeur du vecteur, groupées par descripteur.
// La ligne du milieu est la moyenne de GHIM-10K : la barre monte si la valeur est au-dessus
// de la moyenne, descend (plus pâle) si elle est en dessous. La hauteur du bloc est donnée par la page.
defineProps({
  // Un groupe par descripteur : { cle, couleur, valeurs } ; valeurs entre -1 et 1 (voir rangerParDescripteur).
  groupes: { type: Array, required: true },
})
</script>

<template>
  <div class="empreinte" role="img">
    <span v-for="g in groupes" :key="g.cle" :style="{ color: g.couleur, flexGrow: g.valeurs.length }">
      <i v-for="(v, i) in g.valeurs" :key="i" :style="{ '--haut': Math.max(v, 0), '--bas': Math.max(-v, 0) }" />
    </span>
  </div>
</template>

<style scoped>
.empreinte {
  position: relative;
  display: flex;
  gap: 3px;
}
.empreinte::before {
  content: '';
  position: absolute;
  top: 50%;
  right: 0;
  left: 0;
  border-top: 1px solid var(--border);
}
/* Un <span> par descripteur, un <i> par valeur. */
.empreinte > span {
  display: flex;
  flex-basis: 0;
  min-width: 0;
}
.empreinte i {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
}
.empreinte i::before,
.empreinte i::after {
  content: '';
  position: absolute;
  right: 0;
  left: 0;
  height: 50%;
  background: currentColor;
  /* Changement de photo : les barres glissent vers leurs nouvelles hauteurs. */
  transition: transform 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}
.empreinte i::before {
  bottom: 50%;
  transform: scaleY(var(--haut));
  transform-origin: bottom;
}
.empreinte i::after {
  top: 50%;
  opacity: 0.5;
  transform: scaleY(var(--bas));
  transform-origin: top;
}
/* À partir de la tablette, un fin espace sépare les barres. */
@media (min-width: 640px) {
  .empreinte > span {
    gap: 1px;
  }
}
</style>
