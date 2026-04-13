import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

try {
  const root = document.getElementById('root');
  if (!root) throw new Error('Root element not found');
  
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
} catch (error) {
  console.error('CRITICAL RENDER ERROR:', error);
  document.body.innerHTML = `<div style="padding: 20px; color: red;"><h1>Critical Error</h1><pre>${error instanceof Error ? error.stack : String(error)}</pre></div>`;
}
