import { X, ExternalLink, MapPin } from 'lucide-react'
import type { MapPoint } from '../types'
import { TYPE_LABELS, STATUS_LABELS, SOURCE_LABELS } from '../types'

interface Props {
  point: MapPoint
  onClose: () => void
}

function formatPrice(p: number | null): string {
  if (!p) return '—'
  return new Intl.NumberFormat('ru-RU').format(Math.round(p)) + ' ₽'
}

export default function DetailPanel({ point, onClose }: Props) {
  const p = point
  const [statusText, statusClass] = STATUS_LABELS[p.status] || ['—', '']

  return (
    <div className="absolute right-0 top-0 bottom-0 w-[400px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 z-50 shadow-xl overflow-y-auto detail-scroll animate-slide-in">
      {/* Close */}
      <button onClick={onClose} className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors z-10">
        <X size={20} />
      </button>

      {/* Header */}
      <div className="p-7 pb-5 border-b border-gray-100 dark:border-gray-800">
        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-red-600 mb-2">
          {TYPE_LABELS[p.type] || p.type || 'Объект'}
        </div>
        <h2 className="font-display text-xl font-semibold leading-tight">
          {p.title || 'Без названия'}
        </h2>
      </div>

      {/* Price */}
      <div className="px-7 py-5 bg-gray-50 dark:bg-gray-800 flex items-baseline gap-4">
        <div>
          <div className="font-display text-3xl font-bold text-green-600">{formatPrice(p.price)}</div>
          <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">начальная цена</div>
        </div>
        {p.market_price && (
          <div className="text-right">
            <div className="text-lg font-semibold text-blue-600">{formatPrice(p.market_price)}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider">рынок</div>
          </div>
        )}
      </div>

      {/* Discount */}
      {p.discount_pct !== null && p.discount_pct !== undefined && (
        <div className="px-7 py-3 border-b border-gray-100 dark:border-gray-800">
          <span className={`inline-flex items-center px-3 py-1 rounded text-sm font-bold ${p.discount_pct > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {p.discount_pct > 0 ? '−' : '+'}{Math.abs(p.discount_pct).toFixed(1)}% от рынка
          </span>
        </div>
      )}

      {/* Info */}
      <div className="p-7 space-y-3 border-b border-gray-100 dark:border-gray-800">
        <h3 className="text-xs font-semibold uppercase tracking-[0.1em] text-gray-400 mb-3">Информация</h3>
        <Row label="Статус" value={<span className={`px-2 py-0.5 rounded text-xs font-semibold ${statusClass}`}>{statusText}</span>} />
        {p.area && <Row label="Площадь" value={`${p.area} м²`} />}
        {p.rooms && <Row label="Комнат" value={String(p.rooms)} />}
        <Row label="Опубликовано" value={p.publish_date || '—'} />
        <Row label="Источник" value={<span className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-700">{SOURCE_LABELS[p.source] || p.source}</span>} />
      </div>

      {/* Actions */}
      <div className="p-7 flex gap-3">
        {p.url && (
          <a href={p.url} target="_blank" rel="noopener" className="flex-1 flex items-center justify-center gap-2 py-3 bg-gray-900 dark:bg-white text-white dark:text-gray-900 font-semibold text-sm uppercase tracking-wider hover:bg-red-600 dark:hover:bg-red-600 dark:hover:text-white transition-colors">
            <ExternalLink size={14} />
            Открыть
          </a>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-baseline">
      <span className="text-sm text-gray-500">{label}</span>
      <span className="text-sm font-semibold text-right max-w-[55%]">{value}</span>
    </div>
  )
}
