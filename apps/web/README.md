# apps/web — фронтенд Search for Research (SFR-3)

Next.js (App Router) + TypeScript + Tailwind v4 + компоненты в стиле shadcn/ui.
Три страницы поверх API `apps/api`: лендинг `/`, выдача `/results?q=…`,
открытая страница НР `/supervisor/[id]` (SSR + ISR, sitemap по каталогу).

Дизайн — источник истины: `design/DESIGN_HANDOFF.md`, `design/DESIGN_SYSTEM.md`
(токены §1 лежат в `app/globals.css`), макеты `design/mockups/*`.

## Команды (из корня репозитория)

```bash
make web-setup   # npm ci
make web-dev     # дев-сервер на :3000 (нужен запущенный API: make api)
make web-lint    # eslint
make web-typecheck
make web-test    # юнит-тесты (Vitest)
make web-build   # прод-сборка; живой API не требуется
make web-e2e     # Playwright против живого API; скриншоты в e2e/screenshots/
```

Конфиг: `SFR_API_URL` — адрес API для SSR и прокси (по умолчанию
`http://127.0.0.1:8000`); `NEXT_PUBLIC_SITE_URL` — канонический адрес сайта
(sitemap, OG); `NEXT_PUBLIC_CLAIM_EMAIL` — адрес для «Это вы?» (пока пуст).
Клиентские запросы ходят через route handler `/api/match` — CORS и внутренний
адрес API наружу не выносятся.

Витрина состояний компонентов (skeleton, serendipity, empty, error) — `/dev/states`.
