import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMapData, fetchStats, triggerScrape } from './api/client'
import MapView from './components/MapView'
import Sidebar from './components/Sidebar'
import DetailPanel from './components/DetailPanel'
import Header from './components/Header'
import StatsBar from './components/StatsBar'
import type { MapPoint, Filters } from './types'

export default function App() {
  const [filters, setFilters] = useState<Filters>({ days: 90 })
  const [selected, setSelected] = useState<MapPoint | null>(null)
  const [dark, setDark] = useState(false)

  const { data: points = [], isLoading, error } = useQuery({
    queryKey: ['mapData', filters],
    queryFn: () => fetchMapData(filters as Record<string, string | number | undefined>),
    retry: 2,
    staleTime: 5 * 60 * 1000, // 5 min cache
  })

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    retry: 2,
    staleTime: 5 * 60 * 1000,
  })

  const handleScrape = useCallback(async () => {
    await triggerScrape()
  }, [])

  return (
    <div className={`h-screen flex flex-col overflow-hidden ${dark ? 'dark' : ''}`}>
      <Header onScrape={handleScrape} dark={dark} onToggleDark={() => setDark(!dark)} />
      <StatsBar stats={stats} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar filters={filters} onChange={setFilters} stats={stats} />
        <div className="flex-1 relative">
          {error ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="bg-white dark:bg-gray-800 px-8 py-6 rounded-lg shadow-lg text-center max-w-md">
                <div className="text-4xl mb-3">⚠️</div>
                <div className="font-semibold text-lg mb-2">Ошибка загрузки</div>
                <div className="text-sm text-gray-500 mb-4">
                  {error instanceof Error ? error.message : 'Не удалось получить данные с сервера'}
                </div>
                <div className="text-xs text-gray-400">
                  API: {import.meta.env.VITE_API_URL || '(локальный)'}
                </div>
              </div>
            </div>
          ) : (
            <MapView points={points} loading={isLoading} onSelect={setSelected} />
          )}
          {selected && <DetailPanel point={selected} onClose={() => setSelected(null)} />}
        </div>
      </div>
    </div>
  )
}
