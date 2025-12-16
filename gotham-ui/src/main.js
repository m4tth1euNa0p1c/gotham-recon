import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { ApolloClient, InMemoryCache, createHttpLink } from '@apollo/client/core'
import { DefaultApolloClient } from '@vue/apollo-composable'
import App from './App.vue'
import './style.css'

// Apollo Client Setup
const httpLink = createHttpLink({
  uri: '/graphql'
})

const apolloClient = new ApolloClient({
  link: httpLink,
  cache: new InMemoryCache()
})

// Router Setup
const routes = [
  { path: '/', name: 'Dashboard', component: () => import('./views/Dashboard.vue') },
  { path: '/mission/:id', name: 'Mission', component: () => import('./views/MissionView.vue') }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Create App
const app = createApp(App)
app.provide(DefaultApolloClient, apolloClient)
app.use(createPinia())
app.use(router)
app.mount('#app')
