import { Sun, Moon, RefreshCw, Building2, Map, BarChart3 } from 'lucide-react'
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
    } catch {
      setScrapeMsg('Ошибка')
    } finally {
      setTimeout(() => { setScraping(false); setScrapeMsg(null) }, 5000)
    }
  }

  return (
    <header className="bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 text-white h-14 flex items-center justify-between px-4 md:px-6 shrink-0 shadow-lg">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center">
            <Building2 size={18} className="text-white" />
          </div>
          <a href="/" className="font-display text-lg md:text-xl font-bold tracking-tight">
            торги<span className="text-red-500">.</span>недвижимость
          </a>
        </div>
        <div className="hidden md:flex items-center gap-1 ml-6">
          <span className="px-3 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-red-600/20 text-red-400 border border-red-600/30">
            <Map size={10} className="inline mr-1" />
            Карта
          </span>
          <span className="px-3 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-white/5 text-white/40 border border-white/10">
            <BarChart3 size={10} className="inline mr-1" />
            Аналитика
          </span>
        </div>
      </div>
      <nav className="flex items-center gap-2 md:gap-4">
        {scrapeMsg && (
          <span className="text-xs text-green-400 animate-pulse hidden sm:inline">{scrapeMsg}</span>
        )}
        <button
          onClick={handleScrape}
          disabled={scraping}
          className="flex items-center gap-2 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 disabled:opacity-50 px-4 py-2 text-xs md:text-sm font-semibold uppercase tracking-wider transition-all rounded-lg shadow-md hover:shadow-lg"
        >
          <RefreshCw size={14} className={scraping ? 'animate-spin' : ''} />
          <span className="hidden sm:inline">{scraping ? 'Сбор данных...' : 'Обновить'}</span>
        </button>
        <button onClick={onToggleDark} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
          {dark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </nav>
    </header>
  )
}
