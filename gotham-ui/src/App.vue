<template>
  <div class="min-h-screen bg-gray-900 text-gray-100">
    <!-- Navigation -->
    <nav class="bg-gray-800 border-b border-gray-700">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center">
            <router-link to="/" class="flex items-center">
              <span class="text-2xl font-bold text-green-400">GOTHAM</span>
              <span class="ml-2 text-sm text-gray-400">Reconnaissance</span>
            </router-link>
          </div>
          <div class="flex items-center space-x-4">
            <span class="text-sm text-gray-400">{{ currentTime }}</span>
            <div class="w-3 h-3 rounded-full" :class="connectionStatus"></div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const currentTime = ref(new Date().toLocaleTimeString())
const isConnected = ref(true)

const connectionStatus = computed(() =>
  isConnected.value ? 'bg-green-500' : 'bg-red-500'
)

let interval
onMounted(() => {
  interval = setInterval(() => {
    currentTime.value = new Date().toLocaleTimeString()
  }, 1000)
})

onUnmounted(() => {
  clearInterval(interval)
})
</script>
