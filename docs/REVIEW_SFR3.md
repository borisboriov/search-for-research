# Независимое код-ревью после SFR-3 (05.09.2026)

_Проведено внешним агентом планирования по снимку исходников (без запуска). Известные и осознанные ограничения из SFR3_REPORT.md (нет email/должностей в данных, serendipity не выставляется API, бейдж = косинус) не повторяются. Исправления — в спеке SFR-4, §0._

**Проверено и НЕ подтвердилось:** XSS (raw HTML нигде нет, всё через JSX); прокси `/api/match` глухой — один метод, один путь, тело пересобирается; `SFR_API_URL` server-only; open redirect в «К результатам» невозможен; `?score=` вне (0,1] не рендерится; гонка на `/results` закрыта; пагинация `/api/supervisors` корректна; старт API без индекса — fail-fast; e2e независимы по порядку.

## Находки

| Sev | Где | Что не так | Последствие | Исправление |
|---|---|---|---|---|
| **High** | `apps/web/lib/api.ts` `get()` + `app/supervisor/[id]/page.tsx` | `get()` возвращает `null` и на 404, и на 5xx/сети; страница делает `notFound()`. Под ISR 404 кэшируется на час, а фоновая ревалидация при упавшем API заменяет живую страницу на 404 | Сбой API → весь sitemap отдаёт 404 Googlebot'у до часа | `404 → null`, сеть/5xx → `throw` (500 через error boundary, не кэшируется); лендинг/sitemap ловят ошибку локально |
| **High** | `app/sitemap.ts`, `app/page.tsx`, `lib/api.ts listAllSupervisors` | Сборка «без API» даёт ISR-снапшот: sitemap с 1 URL и лендинг без счётчика — час после каждого деплоя; при ошибке на N-й странице пагинации возвращается частичный список и тоже кэшируется | После деплоя час неполный sitemap | Кэшировать только успешные ответы; при ошибке пагинации — `throw`; пост-деплойная ревалидация `/` и `/sitemap.xml`; проверка `grep -c supervisor sitemap.xml == profiles_count` |
| Medium | `app/api/match/route.ts`; API `schemas.py`, `service.py` | Нет лимита тела и таймаута: прокси читает тело любого размера, `fetch` без `AbortSignal`; в API `query` без `max_length` на уровне pydantic | Десяток запросов с телом 50 МБ → OOM на VPS; зависший API — висящие запросы | Прокси: content-length ≤ 4 КБ, `AbortSignal.timeout(15000)`; API `Field(max_length=2000)`; nginx `client_max_body_size 16k` |
| Medium | API `main.py` `match` (sync) | Sync-эндпоинт → threadpool 40 потоков → 40 параллельных `encode` на CPU при ~2 rps модели | 20 одновременных запросов → ×10 медленнее, память ×N | `Semaphore(2)`/`CapacityLimiter` вокруг `search`, `uvicorn --limit-concurrency 8`, 503 при переполнении |
| Medium | `app/supervisor/[id]/page.tsx` | `id` не валидируется по формату — любая строка идёт в API и создаёт ISR-запись | Перебор мусорных id → нагрузка на API + рост `.next/cache` | `/^A\d{4,12}$/` до fetch, иначе `notFound()` |
| Medium | `app/results/page.tsx` | Любой `!response.ok` (включая 422 «слишком короткий запрос» при ручном `?q=ab`) показывается как «Сервис недоступен» | Ложная ошибка, бесконечный «Повторить» | `validateQuery` до fetch; 422 рендерить текстом `detail` |
| Medium | `layout.tsx`, `robots.ts`, `sitemap.ts` | Fallback `http://localhost:3000` для `NEXT_PUBLIC_SITE_URL`, инлайнится на билде | Забыли переменную при сборке → canonical/OG/sitemap на localhost | В `next.config.ts` падать при `NODE_ENV=production && !NEXT_PUBLIC_SITE_URL` |
| Medium | `apps/api/Dockerfile` | Процесс от root; нет `.dockerignore` (риск `.env`/`data/` в контексте); `uv:0.11` плавающий тег | Компрометация API = root в контейнере | `USER app`; `.dockerignore` (`.env*`, `data/`, `**/tests`); пин `uv:0.11.x` |
| Medium | `.github/workflows/ci.yml` | `uv sync` без `--locked` | CI зелёный при расхождении lock ↔ pyproject, Docker (`--frozen`) падает | `uv sync --locked --all-packages` |
| Low | `next.config.ts` | Нет security-заголовков, `poweredByHeader` включён | Clickjacking | `headers()` или nginx; `poweredByHeader: false` |
| Low | `app/dev/states/page.tsx` | Витрина состояний в прод-бандле | Публичная страница с фейковыми данными | `notFound()` при `NODE_ENV=production` |
| Low | `results/page.tsx` счётчик вузов | `null` institution считается вузом; полное имя vs короткое в фильтре | «· 2 вуза» при одном | `institutionShort` + `filter(Boolean)` |
| Low | `works-list.tsx` | `key = title-year` — дубли у расщеплённых профилей | React-warning, ремаунт `<details>` | ключ с индексом или `openalex_id` |
| Low | `contact-card.tsx` | `clipboard.writeText` без `.catch` — на http молча не работает | Кнопка «Скопировать» мертва без TLS | `.catch` + фолбэк; деплой только https |
| Low | API `main.py` 422-хендлер | Текст про JSON и на GET `/supervisors?limit=abc` | Вводящее сообщение | ветвить по методу |
| Low | `page.tsx` копирайт | «Топ-5» при `k: 10` | Расхождение | согласовать |

## Что сделано хорошо
Прокси минимален и глухой; деградация вместо выдуманных чисел проведена последовательно и покрыта тестами; одно кодирование на запрос, прогрев в lifespan, fail-fast без индекса, keyset-пагинация; островок для `?score=` сохраняет ISR; lock-файлы, Node 24, CPU-колёса torch (образ 10 → 2,4 ГБ), `HEALTHCHECK` с адекватным start-period.
