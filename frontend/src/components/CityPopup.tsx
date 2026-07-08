import { useState, useEffect } from 'react'
import { MapPin, X } from 'lucide-react'

interface Props {
  onSelect: (city: string) => void
}

const CITIES = [
  { name: 'Москва', lat: 55.7558, lon: 37.6173, emoji: '🏛️' },
  { name: 'Санкт-Петербург', lat: 59.9343, lon: 30.3351, emoji: '🏰' },
]

export default function CityPopup({ onSelect }: Props) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const dismissed = sessionStorage.getItem('city-popup-dismissed')
    if (!dismissed) {
      setVisible(true)
    }
  }, [])

  const handleSelect = (city: string) => {
    onSelect(city)
    sessionStorage.setItem('city-popup-dismissed', '1')
    setVisible(false)
  }

  const handleDismiss = () => {
    sessionStorage.setItem('city-popup-dismissed', '1')
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl max-w-md w-full mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-gray-900 to-gray-700 px-6 py-5 text-white relative">
          <button onClick={handleDismiss} className="absolute top-4 right-4 text-white/60 hover:text-white transition-colors">
            <X size={18} />
          </button>
          <div className="flex items-center gap-3">
            <MapPin size={24} className="text-red-400" />
            <div>
              <h2 className="font-display text-lg font-bold">Выберите город</h2>
              <p className="text-sm text-white/70 mt-0.5">Покажем торги по недвижимости</p>
            </div>
          </div>
        </div>

        {/* Cities */}
        <div className="p-6 space-y-3">
          {CITIES.map(city => (
            <button
              key={city.name}
              onClick={() => handleSelect(city.name)}
              className="w-full flex items-center gap-4 p-4 rounded-lg border-2 border-gray-200 dark:border-gray-700 hover:border-red-500 dark:hover:border-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all group"
            >
              <span className="text-3xl">{city.emoji}</span>
              <div className="text-left">
                <div className="font-semibold text-gray-900 dark:text-white group-hover:text-red-600 transition-colors">
                  {city.name}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  Показать торги в регионе
                </div>
              </div>
              <svg className="w-5 h-5 text-gray-300 group-hover:text-red-500 ml-auto transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          ))}

          <button
            onClick={handleDismiss}
            className="w-full text-center text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 py-2 transition-colors"
          >
            Показать все города
          </button>
        </div>
      </div>
    </div>
  )
}
