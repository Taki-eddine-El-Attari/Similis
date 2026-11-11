<script setup>
// Petit graphique en barres (Chart.js) : sert aux histogrammes de couleur et à l'histogramme LBP.
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { BarController, BarElement, CategoryScale, Chart, LinearScale, Tooltip } from 'chart.js'
import { accent, estSombre } from '@/apparence'

// On n'enregistre que les morceaux de Chart.js utilisés : le fichier final est plus léger.
Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip)

const props = defineProps({
  valeurs: { type: Array, required: true }, // hauteur de chaque barre
  etiquettes: { type: Array, required: true }, // nom de chaque barre, montré au survol
  couleur: { type: String, required: true }, // variable CSS du thème, par exemple '--canal-r'
  description: { type: String, required: true }, // texte lu par les lecteurs d'écran
})

const toile = ref(null)
let graphique = null

// Chart.js dessine dans un canvas : il lui faut la vraie couleur, pas le nom de la variable CSS.
function lireCouleur() {
  return getComputedStyle(document.documentElement).getPropertyValue(props.couleur).trim()
}

onMounted(() => {
  graphique = new Chart(toile.value, {
    type: 'bar',
    data: {
      labels: props.etiquettes,
      // Les barres se touchent, comme dans un histogramme.
      datasets: [{ data: props.valeurs, backgroundColor: lireCouleur(), barPercentage: 1, categoryPercentage: 1 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false, // la hauteur vient du bloc qui contient le graphique
      animation: { duration: 300 },
      scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
      plugins: {
        tooltip: {
          displayColors: false,
          // Valeur en pourcentage : les histogrammes sont des fréquences.
          callbacks: { label: (barre) => (barre.parsed.y * 100).toFixed(2) + ' %' },
        },
      },
    },
  })
})

// Nouvelles valeurs (autre image) : on redessine.
watch(
  () => props.valeurs,
  (valeurs) => {
    graphique.data.datasets[0].data = valeurs
    graphique.update()
  },
)

// Changement de thème ou d'accent : les couleurs des graphiques changent aussi.
watch([estSombre, accent], async () => {
  await nextTick() // on attend que la nouvelle classe soit posée sur <html>
  graphique.data.datasets[0].backgroundColor = lireCouleur()
  graphique.update()
})

onBeforeUnmount(() => graphique?.destroy())
</script>

<template>
  <div class="relative h-16">
    <canvas ref="toile" role="img" :aria-label="description" />
  </div>
</template>
