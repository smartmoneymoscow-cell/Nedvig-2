import type { MapPoint, PaginatedResponse, Stats, Filters } from '../types'

const API_BASE = import.meta.env.VITE_API_URL || ''

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function fetchJSON<T>(url: string): Promise<T> {
  try {
    const res = await fetch(url)
    if (!res.ok) {
      const body = await res.text().catch(() => '')
      throw new ApiError(res.status, `HTTP ${res.status}: ${body || res.statusText}`)
    }
    return res.json()
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new ApiError(0, `Network error: ${err instanceof Error ? err.message : String(err)}`)
  }
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
  try {
    const res = await fetch(`${API_BASE}/api/scrape/trigger`, { method: 'POST' })
    if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`)
    return res.json()
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new ApiError(0, `Network error: ${err instanceof Error ? err.message : String(err)}`)
  }
}
