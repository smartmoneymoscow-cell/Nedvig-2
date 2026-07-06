import { Sun, Moon, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { triggerScrape } from '../api/client'

interface Props {
  onScrape: () => void
  dark: boolean
  onToggleDark: () => void
}

export default function Header({ onScrape, dark, onToggleDark }: Props) {
  const [scraping, setScraping] = useState(false)

  const handleScrape = async () => {
    setScraping(true)
    try { await onScrape() } finally { setTimeout(() => setScraping(false), 30000) }
  }

  return (
    <header className="bg-gray-900 text-white h-14 flex items-center justify-between px-6 shrink-0">
      <a href="/" className="font-display text-xl font-bold tracking-tight">
        торги<span className="text-red-500">.</span>недвижимость
      </a>
      <nav className="flex items-center gap-4">
        <button
          onClick={handleScrape}
          disabled={scraping}
          className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 px-4 py-1.5 text-sm font-semibold uppercase tracking-wider transition-colors"
        >
          <RefreshCw size={14} className={scraping ? 'animate-spin' : ''} />
          {scraping ? 'Сбор...' : 'Обновить'}
        </button>
        <button onClick={onToggleDark} className="p-2 hover:bg-gray-700 rounded transition-colors">
          {dark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </nav>
    </header>
  )
}
