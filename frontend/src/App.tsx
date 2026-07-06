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

  const { data: points = [], isLoading } = useQuery({
    queryKey: ['mapData', filters],
    queryFn: () => fetchMapData(filters),
  })

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
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
          <MapView points={points} loading={isLoading} onSelect={setSelected} />
          {selected && <DetailPanel point={selected} onClose={() => setSelected(null)} />}
        </div>
      </div>
    </div>
  )
}
