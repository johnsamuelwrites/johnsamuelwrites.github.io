import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "main"))

from abstract.pipe_to_tab import convert_file, pipe_to_tab, pipe_to_tab_line


class PipeToTabTests(unittest.TestCase):
    def test_separator_pipes_become_tabs(self):
        self.assertEqual(
            pipe_to_tab_line('LAST|P40|en:"Games"'),
            'LAST\tP40\ten:"Games"',
        )

    def test_escaped_pipe_inside_value_becomes_literal(self):
        self.assertEqual(
            pipe_to_tab_line('LAST|P40|en:"Model \\| Project 3D"'),
            'LAST\tP40\ten:"Model | Project 3D"',
        )

    def test_backslash_quote_becomes_doubled_quote(self):
        self.assertEqual(
            pipe_to_tab_line('LAST|P40|es:"dice \\"hola\\" ahora"'),
            'LAST\tP40\tes:"dice ""hola"" ahora"',
        )

    def test_escaped_backslash_becomes_single_backslash(self):
        self.assertEqual(
            pipe_to_tab_line('LAST|P40|en:"a\\\\b"'),
            'LAST\tP40\ten:"a\\b"',
        )

    def test_lines_without_values_are_unchanged_apart_from_separators(self):
        self.assertEqual(pipe_to_tab_line("CREATE"), "CREATE")
        self.assertEqual(pipe_to_tab_line("LAST|P8|Q3185"), "LAST\tP8\tQ3185")

    def test_pipe_to_tab_preserves_line_count(self):
        text = 'CREATE\nLAST|Len|"M0001 abstract content"\nLAST|P8|Q3185'
        self.assertEqual(len(pipe_to_tab(text).splitlines()), 3)

    def test_convert_file_writes_tab_separated_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "in.quickstatements"
            destination = root / "out.quickstatements"
            source.write_text('LAST|P40|en:"A \\| B"\n', encoding="utf-8")
            convert_file(source, destination)
            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                'LAST\tP40\ten:"A | B"\n',
            )


if __name__ == "__main__":
    unittest.main()
