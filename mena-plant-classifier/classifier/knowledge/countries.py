"""Country lexicon with MENA membership.

Used to detect the study's country from a dedicated country/affiliation field or,
failing that, from the affiliation string / free text. Each entry lists surface
aliases (adjectives, common city→country cues are handled separately) and whether
the country belongs to the Middle East / North Africa region.

MENA membership follows the common "MENA + Turkey/Iran" convention used across
medicinal-plant reviews. The extended tail (Sudan, Mauritania, Somalia,
Djibouti, Comoros) is included because those states appear in Arab-League /
broad-MENA definitions; flip ``mena`` there if a stricter scope is wanted.
"""
from __future__ import annotations

# canonical country -> {"mena": bool, "aliases": [...], "adjectives": [...]}
COUNTRIES: dict[str, dict] = {
    # ---- Core MENA ----------------------------------------------------------
    "Saudi Arabia": {"mena": True, "aliases": ["ksa", "kingdom of saudi arabia"],
                      "adjectives": ["saudi", "saudi arabian"]},
    "Iran": {"mena": True, "aliases": ["islamic republic of iran"],
             "adjectives": ["iranian", "persian"]},
    "Iraq": {"mena": True, "aliases": [], "adjectives": ["iraqi"]},
    "Egypt": {"mena": True, "aliases": [], "adjectives": ["egyptian"]},
    "Turkey": {"mena": True, "aliases": ["turkiye", "türkiye"], "adjectives": ["turkish"]},
    "Jordan": {"mena": True, "aliases": [], "adjectives": ["jordanian"]},
    "Lebanon": {"mena": True, "aliases": [], "adjectives": ["lebanese"]},
    "Syria": {"mena": True, "aliases": ["syrian arab republic"], "adjectives": ["syrian"]},
    "Palestine": {"mena": True, "aliases": ["west bank", "gaza"],
                  "adjectives": ["palestinian"]},
    "Israel": {"mena": True, "aliases": [], "adjectives": ["israeli"]},
    "Yemen": {"mena": True, "aliases": [], "adjectives": ["yemeni"]},
    "Oman": {"mena": True, "aliases": ["sultanate of oman"], "adjectives": ["omani"]},
    "United Arab Emirates": {"mena": True, "aliases": ["uae", "u.a.e", "emirates",
                             "abu dhabi", "dubai", "sharjah"], "adjectives": ["emirati"]},
    "Qatar": {"mena": True, "aliases": [], "adjectives": ["qatari"]},
    "Kuwait": {"mena": True, "aliases": [], "adjectives": ["kuwaiti"]},
    "Bahrain": {"mena": True, "aliases": [], "adjectives": ["bahraini"]},
    "Morocco": {"mena": True, "aliases": [], "adjectives": ["moroccan"]},
    "Algeria": {"mena": True, "aliases": [], "adjectives": ["algerian"]},
    "Tunisia": {"mena": True, "aliases": [], "adjectives": ["tunisian"]},
    "Libya": {"mena": True, "aliases": [], "adjectives": ["libyan"]},
    # ---- Broad / Arab-League MENA -------------------------------------------
    "Sudan": {"mena": True, "aliases": [], "adjectives": ["sudanese"]},
    "Mauritania": {"mena": True, "aliases": [], "adjectives": ["mauritanian"]},
    "Somalia": {"mena": True, "aliases": [], "adjectives": ["somali"]},
    "Djibouti": {"mena": True, "aliases": [], "adjectives": ["djiboutian"]},
    "Comoros": {"mena": True, "aliases": [], "adjectives": ["comorian"]},
    # ---- Frequent NON-MENA contributors (for correct negative labelling) ----
    "India": {"mena": False, "aliases": [], "adjectives": ["indian"]},
    "Pakistan": {"mena": False, "aliases": [], "adjectives": ["pakistani"]},
    "China": {"mena": False, "aliases": ["p.r. china", "pr china"], "adjectives": ["chinese"]},
    "United States": {"mena": False, "aliases": ["usa", "u.s.a", "u.s.", "united states of america"],
                      "adjectives": ["american"]},
    "United Kingdom": {"mena": False, "aliases": ["uk", "u.k.", "england", "scotland", "wales"],
                       "adjectives": ["british", "english"]},
    "Nigeria": {"mena": False, "aliases": [], "adjectives": ["nigerian"]},
    "Malaysia": {"mena": False, "aliases": [], "adjectives": ["malaysian"]},
    "Indonesia": {"mena": False, "aliases": [], "adjectives": ["indonesian"]},
    "Germany": {"mena": False, "aliases": [], "adjectives": ["german"]},
    "France": {"mena": False, "aliases": [], "adjectives": ["french"]},
    "Italy": {"mena": False, "aliases": [], "adjectives": ["italian"]},
    "Spain": {"mena": False, "aliases": [], "adjectives": ["spanish"]},
    "Brazil": {"mena": False, "aliases": [], "adjectives": ["brazilian"]},
    "South Korea": {"mena": False, "aliases": ["korea", "republic of korea"], "adjectives": ["korean"]},
    "Japan": {"mena": False, "aliases": [], "adjectives": ["japanese"]},
    "Ethiopia": {"mena": False, "aliases": [], "adjectives": ["ethiopian"]},
    "South Africa": {"mena": False, "aliases": [], "adjectives": ["south african"]},
    "Bangladesh": {"mena": False, "aliases": [], "adjectives": ["bangladeshi"]},
    "Thailand": {"mena": False, "aliases": [], "adjectives": ["thai"]},
    "Greece": {"mena": False, "aliases": [], "adjectives": ["greek"]},
}


def mena_countries() -> set[str]:
    return {c for c, v in COUNTRIES.items() if v["mena"]}
