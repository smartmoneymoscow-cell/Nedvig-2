import type { MapPoint, PaginatedResponse, Stats, Filters } from '../types'

// In static mode, read from JSON files on the same origin (GH Pages)
// In API mode, read from the API backend
const API_BASE = import.meta.env.VITE_API_URL || ''
const STATIC_MODE = !API_BASE

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchMapData(params: Filters = {}): Promise<MapPoint[]> {
  if (STATIC_MODE) {
    return fetchJSON<MapPoint[]>('static-api/map-data.json')
  }
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') searchParams.set(k, String(v))
  })
  return fetchJSON<MapPoint[]>(`${API_BASE}/api/map-data?${searchParams}`)
}

export async function fetchProperties(filters: Filters = {}): Promise<PaginatedResponse> {
  if (STATIC_MODE) {
    return fetchJSON<PaginatedResponse>('static-api/properties.json')
  }
  const searchParams = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') searchParams.set(k, String(v))
  })
  return fetchJSON<PaginatedResponse>(`${API_BASE}/api/properties?${searchParams}`)
}

export async function fetchStats(): Promise<Stats> {
  if (STATIC_MODE) {
    return fetchJSON<Stats>('static-api/stats.json')
  }
  return fetchJSON<Stats>(`${API_BASE}/api/stats`)
}

export async function triggerScrape(): Promise<{ status: string }> {
  if (STATIC_MODE) {
    return { status: 'static_mode' }
  }
  const res = await fetch(`${API_BASE}/api/scrape/trigger`, { method: 'POST' })
  return res.json()
}
