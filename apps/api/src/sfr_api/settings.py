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
    # SFR-5 перекалибровал порог на корпусе 12 вузов (frida_clean-5540p-a2f13892):
    # 0.29 — середина безопасного интервала 0.26…0.31, отсекает 18 из 19
    # подтверждённых посторонних запросов и не режет ни одного из 26 настоящих.
    # Порог принадлежит паре модель×индекс; у mpnet своя шкала.
    # ВАЖНО: цифра промежуточная — у 5 007 профилей из 5 540 ещё нет работ
    # (дневной бюджет OpenAlex, docs/DECISIONS.md); после бэкфилла перекалибровать.
    score_threshold: float = 0.29

    # Серая зона (SPEC_SFR4 §0.9). На корпусе 12 вузов распределения разошлись:
    # самый высокий посторонний запрос даёт 0.310, самый слабый настоящий — 0.350.
    # 0.33 — середина этого зазора: top-1 ниже означает «совпадения слабые»,
    # выдача остаётся, но с баннером.
    score_weak: float = 0.33
    # Словесные грейды карточек — та же шкала: >= score_high «высокое совпадение»,
    # [score_weak, score_high) «среднее», ниже — «слабое». 0.44 — медиана top-1
    # по удачным запросам golden set; величина выведена из распределения, а не
    # откалибрована (набора «высоких» совпадений для калибровки не существует).
    score_high: float = 0.44

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
