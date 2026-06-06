#!/usr/bin/env python3
"""Multilingual name handling for the BedRock cleanup stage.

Three jobs:
  1. split_bilingual()  — pull name:en / name:am / name:om out of a single source
     string that mixes scripts (Fayda packs both into one field, separated by / | -).
  2. translate_am()     — Amharic for a label, via the curated bounded-vocabulary lookup
     (lookups/am_vocab.json); falls back to transliteration for residual tokens.
  3. translit_lat2eth() — approximate Latin -> Ethiopic (fidel) transliteration, so every
     feature can carry a name:am even when no real Amharic exists (flagged as approximate).

The source of every name:am (data | vocab | translit) is reported by verify_osm.py.
"""
import json, os, re, functools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOCAB_PATH = os.path.join(ROOT, "lookups", "am_vocab.json")

ETHIOPIC = (0x1200, 0x137F)          # Ethiopic Unicode block
_SEP = re.compile(r"\s*[/|]\s*|\s+[-–]\s+")   # Fayda separators: / | and spaced hyphen/en-dash

def is_ethiopic(s):
    return any(ETHIOPIC[0] <= ord(c) <= ETHIOPIC[1] for c in s)

def _clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())

def split_bilingual(raw):
    """Split a mixed-script source name into {'en':..., 'am':...} (either may be '')."""
    raw = _clean(raw)
    if not raw:
        return {"en": "", "am": ""}
    parts = [p.strip() for p in _SEP.split(raw) if p and p.strip()]
    if len(parts) <= 1:                       # single script -> classify the whole thing
        return {"am": raw, "en": ""} if is_ethiopic(raw) else {"en": raw, "am": ""}
    am = " ".join(p for p in parts if is_ethiopic(p))
    en = " ".join(p for p in parts if not is_ethiopic(p))
    return {"en": _clean(en), "am": _clean(am)}

@functools.lru_cache(maxsize=1)
def _vocab():
    try:
        return {k.lower(): v for k, v in json.load(open(VOCAB_PATH, encoding="utf-8")).items()}
    except Exception:
        return {}

# --- approximate Latin -> Ethiopic transliteration -------------------------------------
# Ethiopic syllables are consonant+vowel. We map a base consonant to its 7 orders
# (ä u i a e ə o) and assemble syllables from a romanized token. Approximate by design.
_ORDERS = "ä u i a e ə o".split()          # index 0..6 ; order 6 used for bare consonant
_BASE = {  # consonant -> first-order (ä) codepoint; orders are +0..+6
    "h": 0x1200, "l": 0x1208, "m": 0x1218, "r": 0x1228, "s": 0x1230, "sh": 0x1238,
    "q": 0x1240, "b": 0x1260, "v": 0x1268, "t": 0x1270, "c": 0x1290, "ch": 0x1278,
    "n": 0x1290, "ny": 0x1298, "k": 0x12A8, "w": 0x12C8, "z": 0x12D8, "zh": 0x12E0,
    "y": 0x12E8, "d": 0x12F0, "j": 0x1300, "g": 0x1308, "f": 0x1348, "p": 0x1350,
    "ts": 0x1338, "x": 0x1238,
}
_VOWEL_ORDER = {"a": 3, "e": 4, "i": 2, "o": 6, "u": 1, "ə": 5, "": 6}
_GLOTTAL = {"a": 0x12A0, "e": 0x12A4, "i": 0x12A2, "o": 0x12A6, "u": 0x12A1, "": 0x12A5}
_CONS = sorted(_BASE, key=len, reverse=True)     # match digraphs (sh, ch..) before singles

def translit_lat2eth(text):
    """Very approximate romanized-Amharic -> fidel. Returns '' if nothing transliterable."""
    out, words = [], re.findall(r"[A-Za-z]+|\d+|[^\sA-Za-z\d]+", text or "")
    for w in words:
        if not w.isalpha():
            out.append(w); continue
        s, i, syll = w.lower(), 0, []
        while i < len(s):
            cons = next((c for c in _CONS if s.startswith(c, i)), None)
            if cons:
                i += len(cons)
                vowel = s[i] if i < len(s) and s[i] in "aeiou" else ""
                if vowel: i += 1
                syll.append(chr(_BASE[cons] + _VOWEL_ORDER.get(vowel, 6)))
            elif s[i] in "aeiou":               # bare/leading vowel -> glottal series
                syll.append(chr(_GLOTTAL.get(s[i], _GLOTTAL[""]))); i += 1
            else:
                i += 1                           # skip anything unmappable
        out.append("".join(syll) or w)
    return _clean(" ".join(out))

def translate_am(text, fallback_translit=True):
    """Amharic for an English/Latin label: whole-string vocab hit, else per-token vocab +
    transliteration of the remainder. Returns ('', source) where source in
    {'', 'vocab', 'translit'} so callers can report provenance."""
    text = _clean(text)
    if not text:
        return "", ""
    if is_ethiopic(text):                       # already Amharic
        return text, "data"
    v = _vocab()
    if text.lower() in v:
        return v[text.lower()], "vocab"
    toks, src_vocab = text.split(" "), False
    rendered = []
    for t in toks:
        key = t.lower().strip(".,()")
        if key in v:
            rendered.append(v[key]); src_vocab = True
        elif fallback_translit:
            rendered.append(translit_lat2eth(t))
        else:
            rendered.append("")
    am = _clean(" ".join(x for x in rendered if x))
    if not am:
        return "", ""
    return am, ("vocab" if src_vocab and not fallback_translit else
                ("mixed" if src_vocab else "translit"))

def names_for(en="", am="", om="", primary="am"):
    """Assemble the OSM name tag set. `name` = primary lang if present, else the other."""
    en, am, om = _clean(en), _clean(am), _clean(om)
    tags = {}
    if en: tags["name:en"] = en
    if am: tags["name:am"] = am
    if om: tags["name:om"] = om
    main = (am if primary == "am" else en) or en or am or om
    if main: tags["name"] = main
    return tags
