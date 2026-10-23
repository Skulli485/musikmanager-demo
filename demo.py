"""Korrigiert einen Tippfehler im Künstlernamen einer erfundenen Testbibliothek.

    python demo.py

Läuft in einem temporären Ordner, verändert nichts auf deinem Rechner.
"""
from pathlib import Path
import tempfile

from musik_demo.correction import describe, execute, plan_correction
from musik_demo.demo_tags import TextTags, make_track
from musik_demo.names import consensus, folder_name_for_artist


class FailingTags(TextTags):
    """Simuliert einen Schreibfehler bei der zweiten Datei."""
    def __init__(self):
        self.calls = 0

    def write_artist(self, path, artist):
        self.calls += 1
        if self.calls == 2:
            raise OSError("Datei ist von einem anderen Programm gesperrt")
        super().write_artist(path, artist)


def show(folder: Path, tags: TextTags) -> None:
    for track in sorted(folder.rglob("*.demo")):
        print(f"    {track.relative_to(folder.parent)}  artist={tags.read_artist(track)}")


def main() -> None:
    tags = TextTags()
    with tempfile.TemporaryDirectory() as tmp:
        library = Path(tmp) / "Musik"
        album = library / "Brinstorm" / "2024 - Northern Static"
        make_track(album, "01", "Brinstorm", "Lantern Code")
        make_track(album, "02", "Brinstorm", "Salt Engine")
        make_track(album, "03", "Brinstorm feat. Ada Rook", "Hollow Wire")
        make_track(album, "04", "Brinstorm", "Last Signal")
        folder = library / "Brinstorm"

        print("Ausgangslage:")
        show(folder, tags)
        local = [tags.read_artist(p) for p in folder.rglob("*.demo")]
        print(f"\nLokaler Hinweis (nur Hinweis, kein Beweis): {consensus(local) or '(uneinheitlich)'}")
        print("Bestätigter Datenbankname: Brainstorm\n")

        plan = plan_correction(folder, {"Brinstorm"}, "Brainstorm", tags)
        print("Probelauf:")
        for line in describe(plan):
            print("  " + line)

        print("\nAusführung mit simuliertem Schreibfehler:")
        try:
            execute(plan, FailingTags(), report=lambda m: print("  " + m))
        except OSError as exc:
            print(f"  Fehler: {exc}")
        print("  Bibliothek danach:")
        show(folder, tags)

        print("\nAusführung ohne Fehler:")
        plan = plan_correction(folder, {"Brinstorm"}, "Brainstorm", tags)
        execute(plan, tags, report=lambda m: print("  " + m))
        show(library / "Brainstorm", tags)

    print("\nWindows-Ordnernamen:")
    for name in ["A.C.A.B.", "AC/DC", "Con", "  Booze  +  Glory "]:
        print(f"  {name!r:22} → {folder_name_for_artist(name)!r}")


if __name__ == "__main__":
    main()
