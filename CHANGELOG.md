# Changelog

## [2.1.0] — 2026-07-07

### Fixed
- **Deploy:** Removed duplicate root-level files (Dockerfile, main.py, models.py, database.py, requirements.txt, alembic.ini)
- **Deploy:** Fixed scraper-worker Dockerfile — proper Tor management via entrypoint script
- **Deploy:** Fixed API Dockerfile — safe Alembic migrations via prestart.sh
- **Deploy:** Added HEALTHCHECK to both Dockerfiles
- **Deploy:** docker-compose now requires DB_PASSWORD, JWT_SECRET, ADMIN_API_KEY (no defaults)
- **Security:** Removed default JWT_SECRET — production startup warns if empty
- **Security:** Admin API key now required in production mode (DEBUG=false)
- **Security:** Removed API key from query params (header-only)
- **Scrapers:** Proxy Manager — removed hardcoded proxy, added multi-URL health check
- **Scrapers:** Proxy Manager — added direct connection fallback when no proxies available
- **Scrapers:** Tor config — added BY/KZ exit nodes, removed StrictNodes
- **Scrapers:** Post-scrape data validation (reject price≤0, area≤0, 0,0 coords)
- **Scrapers:** Pipeline retry with exponential backoff (3 attempts)
- **Frontend:** Added missing leaflet.markercluster dependency
- **Frontend:** Better error handling in API client (ApiError class)
- **Frontend:** Error state UI when API is unreachable
- **Frontend:** Mobile responsive sidebar (drawer pattern)
- **Frontend:** Mobile responsive header, stats bar, detail panel
- **Frontend:** Object counter on map

### Added
- GitHub Actions CI/CD (test.yml, deploy-frontend.yml)
- pyproject.toml with ruff/black configuration
- CHANGELOG.md

### Removed
- Root-level duplicate files (Dockerfile, main.py, models.py, database.py, requirements.txt, alembic.ini)
- Root-level duplicate directories (config/, scrapers/, services/, static/, templates/, alembic/)
- ANALYSIS_REPORT.md, SCRAPER_AUDIT.md, WORK_PLAN.md (stale)
- preview.html (static demo — not actual frontend)

## [2.0.0] — Initial

- FastAPI backend with PostgreSQL
- React + Leaflet + TailwindCSS frontend
- Scrapers: torgi.gov.ru, Fedresurs, CIAN, ETP
- Deploy: Render (backend) + GitHub Pages (frontend)
