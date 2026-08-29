"""Where to draw the «we found nobody» line (SPEC_SFR2 §4).

The cut-off is a property of one *variant* — model plus what was indexed — because
each of them has its own score scale. Calibration therefore takes the top-1 scores
of one run over real queries and one run over queries confirmed to have no answer
in the corpus, and reports what every candidate threshold would cost.

Criterion: no false cut on real queries (in-domain and edge), and as much of the
out-of-domain set caught as that allows. The threshold is a warning, not a refusal
(SFR-1) — but a warning shown on a query that did have a good answer is still wrong.

When several thresholds achieve the same coverage — which happens as soon as the two
score distributions actually separate — the middle of that plateau is taken, not its
upper edge: a threshold pressed against the lowest real query is one unlucky query
away from being wrong, in a set of 22.
"""

from dataclasses import dataclass

from sfr_match.evalset import Query
from sfr_match.evaluate import Run

GRID_STEP = 0.01


@dataclass(frozen=True)
class ThresholdRow:
    threshold: float
    false_cuts_in_domain: int
    false_cuts_edge: int
    ood_caught: int

    @property
    def is_safe(self) -> bool:
        return self.false_cuts_in_domain == 0


def top1_scores(run: Run, queries: list[Query], kinds: set[str]) -> dict[str, float]:
    """Top-1 score per query, restricted to the given ``expect`` kinds."""
    wanted = {query.id for query in queries if query.expect in kinds}
    scores: dict[str, float] = {}
    for query_id in wanted:
        score = run.top_score(query_id)
        if score is not None:
            scores[query_id] = score
    return scores


def grid(*score_sets: dict[str, float], step: float = GRID_STEP) -> list[float]:
    """Candidate thresholds spanning every observed score, on a round step."""
    values = [score for scores in score_sets for score in scores.values()]
    if not values:
        return []
    low = int(min(values) / step) - 1
    high = int(max(values) / step) + 2
    return [round(index * step, 4) for index in range(low, high)]


def calibrate(
    in_domain: dict[str, float],
    edge: dict[str, float],
    ood: dict[str, float],
    thresholds: list[float] | None = None,
) -> list[ThresholdRow]:
    """One row per candidate threshold: what it cuts wrongly and what it catches."""
    thresholds = thresholds or grid(in_domain, edge, ood)
    return [
        ThresholdRow(
            threshold=threshold,
            false_cuts_in_domain=sum(1 for score in in_domain.values() if score < threshold),
            false_cuts_edge=sum(1 for score in edge.values() if score < threshold),
            ood_caught=sum(1 for score in ood.values() if score < threshold),
        )
        for threshold in thresholds
    ]


def recommend(rows: list[ThresholdRow]) -> ThresholdRow | None:
    """Best coverage among thresholds that cut nothing real, taken at maximum margin.

    Prefers thresholds that spare edge queries too; falls back to «in-domain only»
    if sparing edge queries costs coverage.
    """
    for candidates in (
        [row for row in rows if row.is_safe and row.false_cuts_edge == 0],
        [row for row in rows if row.is_safe],
    ):
        if not candidates:
            continue
        best_coverage = max(row.ood_caught for row in candidates)
        plateau = [row for row in candidates if row.ood_caught == best_coverage]
        return plateau[len(plateau) // 2]
    return None
