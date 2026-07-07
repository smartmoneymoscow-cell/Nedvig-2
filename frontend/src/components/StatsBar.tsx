import type { Stats } from '../types'

interface Props {
  stats?: Stats
}

export default function StatsBar({ stats }: Props) {
  if (!stats) return null

  return (
    <div className="bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 md:px-6 py-2 flex items-center gap-4 md:gap-8 overflow-x-auto shrink-0">
      <StatItem value={stats.total.toLocaleString('ru-RU')} label="объектов" />
      <Divider />
      <StatItem value={stats.by_status.active?.toLocaleString('ru-RU') || '0'} label="активных" />
      <Divider />
      <StatItem value={stats.avg_discount ? `${stats.avg_discount.toFixed(1)}%` : '—'} label="ср. скидка" />
      <Divider className="hidden md:block" />
      <StatItem className="hidden md:flex" value={stats.by_source.torgi_gov?.toLocaleString('ru-RU') || '0'} label="torgi.gov.ru" />
      <Divider className="hidden md:block" />
      <StatItem className="hidden md:flex" value={stats.by_source.fedresurs?.toLocaleString('ru-RU') || '0'} label="Федресурс" />
    </div>
  )
}

function StatItem({ value, label, className = '' }: { value: string; label: string; className?: string }) {
  return (
    <div className={`flex items-baseline gap-2 whitespace-nowrap ${className}`}>
      <span className="font-display text-xl md:text-2xl font-bold text-gray-900 dark:text-white">{value}</span>
      <span className="text-[10px] md:text-xs text-gray-500 uppercase tracking-widest">{label}</span>
    </div>
  )
}

function Divider({ className = '' }: { className?: string }) {
  return <div className={`w-px h-8 bg-gray-200 dark:bg-gray-700 ${className}`} />
}
