"""API configuration. Everything that can move between environments lives here."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from sfr_match.index import resolve_index_dir


class ApiSettings(BaseSettings):
    """Read from ``SFR_API_*`` environment variables (and ``.env``).

    The index is *not* built here: it is produced offline by ``make index-sfr5c``
    and mounted read-only. The service only needs to know which directory to open.
    """

    model_config = SettingsConfigDict(
        env_prefix="SFR_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Which index to serve. index_dir, when set, wins over the model/clean/compose triple.
    # SFR-5c (выкладка 26.09): боевой индекс — каталог 12 вузов с потолком на вуз
    # (`make index-sfr5c`, 9 002 профиля). Индексы SFR-2, SFR-5 и SFR-5b остаются
    # на диске для воспроизводимости своих отчётов и включаются через env.
    index_root: Path = Path("data/indexes_sfr5c")
    model: str = "frida"
    clean: bool = True
    compose: str = "full"
    index_dir: Path | None = None

    # "We found nobody confident enough" — a warning, not a refusal (SFR-1, NEXT.md).
    # Откалибровано на боевом корпусе (frida_clean-9002p-35e591d4, у всех
    # 9 002 профилей есть работы). Распределения посторонних и настоящих
    # перекрываются, как и на всех прошлых индексах: самый высокий посторонний
    # даёт 0.366 (o34, киноведение — спорный случай с SFR-5), самый слабый
    # настоящий — 0.349 (q27, история России, edge). Безопасных порогов выше
    # 0.348 нет, плато максимального покрытия — [0.31…0.34], 0.33 — его
    # середина: ловит 18 из 19 посторонних, не режет ни одного настоящего
    # запроса (19 — набор до 26.09, `make ood19-sfr5c`). Тот же порог даёт
    # калибровка на 17 посторонних (без o13/o15).
    # Единственный пропущенный (0.366) попадает в серую зону и получает баннер.
    # Порог принадлежит паре модель×индекс: §13 docs/reports/SFR5c_REPORT.md.
    score_threshold: float = 0.33

    # Серая зона (SPEC_SFR4 §0.9): top-1 в [score_threshold, score_weak)
    # показывает выдачу с баннером «совпадения слабые». 0.40 стоит чуть выше
    # минимума настоящих запросов (in-domain 0.395, edge 0.349), то есть
    # предупреждение получают ровно самые слабые из живых попаданий — и вместе
    # с ними единственный посторонний, которого порог не поймал.
    score_weak: float = 0.40
    # Словесные грейды карточек — та же шкала: >= score_high «высокое совпадение»,
    # [score_weak, score_high) «среднее», ниже — «слабое». 0.49 — медиана top-1
    # по удачным запросам golden set, то есть по тем, у кого top-1 действительно
    # релевантен (0.4916 на сетке 0.01 вниз; на 5 538 было 0.4791 → 0.47).
    # Величина выведена из распределения, а не откалибрована: набора «высоких»
    # совпадений для калибровки не существует. Рецепт — в коде,
    # `threshold_hints` в scripts/analyze_sfr5.py.
    score_high: float = 0.49

    # Card enrichment (citations, top works) built offline by `sfr export cards`.
    # Optional: a missing file degrades to empty card fields (tests, bare index).
    cards_path: Path | None = Path("data/exports/cards_sfr5c.jsonl")

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
