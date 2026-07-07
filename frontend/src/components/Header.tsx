import { Sun, Moon, RefreshCw } from 'lucide-react'
import { useState } from 'react'

interface Props {
  onScrape: () => void
  dark: boolean
  onToggleDark: () => void
}

export default function Header({ onScrape, dark, onToggleDark }: Props) {
  const [scraping, setScraping] = useState(false)
  const [scrapeMsg, setScrapeMsg] = useState<string | null>(null)

  const handleScrape = async () => {
    setScraping(true)
    setScrapeMsg(null)
    try {
      await onScrape()
      setScrapeMsg('Запущено!')
    } catch (err) {
      setScrapeMsg('Ошибка')
    } finally {
      setTimeout(() => { setScraping(false); setScrapeMsg(null) }, 5000)
    }
  }

  return (
    <header className="bg-gray-900 text-white h-14 flex items-center justify-between px-4 md:px-6 shrink-0">
      <a href="/" className="font-display text-lg md:text-xl font-bold tracking-tight">
        торги<span className="text-red-500">.</span>недвижимость
      </a>
      <nav className="flex items-center gap-2 md:gap-4">
        {scrapeMsg && (
          <span className="text-xs text-green-400 animate-pulse hidden sm:inline">{scrapeMsg}</span>
        )}
        <button
          onClick={handleScrape}
          disabled={scraping}
          className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 px-3 md:px-4 py-1.5 text-xs md:text-sm font-semibold uppercase tracking-wider transition-colors"
        >
          <RefreshCw size={14} className={scraping ? 'animate-spin' : ''} />
          <span className="hidden sm:inline">{scraping ? 'Сбор...' : 'Обновить'}</span>
        </button>
        <button onClick={onToggleDark} className="p-2 hover:bg-gray-700 rounded transition-colors">
          {dark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </nav>
    </header>
  )
}
