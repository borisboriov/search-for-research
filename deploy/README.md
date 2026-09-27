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
# заполнить .env: SITE_ADDRESS (одно имя или несколько через запятую,
#   значение в кавычках), NEXT_PUBLIC_SITE_URL (канонический адрес, один),
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
for name in $(echo "$SITE_ADDRESS" | tr ',' ' '); do dig +short "$name"; done
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
| путь `cards` | `settings.py` (`cards_path`), `docker-compose.yml` (`SFR_API_CARDS_PATH`), `sync-artifacts.sh` |
| пороги | **только** `settings.py`: `score_threshold`, `score_weak`, `score_high` (env `SFR_API_SCORE_THRESHOLD`, `SFR_API_SCORE_WEAK`, `SFR_API_SCORE_HIGH`). Compose их намеренно не передаёт, `deploy/.env` в контейнер api не попадает — других мест нет |

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

- **Логи /match** (материал калибровки порога): JSON-строки в stdout api —
  `docker logs sfr-api | grep '"query"'`; ротация настроена в compose
  (json-file, 20 МБ × 5).
- **Access-лог proxy** (воронка «выдача → профиль»): `/data/access.log`
  внутри тома caddy-data, JSON с uri и Referer.
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
   работающем стенде их надо пересоздать:

   ```bash
   docker compose down
   docker volume rm sfr-deploy_caddy-data sfr-deploy_caddy-config
   docker compose up -d --build     # TLS-сертификат будет выпущен заново
   ```

   На чистом сервере ничего делать не нужно.
