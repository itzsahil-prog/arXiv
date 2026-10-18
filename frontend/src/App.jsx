import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import Check from './pages/Check.jsx'
import History from './pages/History.jsx'
import Library from './pages/Library.jsx'

const TABS = [
  ['check', 'Check a paper'],
  ['history', 'History'],
  ['library', 'Library'],
]

export default function App() {
  const [tab, setTab] = useState(() => window.location.hash.slice(1) || 'check')
  const [stats, setStats] = useState(null)

  const refresh = useCallback(() => api.stats().then(setStats).catch(() => {}), [])
  useEffect(() => { refresh() }, [refresh])
  useEffect(() => { window.location.hash = tab }, [tab])

  return (
    <div className="app">
      <nav className="rail" aria-label="Main">
        <div className="brand">Overlap</div>
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? 'on' : ''} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </nav>
      <main className="main">
        {tab === 'check' && <Check stats={stats} goLibrary={() => setTab('library')} />}
        {tab === 'history' && <History />}
        {tab === 'library' && <Library stats={stats} refresh={refresh} />}
      </main>
    </div>
  )
}
