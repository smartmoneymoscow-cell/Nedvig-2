import type { MapPoint, PaginatedResponse, Stats, Filters } from '../types'

const API_BASE = import.meta.env.VITE_API_URL || ''

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchMapData(params: Record<string, string | number | undefined> = {}): Promise<MapPoint[]> {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') searchParams.set(k, String(v))
  })
  return fetchJSON<MapPoint[]>(`${API_BASE}/api/map-data?${searchParams}`)
}

export async function fetchProperties(filters: Filters = {}): Promise<PaginatedResponse> {
  const searchParams = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') searchParams.set(k, String(v))
  })
  return fetchJSON<PaginatedResponse>(`${API_BASE}/api/properties?${searchParams}`)
}

export async function fetchStats(): Promise<Stats> {
  return fetchJSON<Stats>(`${API_BASE}/api/stats`)
}

export async function triggerScrape(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/scrape/trigger`, { method: 'POST' })
  return res.json()
}
