from pathlib import Path
import os
import tempfile
import unittest

from musik_demo.correction import describe, execute, plan_correction
from musik_demo.demo_tags import TextTags, make_track


class FailOnNth(TextTags):
    def __init__(self, n, half_write=False):
        self.n, self.calls, self.half_write = n, 0, half_write

    def write_artist(self, path, artist):
        self.calls += 1
        if self.calls == self.n:
            if self.half_write:
                path.write_text("artist=KAPUTT", encoding="utf-8")
            raise OSError("simulierter Schreibfehler")
        super().write_artist(path, artist)


class CorrectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / "Brinstorm"
        album = self.folder / "2024 - Album"
        self.tracks = [make_track(album, f"0{i}", a, f"Titel {i}")
                       for i, a in enumerate(["Brinstorm", "Brinstorm", "Brinstorm feat. Gast", "brinstorm"], start=1)]
        self.tags = TextTags()

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self):
        return sorted((str(p.relative_to(self.root)), p.read_text(encoding="utf-8")) for p in self.root.rglob("*.demo"))

    def test_plan_changes_nothing_and_skips_guest_artists(self):
        before = self.snapshot()
        plan = plan_correction(self.folder, {"Brinstorm"}, "Brainstorm", self.tags)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(plan.tag_changes), 3)  # Groß/klein egal, Gastmusiker nicht
        self.assertEqual(plan.untouched_artists, ["Brinstorm feat. Gast"])
        self.assertIn("[PLAN] Ordner Brinstorm → Brainstorm", describe(plan))

    def test_successful_correction(self):
        plan = plan_correction(self.folder, {"Brinstorm"}, "Brainstorm", self.tags)
        execute(plan, self.tags, report=lambda _: None)
        new_folder = self.root / "Brainstorm"
        self.assertTrue(new_folder.is_dir())
        self.assertFalse(self.folder.exists())
        artists = sorted(self.tags.read_artist(p) for p in new_folder.rglob("*.demo"))
        self.assertEqual(artists, ["Brainstorm", "Brainstorm", "Brainstorm", "Brinstorm feat. Gast"])

    def test_write_error_rolls_back_everything(self):
        before = self.snapshot()
        plan = plan_correction(self.folder, {"Brinstorm"}, "Brainstorm", self.tags)
        with self.assertRaises(OSError):
            execute(plan, FailOnNth(3), report=lambda _: None)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.folder.is_dir())

    def test_half_written_file_is_restored(self):
        before = self.snapshot()
        plan = plan_correction(self.folder, {"Brinstorm"}, "Brainstorm", self.tags)
        with self.assertRaises(OSError):
            execute(plan, FailOnNth(2, half_write=True), report=lambda _: None)
        self.assertEqual(self.snapshot(), before)

    def test_cancel_rolls_back(self):
        before = self.snapshot()
        plan = plan_correction(self.folder, {"Brinstorm"}, "Brainstorm", self.tags)
        calls = iter([False, False, True])
        with self.assertRaises(InterruptedError):
            execute(plan, self.tags, report=lambda _: None, cancelled=lambda: next(calls, True))
        self.assertEqual(self.snapshot(), before)

    def test_file_changed_after_plan_blocks_before_any_write(self):
        plan = plan_correction(self.folder, {"Brinstorm"}, "Brainstorm", self.tags)
        self.tracks[1].write_text("artist=Brinstorm\ntitle=geändert von außen, länger\n", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "seit der Prüfung geändert"):
            execute(plan, self.tags, report=lambda _: None)
        self.assertEqual(self.snapshot(), before)

    def test_existing_target_folder_is_never_merged(self):
        (self.root / "brainstorm").mkdir()
        with self.assertRaisesRegex(ValueError, "nie automatisch zusammengeführt"):
            plan_correction(self.folder, {"Brinstorm"}, "Brainstorm", self.tags)

    def test_trailing_dot_name_needs_no_folder_rename(self):
        folder = self.root / "A.C.A.B"
        make_track(folder, "01", "A.C.A.B", "x")
        plan = plan_correction(folder, {"A.C.A.B"}, "A.C.A.B.", self.tags)
        self.assertFalse(plan.renames_folder)
        self.assertEqual(plan.tag_changes, [])

    @unittest.skipIf(os.name == "nt", "Symlinks unter Windows brauchen Adminrechte")
    def test_symlink_source_rejected(self):
        link = self.root / "Link"
        link.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "nicht verfügbar"):
            plan_correction(link, {"Brinstorm"}, "Brainstorm", self.tags)


if __name__ == "__main__":
    unittest.main()
