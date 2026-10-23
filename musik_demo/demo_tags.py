"""Ersatz für echte Audio-Tags: Eine .demo-Datei enthält Zeilen wie "artist=…".

Nur für Demo und Tests – die echte App schreibt ID3/FLAC-Tags mit mutagen.
"""
from __future__ import annotations

from pathlib import Path


class TextTags:
    def read_artist(self, path: Path) -> str:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("artist="):
                return line.split("=", 1)[1]
        return ""

    def write_artist(self, path: Path, artist: str) -> None:
        lines = path.read_text(encoding="utf-8").splitlines()
        lines = [f"artist={artist}" if line.startswith("artist=") else line for line in lines]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_track(folder: Path, name: str, artist: str, title: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.demo"
    path.write_text(f"artist={artist}\ntitle={title}\n", encoding="utf-8")
    return path
