"""API configuration. Everything that can move between environments lives here."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from sfr_match.index import DEFAULT_INDEX_ROOT, resolve_index_dir


class ApiSettings(BaseSettings):
    """Read from ``SFR_API_*`` environment variables (and ``.env``).

    The index is *not* built here: it is produced offline by ``make index-sfr2``
    and mounted read-only. The service only needs to know which directory to open.
    """

    model_config = SettingsConfigDict(
        env_prefix="SFR_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Which index to serve. index_dir, when set, wins over the model/clean/compose triple.
    index_root: Path = DEFAULT_INDEX_ROOT
    model: str = "frida"
    clean: bool = True
    compose: str = "full"
    index_dir: Path | None = None

    # "We found nobody confident enough" — a warning, not a refusal (SFR-1, NEXT.md).
    # 0.27 is the SFR-2 recalibration on 17 confirmed out-of-domain queries: it catches
    # 17/17 of them and cuts none of the 26 real ones, with ~0.06 of margin on each side.
    # It belongs to the `frida_clean` index — mpnet's own scale calibrates to 0.43.
    score_threshold: float = 0.27

    # The grey zone (SPEC_SFR4 §0.9, decision of 05.09): 0.27 was calibrated on
    # everyday out-of-domain queries (scores <= 0.21), but academically-phrased
    # queries with no answer in the corpus land higher — the live "computer
    # science backend engineering" run scored 0.34 with a garbage top-10 and no
    # warning. 0.36 sits between the minimum of live true hits (0.31) and their
    # mean (0.43): top-1 below it means "matches are weak", shown as a banner
    # while the results stay visible. Belongs to frida_clean, like 0.27.
    score_weak: float = 0.36
    # Word grades on the cards use the same scale: >= score_high is "высокое
    # совпадение", [score_weak, score_high) is "среднее", below — "слабое".
    score_high: float = 0.42

    # Card enrichment (citations, top works) built offline by `sfr export cards`.
    # Optional: a missing file degrades to empty card fields (tests, bare index).
    cards_path: Path | None = Path("data/exports/cards.jsonl")

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
