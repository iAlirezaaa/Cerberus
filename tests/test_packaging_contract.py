"""Regression checks for the distributable CLI and desktop entry points.

These checks use only the Python standard library and do not start Qt.
"""
from __future__ import annotations

import ast
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def test_public_console_scripts_point_to_real_functions(self):
        scripts = self.config["project"]["scripts"]
        for command in ("cerberus", "cerberus-desktop"):
            with self.subTest(command=command):
                module_name, separator, function_name = scripts[command].partition(":")
                self.assertEqual(separator, ":", "Entry point must use module:function")
                source = ROOT.joinpath(*module_name.split(".")).with_suffix(".py")
                self.assertTrue(source.is_file(), f"Missing entry-point module: {source}")
                tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
                defined = {
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                self.assertIn(function_name, defined, f"Missing entry-point function in {source}")

    def test_gui_dependency_is_optional(self):
        project = self.config["project"]
        self.assertEqual(project.get("dependencies", []), [],
                         "The core must remain installable without GUI dependencies")
        gui = project["optional-dependencies"]["gui"]
        self.assertTrue(any(item.lower().startswith("pyside6") for item in gui))

    def test_package_includes_animation_and_metadata_assets(self):
        patterns = self.config["tool"]["setuptools"]["package-data"]["cerberus"]
        for expected in ("assets/*.json", "assets/gifs/*.gif", "assets/clips/*/*.png"):
            with self.subTest(pattern=expected):
                self.assertIn(expected, patterns)


if __name__ == "__main__":
    unittest.main()
