"""Cleaning of profile_text — examples taken verbatim from the SFR-0 corpus."""

from sfr_match.cleaning import clean_profile_text, has_latex, is_author_list, strip_latex

# Real fragment from the BESIII profile (P. Egorov) in data/exports/profiles.jsonl.
BESIII = (
    "Using a sample of $(10.09\\ifmmode\\pm\\else\\textpm\\fi{}0.04)"
    "\\ifmmode\\times\\else\\texttimes\\fi{}{10}^{9}\\text{ }\\text{ }"
    "J/\\ensuremath{\\psi}$ events collected with the BESIII detector"
)
# Real fragment from the graphene profile (Dmitry Yu. Usachov).
BORON_NITRIDE = "hexagonal boron nitride ($h$-BN) from tight chemical bonding to a Ni(111) film"
# Real fragment from a BESIII title-abstract with an inline reaction.
REACTION = "${e}^{+}{e}^{\\ensuremath{-}}\\ensuremath{\\rightarrow}\\ensuremath{\\gamma}X"
# Real fragment from the ATLAS profile (N. Nikitin).
ATLAS_AUTHORS = (
    "Author(s): Collaboration, The ATLAS; Aad, G; Abat, E; Abdallah, J; Abdelalim, AA; "
    "Abdesselam, A; Abdinov, O; Abi, BA; Abolins, M; Abramowicz, H"
)


def test_latex_math_becomes_readable_text() -> None:
    assert strip_latex(BESIII) == (
        "Using a sample of (10.09±0.04)×10^9 J/ψ events collected with the BESIII detector"
    )


def test_inline_math_delimiters_do_not_eat_the_word() -> None:
    assert strip_latex(BORON_NITRIDE) == (
        "hexagonal boron nitride (h-BN) from tight chemical bonding to a Ni(111) film"
    )


def test_reaction_keeps_particles_and_arrow() -> None:
    assert strip_latex(REACTION) == "e^+e^-→γX"


def test_text_without_latex_is_returned_unchanged() -> None:
    text = "Мы измеряем массу бозона Хиггса в распадах на четыре лептона."
    assert strip_latex(text) == text
    assert not has_latex(text)


def test_unknown_command_is_dropped_but_keeps_word_boundary() -> None:
    assert strip_latex("first\\qquad second") == "first second"


def test_explicit_author_list_marker() -> None:
    assert is_author_list(ATLAS_AUTHORS)


def test_bare_author_list_without_marker() -> None:
    assert is_author_list("Aad, G; Abat, E; Abdallah, J; Abdelalim, AA; Abdesselam, A")


def test_abstract_mentioning_a_name_is_not_an_author_list() -> None:
    text = (
        "We report a measurement of the Higgs boson mass following the method of Smith, J; "
        "the systematic uncertainty is dominated by the calorimeter calibration."
    )
    assert not is_author_list(text)


def test_empty_fragment_is_not_an_author_list() -> None:
    assert not is_author_list("   ")


def test_clean_profile_text_drops_author_list_but_keeps_the_title() -> None:
    profile = (
        "N. Nikitin — Московский физико-технический институт. h-index: 60.\n"
        "Ключевые темы: Particle physics theoretical and experimental studies.\n"
        f"«The ATLAS Experiment at the CERN Large Hadron Collider» (2008). {ATLAS_AUTHORS}…\n"
        "«Test of Lepton Universality Using B+ → K+ ℓ+ ℓ− Decays» (2014). A measurement of…"
    )
    cleaned = clean_profile_text(profile)
    assert "«The ATLAS Experiment at the CERN Large Hadron Collider» (2008)." in cleaned
    assert "Abdelalim" not in cleaned
    assert "Test of Lepton Universality" in cleaned
    assert "A measurement of…" in cleaned


def test_clean_profile_text_keeps_structure_and_strips_latex() -> None:
    profile = (
        f"A. Author — МФТИ. h-index: 10.\nКлючевые темы: Particle physics.\n«T» (2020). {BESIII}"
    )
    cleaned = clean_profile_text(profile)
    assert len(cleaned.split("\n")) == 3
    assert "\\ensuremath" not in cleaned
    assert "J/ψ events" in cleaned
