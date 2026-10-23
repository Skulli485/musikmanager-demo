"""Künstlernamen vergleichen und als sichere Windows-Ordnernamen schreiben.

Auszug aus dem Musikmanager (v11.21).
"""
from __future__ import annotations

from collections import Counter
import re
import unicodedata

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def collapse_spaces(value) -> str:
    return " ".join(str(value or "").split())


def normalized(value) -> str:
    """Vergleichsschlüssel: Unicode-NFC, Unterstrich = Leerzeichen, ohne Groß/klein."""
    return collapse_spaces(unicodedata.normalize("NFC", str(value)).replace("_", " ")).casefold()


def normalized_windows_folder(value) -> str:
    """Windows kann keinen Ordner "A.C.A.B." speichern – nur "A.C.A.B".
    Beide Schreibweisen gelten daher als derselbe Name."""
    return normalized(value).rstrip(" .")


def windows_safe_folder_name(value) -> str:
    """Gibt die unter Windows darstellbare Form zurück oder lehnt den Namen ab."""
    name = unicodedata.normalize("NFC", str(value)).strip().rstrip(" .")
    stem = name.split(".", 1)[0].upper()
    if not name or name in {".", ".."} or FORBIDDEN.search(name) or stem in WINDOWS_RESERVED_NAMES:
        raise ValueError("Ungültiger Windows-Ordnername.")
    return name


def folder_name_for_artist(value) -> str:
    """Deterministische Ordnerschreibweise aus einem Datenbanknamen – Tags bleiben unverändert."""
    name = unicodedata.normalize("NFC", collapse_spaces(value))
    name = FORBIDDEN.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(" .")
    if not name:
        raise ValueError("Der Datenbankname ergibt keinen gültigen Ordnernamen.")
    if name.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES:
        name = "_" + name
    return windows_safe_folder_name(name)


def consensus(values) -> str:
    """Ein lokaler Name gilt nur als *Hinweis*, wenn mindestens drei Dateien
    einheitlich dasselbe sagen. Er wird trotzdem nie automatisch übernommen –
    derselbe Tippfehler in vielen Dateien macht ihn nicht richtig."""
    counts = Counter(normalized(v) for v in values if collapse_spaces(v))
    if not counts:
        return ""
    key, count = counts.most_common(1)[0]
    if count < 3 or len(counts) != 1:
        return ""
    return next(v for v in values if normalized(v) == key)
