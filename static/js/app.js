/**
 * Estate Auction Map Application
 * Frontend for displaying auction properties on Yandex Maps
 */

class EstateAuctionApp {
    constructor() {
        this.map = null;
        this.clusterer = null;
        this.properties = [];
        this.currentFilters = {};
        this.detailOpen = false;

        this.init();
    }

    async init() {
        await this.initMap();
        this.bindEvents();
        await this.loadData();
        await this.loadStats();
    }

    // === Map Initialization ===
    async initMap() {
        return new Promise((resolve) => {
            ymaps.ready(() => {
                this.map = new ymaps.Map('map', {
                    center: [55.7558, 37.6173], // Moscow
                    zoom: 10,
                    controls: ['zoomControl', 'searchControl', 'typeControl', 'fullscreenControl'],
                    type: 'vector#dark',
                });

                // Custom clusterer
                this.clusterer = new ymaps.Clusterer({
                    preset: 'islands#invertedVioletClusterIcons',
                    groupByCoordinates: false,
                    clusterDisableClickZoom: false,
                    clusterHideIconOnBalloonOpen: false,
                    geoObjectHideIconOnBalloonOpen: false,
                    gridSize: 80,
                    clusterBalloonContentLayout: 'cluster#balloonTwoColumns',
                });

                this.map.geoObjects.add(this.clusterer);
                resolve();
            });
        });
    }

    // === Data Loading ===
    async loadData() {
        try {
            const params = new URLSearchParams();

            if (this.currentFilters.city) params.set('city', this.currentFilters.city);
            if (this.currentFilters.type) params.set('property_type', this.currentFilters.type);
            if (this.currentFilters.status) params.set('status', this.currentFilters.status);
            if (this.currentFilters.source) params.set('source', this.currentFilters.source);
            if (this.currentFilters.days) params.set('days', this.currentFilters.days);

            const resp = await fetch(`/api/map-data?${params}`);
            this.properties = await resp.json();

            this.renderMarkers();
            this.updateStatsCount();
        } catch (err) {
            console.error('Failed to load data:', err);
        }
    }

    async loadStats() {
        try {
            const resp = await fetch('/api/stats');
            const stats = await resp.json();
            this.renderStats(stats);
        } catch (err) {
            console.error('Failed to load stats:', err);
        }
    }

    // === Map Rendering ===
    getColorByDate(publishDate) {
        if (!publishDate) return '#9b59b6'; // purple for unknown

        const now = new Date();
        const pub = new Date(publishDate);
        const diffDays = Math.floor((now - pub) / (1000 * 60 * 60 * 24));

        if (diffDays <= 0) return '#e74c3c';  // red — today
        if (diffDays <= 3) return '#e67e22';  // orange — 1-3 days
        if (diffDays <= 7) return '#f1c40f';  // yellow — 4-7 days
        if (diffDays <= 28) return '#2ecc71'; // green — 2-4 weeks
        if (diffDays <= 90) return '#3498db'; // blue — 1-3 months
        return '#9b59b6';                     // purple — 3+ months
    }

    getMarkerIcon(property) {
        const color = this.getColorByDate(property.publish_date);
        const size = property.discount_pct && property.discount_pct > 20 ? 40 : 32;

        return {
            iconLayout: 'default#image',
            iconImageHref: this.createMarkerSvg(color, size),
            iconImageSize: [size, size],
            iconImageOffset: [-size/2, -size],
        };
    }

    createMarkerSvg(color, size) {
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size*1.4}" viewBox="0 0 24 34">
            <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 22 12 22s12-13 12-22C24 5.4 18.6 0 12 0z" fill="${color}"/>
            <circle cx="12" cy="12" r="6" fill="white" opacity="0.9"/>
            <text x="12" y="15" text-anchor="middle" font-size="9" font-weight="bold" fill="${color}">🏠</text>
        </svg>`;
        return 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg);
    }

    formatPrice(price) {
        if (!price) return '—';
        if (price >= 1000000) {
            return (price / 1000000).toFixed(1) + ' млн ₽';
        }
        return (price / 1000).toFixed(0) + ' тыс. ₽';
    }

    formatFullPrice(price) {
        if (!price) return '—';
        return new Intl.NumberFormat('ru-RU').format(Math.round(price)) + ' ₽';
    }

    createBalloonContent(prop) {
        const price = this.formatFullPrice(prop.price);
        const marketPrice = this.formatFullPrice(prop.market_price);
        const color = this.getColorByDate(prop.publish_date);

        let discountHtml = '';
        if (prop.discount_pct !== null && prop.discount_pct !== undefined) {
            const cls = prop.discount_pct > 0 ? 'positive' : 'negative';
            const sign = prop.discount_pct > 0 ? '−' : '+';
            discountHtml = `<span class="balloon-discount ${cls}">${sign}${Math.abs(prop.discount_pct).toFixed(1)}% от рынка</span>`;
        }

        const statusLabels = {
            active: '🔴 Идут торги',
            upcoming: '🟡 Скоро',
            completed: '⚪ Завершены',
            cancelled: '⚫ Отменены',
        };

        const typeLabels = {
            apartment: '🏢 Квартира',
            house: '🏡 Дом',
            land: '🌍 Участок',
            commercial: '🏪 Коммерческая',
            room: '🚪 Комната',
            garage: '🚗 Гараж',
            other: '📦 Другое',
        };

        return `
            <div class="balloon-content">
                <div class="balloon-title">${prop.title || 'Без названия'}</div>
                <div class="balloon-price">${price}</div>
                ${prop.market_price ? `<div class="balloon-row"><span>Рынок:</span><span>${marketPrice}</span></div>` : ''}
                ${discountHtml}
                <div class="balloon-row"><span>Тип:</span><span>${typeLabels[prop.type] || prop.type || '—'}</span></div>
                ${prop.area ? `<div class="balloon-row"><span>Площадь:</span><span>${prop.area} м²</span></div>` : ''}
                ${prop.rooms ? `<div class="balloon-row"><span>Комнат:</span><span>${prop.rooms}</span></div>` : ''}
                <div class="balloon-row"><span>Статус:</span><span>${statusLabels[prop.status] || prop.status || '—'}</span></div>
                <div class="balloon-row"><span>Опубликовано:</span><span>${prop.publish_date || '—'}</span></div>
                ${prop.url ? `<a class="balloon-link" href="${prop.url}" target="_blank">Открыть на ${prop.source === 'torgi_gov' ? 'torgi.gov.ru' : 'ЦИАН'} →</a>` : ''}
            </div>
        `;
    }

    renderMarkers() {
        this.clusterer.removeAll();

        const placemarks = this.properties.map(prop => {
            const pm = new ymaps.Placemark(
                [prop.lat, prop.lon],
                {
                    balloonContent: this.createBalloonContent(prop),
                    clusterCaption: prop.title || 'Объект',
                },
                {
                    ...this.getMarkerIcon(prop),
                    hideIconOnBalloonOpen: false,
                }
            );

            pm.events.add('click', () => this.showDetail(prop));
            return pm;
        });

        this.clusterer.add(placemarks);

        // Fit bounds
        if (placemarks.length > 0) {
            this.map.setBounds(this.clusterer.getBounds(), {
                checkZoomRange: true,
                zoomMargin: 30,
            });
        }
    }

    // === Detail Panel ===
    showDetail(prop) {
        const panel = document.getElementById('detailPanel');
        const title = document.getElementById('detailTitle');
        const content = document.getElementById('detailContent');

        title.textContent = prop.title || prop.address || 'Объект';

        const statusLabels = {
            active: ['Идут торги', 'badge-active'],
            upcoming: ['Скоро начнутся', 'badge-upcoming'],
            completed: ['Завершены', 'badge-completed'],
            cancelled: ['Отменены', 'badge-cancelled'],
        };

        const [statusText, statusClass] = statusLabels[prop.status] || ['—', ''];

        let discountSection = '';
        if (prop.market_price) {
            const discountClass = prop.discount_pct > 0 ? 'discount-positive' : 'discount-negative';
            const discountSign = prop.discount_pct > 0 ? '−' : '+';
            discountSection = `
                <div class="detail-section">
                    <h3>Рыночная оценка</h3>
                    <div class="detail-row">
                        <span class="detail-label">Рыночная цена</span>
                        <span class="detail-value price-market">${this.formatFullPrice(prop.market_price)}</span>
                    </div>
                    ${prop.area ? `<div class="detail-row">
                        <span class="detail-label">Цена/м² (рынок)</span>
                        <span class="detail-value">${this.formatFullPrice(prop.market_price / prop.area)}/м²</span>
                    </div>` : ''}
                    <div class="detail-row">
                        <span class="detail-label">Скидка</span>
                        <span class="detail-value ${discountClass}">${discountSign}${Math.abs(prop.discount_pct).toFixed(1)}%</span>
                    </div>
                </div>
            `;
        }

        content.innerHTML = `
            <div class="detail-content">
                <div class="detail-section">
                    <h3>Торги</h3>
                    <div class="detail-row">
                        <span class="detail-label">Статус</span>
                        <span class="detail-value"><span class="badge ${statusClass}">${statusText}</span></span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Начальная цена</span>
                        <span class="detail-value price-auction">${this.formatFullPrice(prop.price)}</span>
                    </div>
                    ${prop.area ? `<div class="detail-row">
                        <span class="detail-label">Цена/м²</span>
                        <span class="detail-value">${this.formatFullPrice(prop.price / prop.area)}/м²</span>
                    </div>` : ''}
                    <div class="detail-row">
                        <span class="detail-label">Опубликовано</span>
                        <span class="detail-value">${prop.publish_date || '—'}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Источник</span>
                        <span class="detail-value"><span class="badge-source">${prop.source === 'torgi_gov' ? 'torgi.gov.ru' : 'ГосПлан'}</span></span>
                    </div>
                </div>

                <div class="detail-section">
                    <h3>Объект</h3>
                    <div class="detail-row">
                        <span class="detail-label">Адрес</span>
                        <span class="detail-value">${prop.title || '—'}</span>
                    </div>
                    ${prop.area ? `<div class="detail-row">
                        <span class="detail-label">Площадь</span>
                        <span class="detail-value">${prop.area} м²</span>
                    </div>` : ''}
                    ${prop.rooms ? `<div class="detail-row">
                        <span class="detail-label">Комнат</span>
                        <span class="detail-value">${prop.rooms}</span>
                    </div>` : ''}
                </div>

                ${discountSection}

                <div class="detail-actions">
                    ${prop.url ? `<a href="${prop.url}" target="_blank" class="btn btn-primary">Открыть торги →</a>` : ''}
                    <button class="btn btn-secondary" onclick="app.zoomTo(${prop.lat}, ${prop.lon})">На карте</button>
                </div>
            </div>
        `;

        panel.classList.add('open');
        this.detailOpen = true;
    }

    hideDetail() {
        document.getElementById('detailPanel').classList.remove('open');
        this.detailOpen = false;
    }

    zoomTo(lat, lon) {
        this.map.setCenter([lat, lon], 16, { duration: 300 });
    }

    // === Stats ===
    renderStats(stats) {
        const el = document.getElementById('statsContent');
        el.innerHTML = `
            <div class="stat-row">
                <span class="stat-label">Всего объектов</span>
                <span class="stat-value">${stats.total.toLocaleString('ru-RU')}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">torgi.gov.ru</span>
                <span class="stat-value">${(stats.by_source.torgi_gov || 0).toLocaleString('ru-RU')}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">ГосПлан</span>
                <span class="stat-value">${(stats.by_source.gosplan || 0).toLocaleString('ru-RU')}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Средняя скидка</span>
                <span class="stat-value">${stats.avg_discount ? stats.avg_discount.toFixed(1) + '%' : '—'}</span>
            </div>
            ${stats.top_cities.length > 0 ? `
                <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);">
                    <div class="stat-label" style="margin-bottom: 6px;">Топ городов:</div>
                    ${stats.top_cities.slice(0, 5).map(c => `
                        <div class="stat-row">
                            <span class="stat-label">${c.city}</span>
                            <span class="stat-value">${c.count} ${c.avg_discount ? `(${c.avg_discount.toFixed(0)}%)` : ''}</span>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        `;
    }

    updateStatsCount() {
        // Quick update from loaded data
    }

    // === Event Binding ===
    bindEvents() {
        // Toggle sidebar
        document.getElementById('toggleSidebar').addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('collapsed');
        });

        // Apply filters
        document.getElementById('applyFilters').addEventListener('click', () => {
            this.currentFilters = {
                city: document.getElementById('filterCity').value,
                type: document.getElementById('filterType').value,
                status: document.getElementById('filterStatus').value,
                source: document.getElementById('filterSource').value,
                days: document.getElementById('filterDays').value,
            };
            this.loadData();
        });

        // Reset filters
        document.getElementById('resetFilters').addEventListener('click', () => {
            document.getElementById('filterCity').value = '';
            document.getElementById('filterType').value = '';
            document.getElementById('filterStatus').value = '';
            document.getElementById('filterSource').value = '';
            document.getElementById('filterDays').value = '30';
            document.getElementById('priceMin').value = '';
            document.getElementById('priceMax').value = '';
            this.currentFilters = {};
            this.loadData();
        });

        // Close detail
        document.getElementById('closeDetail').addEventListener('click', () => {
            this.hideDetail();
        });

        // Trigger scrape
        document.getElementById('triggerScrape').addEventListener('click', async () => {
            const status = document.getElementById('scrapeStatus');
            status.textContent = '⏳ Запуск сбора данных...';
            try {
                const resp = await fetch('/api/scrape/trigger', { method: 'POST' });
                const data = await resp.json();
                status.textContent = '✅ Сбор данных запущен в фоне';
                // Poll for completion
                setTimeout(() => {
                    this.loadData();
                    this.loadStats();
                    status.textContent = '';
                }, 30000);
            } catch (err) {
                status.textContent = '❌ Ошибка запуска';
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.detailOpen) {
                this.hideDetail();
            }
        });
    }
}

// Initialize app
const app = new EstateAuctionApp();
