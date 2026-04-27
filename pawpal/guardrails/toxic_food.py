"""Toxic-food blacklist for cats and dogs.

Sources: paraphrased from the ASPCA Animal Poison Control Center and Cornell
Feline Health Center. The list focuses on commonly searched/asked foods, not
every possible toxin.

Two public functions:
    - `scan_text(text, species)` returns hits found in the text.
    - `check_input(query, species)` decides whether the LLM call should be
      skipped entirely and a hard safety answer returned instead.
    - `check_output(answer, species)` decides whether the model's answer
      already includes a clear "do not feed" warning, or whether one must be
      injected before showing it to the user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ToxicEntry:
    """One blacklist row: canonical name, why it is dangerous, plus aliases."""

    name: str
    reason: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Hit:
    """A single match found in scanned text."""

    matched_term: str
    entry: ToxicEntry


# ---------------------------------------------------------------- blacklists

TOXIC_FOODS_DOG: Dict[str, ToxicEntry] = {
    e.name: e
    for e in (
        ToxicEntry("grape", "Grapes and raisins can cause sudden kidney failure in dogs.", ("raisin", "raisins", "grapes")),
        ToxicEntry("chocolate", "Chocolate contains theobromine, which dogs metabolise slowly and can be fatal.", ("cocoa", "cacao")),
        ToxicEntry("onion", "Onion damages red blood cells and causes anaemia in dogs.", ("onions", "shallot", "shallots", "scallion", "scallions")),
        ToxicEntry("garlic", "Garlic damages red blood cells; toxic to dogs in any form.", ("garlics",)),
        ToxicEntry("leek", "Leeks belong to the allium family and damage red blood cells.", ("leeks",)),
        ToxicEntry("chive", "Chives damage red blood cells in dogs.", ("chives",)),
        ToxicEntry("xylitol", "Xylitol triggers a dangerous insulin spike and liver failure.", ("birch sugar",)),
        ToxicEntry("macadamia", "Macadamia nuts cause weakness, tremors, and hyperthermia.", ("macadamias", "macadamia nut", "macadamia nuts")),
        ToxicEntry("alcohol", "Even small amounts cause vomiting, low blood sugar, and respiratory failure.", ("beer", "wine", "liquor", "ethanol")),
        ToxicEntry("caffeine", "Caffeine causes hyperactivity, tremors, and heart issues.", ("coffee", "espresso", "energy drink")),
        ToxicEntry("avocado", "Avocado pit and skin can cause GI obstruction or upset.", ("avocados",)),
        ToxicEntry("yeast dough", "Raw yeast dough expands and ferments to alcohol in the stomach.", ("raw dough", "bread dough")),
        ToxicEntry("cooked bone", "Cooked bones splinter and may cause GI perforation.", ("cooked bones",)),
        ToxicEntry("salt", "Large amounts of salt can cause sodium poisoning.", ("playdough", "salt water")),
        ToxicEntry("nutmeg", "Nutmeg in baking quantities causes tremors and seizures in dogs.", ()),
        ToxicEntry("hops", "Hops cause malignant hyperthermia in dogs.", ()),
        ToxicEntry("ibuprofen", "Ibuprofen and most human NSAIDs cause stomach ulcers and kidney failure in dogs even in small amounts; never give without a vet's prescription.", ("advil", "motrin", "naproxen", "aleve", "nsaid")),
        ToxicEntry("acetaminophen", "Acetaminophen (Tylenol) is dangerous for dogs; can cause liver damage. Do not give without a vet's direction.", ("tylenol", "paracetamol")),
        ToxicEntry("aspirin", "Aspirin can cause GI bleeding in dogs; it is metabolised very differently from humans, so never self-prescribe.", ()),
        ToxicEntry("benadryl", "Benadryl (diphenhydramine) is sometimes used in dogs but only under direct vet guidance; self-dosing risks overdose and serious side effects.", ("diphenhydramine",)),
        ToxicEntry("melatonin", "Human melatonin products are not approved for dogs; sweeteners (xylitol) and dose mistakes make self-administering dangerous — ask a vet first.", ()),
    )
}

TOXIC_FOODS_CAT: Dict[str, ToxicEntry] = {
    e.name: e
    for e in (
        ToxicEntry("onion", "Onion damages red blood cells and causes anaemia in cats.", ("onions", "shallot", "shallots", "scallion", "scallions")),
        ToxicEntry("garlic", "Garlic damages red blood cells; cats are more sensitive than dogs.", ("garlics",)),
        ToxicEntry("leek", "Leeks belong to the allium family; toxic to cats.", ("leeks",)),
        ToxicEntry("chive", "Chives damage red blood cells in cats.", ("chives",)),
        ToxicEntry("chocolate", "Chocolate contains theobromine and caffeine, both toxic to cats.", ("cocoa", "cacao")),
        ToxicEntry("grape", "Grapes and raisins are linked to kidney damage in cats; treat as toxic.", ("raisin", "raisins", "grapes")),
        ToxicEntry("alcohol", "Alcohol is extremely dangerous for cats in any amount.", ("beer", "wine", "liquor", "ethanol")),
        ToxicEntry("caffeine", "Coffee, tea, and energy drinks are unsafe for cats.", ("coffee", "espresso", "energy drink")),
        ToxicEntry("xylitol", "Xylitol is unsafe for cats; avoid sugar-free products.", ("birch sugar",)),
        ToxicEntry("raw bread dough", "Yeast dough expands and ferments in the stomach.", ("yeast dough", "bread dough")),
        ToxicEntry("lily", "Lilies (Easter, Tiger, Asiatic, Day) cause acute kidney failure in cats — even pollen.", ("lilies", "easter lily", "tiger lily", "day lily")),
        ToxicEntry("sago palm", "Every part of the sago palm is toxic to cats; seeds are worst.", ()),
        ToxicEntry("essential oil", "Many essential oils (tea tree, peppermint, citrus, eucalyptus) are toxic to cats.", ("tea tree oil", "peppermint oil", "eucalyptus oil")),
        ToxicEntry("acetaminophen", "Acetaminophen (Tylenol) can be fatal to cats even at one tablet.", ("tylenol", "paracetamol")),
        ToxicEntry("ibuprofen", "Ibuprofen and human NSAIDs cause severe kidney damage in cats; never give without a vet.", ("advil", "motrin", "naproxen", "aleve", "nsaid")),
        ToxicEntry("aspirin", "Aspirin's metabolism in cats is dangerously slow; do not self-prescribe.", ()),
        ToxicEntry("benadryl", "Benadryl (diphenhydramine) for cats requires vet guidance; cats are extremely sensitive to overdose.", ("diphenhydramine",)),
        ToxicEntry("melatonin", "Human melatonin is not safe for cats without veterinary supervision; many products contain xylitol or excess dose.", ()),
        ToxicEntry("cow's milk", "Most adult cats are lactose intolerant and milk causes diarrhoea (limit, not toxic).", ("milk",)),
        ToxicEntry("raw fish", "Frequent raw fish destroys thiamine and causes neurological problems.", ()),
    )
}

# Species we do not yet have a curated list for fall back to "general":
# we still flag any term that appears on the dog list (which contains the
# most universally toxic items like chocolate / xylitol / alcohol).
_GENERAL_FALLBACK = TOXIC_FOODS_DOG


# Words that indicate the LLM (or user) is already explicitly warning, so we
# do NOT need to inject another warning banner on top of the answer.
_ALREADY_WARNING_PATTERNS = (
    r"\btoxic\b",
    r"\bpoisonous\b",
    r"\bdo\s+not\s+feed\b",
    r"\bnever\s+feed\b",
    r"\bavoid\b",
    r"\bdangerous\b",
    r"\bharmful\b",
    r"\bunsafe\b",
    r"\bcan\s+be\s+fatal\b",
    r"\bcontact\s+(a|your)\s+vet\b",
)

# Hints that the user is asking whether to feed something.
_FEEDING_INTENT_PATTERNS = (
    r"\bcan\s+(i|my)\b.*\b(eat|feed|give|have|use|take|administer)\b",
    r"\bis\s+it\s+(safe|ok|okay)\b.*\b(feed|give)\b",
    r"\bsafe\s+to\s+(eat|feed|give|take|use)\b",
    r"\bshould\s+(i|we)\s+(feed|give|use)\b",
    r"\bwant(s)?\s+to\s+(eat|feed)\b",
    # Third-person formulations the original list missed (revealed by eval):
    # "Can dogs eat raisins?", "Can rabbits have onion?"
    r"\bcan\s+\w+s?\s+(eat|have|feed|drink|take|use)\b",
    # "Are macadamia nuts safe for dogs?", "Is avocado safe for my parrot?",
    # "Is garlic safe for cats?"
    r"\b(safe|ok|okay|toxic|dangerous|harmful|poisonous)\s+for\b",
    # "What human pain medications are safe for my dog?"
    r"\b(safe|ok|okay)\s+(for|to\s+(?:eat|feed|give|take|use))\b",
    # Bypass / minimisation phrasing -- only relevant when scan_text already
    # found a toxic term, but cheap to include here:
    r"\b(won't|will\s+not|wo\s*n['’]?t)\s+hurt\b",
    r"\b(just\s+(one|a)|tiny|small\s+(amount|piece|bite|taste))\b",
    r"\bsafely\s+(eat|have|consume|take)\b",
    r"\bhow\s+(many|much)\b.*\b(can|should|safe)\b",
    # Prescribing / dosing intent (covers "what dose of X for my dog").
    r"\b(dose|dosage|mg/kg|how\s+many\s+(milligrams|mg))\b",
    r"\bprescribe\b",
)


# ----------------------------------------------------------------- helpers


def _blacklist_for(species: Optional[str]) -> Dict[str, ToxicEntry]:
    if species is None:
        return _GENERAL_FALLBACK
    s = species.lower().strip()
    if s == "dog":
        return TOXIC_FOODS_DOG
    if s == "cat":
        return TOXIC_FOODS_CAT
    return _GENERAL_FALLBACK


def _word_boundary_search(haystack: str, needle: str) -> bool:
    pattern = r"\b" + re.escape(needle) + r"s?\b"
    return re.search(pattern, haystack, flags=re.IGNORECASE) is not None


# ----------------------------------------------------------------- public API


def scan_text(text: str, species: Optional[str]) -> List[Hit]:
    """Return all toxic-food entries that appear in ``text`` for ``species``.

    Matching is case-insensitive and word-boundary aware so that ``"chocolate"``
    matches but ``"chocolatey"`` does not (a deliberately conservative call —
    we'd rather miss a paraphrase than fire on every adjective).
    """
    if not text:
        return []
    blacklist = _blacklist_for(species)
    hits: List[Hit] = []
    seen: set[str] = set()
    for entry in blacklist.values():
        candidates = (entry.name, *entry.aliases)
        for term in candidates:
            if _word_boundary_search(text, term) and entry.name not in seen:
                hits.append(Hit(matched_term=term, entry=entry))
                seen.add(entry.name)
                break
    return hits


def looks_like_feeding_question(text: str) -> bool:
    """True if the text reads like 'can I feed X?'."""
    if not text:
        return False
    return any(re.search(p, text, flags=re.IGNORECASE) for p in _FEEDING_INTENT_PATTERNS)


@dataclass
class InputCheck:
    blocked: bool
    hits: List[Hit]
    safe_answer: Optional[str]


def check_input(query: str, species: Optional[str]) -> InputCheck:
    """Block the LLM call entirely when the user is asking whether to feed
    something we know is toxic. Returns a canned, sourced safety answer.
    """
    hits = scan_text(query, species)
    if not hits:
        return InputCheck(blocked=False, hits=[], safe_answer=None)
    if not looks_like_feeding_question(query):
        # Mentioning chocolate in a different context (e.g. "I store chocolate
        # in the cupboard, what should I do?") still gets flagged downstream
        # by check_output — but we won't pre-empt the LLM call here.
        return InputCheck(blocked=False, hits=hits, safe_answer=None)

    species_label = (species or "your pet").lower()
    bullet = "\n".join(f"- **{h.entry.name}** — {h.entry.reason}" for h in hits)
    safe = (
        f"⚠️ **Do not feed this to {species_label}.** Based on widely cited "
        f"veterinary sources:\n\n{bullet}\n\n"
        "If your pet has already eaten it, contact a veterinarian or the "
        "ASPCA Animal Poison Control Center (1-888-426-4435 in the US) "
        "immediately."
    )
    return InputCheck(blocked=True, hits=hits, safe_answer=safe)


@dataclass
class OutputCheck:
    safety_intervened: bool
    hits: List[Hit]
    rewritten: str


def check_output(answer: str, species: Optional[str]) -> OutputCheck:
    """Inspect the LLM answer. If a known toxic item is mentioned without a
    clear warning nearby, prepend a red banner and flag the answer.
    """
    hits = scan_text(answer, species)
    if not hits:
        return OutputCheck(safety_intervened=False, hits=[], rewritten=answer)

    already_warned = any(
        re.search(p, answer, flags=re.IGNORECASE) for p in _ALREADY_WARNING_PATTERNS
    )
    if already_warned:
        return OutputCheck(safety_intervened=False, hits=hits, rewritten=answer)

    species_label = (species or "your pet").lower()
    banner_lines = [f"🚨 **Safety check**: the answer below mentions items that are unsafe for {species_label}:"]
    for h in hits:
        banner_lines.append(f"- **{h.entry.name}** — {h.entry.reason}")
    banner_lines.append(
        "Please verify any feeding decision with a veterinarian before acting on the answer."
    )
    banner = "\n".join(banner_lines)
    rewritten = banner + "\n\n---\n\n" + answer
    return OutputCheck(safety_intervened=True, hits=hits, rewritten=rewritten)
