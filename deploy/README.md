# Деплой Search For Research (SFR-4)

Компоновка: `api` (FastAPI + FRIDA) + `web` (Next.js standalone) + `proxy`
(Caddy с rate limiting и авто-TLS). Наружу опубликован только proxy;
API из интернета недостижим — браузер ходит `proxy → web → api` по
внутренней сети compose.

Требования к серверу измерены в SFR-2: **8 ГБ RAM, ≥2 vCPU, ≥20 ГБ диска**,
Ubuntu 24.04, хостинг в РФ. DNS A-запись домена должна указывать на сервер
**до** первого запуска (Caddy выпускает TLS при старте).

## Развёртывание с нуля

Все команды — от ssh-пользователя с sudo (не root).

```bash
# 1. Docker (официальный репозиторий) + право пользователя
sudo apt-get update && sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker

# 2. Код
git clone https://github.com/<owner>/search-for-research.git
cd search-for-research

# 3. Окружение
cd deploy && cp env.example .env
# заполнить .env: SITE_ADDRESS, NEXT_PUBLIC_SITE_URL,
# REVALIDATE_SECRET=$(openssl rand -hex 32), SFR_API_LOG_SALT=$(openssl rand -hex 16),
# NEXT_PUBLIC_CLAIM_EMAIL (или оставить пустым — ссылка «Это вы?» скрыта)
cd ..

# 4. Артефакты — с машины разработчика (на сервере ничего не собирается):
#    (локально) deploy/sync-artifacts.sh user@host search-for-research

# 5. Проверить DNS и запустить
dig +short $SITE_ADDRESS   # должен вернуть IP этого сервера
cd deploy && docker compose up -d --build
# первый старт api качает веса FRIDA (~2 ГБ) в том hf-cache — единожды;
# healthcheck api ждёт до 3 минут (start-period)

# 6. Пост-деплойная ревалидация: сборка web шла без живого API, поэтому
#    снапшоты лендинга и sitemap деградированы — обновить их:
source .env
curl -X POST -H "x-revalidate-secret: $REVALIDATE_SECRET" https://$SITE_ADDRESS/api/revalidate

# 7. Проверки
docker exec sfr-proxy id                              # uid=10001(caddy), не root (SFR-4b)
curl -s https://$SITE_ADDRESS/api/health || true      # 404 — так и должно быть (API закрыт)
curl -s -o /dev/null -w '%{http_code}\n' https://$SITE_ADDRESS/            # 200, лендинг
n=$(curl -s https://$SITE_ADDRESS/sitemap.xml | grep -c '/supervisor/')
echo "sitemap: $n профилей"   # должно равняться profiles_count (535)
curl -s https://$SITE_ADDRESS/robots.txt | grep sitemap
```

## Обновление

```bash
cd search-for-research
git pull
# если менялись артефакты — с машины разработчика: deploy/sync-artifacts.sh user@host
cd deploy
docker compose up -d --build        # пересборка только изменившихся образов
# --build здесь не только про наш код: пересборка подтягивает патчи базовых
# образов и `apk upgrade` в прокси. Это единственный способ закрывать CVE
# базы — CI их не видит (docs/SFR4b_REPORT.md).
source .env
curl -X POST -H "x-revalidate-secret: $REVALIDATE_SECRET" https://$SITE_ADDRESS/api/revalidate
curl -s https://$SITE_ADDRESS/sitemap.xml | grep -c '/supervisor/'   # == profiles_count
```

Выбранная схема сборки web: **сборка без живого API + обязательная
пост-деплойная ревалидация** (`/` и `/sitemap.xml`). Альтернатива — строить
образ при поднятом api — отвергнута: docker build не видит сеть compose,
а городить временный туннель ради двух страниц не стоит (docs/DECISIONS.md).

## Локальная репетиция

```bash
make deploy-local     # из корня репо: прокси на http://localhost:8080, без TLS
SFR_WEB_URL=http://localhost:8080 make web-e2e   # e2e против боевой компоновки
make deploy-local-down
```

Проверка, что API закрыт: `curl -s localhost:8000` изнутри машины должен
получить отказ соединения (порт не опубликован).

## Наблюдаемость

- **Логи /match** (материал калибровки порога): JSON-строки в stdout api —
  `docker logs sfr-api | grep '"query"'`; ротация настроена в compose
  (json-file, 20 МБ × 5).
- **Access-лог proxy** (воронка «выдача → профиль»): `/data/access.log`
  внутри тома caddy-data, JSON с uri и Referer.
- **Health**: `docker compose exec api curl -s localhost:8000/api/health` —
  модель, версия индекса, пороги, hit-rate кэша.
- **Uptime**: crontab на сервере —
  `*/5 * * * * ~/search-for-research/deploy/uptime-check.sh https://search-for-research.ru >> ~/uptime.log 2>&1`.
  Внешний uptime-сервис — на Борисе.

## Rate limiting

Правила в `proxy/Caddyfile`: POST `/api/match` — burst 10 за 10 с + 30/мин
с IP (для всех, включая ботов; не 10/мин — за одним NAT-IP может сидеть
целая лаборатория); страницы и GET — 120/мин с IP, статические ассеты
`/_next/*` не считаются (одна загрузка страницы тянет их десятками);
поисковые боты (Googlebot/YandexBot/… по User-Agent) страницы читают без
лимитов. Превышение — HTTP 429. UA спуфится — для пилота это осознанный
компромисс.

## Прокси работает не от root (SFR-4b)

С SFR-4b контейнер `proxy` запускается от `caddy` (uid 10001), а не от root:
это единственный контейнер, смотрящий в интернет. Два следствия.

1. **Порты 80/443.** Бинарю Caddy проставлена файловая capability
   `cap_net_bind_service` (`setcap` в Dockerfile) — без неё непривилегированный
   процесс не займёт порт ниже 1024. Локальная репетиция слушает 8080 и эту
   ветку **не проверяет**: после первого боевого запуска убедиться, что прокси
   поднялся (`docker compose ps proxy` — healthy) и сайт открывается по https.
   Если нет — `docker logs sfr-proxy` покажет `permission denied` на bind;
   временный обход до разбора: убрать строку `USER caddy` из
   `deploy/proxy/Dockerfile` и пересобрать.

2. **Тома `caddy-data` и `caddy-config`.** Владельца docker снимает с каталога
   образа в момент **создания** тома. Тома, созданные до SFR-4b, остались
   root'овыми, и Caddy в них не запишет ни сертификат, ни access-лог. На
   работающем стенде их надо пересоздать:

   ```bash
   docker compose down
   docker volume rm sfr-deploy_caddy-data sfr-deploy_caddy-config
   docker compose up -d --build     # TLS-сертификат будет выпущен заново
   ```

   На чистом сервере ничего делать не нужно.
