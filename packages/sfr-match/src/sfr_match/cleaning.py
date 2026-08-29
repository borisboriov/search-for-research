"""Profile-text preprocessing: LaTeX de-noising and author-list abstract removal.

Addresses problems #1–2 from SFR-0 ``docs/REPORT.md``:

1. Physics abstracts arrive with TeX escapes (``\\ensuremath``, ``$…$``, ``\\ifmmode``)
   that eat the profile character budget and add tokens with no semantic content.
2. Some mega-collaboration works carry an author list instead of an abstract
   (``Author(s): Collaboration, The ATLAS; Aad, G; Abat, E; …``).

Pure functions over ``profile_text`` — the exported JSONL is never rewritten
(the cleaning is applied at index time, per SPEC_SFR1 §5).
"""

import re

# --- LaTeX -----------------------------------------------------------------

# ``\ifmmode\pm\else\textpm\fi{}`` — keep the math-mode branch, drop the rest.
_IFMMODE = re.compile(r"\\ifmmode(.*?)\\else.*?\\fi\s*(?:\{\s*\})?", re.DOTALL)

# Commands worth keeping as a symbol: the same characters already appear, in
# Unicode form, in the titles of the very same works.
_SYMBOLS = {
    "pm": "±",
    "mp": "∓",
    "times": "×",
    "cdot": "·",
    "cdots": "…",
    "ldots": "…",
    "rightarrow": "→",
    "to": "→",
    "leftarrow": "←",
    "leftrightarrow": "↔",
    "Rightarrow": "⇒",
    "approx": "≈",
    "sim": "~",
    "simeq": "≃",
    "neq": "≠",
    "ne": "≠",
    "leq": "≤",
    "le": "≤",
    "geq": "≥",
    "ge": "≥",
    "ll": "≪",
    "gg": "≫",
    "pi": "π",
    "mu": "μ",
    "nu": "ν",
    "psi": "ψ",
    "phi": "φ",
    "chi": "χ",
    "eta": "η",
    "rho": "ρ",
    "tau": "τ",
    "theta": "θ",
    "sigma": "σ",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "varepsilon": "ε",
    "lambda": "λ",
    "omega": "ω",
    "kappa": "κ",
    "zeta": "ζ",
    "xi": "ξ",
    "Lambda": "Λ",
    "Sigma": "Σ",
    "Delta": "Δ",
    "Omega": "Ω",
    "Gamma": "Γ",
    "Phi": "Φ",
    "Psi": "Ψ",
    "Xi": "Ξ",
    "Theta": "Θ",
    "Upsilon": "Υ",
    "sqrt": "√",
    "infty": "∞",
    "degree": "°",
    "prime": "′",
    "ell": "ℓ",
    "textpm": "±",
    "texttimes": "×",
    "textdegree": "°",
}

# Structural/typographic commands: drop the command, keep the braced content.
_STRUCTURAL = frozenset(
    [
        "ensuremath",
        "text",
        "textrm",
        "textit",
        "textbf",
        "mathrm",
        "mathbf",
        "mathit",
        "mathcal",
        "mathbb",
        "mathsf",
        "mathtt",
        "operatorname",
        "hbox",
        "mbox",
        "rm",
        "it",
        "bf",
        "overline",
        "underline",
        "bar",
        "hat",
        "vec",
        "tilde",
        "left",
        "right",
        "big",
        "Big",
        "bigg",
        "Bigg",
        "displaystyle",
        "textstyle",
        "nonumber",
        "label",
        "boldsymbol",
        "scriptstyle",
    ]
)

_COMMAND = re.compile(r"\\([a-zA-Z]+)\s*")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?»)\]])")
_SPACE_AFTER_OPEN = re.compile(r"([(\[«])\s+")

LATEX_MARKERS = ("\\", "$")


def has_latex(text: str) -> bool:
    """Cheap check used for reporting how much of the corpus is affected."""
    return any(marker in text for marker in LATEX_MARKERS)


def _replace_command(match: re.Match[str]) -> str:
    name = match.group(1)
    if name in _SYMBOLS:
        return _SYMBOLS[name]
    if name in _STRUCTURAL:
        return ""
    return " "  # unknown command: drop it, keep the word boundary


def strip_latex(text: str) -> str:
    """Turn TeX escapes into plain text (or nothing), preserving the readable content."""
    if not has_latex(text):
        return text
    text = _IFMMODE.sub(r"\1", text)
    text = _COMMAND.sub(_replace_command, text)
    text = text.replace("$", "")
    text = text.replace("{", "").replace("}", "")
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _SPACE_AFTER_OPEN.sub(r"\1", text)
    return " ".join(text.split())


# --- "abstract" that is really an author list -------------------------------

# ``Aad, G;`` / ``Abdelalim, AA;`` / ``Иванов, И. И.;`` — surname, initials, separator.
_NAME_TOKEN = re.compile(
    r"[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё'’\-]{1,20},\s*(?:[A-ZА-ЯЁ]\.?\s*){1,3}(?=[;,]|\s|$)"
)
_EXPLICIT_MARKER = re.compile(r"^\s*Author\(s\)\s*:", re.IGNORECASE)

AUTHOR_LIST_MIN_NAMES = 4
AUTHOR_LIST_MIN_COVERAGE = 0.5


def is_author_list(text: str) -> bool:
    """True when the fragment is a list of authors rather than a scientific abstract.

    Two signals: the explicit ``Author(s):`` marker used by some indexers, and
    the share of the fragment covered by ``Surname, I;`` patterns.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if _EXPLICIT_MARKER.search(stripped):
        return True
    matches = _NAME_TOKEN.findall(stripped)
    if len(matches) < AUTHOR_LIST_MIN_NAMES:
        return False
    covered = sum(len(m) for m in matches)
    return covered / len(stripped) >= AUTHOR_LIST_MIN_COVERAGE


# --- profile_text ------------------------------------------------------------

# A work line looks like ``«Title» (2019). Abstract fragment…``
_WORK_LINE = re.compile(r"^(«.*?»(?:\s*\(\d{4}\))?\.)\s*(.*)$", re.DOTALL)


def clean_profile_text(text: str) -> str:
    """Clean a whole ``profile_text``: drop author-list abstracts, de-TeX the rest.

    Keeps the line structure (header, topics, one line per work) so that a cleaned
    profile is still a readable card.
    """
    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line
        work = _WORK_LINE.match(line)
        if work:
            title_part, abstract_part = work.group(1), work.group(2)
            line = title_part if is_author_list(abstract_part) else line
        cleaned = strip_latex(line).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)
