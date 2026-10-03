import { createApp } from 'vue'
import { ElCard, ElContainer, ElHeader, ElMain, ElPagination } from 'element-plus'
import 'element-plus/es/components/card/style/css'
import 'element-plus/es/components/container/style/css'
import 'element-plus/es/components/header/style/css'
import 'element-plus/es/components/main/style/css'
import 'element-plus/es/components/pagination/style/css'

import App from './App.vue'
import router from './router'
import './styles/index.css'
import './styles/home.css'
import './styles/information.css'
import './styles/teams.css'
import './styles/recruitment.css'
import './styles/account.css'
import './styles/motion.css'
import './styles/home-motion.css'
import reveal from './directives/reveal'

const app = createApp(App)

app.use(router)
app.directive('reveal', reveal)
app.component(ElCard.name, ElCard)
app.component(ElContainer.name, ElContainer)
app.component(ElHeader.name, ElHeader)
app.component(ElMain.name, ElMain)
app.component(ElPagination.name, ElPagination)
app.mount('#app')
