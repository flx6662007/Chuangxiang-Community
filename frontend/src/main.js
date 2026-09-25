import { createApp } from 'vue'
import { ElCard, ElContainer, ElHeader, ElMain } from 'element-plus'
import 'element-plus/es/components/card/style/css'
import 'element-plus/es/components/container/style/css'
import 'element-plus/es/components/header/style/css'
import 'element-plus/es/components/main/style/css'

import App from './App.vue'
import router from './router'
import './styles/index.css'

const app = createApp(App)

app.use(router)
app.component(ElCard.name, ElCard)
app.component(ElContainer.name, ElContainer)
app.component(ElHeader.name, ElHeader)
app.component(ElMain.name, ElMain)
app.mount('#app')
