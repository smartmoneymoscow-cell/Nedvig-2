import { useState } from 'react'
import { Filter, X } from 'lucide-react'
import type { Filters, Stats } from '../types'

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
  stats?: Stats
}

export default function Sidebar({ filters, onChange, stats }: Props) {
  const [local, setLocal] = useState<Filters>(filters)
  const [mobileOpen, setMobileOpen] = useState(false)

  const apply = () => {
    onChange({ ...local })
    setMobileOpen(false)
  }
  const reset = () => {
    const cleared: Filters = { days: 90 }
    setLocal(cleared)
    onChange(cleared)
  }

  const set = (k: keyof Filters, v: string | number | undefined) => setLocal(prev => ({ ...prev, [k]: v }))

  const sidebarContent = (
    <>
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3 pb-2 border-b-2 border-gray-900 dark:border-white">Фильтры</h3>

        <Field label="Город">
          <input type="text" value={local.city || ''} onChange={e => set('city', e.target.value)} placeholder="Москва, СПб..." className="input" />
        </Field>

        <Field label="Тип объекта">
          <select value={local.property_type || ''} onChange={e => set('property_type', e.target.value || undefined)} className="input">
            <option value="">Все типы</option>
            <option value="apartment">Квартира</option>
            <option value="house">Дом</option>
            <option value="land">Участок</option>
            <option value="commercial">Коммерческая</option>
            <option value="room">Комната</option>
            <option value="garage">Гараж</option>
          </select>
        </Field>

        <Field label="Статус">
          <select value={local.status || ''} onChange={e => set('status', e.target.value || undefined)} className="input">
            <option value="">Все статусы</option>
            <option value="active">Идут торги</option>
            <option value="upcoming">Скоро</option>
            <option value="completed">Завершены</option>
          </select>
        </Field>

        <Field label="Источник">
          <select value={local.source || ''} onChange={e => set('source', e.target.value || undefined)} className="input">
            <option value="">Все</option>
            <option value="torgi_gov">torgi.gov.ru</option>
            <option value="fedresurs">Федресурс</option>
            <option value="etp">ЭТП</option>
          </select>
        </Field>

        <Field label="Цена, ₽">
          <div className="flex gap-2">
            <input type="number" value={local.price_min || ''} onChange={e => set('price_min', e.target.value ? Number(e.target.value) : undefined)} placeholder="От" className="input flex-1" />
            <span className="text-gray-400 self-center">—</span>
            <input type="number" value={local.price_max || ''} onChange={e => set('price_max', e.target.value ? Number(e.target.value) : undefined)} placeholder="До" className="input flex-1" />
          </div>
        </Field>

        <Field label="Мин. скидка, %">
          <input type="number" value={local.discount_min || ''} onChange={e => set('discount_min', e.target.value ? Number(e.target.value) : undefined)} placeholder="10" className="input" />
        </Field>

        <Field label="Период">
          <select value={local.days || 90} onChange={e => set('days', Number(e.target.value))} className="input">
            <option value="7">Неделя</option>
            <option value="30">Месяц</option>
            <option value="90">Квартал</option>
            <option value="365">Год</option>
          </select>
        </Field>

        <button onClick={apply} className="w-full py-2.5 bg-gray-900 dark:bg-white text-white dark:text-gray-900 font-semibold text-sm uppercase tracking-wider hover:bg-red-600 dark:hover:bg-red-600 dark:hover:text-white transition-colors mt-2">
          Показать
        </button>
        <button onClick={reset} className="w-full py-2 bg-transparent text-gray-400 border border-gray-200 dark:border-gray-700 text-xs uppercase tracking-wider hover:border-gray-400 hover:text-gray-600 transition-colors mt-2">
          Сбросить
        </button>
      </div>

      {/* Legend */}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3 pb-2 border-b-2 border-gray-900 dark:border-white">Легенда</h3>
        <div className="flex flex-col gap-1.5">
          <LegendItem color="#dc2626" label="Сегодня" />
          <LegendItem color="#d97706" label="1–3 дня" />
          <LegendItem color="#ca8a04" label="4–7 дней" />
          <LegendItem color="#16a34a" label="2–4 недели" />
          <LegendItem color="#2563eb" label="1–3 месяца" />
          <LegendItem color="#7c3aed" label="3+ месяцев" />
        </div>
      </div>

      {/* Top cities */}
      {stats?.top_cities && stats.top_cities.length > 0 && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 mb-3 pb-2 border-b-2 border-gray-900 dark:border-white">Топ городов</h3>
          <div className="flex flex-col gap-1">
            {stats.top_cities.slice(0, 5).map(c => (
              <div key={c.city} className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">{c.city}</span>
                <span className="font-semibold">{c.count} {c.avg_discount ? `(${c.avg_discount.toFixed(0)}%)` : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )

  return (
    <>
      {/* Mobile filter toggle button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="md:hidden fixed bottom-4 right-4 z-[1001] bg-gray-900 dark:bg-white text-white dark:text-gray-900 p-3 rounded-full shadow-lg"
      >
        <Filter size={20} />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-[1002] bg-black/50" onClick={() => setMobileOpen(false)} />
      )}

      {/* Sidebar — desktop: always visible, mobile: slide-in drawer */}
      <aside className={`
        md:w-72 md:shrink-0 md:relative md:translate-x-0
        ${mobileOpen ? 'fixed inset-y-0 left-0 z-[1003] translate-x-0' : 'fixed -translate-x-full md:translate-x-0'}
        w-80 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 overflow-y-auto p-5 flex flex-col gap-6 transition-transform
      `}>
        {/* Mobile close button */}
        <button onClick={() => setMobileOpen(false)} className="md:hidden absolute top-4 right-4 p-1 text-gray-400">
          <X size={18} />
        </button>
        {sidebarContent}
      </aside>
    </>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  )
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500">
      <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
      {label}
    </div>
  )
}
