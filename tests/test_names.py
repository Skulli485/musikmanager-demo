import unittest

from musik_demo.names import consensus, folder_name_for_artist, normalized_windows_folder, windows_safe_folder_name


class NamesTest(unittest.TestCase):
    def test_trailing_dot_is_same_windows_name(self):
        self.assertEqual(normalized_windows_folder("A.C.A.B."), normalized_windows_folder("a.c.a.b"))

    def test_folder_name_for_artist(self):
        self.assertEqual(folder_name_for_artist("AC/DC"), "AC_DC")
        self.assertEqual(folder_name_for_artist("  Booze  +  Glory "), "Booze + Glory")
        self.assertEqual(folder_name_for_artist("Con"), "_Con")
        self.assertEqual(folder_name_for_artist("Motörhead"), "Motörhead")

    def test_unsafe_names_rejected(self):
        for name in ("", "..", "a|b", "NUL", "com1.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                windows_safe_folder_name(name)

    def test_consensus_needs_three_matching_values(self):
        self.assertEqual(consensus(["Brinstorm"] * 3), "Brinstorm")
        self.assertEqual(consensus(["Brinstorm"] * 2), "")
        self.assertEqual(consensus(["Brinstorm", "Brinstorm", "Brinstorm", "Brainstorm"]), "")
        self.assertEqual(consensus(["", "  "]), "")


if __name__ == "__main__":
    unittest.main()
