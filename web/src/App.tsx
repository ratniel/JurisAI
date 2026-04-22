import { Route, Routes } from 'react-router-dom'

import './App.css'
import { ChatPage } from './routes/ChatPage'
import { HomePage } from './routes/HomePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/chat/:sessionId" element={<ChatPage />} />
    </Routes>
  )
}
