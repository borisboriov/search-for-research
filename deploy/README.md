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
# заполнить .env: SITE_ADDRESS (канонический адрес), REDIRECT_FROM /
#   REDIRECT_TO (301 www → апекс, #21; имя из REDIRECT_FROM в SITE_ADDRESS
#   не ставить — Caddy не стартует), NEXT_PUBLIC_SITE_URL (канонический адрес, один),
# REVALIDATE_SECRET=$(openssl rand -hex 32), SFR_API_LOG_SALT=$(openssl rand -hex 16),
# NEXT_PUBLIC_CLAIM_EMAIL (или оставить пустым — ссылка «Это вы?» скрыта)
cd ..

# 4. Артефакты — с машины разработчика (на сервере ничего не собирается):
#    (локально) deploy/sync-artifacts.sh user@host search-for-research

# 5. Проверить DNS и запустить
#    SITE_ADDRESS может содержать несколько имён через запятую (Caddy выпустит
#    сертификат на каждое), поэтому в командах ниже используется канонический
#    адрес из NEXT_PUBLIC_SITE_URL — одно имя, пригодное для curl и dig.
#    ВНИМАНИЕ при переносе домена или чистке зоны: на апексе лежат две
#    TXT-записи верификации — google-site-verification=… и
#    yandex-verification: … (12.09). Они не участвуют в работе сайта, но на
#    них держатся Search Console и Яндекс.Вебмастер: удалишь — кабинет
#    отвалится вместе с отчётами по индексации.
source deploy/.env && DOMAIN=${NEXT_PUBLIC_SITE_URL#https://}   # мы ещё в корне репо
for name in $(echo "$SITE_ADDRESS" | tr ',' ' ') ${REDIRECT_FROM:-}; do dig +short "$name"; done
# каждое имя должно вернуть IP этого сервера
cd deploy && docker compose up -d --build
# первый старт api качает веса FRIDA (~2 ГБ) в том hf-cache — единожды;
# healthcheck api ждёт до 3 минут (start-period)

# 6. Пост-деплойная ревалидация: сборка web шла без живого API, поэтому
#    снапшоты лендинга и sitemap деградированы — обновить их:
source .env && DOMAIN=${NEXT_PUBLIC_SITE_URL#https://}
curl -X POST -H "x-revalidate-secret: $REVALIDATE_SECRET" https://$DOMAIN/api/revalidate

# 7. Проверки
docker exec sfr-proxy id                              # uid=10001(caddy), не root (SFR-4b)
curl -s https://$DOMAIN/api/health || true      # 404 — так и должно быть (API закрыт)
curl -s -o /dev/null -w '%{http_code}\n' https://$DOMAIN/            # 200, лендинг
n=$(curl -s https://$DOMAIN/sitemap.xml | grep -c '/supervisor/')
echo "sitemap: $n профилей"   # должно равняться profiles_count (9 002)
curl -s https://$DOMAIN/robots.txt | grep sitemap
```

**Переход на 301 `www` → апекс (#21, при первом обновлении после 27.09).** В
`deploy/.env` на сервере: `SITE_ADDRESS="search-for-research.ru"` (без `www`),
`REDIRECT_FROM=www.search-for-research.ru`, `REDIRECT_TO=https://search-for-research.ru`
— все три строки вместе, иначе одно имя окажется в двух блоках Caddyfile и
прокси не стартует. Проверка после `docker compose up -d --build proxy`:
`curl -sI https://www.search-for-research.ru/supervisor/A5050048876 | head -3`
→ `301` и `location: https://search-for-research.ru/supervisor/A5050048876`.

## Обновление

```bash
cd search-for-research
git pull
# если менялись артефакты — с машины разработчика: deploy/sync-artifacts.sh user@host
cd deploy
docker compose up -d --build        # пересборка только изменившихся образов
docker compose restart api          # если привозились артефакты: api читает их на старте
# --build здесь не только про наш код: пересборка подтягивает патчи базовых
# образов и `apk upgrade` в прокси. Это единственный способ закрывать CVE
# базы — CI их не видит (docs/reports/SFR4b_REPORT.md).
source .env && DOMAIN=${NEXT_PUBLIC_SITE_URL#https://}
curl -X POST -H "x-revalidate-secret: $REVALIDATE_SECRET" https://$DOMAIN/api/revalidate
curl -s https://$DOMAIN/sitemap.xml | grep -c '/supervisor/'   # == profiles_count
```

### Смена индекса (переезд на новый каталог)

**Правило (`docs/DECISIONS.md` 17.09): индекс, `cards` и пороги меняются
одновременно — и при выкладке, и при откате.** Пороги принадлежат паре
модель×индекс: новый индекс с прежними числами (или прежний с новыми) — это
чужая шкала грейдов и баннера, а сервис на старте сверяет пороги из настроек
со штампом в `meta.json` индекса и отдаёт результат в `/api/health` полем
`thresholds_match`. Все три вещи лежат в git, в четырёх файлах:

| Что | Где |
|---|---|
| путь индекса | `apps/api/src/sfr_api/settings.py` (`index_root`), `deploy/docker-compose.yml` (`SFR_API_INDEX_ROOT` и volume), `apps/api/Dockerfile` (`ENV SFR_API_INDEX_ROOT`), `deploy/sync-artifacts.sh` |
| путь `cards` | `settings.py` (`cards_path`), `docker-compose.yml` (`SFR_API_CARDS_PATH` и bind-монтирование одного файла), `sync-artifacts.sh` |
| пороги | **только** `settings.py`: `score_threshold`, `score_weak`, `score_high` (env `SFR_API_SCORE_THRESHOLD`, `SFR_API_SCORE_WEAK`, `SFR_API_SCORE_HIGH`). Compose их намеренно не передаёт, `deploy/.env` в контейнер api не попадает — других мест нет |

**`cards` монтируется одним файлом** (#13): в контейнер api попадает только
`cards_sfr5c.jsonl`, не весь `data/exports`. Следствие: `rsync` заменяет файл
через переименование, а работающий контейнер держит старый — после
`sync-artifacts.sh` нужен явный `docker compose restart api`. `up -d --build`
его не заменяет: compose пересоздаёт контейнер, только если изменились образ
или конфиг сервиса, а новые данные при том же образе — не изменение. Без файла
на сервере контейнер не поднимется — это намеренно (`create_host_path: false`).

**Дата данных в `meta.json`** (#16): локальный индекс проштампован полем
`data_updated_at`. Api до этой ветки читает `meta.json` строго и на незнакомом
ключе не стартует (с неё — пропускает незнакомые ключи). Поэтому на первой
выкладке после #16 `sync-artifacts.sh` и пересборка api — одним заходом, без
перезапуска старого контейнера между ними; при откате кода ниже этой ветки —
удалить ключ `data_updated_at` из `meta.json` на сервере или привезти прежний
`meta.json`.

**Чеклист выкладки нового индекса** (#99 и дальше):

1. **Калибровка до штампа.** Цель `make index-sfr5c` штампует в `meta.json`
   пороги из *текущего* `ApiSettings` — на новом корпусе это ложный штамп:
   `thresholds_match: true` будет значить «проштамповано», а не
   «откалибровано». Порядок: собрать индекс → `sfr-match calibrate` и рецепт
   `weak`/`high` (`threshold_hints` в `scripts/analyze_sfr5.py`) → `sfr-match
   stamp-thresholds --index-dir <индекс>/frida_clean --none … --weak … --high …`
   новыми числами → те же числа в `settings.py`.
2. **Один PR на все четыре файла** из таблицы выше; `grep` по старому имени
   каталога индекса и старым числам порогов по `apps/`, `deploy/`, `Makefile`
   должен быть пуст.
3. **Записать SHA `main` до merge** выкладочного PR — это точка отката (для
   выкладки SFR-5c 26.09: `2e20bf9`, merge — `73c07e2`).
4. После выкладки — проверки из «Обновления» плюс `/api/health`: новый
   `index_version`, `profiles_count` = число в sitemap, **`thresholds_match: true`**.
5. Старый каталог индекса на сервере не удалять до шага 4. `sync-artifacts.sh`
   кладёт индекс в каталог, названный в скрипте, и удаляет лишнее только в нём
   (`rsync --delete`): после переезда `data/indexes_sfr5` → `data/indexes_sfr5c`
   на VPS лежат оба, ~150 МБ. Убирать — после проверки:
   `rm -rf ~/search-for-research/data/indexes_sfr5`.

**Откат к предыдущему индексу** — все четыре файла сразу, из коммита до
выкладки (`PRE` — SHA из шага 3; для SFR-5c `PRE=2e20bf9`):

```bash
# 1. С машины разработчика — только если старого индекса на VPS уже нет
#    (после шага 5 выше): старая версия скрипта везёт старые артефакты
git show "$PRE:deploy/sync-artifacts.sh" > /tmp/sync-old.sh
bash /tmp/sync-old.sh user@host

# 2. На VPS: вернуть четыре файла, коммитов на сервере не делать
cd ~/search-for-research
git checkout "$PRE" -- apps/api/src/sfr_api/settings.py apps/api/Dockerfile \
    deploy/docker-compose.yml deploy/sync-artifacts.sh
cd deploy && docker compose up -d --build api

# 3. Ревалидация ISR: лендинг и sitemap показывают число профилей
source .env && DOMAIN=${NEXT_PUBLIC_SITE_URL#https://}
curl -X POST -H "x-revalidate-secret: $REVALIDATE_SECRET" https://$DOMAIN/api/revalidate

# 4. Последний шаг — сверка: старый index_version, его profiles_count и пороги,
#    thresholds_match: true. false — откачено не всё: пороги не совпали с
#    индексом, ищи файл из таблицы, который остался новым
docker compose exec -T api curl -s localhost:8000/api/health \
  | python3 -c 'import json,sys; h=json.load(sys.stdin); print(h["index_version"], h["profiles_count"], h["score_threshold"], h["score_weak"], h["score_high"], "thresholds_match:", h["thresholds_match"])'
curl -s https://$DOMAIN/sitemap.xml | grep -c '/supervisor/'   # == profiles_count
```

Затем закрепить откат в git: `git revert -m 1 <merge выкладки>` отдельным PR в
`main`, после merge на VPS — `git checkout -- . && git pull` (рабочее дерево
сервера совпадёт с `main`, пересборка не нужна). Откат «только путей» без
порогов — ровно тот случай, который `thresholds_match: false` и ловит.

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

- **История /match**: PostgreSQL и постоянный аналитический журнал;
  закрытый `analytics-export` для data science. Не печатать raw stdout в терминал.
- **Access-лог proxy**: закрытая HTTP-диагностика `/data/access.log`,
  headers и query-параметры исключены; архивирование оператором сохраняет историю.
- **Продуктовая воронка**: `analytics-report`, явные события по visit/search ID.
- **Health**: `docker compose exec api curl -s localhost:8000/api/health` —
  модель, версия индекса, пороги, hit-rate кэша.
- **Uptime**: crontab на сервере —
  `*/5 * * * * /home/USER/search-for-research/deploy/uptime-check.sh https://search-for-research.ru >> /home/USER/uptime.log 2>&1`
  (абсолютные пути: cron не наследует ни `~`, ни PATH оболочки).
- **Внешний uptime** (с 12.09): UptimeRobot дёргает `https://search-for-research.ru/`
  раз в 5 минут, при отказе шлёт письмо Борису; публичная status-страница
  намеренно выключена. Крон и внешний пингер не дублируют друг друга: крон
  видит контейнеры изнутри, но молчит вместе с сервером, если тот недоступен
  целиком, — внешний пингер видит ровно то, что видит посетитель.

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
   работающем стенде поправить владельца с сохранением томов и журналов:

   ```bash
   docker compose run --rm --user root --entrypoint chown proxy -R 10001:10001 /data /config
   docker compose up -d --build proxy
   ```

   На чистом сервере ничего делать не нужно.

## Аналитика PoC: PostgreSQL, журнал и доступ

Аналитический слой отделён от ETL: SQLite, каталог, индекс, модель и пороги
остаются прежними. PostgreSQL **17.11-bookworm** находится в том же Compose,
без опубликованного порта; `analytics-db` сохраняется при пересоздании.
`analytics-journal` хранит fsync-журнал, ожидающие записи, закрытые gzip-архивы
и карантин. Приложение работает от `sfr_runtime` с INSERT и чтением только ID
для устранения дублей. Миграции выполняет отдельный `sfr_migrator`; закрытые
выгрузки и отчёты читает `sfr_reader` с SELECT и read-only транзакциями.
Пароли — три разных hex-секрета в `deploy/.env`, не в командной строке/git.
Для уже существующего тома init-скрипт повторно не выполняется: оператор
создаёт/проверяет роли и применяет миграции, не пересоздаёт том. Обновление
пароля в `.env` само по себе не меняет пароль существующей роли.
Init выполняется через `psql -f` (`init-runtime.sql`), без исполнения
host bind-скрипта: на некоторых macOS Docker mounts проверка `-x` истинна
для 0644, но exec запрещён. При прерванном первом init PostgreSQL уже
может содержать данные и пропустит init при рестарте. В этом случае
сохранить том и явно выполнить идемпотентное создание отсутствующих ролей:

```bash
# Команда для оператора после проверки выбранного проекта/БД, без удаления тома.
docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec -T postgres \
  sh -c 'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 \
  -f /docker-entrypoint-initdb.d/10-runtime.sql'
docker compose --env-file deploy/.env -f deploy/docker-compose.yml run --rm analytics-migrate
```

Существующие роли и пароли не заменяются. Неожиданные повышенные права
или членство ролей приводят к явной ошибке; это требует решения оператора.
Миграция после provisioning повторно выдаёт минимальные права runtime и
SELECT для reader. Не исправлять прерванный init удалением тома.


Начальные ограничения PostgreSQL: 512 MiB RAM, 1 CPU, `shared_buffers=64MB`,
`work_mem=4MB`, `maintenance_work_mem=32MB`, `max_connections=20`;
пул API — 2 соединения без overflow, ограниченные connect/statement/lock
таймауты. Это исходная конфигурация для репетиции рядом с FRIDA, а не
доказательство запаса под нагрузкой. Снимок VPS 01.10 (4 CPU, 7,76 GiB RAM,
43,77 GiB свободно) измерен в спокойный момент. Измерения и ограничения
репетиции передаются в техническом отчёте. Все компоненты — UTC;
PostgreSQL хранит `timestamptz`. Для переноса БД меняются
`SFR_API_ANALYTICS_DATABASE_URL`, `SFR_ANALYTICS_MIGRATION_DATABASE_URL` и
`SFR_ANALYTICS_OPERATOR_DATABASE_URL`; приложение не зависит от адреса VPS.

Сырые запросы, имена/контакты внутри них, результаты, raw IP и разрешённый
контекст — чувствительные исследовательские данные. Они **не обезличены**.
Не пересылать raw логи в issue/PR/чат; публичный отчёт содержит только
агрегаты. Воронка — явные события одной `search_id`, не IP/Referer.
Наблюдаемые визиты не являются уникальными людьми. Копирование письма
не доказывает отправку/ответ/качество подбора. Внешние часы клиента не
задают порядок: логический `client_seq` внутри визита, серверное время
приёма для периода, монотонное время для задержек. Повторная доставка
идемпотентна; отсутствие события не доказывает причину ухода.

На Caddy полностью удалены request/response headers из access/error логов
и вся query-строка URL; разрешённые diagnostic headers и очищенные URL
хранятся отдельно приложением. Секретные headers не попадают в этот слой.
Caddy заменяет входные X-Forwarded-For/X-Real-IP, Next доверяет только
этой закрытой цепочке, API доверяет только фиксированному адресу Next
(`SFR_COMPOSE_WEB_IP`); при изменении подсети IP и доверие меняются вместе.
`SFR_COMPOSE_IP_RANGE` ограничивает динамические адреса верхней половиной
/24-подсети, чтобы PostgreSQL/API/proxy не заняли фиксированный адрес Next.
`/api/events` ограничен отдельно 120 POST/мин/IP; этот путь и `/api/match`
исключены из зоны страниц. Предельное тело на прокси — 16 KiB; Next/API
дополнительно проверяют схему, размеры полей и количество событий.

### Изолированная репетиция и миграции

Не останавливать существующий локальный стенд. Выбрать свободный порт,
имя проекта и не пересекающуюся подсеть:

```bash
make deploy-local SFR_COMPOSE_PROJECT=sfr-analytics-rehearsal SFR_LOCAL_PORT=18080 \
  SFR_COMPOSE_SUBNET=172.29.179.0/24 SFR_COMPOSE_WEB_IP=172.29.179.3 \
  SFR_COMPOSE_IP_RANGE=172.29.179.128/25
SFR_WEB_URL=http://localhost:18080 make web-e2e
# down только своего проекта, БЕЗ -v: аналитические данные сохраняются
make deploy-local-down SFR_COMPOSE_PROJECT=sfr-analytics-rehearsal SFR_LOCAL_PORT=18080 \
  SFR_COMPOSE_SUBNET=172.29.179.0/24 SFR_COMPOSE_WEB_IP=172.29.179.3 \
  SFR_COMPOSE_IP_RANGE=172.29.179.128/25
```

`make deploy-local` задаёт безопасные пароли только для локальной репетиции,
версию релиза из текущего git SHA, собирает образы с именем своего проекта,
ожидает healthy у всех сервисов (до 300 секунд), затем применяет миграции и
ревалидирует Next. Не считать ответ `up -d` доказательством готовности API. В production сначала заполнить
три секрета и `SFR_ANALYTICS_RELEASE` текущим SHA. Из корня проекта:

```bash
# Команды подготовлены для последующей выкладки; в этой сессии не выполнять на VPS.
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d postgres
docker compose --env-file deploy/.env -f deploy/docker-compose.yml build api web proxy
docker compose --env-file deploy/.env -f deploy/docker-compose.yml run --rm analytics-migrate
# Проверить migration/check/backup до пересоздания приложения.
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d api web proxy
```

Миграции Alembic живут в пакете аналитики API, отдельно от ETL; применяются
к новой и существующей БД. Перед миграцией — логический backup и внешняя
копия. Откат приложения не удаляет `analytics-db`/`analytics-journal` и не
запускает downgrade/delete. Старый код может перестать собирать новые
события, поэтому зафиксировать границу версии и неполноту.

### Отчёт, диагностика и закрытая выгрузка

Python CLI/Make-цели запускаются оператором, публичных HTTP-экспортов нет.
Для локального Python подключение передаётся через
`SFR_ANALYTICS_OPERATOR_DATABASE_URL` (роль читателя); runtime DSN не
подходит для чтения полного слоя. Для внутренней сети Compose есть
`analytics-operator` с выходным приватным каталогом `data/analytics:/output`:

```bash
# Подготовить каталог с доступом uid приложения; не chmod 777.
mkdir -p data/analytics && chmod 700 data/analytics
# check/replay используют uid приложения (10001) для постоянного журнала.
# report/export запускаются uid оператора, чтобы локальные файлы принадлежали ему.
docker compose --env-file deploy/.env -f deploy/docker-compose.yml run --rm \
  analytics-operator check
docker compose --env-file deploy/.env -f deploy/docker-compose.yml run --rm \
  --user "$(id -u):$(id -g)" analytics-operator report --start 2026-10-01T00:00:00 --end 2026-10-03T00:00:00 \
  --timezone Europe/Moscow --out /output/report-20261001
docker compose --env-file deploy/.env -f deploy/docker-compose.yml run --rm \
  --user "$(id -u):$(id -g)" analytics-operator export --out /output/research-20261001.json
# После восстановления БД: догрузка тем же runtime-пользователем.
docker compose --env-file deploy/.env -f deploy/docker-compose.yml run --rm \
  analytics-operator replay
```

Совместимый JSONL успешных `/match` доступен через `export --format match-jsonl`;
прежние поля и нормализованный `query` берутся из сохранённых серверных фактов.
Полный исходный текст остаётся в закрытом schema-v1 JSON.

Эквиваленты с доступным внутренним DSN: `make analytics-check`,
`make analytics-replay`, `make analytics-export ANALYTICS_ARGS="--out ..."`,
`make analytics-report ANALYTICS_ARGS="--start ... --end ... --timezone Europe/Moscow --out ..."`.
Отчёт можно пересчитать из закрытого schema-v1 JSON через `--export FILE`.
Период полуоткрытый `[start,end)`; без offset время трактуется в указанной
зоне, затем обе границы переводятся в UTC. Неоднозначные DST-времена требуют
явного offset. Отчёт содержит HTML, JSON и CSV воронки/попыток/разрезов,
абсолютные количества и знаменатели, отдельно server latency и browser
elapsed до показа, confidence/errors, повторные попытки, версии, устройства,
прямые профили, объявленные технические прогоны и предполагаемых ботов.
Основная воронка исключает эти два класса трафика; классификация UA не
доказывает, кто отправил запрос. Полнота/догрузка и неверные часы указаны
отдельно. Когорта ограничена серверным временем приёма событий в периоде:
визиты, начавшиеся до периода, не включаются в последовательную воронку.
Позднюю доставку после закрытия периода видно после повторного расчёта.
HTML не включает raw query/context; строки экранированы. JSON-экспорт
содержит полные запросы и связанные результаты, это **закрытый** файл.
Файлы создаются с 0600, каталоги — 0700; существующие файлы не затираются.

`analytics-check` проверяет доступность БД, актуальность миграций, число
записей, последнюю запись/приём/догрузку, очередь/архив/карантин, ошибки и
свободное место. Неполнота, очередь или карантин дают ненулевой статус.
Сбой БД оставляет fsync-запись в журнале, поиск продолжает работу. При
переполнении буфера/диска приёмник не подтверждает событие; оператор видит
категориальную ошибку и неполноту. Клиентская сеть/закрытие вкладки могут
потерять события до доставки — абсолютная полнота не обещается.

### Архивы, место, backup и внешняя копия

Автоматического удаления по возрасту нет. Закрытые файлы fsync-журнала
сжимаются и сохраняются; повреждённые записи остаются в карантине.
Для Caddy 2.11.4 `roll_keep_for 0` означает default 90 дней
([tagged source](https://github.com/caddyserver/caddy/blob/v2.11.4/modules/logging/filewriter.go#L240)),
поэтому `roll_disabled` исключает скрытую потерю истории. Операторская
`make analytics-rotate` атомарно переименовывает access.log на том же томе,
перезапускает **только выбранный proxy**, затем сжимает закрытый файл;
архив остаётся в `/data/archive`. Это явная эксплуатационная операция
с коротким перезапуском proxy, её не выполняют фоновые отчёты.

Сначала контролировать `analytics-check`, `docker compose exec postgres df -h`
и размер томов/архивов. При нехватке места — прекратить технические
прогоны, выгрузить на Mac и проверить манифест, добавить диск/вынести БД;
не удалять историю автоматически. Рост БД/архивов остаётся ответственностью
оператора. Runtime Docker stdout ротируется как диагностика; источником
истории поиска являются PostgreSQL/постоянный журнал, не stdout.

```bash
# Логический pg_dump, согласованный snapshot, custom format. Живой PGDATA не копировать.
make analytics-backup ANALYTICS_ARGS="--directory data/backups/analytics-20261002"
# NEW отдельная тестовая БД; не перезаписывает существующую, не удаляет данные.
make analytics-restore-check \
  ANALYTICS_ARGS="--directory data/backups/analytics-20261002 --database sfr_restore_20261002"
# Восстановленная БД сохранена; JSON содержит counts/row fingerprints/версию миграции.
# Сравнение source/restore в репетиции: добавить --compare-source на неизменяемом наборе.

# Внешний экземпляр на Mac: сервер только читает, pg_dump/tar передаются потоками.
make analytics-pull ANALYTICS_ARGS="--host deploy@135.106.208.233 --out data/backups/vps-20261002"
# Та же проверка в изолированном локальном Compose, без SSH:
SFR_COMPOSE_PROJECT=sfr-analytics-rehearsal \
SFR_COMPOSE_OVERRIDE=deploy/docker-compose.local.yml \
make analytics-pull ANALYTICS_ARGS="--local --out data/backups/local-20261002"
```

Все backup/pull/rotation команды используют выбранный `SFR_COMPOSE_PROJECT`,
`SFR_COMPOSE_OVERRIDE` и `SFR_COMPOSE_ENV_FILE` (default `deploy/.env` если
файл существует). Локальные переменные Compose нужно передать совместно,
как при старте стенда. Манифест SHA-256 фиксирует каждый dump/tar;
выгрузка содержит БД, постоянный журнал, access-лог и архивы. Активные
журналы могут дописываться: это наблюдаемая копия, а не единый snapshot
всех файлов. БД в `pg_dump` согласована транзакционно. Повторная выгрузка
после догрузки устраняет отставание. Копия на том же VPS не защищает от
потери VPS; подтверждённый внешний экземпляр — на Mac. Перед выкладкой
сделать внешнюю копию и проверочное восстановление, затем миграции.
`deploy/analytics/backup.cron.example` — подготовленное расписание и
инструкция; **на production в этой сессии не установлено**. Локальные
backup/exports не публиковать, не включать в git или web static.

Для регрессии логирования на реальном Caddy после сборки proxy:

```bash
make analytics-test-caddy CADDY_TEST_ARGS="--image sfr-analytics-rehearsal-proxy:latest"
```

Проверка запускает отдельный контейнер без сети и host ports с синтетическим
loopback backend: пути `/api/match`, `/results`, `/supervisor/A123` сохраняются,
произвольные query-параметры и secret headers отсутствуют в access/runtime
логах. Двойное экранирование regexp в Caddyfile может ошибочно удалить весь
URI; проверяется фактический Go/Caddy encoder, а не Python-аналог regex.
После проверки контейнер остановлен, его синтетический том сохраняется.
