# apps/api — сервис поиска научных руководителей

FastAPI поверх индекса, собранного офлайн (`make index-sfr2`). Модель и индекс
грузятся один раз при старте, прогреваются и переиспользуются; API индекс **не строит**.

## Эндпоинты

| Метод | Путь | Что делает |
|---|---|---|
| `POST` | `/api/match` | `{"query": "…", "k": 10}` → карточки НР, `below_threshold`, `index_version` |
| `GET` | `/api/supervisors/{author_id}` | одна карточка по OpenAlex-id |
| `GET` | `/api/health` | модель, версия индекса, число профилей, порог, бэкенд поиска |

Карточки **открытые и бесплатные** — авторизации нет по продуктовому решению
(план MVP v1.3): монетизация будет на сервисах вокруг данных, не на данных.

`below_threshold` — предупреждение «уверенных совпадений нет», а не отказ:
выдача возвращается всегда (SFR-1 показал перекрытие распределений score).

## Запуск

```bash
make index-sfr2                 # собрать индекс (офлайн, один раз)
make api                        # uvicorn на localhost:8000
curl -s localhost:8000/api/health | jq
curl -s localhost:8000/api/match -H 'content-type: application/json' \
  -d '{"query":"нейросети для медицинских изображений","k":5}' | jq
```

В контейнере: `make docker-up` (см. `docker-compose.yml` в корне репозитория).

## Настройки

Переменные окружения с префиксом `SFR_API_` (см. `settings.py`):
`SFR_API_MODEL`, `SFR_API_INDEX_ROOT`, `SFR_API_INDEX_DIR`, `SFR_API_COMPOSE`,
`SFR_API_SCORE_THRESHOLD`, `SFR_API_CORS_ORIGINS`, `SFR_API_MAX_K`.
Переключение на запасную модель — `SFR_API_MODEL=mpnet` плюс собранный под неё индекс.
