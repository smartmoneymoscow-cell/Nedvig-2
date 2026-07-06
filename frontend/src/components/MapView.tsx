import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet.markercluster'
import type { MapPoint } from '../types'

interface Props {
  points: MapPoint[]
  loading: boolean
  onSelect: (p: MapPoint) => void
}

function getColor(dateStr: string | null): string {
  if (!dateStr) return '#7c3aed'
  const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000)
  if (days <= 0) return '#dc2626'
  if (days <= 3) return '#d97706'
  if (days <= 7) return '#ca8a04'
  if (days <= 28) return '#16a34a'
  if (days <= 90) return '#2563eb'
  return '#7c3aed'
}

function makeIcon(color: string, big: boolean) {
  const s = big ? 32 : 24
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${s}" height="${s * 1.4}" viewBox="0 0 24 34"><path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 22 12 22s12-13 12-22C24 5.4 18.6 0 12 0z" fill="${color}"/><circle cx="12" cy="11" r="5.5" fill="white"/><circle cx="12" cy="11" r="2.5" fill="${color}"/></svg>`
  return L.icon({
    iconUrl: `data:image/svg+xml,${encodeURIComponent(svg)}`,
    iconSize: [s, s * 1.4],
    iconAnchor: [s / 2, s * 1.4],
    popupAnchor: [0, -s * 1.4],
  })
}

function formatPrice(p: number | null): string {
  if (!p) return '—'
  if (p >= 1e6) return `${(p / 1e6).toFixed(1)} млн ₽`
  if (p >= 1e3) return `${(p / 1e3).toFixed(0)} тыс ₽`
  return `${p.toFixed(0)} ₽`
}

export default function MapView({ points, loading, onSelect }: Props) {
  const mapRef = useRef<L.Map | null>(null)
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const pointsRef = useRef<MapPoint[]>([])
  pointsRef.current = points

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current, {
      center: [55.7558, 37.6173],
      zoom: 10,
      zoomControl: true,
    })

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
      maxZoom: 19,
    }).addTo(map)

    const cluster = L.markerClusterGroup({
      maxClusterRadius: 60,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
    })
    map.addLayer(cluster)

    mapRef.current = map
    clusterRef.current = cluster

    return () => { map.remove(); mapRef.current = null }
  }, [])

  useEffect(() => {
    const cluster = clusterRef.current
    if (!cluster) return

    cluster.clearLayers()

    const markers = points.map(p => {
      const color = getColor(p.publish_date)
      const big = p.discount_pct !== null && p.discount_pct > 20
      const icon = makeIcon(color, big)
      const marker = L.marker([p.lat, p.lon], { icon })

      const disc = p.discount_pct !== null && p.discount_pct !== undefined
        ? `<div style="margin-top:4px"><span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700;background:${p.discount_pct > 0 ? '#dcfce7' : '#fee2e2'};color:${p.discount_pct > 0 ? '#16a34a' : '#dc2626'}">${p.discount_pct > 0 ? '−' : '+'}${Math.abs(p.discount_pct).toFixed(1)}%</span></div>`
        : ''

      marker.bindPopup(`
        <div style="min-width:220px;font-family:'Source Sans 3',system-ui,sans-serif">
          <div style="font-size:14px;font-weight:600;margin-bottom:6px">${p.title || '—'}</div>
          <div style="font-family:'Playfair Display',serif;font-size:18px;font-weight:700;color:#059669">${formatPrice(p.price)}</div>
          ${p.market_price ? `<div style="font-size:12px;color:#6b7280;margin-top:2px">Рынок: ${formatPrice(p.market_price)}</div>` : ''}
          ${disc}
          <div style="font-size:12px;color:#6b7280;margin-top:6px">${p.type || '—'}${p.area ? ` · ${p.area} м²` : ''}${p.rooms ? ` · ${p.rooms} комн.` : ''}</div>
          ${p.url ? `<a href="${p.url}" target="_blank" style="display:inline-block;margin-top:8px;font-size:12px;color:#2563eb">Открыть →</a>` : ''}
        </div>
      `)

      marker.on('click', () => onSelect(p))
      return marker
    })

    cluster.addLayers(markers)

    if (markers.length > 0) {
      const bounds = cluster.getBounds()
      if (bounds.isValid()) {
        mapRef.current?.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 })
      }
    }
  }, [points, onSelect])

  return (
    <div className="w-full h-full relative">
      <div ref={containerRef} className="w-full h-full" />
      {loading && (
        <div className="absolute inset-0 bg-white/80 dark:bg-gray-900/80 flex items-center justify-center z-[1000]">
          <div className="flex flex-col items-center gap-3">
            <div className="w-10 h-10 border-3 border-gray-200 border-t-red-500 rounded-full animate-spin" />
            <span className="text-sm text-gray-500">Загрузка данных...</span>
          </div>
        </div>
      )}
      {!loading && points.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="bg-white/90 dark:bg-gray-800/90 px-8 py-6 rounded-lg shadow-lg text-center max-w-sm">
            <div className="text-4xl mb-3">🏠</div>
            <div className="font-semibold text-lg mb-1">Нет объектов</div>
            <div className="text-sm text-gray-500">Попробуйте изменить фильтры или обновить данные</div>
          </div>
        </div>
      )}
    </div>
  )
}
