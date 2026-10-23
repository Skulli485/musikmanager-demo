"""Bestätigte Künstlerkorrektur als Gruppe – mit Probelauf und vollständigem Rückrollen.

Auszug aus dem Musikmanager (v11.21), für die Demo vereinfacht:
In der echten App werden ID3/FLAC-Tags mit mutagen geschrieben und der neue
Name stammt aus einem vom Menschen ausgewählten MusicBrainz-Treffer. Hier ist
das Tag-Lesen/-Schreiben austauschbar, damit die Demo ohne Audiodateien läuft.

Ablauf:
  plan    – alles prüfen, nichts ändern (Zielkollision, Dateifingerabdruck, betroffene Dateien)
  execute – Rückrollkopien anlegen und per SHA-256 bestätigen, Tags schreiben,
            Ordner umbenennen. Bei *jedem* Fehler wird in umgekehrter Reihenfolge
            zurückgerollt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import shutil
import tempfile
from typing import Callable, Protocol

from .names import collapse_spaces, folder_name_for_artist, normalized_windows_folder

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".demo"}


class TagIO(Protocol):
    def read_artist(self, path: Path) -> str: ...
    def write_artist(self, path: Path, artist: str) -> None: ...


@dataclass
class TagChange:
    path: Path
    relative: Path
    old_artist: str
    fingerprint: tuple[int, int]
    backup: Path | None = None


@dataclass
class CorrectionPlan:
    artist_name: str
    source: Path
    destination: Path
    tag_changes: list[TagChange] = field(default_factory=list)
    untouched_artists: list[str] = field(default_factory=list)

    @property
    def renames_folder(self) -> bool:
        return self.source != self.destination


def _audio_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)


def _fingerprint(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_size, st.st_mtime_ns


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plan_correction(folder: Path, old_names: set[str], approved_name: str, tags: TagIO) -> CorrectionPlan:
    """Prüft vollständig, bevor irgendetwas geschrieben wird."""
    artist_name = collapse_spaces(approved_name)
    if not artist_name:
        raise ValueError("Kein bestätigter Künstlername.")
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError(f"Quellordner ist nicht verfügbar: {folder}")

    destination = folder.with_name(folder_name_for_artist(artist_name))
    if destination != folder and any(p != folder and p.name.casefold() == destination.name.casefold()
                                     for p in folder.parent.iterdir()):
        raise ValueError(f"Zielordner existiert bereits: {destination.name}. "
                         "Ordner werden nie automatisch zusammengeführt.")

    plan = CorrectionPlan(artist_name, folder, destination)
    old_keys = {normalized_windows_folder(n) for n in old_names}
    target_key = normalized_windows_folder(artist_name)
    untouched = set()
    for path in _audio_files(folder):
        current = collapse_spaces(tags.read_artist(path))
        key = normalized_windows_folder(current)
        if not current or key == target_key:
            continue
        if key not in old_keys:
            # Gastmusiker, Split-Releases usw. bleiben unangetastet
            untouched.add(current)
            continue
        plan.tag_changes.append(TagChange(path, path.relative_to(folder), current, _fingerprint(path)))
    plan.untouched_artists = sorted(untouched)
    return plan


def describe(plan: CorrectionPlan) -> list[str]:
    """Probelauf: zeigt, was passieren würde – ändert nichts."""
    lines = [f"[PLAN] Interpret → {plan.artist_name}"]
    lines += [f"[PLAN] Tag {c.relative}: {c.old_artist} → {plan.artist_name}" for c in plan.tag_changes]
    if plan.renames_folder:
        lines.append(f"[PLAN] Ordner {plan.source.name} → {plan.destination.name}")
    lines += [f"[UNVERÄNDERT] {a}" for a in plan.untouched_artists]
    return lines


def execute(plan: CorrectionPlan, tags: TagIO, report: Callable[[str], None] = print,
            cancelled: Callable[[], bool] = lambda: False) -> bool:
    """Führt den Plan aus. Gibt True zurück oder rollt vollständig zurück und wirft den Fehler weiter."""
    changed: list[TagChange] = []
    renamed = False
    with tempfile.TemporaryDirectory(prefix="musikmanager-rollback-") as tmp:
        backup_dir = Path(tmp)
        try:
            # 1. Erst ALLE Rückrollkopien anlegen und bestätigen, dann schreiben.
            for index, change in enumerate(plan.tag_changes):
                if _fingerprint(change.path) != change.fingerprint:
                    raise ValueError(f"Datei wurde seit der Prüfung geändert: {change.relative}")
                backup = backup_dir / f"{index:06d}{change.path.suffix}"
                shutil.copy2(change.path, backup)
                if _sha256(backup) != _sha256(change.path):
                    raise OSError(f"Rückrollkopie nicht bestätigt: {change.relative}")
                change.backup = backup

            # 2. Tags schreiben
            for change in plan.tag_changes:
                if cancelled():
                    raise InterruptedError("Lauf wurde abgebrochen")
                tags.write_artist(change.path, plan.artist_name)
                changed.append(change)
                report(f"[TAG KORRIGIERT] {change.relative}: {change.old_artist} → {plan.artist_name}")

            # 3. Ordner erst nach erfolgreichen Tagänderungen umbenennen
            if plan.renames_folder:
                if cancelled():
                    raise InterruptedError("Lauf wurde abgebrochen")
                plan.source.rename(plan.destination)
                renamed = True
                report(f"[ORDNER UMBENANNT] {plan.source.name} → {plan.destination.name}")
            return True

        except BaseException as exc:
            errors = []
            if renamed:
                try:
                    plan.destination.rename(plan.source)
                except OSError as err:
                    errors.append(f"Ordner: {err}")
            # Auch die Datei, bei der der Fehler auftrat, kann halb geschrieben sein:
            # jede Datei mit Rückrollkopie wird geprüft und bei Abweichung ersetzt.
            for change in reversed(plan.tag_changes):
                if change.backup is None:
                    continue
                try:
                    if _sha256(change.path) != _sha256(change.backup):
                        shutil.copy2(change.backup, change.path)
                except OSError as err:
                    errors.append(f"{change.relative}: {err}")
            if errors:
                report("[RÜCKROLLEN KRITISCH] " + " | ".join(errors))
            elif changed or renamed:
                report("[RÜCKROLLEN ERFOLGREICH] Alle begonnenen Änderungen wurden zurückgenommen.")
            raise exc
