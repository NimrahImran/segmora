import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@fontsource/bodoni-moda/400.css'
import '@fontsource/bodoni-moda/500.css'
import '@fontsource/hanken-grotesk/400.css'
import '@fontsource/hanken-grotesk/500.css'
import '@fontsource/hanken-grotesk/600.css'
import './styles.css'
import App from './App'
import { DataProvider } from './lib/store'

createRoot(document.getElementById('root')!).render(
  <StrictMode><BrowserRouter><DataProvider><App /></DataProvider></BrowserRouter></StrictMode>,
)
