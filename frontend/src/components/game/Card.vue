<template>
  <div class="card-wrapper">
    <img v-if="card" :src="cardImage" :alt="cardAlt" class="card-image" />
    <div v-else class="card-back">
      <img src="/cards/Background.png" alt="Card Back" class="card-image" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Card as CardType } from '@/types'

const props = defineProps<{
  card?: CardType
}>()

const cardImage = computed(() => {
  if (!props.card) return '/cards/Background.png'

  const suit = props.card.suit
  const rank = props.card.rank

  // Map suit to filename prefix
  const suitMap: Record<string, string> = {
    'c': 'Club',
    'd': 'Diamond',
    'h': 'Heart',
    's': 'Spade'
  }

  // Map rank to filename suffix
  const rankMap: Record<string, string> = {
    '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    '10': '10', 'J': 'J', 'Q': 'Q', 'K': 'K', 'A': 'A'
  }

  const suitName = suitMap[suit] || 'Club'
  const rankName = rankMap[rank] || '2'

  return `/cards/${suitName}${rankName}.png`
})

const cardAlt = computed(() => {
  if (!props.card) return 'Card'
  const suitNames: Record<string, string> = {
    'c': 'Clubs', 'd': 'Diamonds', 'h': 'Hearts', 's': 'Spades'
  }
  return `${props.card.rank} of ${suitNames[props.card.suit] || 'Clubs'}`
})
</script>

<style scoped>
.card-wrapper {
  display: inline-block;
}

.card-image {
  width: 60px;
  height: 84px;
  object-fit: contain;
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.card-back {
  display: inline-block;
}
</style>
