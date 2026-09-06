"""API configuration. Everything that can move between environments lives here."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from sfr_match.index import resolve_index_dir


class ApiSettings(BaseSettings):
    """Read from ``SFR_API_*`` environment variables (and ``.env``).

    The index is *not* built here: it is produced offline by ``make index-sfr5``
    and mounted read-only. The service only needs to know which directory to open.
    """

    model_config = SettingsConfigDict(
        env_prefix="SFR_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Which index to serve. index_dir, when set, wins over the model/clean/compose triple.
    # SFR-5: боевой индекс — каталог 12 вузов (`make index-sfr5`); индекс SFR-2
    # остаётся на диске для воспроизводимости SFR-2 и включается через env.
    index_root: Path = Path("data/indexes_sfr5")
    model: str = "frida"
    clean: bool = True
    compose: str = "full"
    index_dir: Path | None = None

    # "We found nobody confident enough" — a warning, not a refusal (SFR-1, NEXT.md).
    # Перекалибровано после бэкфилла публикаций на полном корпусе
    # (frida_clean-5538p-ea7e3c07, у всех 5 538 профилей есть работы).
    # 0.37 — середина безопасного интервала 0.363…0.380: отсекает 19 из 19
    # подтверждённых посторонних и не режет ни одного из 26 настоящих запросов.
    # На полном корпусе распределения разошлись: самый высокий посторонний
    # даёт 0.363, самый слабый настоящий — 0.391 (на смешанном корпусе
    # интервала не было вовсе). Порог принадлежит паре модель×индекс.
    score_threshold: float = 0.37

    # Серая зона (SPEC_SFR4 §0.9): top-1 в [score_threshold, score_weak)
    # показывает выдачу с баннером «совпадения слабые». 0.40 стоит чуть выше
    # минимума настоящих запросов (in-domain 0.391, edge 0.380), то есть
    # предупреждение получают ровно самые слабые из живых попаданий.
    score_weak: float = 0.40
    # Словесные грейды карточек — та же шкала: >= score_high «высокое совпадение»,
    # [score_weak, score_high) «среднее», ниже — «слабое». 0.47 — медиана top-1
    # по удачным запросам golden set; величина выведена из распределения, а не
    # откалибрована (набора «высоких» совпадений для калибровки не существует).
    score_high: float = 0.47

    # Card enrichment (citations, top works) built offline by `sfr export cards`.
    # Optional: a missing file degrades to empty card fields (tests, bare index).
    cards_path: Path | None = Path("data/exports/cards_sfr5.jsonl")

    # Catalogue listing (sitemap, landing preview): page size cap.
    list_default_limit: int = 100
    list_max_limit: int = 1000

    default_k: int = 10
    max_k: int = 50
    min_query_chars: int = 3
    max_query_chars: int = 500

    # Инференс FRIDA на CPU не параллелится бесплатно: 40 потоков threadpool
    # дают x10 латентность и рост памяти (REVIEW_SFR3 Medium). Одновременно
    # кодируют не больше match_concurrency запросов, ещё match_queue_limit
    # ждут в очереди, остальным — честный 503 сразу.
    match_concurrency: int = 2
    match_queue_limit: int = 6

    # LRU-кэш ответов /match по нормализованному запросу (SPEC_SFR4 §2):
    # дешёвый способ поднять потолок FRIDA (~2 rps на CPU). Корпус фиксирован,
    # поэтому TTL щедрый; hit-rate отдаётся в /health. ttl=0 выключает кэш.
    match_cache_ttl_seconds: int = 3600
    match_cache_max_entries: int = 512

    # Соль для хеша IP в логах /match: сырой IP в лог не пишется, а без соли
    # sha256 от IPv4 перебирается. Задать на сервере (SFR_API_LOG_SALT).
    log_salt: str = ""

    # The future Next.js front (SFR-3) runs on localhost; nothing else is allowed by default.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ]

    warmup: bool = True

    def resolved_index_dir(self) -> Path:
        if self.index_dir is not None:
            return self.index_dir
        return resolve_index_dir(
            self.model,
            clean=self.clean,
            compose=self.compose,  # type: ignore[arg-type]
            root=self.index_root,
        )
