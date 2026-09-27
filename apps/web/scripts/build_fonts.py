"""Шрифты направления B для `next/font/local` — сборка без Google Fonts (#125).

`next/font/google` качал Literata и IBM Plex Sans с fonts.googleapis.com на
каждой сборке образа web, и однажды сборка на этом упала (#125). Здесь те же
гарнитуры собираются один раз из исходников `google/fonts` (OFL) и кладутся в
`apps/web/app/fonts/`: сборка сайта в сеть за шрифтами больше не ходит.

Результат повторяет то, что отдавал Google Fonts, а не исходник целиком:

* незапрошенные оси зафиксированы там же, где их фиксирует Google Fonts, — на
  умолчании **реестра осей Google**, а не шрифта: `opsz` у Literata = 14 (в
  самом шрифте умолчание 12 — на нём контуры расходятся на 1–2 единицы),
  `wdth` у Plex = 100; ось веса сужена так же (Literata 400–900, Plex
  100–700) — такие файлы Google отдаёт на `wght@500;600` / `wght@400;500;600`;
* символы — объединение всех `unicode-range`, которые Google раздавал по
  подмножествам (латиница, кириллица, греческий, вьетнамский и расширения):
  `next/font/local` не умеет `unicode-range` на файл, поэтому файл один;
* хинтинг снят, OpenType-фичи — ровно те, что оставлял Google.

`--verify DIR` сверяет контуры и ширины каждого символа с файлами, которые
отдавал Google (каталог `.next/static/media` сборки на `next/font/google`), на
весах, которые использует сайт.

Запуск из корня репозитория (сеть нужна только здесь, при обновлении шрифтов):

    uv run --no-project --with fonttools --with brotli --with certifi \\
        python apps/web/scripts/build_fonts.py [--verify apps/web/.next/static/media]
"""

from __future__ import annotations

import argparse
import io
import ssl
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import certifi
from fontTools import subset
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

# Коммит google/fonts, из которого собраны файлы: ревизии совпадают с тем, что
# раздавал Google Fonts 26.09 (Literata 3.103, IBM Plex Sans 3.201).
GOOGLE_FONTS_SHA = "23e54b51ddffbc7713c583748e3bd86f62b1fa4a"
RAW = "https://raw.githubusercontent.com/google/fonts/{sha}/ofl/{path}"
OUT_DIR = Path(__file__).resolve().parents[1] / "app" / "fonts"

# unicode-range подмножеств Google Fonts (из CSS сборки на next/font/google).
LATIN = "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"  # noqa: E501
LATIN_EXT = "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF"  # noqa: E501
CYRILLIC = "U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116"
CYRILLIC_EXT = "U+0460-052F,U+1C80-1C8A,U+20B4,U+2DE0-2DFF,U+A640-A69F,U+FE2E-FE2F"
GREEK = "U+0370-0377,U+037A-037F,U+0384-038A,U+038C,U+038E-03A1,U+03A3-03FF"
GREEK_EXT = "U+1F00-1FFF"
VIETNAMESE = "U+0102-0103,U+0110-0111,U+0128-0129,U+0168-0169,U+01A0-01A1,U+01AF-01B0,U+0300-0301,U+0303-0304,U+0308-0309,U+0323,U+0329,U+1EA0-1EF9,U+20AB"  # noqa: E501


@dataclass(frozen=True)
class Family:
    out: str
    source: str
    license: str
    # Ось → значение (зафиксировать) или (min, max) (сузить).
    axes: dict[str, float | tuple[float, float]]
    ranges: tuple[str, ...]
    features: tuple[str, ...]
    # Веса, на которых сверяется результат: те, что использует сайт, и края оси.
    check_weights: tuple[int, ...]


FAMILIES = (
    Family(
        out="Literata",
        source="literata/Literata[opsz,wght].ttf",
        license="literata/OFL.txt",
        axes={"opsz": 14, "wght": (400, 900)},
        ranges=(LATIN, LATIN_EXT, CYRILLIC, CYRILLIC_EXT, GREEK, GREEK_EXT, VIETNAMESE),
        features=(
            "ccmp",
            "dnom",
            "frac",
            "liga",
            "locl",
            "numr",
            "pnum",
            "rvrn",
            "tnum",
            "kern",
            "mark",
        ),
        check_weights=(400, 500, 600, 900),
    ),
    Family(
        out="IBMPlexSans",
        source="ibmplexsans/IBMPlexSans[wdth,wght].ttf",
        license="ibmplexsans/OFL.txt",
        axes={"wdth": 100, "wght": (100, 700)},
        ranges=(LATIN, LATIN_EXT, CYRILLIC, CYRILLIC_EXT, GREEK, VIETNAMESE),
        features=("ccmp", "dnom", "frac", "liga", "locl", "numr", "rvrn", "kern", "mark"),
        check_weights=(100, 400, 500, 600, 700),
    ),
)


def parse_ranges(ranges: tuple[str, ...]) -> set[int]:
    """`U+0400-045F,U+2116,…` → множество кодовых точек."""
    points: set[int] = set()
    for spec in ",".join(ranges).split(","):
        spec = spec.strip().removeprefix("U+")
        start, _, end = spec.partition("-")
        points.update(range(int(start, 16), int(end or start, 16) + 1))
    return points


def download(path: str, dest: Path) -> Path:
    url = RAW.format(sha=GOOGLE_FONTS_SHA, path=path)
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, context=context) as response:
        dest.write_bytes(response.read())
    return dest


def build(family: Family, workdir: Path) -> Path:
    source = download(family.source, workdir / Path(family.source).name)
    # recalcTimestamp=False: head.modified остаётся от исходника, и повторная
    # сборка даёт те же байты.
    font = instancer.instantiateVariableFont(
        TTFont(source, recalcTimestamp=False), dict(family.axes)
    )
    # Пересохранить: после инстансинга ленивый gvar не содержит всех глифов, и
    # субсеттер падает на KeyError.
    buffer = io.BytesIO()
    font.save(buffer)
    buffer.seek(0)
    font = TTFont(buffer, recalcTimestamp=False)
    options = subset.Options()
    options.layout_features = list(family.features)
    options.hinting = False
    options.flavor = "woff2"
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=parse_ranges(family.ranges))
    subsetter.subset(font)
    out = OUT_DIR / f"{family.out}.woff2"
    font.flavor = "woff2"
    font.save(out)
    download(family.license, OUT_DIR / f"{family.out}-OFL.txt")
    return out


def outlines(font: TTFont, weight: int) -> dict[int, tuple[object, int]]:
    """Контур и ширина каждого символа на данном весе (статический срез)."""
    static = instancer.instantiateVariableFont(font, {"wght": weight}, static=True)
    glyphs = static.getGlyphSet()
    result: dict[int, tuple[object, int]] = {}
    for codepoint, name in static.getBestCmap().items():
        pen = DecomposingRecordingPen(glyphs)
        glyphs[name].draw(pen)
        result[codepoint] = (pen.value, static["hmtx"][name][0])
    return result


def verify(family: Family, ours: Path, served_dir: Path) -> int:
    """Сколько символов разошлось с файлами Google Fonts (0 — идентично)."""
    name = TTFont(ours)["name"].getDebugName(1)
    served = [
        path
        for path in sorted(served_dir.glob("*.woff2"))
        if TTFont(path)["name"].getDebugName(1) == name
    ]
    if not served:
        print(
            f"{family.out}: в {served_dir} нет файлов «{name}» — сверять не с чем", file=sys.stderr
        )
        return 1
    mismatches = 0
    checked = 0
    for weight in family.check_weights:
        mine = outlines(TTFont(ours), weight)
        for path in served:
            for codepoint, glyph in outlines(TTFont(path), weight).items():
                checked += 1
                if mine.get(codepoint) != glyph:
                    mismatches += 1
                    print(f"  расхождение: {family.out} U+{codepoint:04X} на весе {weight}")
    print(
        f"{family.out}: {len(served)} файлов Google, {checked} сверок символ×вес, "
        f"расхождений {mismatches}"
    )
    return mismatches


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        type=Path,
        default=None,
        help="Каталог с файлами Google Fonts (.next/static/media сборки на next/font/google)",
    )
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for family in FAMILIES:
            out = build(family, Path(tmp))
            size = out.stat().st_size
            print(f"{out.relative_to(OUT_DIR.parents[3])}: {size / 1024:.0f} КБ")
            if args.verify is not None:
                failed += verify(family, out, args.verify)
    if failed:
        raise SystemExit(f"расхождений с Google Fonts: {failed}")


if __name__ == "__main__":
    main()
