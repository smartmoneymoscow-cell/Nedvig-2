export interface MapPoint {
  id: number
  lat: number
  lon: number
  title: string
  price: number | null
  market_price: number | null
  discount_pct: number | null
  area: number | null
  rooms: number | null
  status: string
  type: string
  publish_date: string | null
  source: string
  url: string | null
}

export interface Property {
  id: number
  source: string
  source_id: string
  source_url: string | null
  title: string | null
  description: string | null
  property_type: string | null
  address: string | null
  region: string | null
  city: string | null
  latitude: number | null
  longitude: number | null
  total_area: number | null
  living_area: number | null
  rooms: number | null
  floor: number | null
  total_floors: number | null
  start_price: number | null
  current_price: number | null
  market_price: number | null
  price_per_sqm: number | null
  discount_pct: number | null
  auction_status: string | null
  auction_date_start: string | null
  auction_date_end: string | null
  publish_date: string | null
  lot_number: string | null
  organizer: string | null
  bid_step: number | null
  deposit: number | null
  is_geocoded: boolean
  is_market_appraised: boolean
  created_at: string | null
  updated_at: string | null
}

export interface PaginatedResponse {
  total: number
  page: number
  page_size: number
  pages: number
  items: Property[]
}

export interface Stats {
  total: number
  by_source: Record<string, number>
  by_status: Record<string, number>
  avg_discount: number | null
  top_cities: { city: string; count: number; avg_discount: number | null }[]
}

export interface Filters {
  city?: string
  property_type?: string
  status?: string
  source?: string
  price_min?: number
  price_max?: number
  area_min?: number
  area_max?: number
  discount_min?: number
  days?: number
  sort_by?: string
  sort_order?: string
  page?: number
  page_size?: number
}

export const TYPE_LABELS: Record<string, string> = {
  apartment: 'Квартира',
  house: 'Дом',
  land: 'Участок',
  commercial: 'Коммерческая',
  room: 'Комната',
  garage: 'Гараж',
  other: 'Другое',
}

export const STATUS_LABELS: Record<string, [string, string]> = {
  active: ['Идут торги', 'bg-green-100 text-green-700'],
  upcoming: ['Скоро', 'bg-yellow-100 text-yellow-700'],
  completed: ['Завершены', 'bg-gray-100 text-gray-500'],
  cancelled: ['Отменены', 'bg-red-100 text-red-700'],
}

export const SOURCE_LABELS: Record<string, string> = {
  torgi_gov: 'torgi.gov.ru',
  fedresurs: 'Федресурс',
  etp: 'ЭТП',
  cian: 'ЦИАН',
}
