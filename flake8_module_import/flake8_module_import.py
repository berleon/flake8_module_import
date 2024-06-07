from __future__ import annotations

import ast
import importlib.util
from typing import Generator


class ModuleImportChecker:
    name = "flake8-module-import"
    version = "0.1.0"

    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.direct_imports = {
            "pathlib", "typing", "__future__", "dataclasses", "pydantic",
            "collections", "math"
        }

    def is_module(self, module: str, name: str) -> bool:
        """Check if the given name is a submodule of the module."""
        full_name = f"{module}.{name}"
        try:
            return importlib.util.find_spec(full_name) is not None
        except ModuleNotFoundError:
            return False

    def run(
        self,
    ) -> Generator[tuple[int, int, str, type[ModuleImportChecker]], None, None]:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] not in self.direct_imports:
                    for name in node.names:
                        if not self.is_module(node.module, name.name):
                            yield (
                                name.lineno,
                                name.col_offset,
                                f"MIM001 Avoid direct import of '{name.name}' "
                                + f"from '{node.module}', import the module "
                                + "instead",
                                type(self),
                            )


def test_module_import_checker() -> None:
    import ast

    code = """

from __future__ import annotations

from sys import path
from pathlib import Path
import sys

from os.path import join
from os import path

    """
    tree = ast.parse(code)
    checker = ModuleImportChecker(tree)
    errors = list(checker.run())

    error_msg = (
        "MIM001 Avoid direct import of '{}' from '{}', import the module instead"
    )
    assert len(errors) == 2
    assert errors[0] == (
        5,
        16,
        error_msg.format("path", "sys"),
        ModuleImportChecker,
    )

    assert errors[1] == (
        9,
        20,
        error_msg.format("join", "os.path"),
        ModuleImportChecker,
    )

    # Ensure "from os import path" is not flagged as an error
    assert all(error_msg.format("path", "os") not in error for error in errors)


if __name__ == "__main__":
    test_module_import_checker()
