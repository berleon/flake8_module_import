from __future__ import annotations
import ast
import importlib.util
import os
from pathlib import Path
import traceback
from typing import Generator


def verbose(message: str, end: str = "\n") -> None:
    """Print message only if FLAKE8_MODULE_IMPORT_VERBOSE env var is set."""
    if os.environ.get("FLAKE8_MODULE_IMPORT_VERBOSE"):
        print(message, end=end)


class ModuleImportChecker:
    name = "flake8-module-import"
    version = "0.1.0"

    def __init__(self, tree: ast.Module, filename: str = "<unknown>") -> None:
        self.tree = tree
        self.filename = filename
        self.direct_imports = {
            "pathlib",
            "typing",
            "__future__",
            "dataclasses",
            "pydantic",
            "collections",
            "math",
            "enum",
            "functools",
            "itertools",
        }
        self.is_init = filename.endswith("__init__.py")
        self.current_module = self.file_path_to_module_path(filename)

    def file_path_to_module_path(self, file_path: str) -> str | None:
        """Convert a file path to a module path by finding package root."""
        if file_path == "<unknown>" or not file_path.endswith(".py"):
            return None

        path = Path(file_path).resolve()

        # Find package root by looking for __init__.py files
        # Start from the file's directory and work upward
        current_dir = path.parent
        package_parts: list[str] = []

        # Collect package parts by walking up directories that contain __init__.py
        while current_dir != current_dir.parent:  # Stop at filesystem root
            init_file = current_dir / "__init__.py"
            if init_file.exists():
                package_parts.insert(0, current_dir.name)
                current_dir = current_dir.parent
            else:
                # Found the package root
                break

        # Only return a module path if the file is within a package structure
        if not package_parts:
            return None

        # Add the module name
        if path.name == "__init__.py":
            # For __init__.py files, use just the package parts
            module_parts = package_parts
        else:
            # For regular .py files, add the filename without extension
            module_parts = package_parts + [path.stem]

        return ".".join(module_parts)

    def resolve_relative_import(
        self,
        module: str | None,
        level: int,
        current_module: str,
    ) -> str | None:
        """Resolve a relative import using level and module to an absolute module path."""
        if not current_module or level == 0:
            return module  # Absolute import

        # Split current module into parts
        current_parts = current_module.split(".")

        # Go up 'level' directories
        if level > len(current_parts):
            verbose(
                f"❌ Invalid relative import: level {level} > {len(current_parts)} parts in {current_module}"
            )
            return None

        # if module is None
        # Calculate target package
        if module is None and self.is_init:
            # If no module is specified, than '.' means the current package and '..' means the parent package
            # -> we need to remove the last 'level' parts
            if level == 1:
                # from . import something
                target_parts = current_parts
            else:
                # from .. import something
                target_parts = current_parts[: -level + 1]
            verbose(
                f"Resolving `from . import`: level={level}, current='{current_parts}' -> '{target_parts}'"
            )
        else:
            # If a module is specified, then '.' means the parent package and '..' means the grandparent package
            # -> do not remove the last part
            target_parts = current_parts[:-level] if level <= len(current_parts) else []

        # Add the module name if it exists
        if module:
            target_parts.append(module)

        result = ".".join(target_parts)
        verbose(
            f"Resolved relative import: level={level}, module='{module}', current='{current_module}' -> '{result}'"
        )
        return result

    def get_import_error(self, module: str | None, name: str, level: int) -> str | None:
        """Check if the given name is a submodule of the module."""
        # Handle relative imports by resolving them to absolute paths
        resolved_module = module
        verbose(f"Checking import '{module}.{name}' (level={level})... ", end="")

        if level > 0:  # Relative import
            current_module = self.file_path_to_module_path(self.filename)
            if current_module:
                resolved_module = self.resolve_relative_import(
                    module, level, current_module
                )
                if not resolved_module:
                    return "invalid relative import"

            else:
                return "unknown current module"

        # Check if the name is actually a submodule
        full_name = f"{resolved_module}.{name}"
        verbose(f"Resolved to '{full_name}'... ", end="")
        try:
            result = importlib.util.find_spec(full_name) is not None
            if result:
                return None  # Valid import, no error
            else:
                # No specs for module, might be a stub or non-existent module
                # We will ignore this case for now
                verbose(f"❌ No spec found for '{full_name}'")
        except ValueError:
            # ValueError can occur of missing .__spec__ (as for stub files)
            verbose(f"💭 ValueError for '{full_name}' -> ignoring")
            return None
        except (ModuleNotFoundError, ImportError):
            if level:
                module_name = "." * level + (module if module else "")
            else:
                module_name = module if module else ""
            return f"Avoid direct import of '{name}' from '{module_name}', import the module instead"

        except Exception as e:
            # Catch-all for unexpected errors
            if os.environ.get("FLAKE8_MODULE_IMPORT_VERBOSE"):
                return (
                    f"Error checking module '{full_name}': {e} "
                    + f"- {traceback.format_exc()}"
                )
            else:
                return "error checking module"

    def run(
        self,
    ) -> Generator[tuple[int, int, str, type[ModuleImportChecker]], None, None]:
        verbose("")
        current_module = self.file_path_to_module_path(self.filename)
        verbose(f"🔍 Checking imports in {self.filename} (module: {current_module})")
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom):
                verbose(
                    f"Checking node: ImportFrom(module='{node.module}', names={[alias.name for alias in node.names]}, level={node.level})"
                )

                # For relative imports (level > 0), always check
                # For absolute imports, check if not in allowlist
                should_check = node.level > 0 or (
                    node.module and node.module.split(".")[0] not in self.direct_imports
                )

                if should_check:
                    for name in node.names:
                        error = self.get_import_error(
                            node.module, name.name, node.level
                        )

                        if error:
                            verbose(f"❌ {error}")
                            yield (
                                node.lineno,
                                node.col_offset,
                                f"MIM001 {error}",
                                type(self),
                            )
                        else:
                            verbose("✅ Valid")


def test_module_import_checker() -> None:
    import ast
    import tempfile
    import sys

    # Enable verbose mode for testing
    os.environ["FLAKE8_MODULE_IMPORT_VERBOSE"] = "1"

    # Create a temporary directory structure to test with
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a package structure
        package_dir = os.path.join(temp_dir, "mypackage")
        os.makedirs(package_dir)

        # Create some modules
        init_file = os.path.join(package_dir, "__init__.py")
        utils_file = os.path.join(package_dir, "utils.py")
        subpackage_dir = os.path.join(package_dir, "subpackage")
        os.makedirs(subpackage_dir)
        sub_init_file = os.path.join(subpackage_dir, "__init__.py")

        # Write some content to create the modules
        with open(init_file, "w") as f:
            f.write("# Package init\n")
        with open(utils_file, "w") as f:
            f.write("def helper_function(): pass\n")
        with open(sub_init_file, "w") as f:
            f.write("# Subpackage init\n")

        # Add the temp directory to sys.path so imports can be resolved
        sys.path.insert(0, temp_dir)

        try:
            # Test code with various import patterns
            code = """
from __future__ import annotations
from pathlib import Path
from typing import List
from sys import path
from os.path import join
from os import path as os_path
from .utils import helper_function
from . import utils
from .subpackage import something
from ..models import state
            """

            tree = ast.parse(code)

            # Test with a file in the package
            test_file = os.path.join(package_dir, "test_module.py")
            checker = ModuleImportChecker(tree, test_file)
            errors = list(checker.run())

            print("Found errors:")
            for error in errors:
                print(f"Line {error[0]}: {error[2]}")

            # Check that we found the expected errors
            error_messages = [error[2] for error in errors]

            # Should flag these imports (not in allowlist and importing specific items)
            assert any("path" in msg and "sys" in msg for msg in error_messages), (
                "Should flag 'from sys import path'"
            )
            assert any("join" in msg and "os.path" in msg for msg in error_messages), (
                "Should flag 'from os.path import join'"
            )
            assert any("helper_function" in msg for msg in error_messages), (
                "Should flag 'from .utils import helper_function'"
            )
            assert any("something" in msg for msg in error_messages), (
                "Should flag 'from .subpackage import something'"
            )
            assert any("state" in msg for msg in error_messages), (
                "Should flag 'from ..models import state'"
            )

            # Should NOT flag these (either in allowlist or importing modules)
            assert not any(
                "Path" in msg and "pathlib" in msg for msg in error_messages
            ), "Should NOT flag 'from pathlib import Path'"
            assert not any(
                "List" in msg and "typing" in msg for msg in error_messages
            ), "Should NOT flag 'from typing import List'"
            assert not any(
                "os_path" in msg and "os" in msg for msg in error_messages
            ), "Should NOT flag 'from os import path'"
            assert not any(
                "utils" in msg and "from '.'" in msg and "import the module" in msg
                for msg in error_messages
            ), "Should NOT flag 'from . import utils'"

            print(f"✅ Test passed! Found {len(errors)} expected errors.")

        finally:
            # Clean up sys.path
            sys.path.remove(temp_dir)

    # Clean up env var
    if "FLAKE8_MODULE_IMPORT_VERBOSE" in os.environ:
        del os.environ["FLAKE8_MODULE_IMPORT_VERBOSE"]


def test_relative_import_resolution():
    """Test the relative import resolution logic."""
    checker = ModuleImportChecker(ast.parse(""), "mypackage/submodule/file.py")

    # Test various relative import scenarios using level parameter
    current_module = "mypackage.submodule.file"

    # from .utils import something -> mypackage.submodule.utils
    result = checker.resolve_relative_import("utils", 1, current_module)
    assert result == "mypackage.submodule.utils", (
        f"Expected 'mypackage.submodule.utils', got '{result}'"
    )

    # from ..parent import something -> mypackage.parent
    result = checker.resolve_relative_import("parent", 2, current_module)
    assert result == "mypackage.parent", f"Expected 'mypackage.parent', got '{result}'"

    # from ... import something -> mypackage (going up 3 levels from file to submodule to mypackage)
    result = checker.resolve_relative_import(None, 3, current_module)
    assert result == "", f"Expected '', got '{result}'"

    # Absolute import
    result = checker.resolve_relative_import("os.path", 0, current_module)
    assert result == "os.path", f"Expected 'os.path', got '{result}'"

    # Test with __init__.py file
    init_checker = ModuleImportChecker(ast.parse(""), "mypackage/submodule/__init__.py")
    init_checker.is_init = True
    current_module_init = "mypackage.submodule"

    # from . import something -> mypackage.submodule (current package)
    result = init_checker.resolve_relative_import(None, 1, current_module_init)
    assert result == "mypackage.submodule", (
        f"Expected 'mypackage.submodule', got '{result}'"
    )

    # from .. import something -> mypackage (parent package)
    result = init_checker.resolve_relative_import(None, 2, current_module_init)
    assert result == "mypackage", f"Expected 'mypackage', got '{result}'"

    print("✅ Relative import resolution tests passed!")


def test_file_path_to_module_path():
    """Test the file path to module path conversion."""
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a package structure
        package_dir = os.path.join(temp_dir, "mypackage")
        os.makedirs(package_dir)
        subpackage_dir = os.path.join(package_dir, "subpackage")
        os.makedirs(subpackage_dir)

        # Create __init__.py files
        with open(os.path.join(package_dir, "__init__.py"), "w") as f:
            f.write("")
        with open(os.path.join(subpackage_dir, "__init__.py"), "w") as f:
            f.write("")

        checker = ModuleImportChecker(ast.parse(""), "<unknown>")

        # Test regular module file
        test_file = os.path.join(package_dir, "utils.py")
        with open(test_file, "w") as f:
            f.write("")
        result = checker.file_path_to_module_path(test_file)
        assert result == "mypackage.utils", (
            f"Expected 'mypackage.utils', got '{result}'"
        )

        # Test __init__.py file
        init_file = os.path.join(subpackage_dir, "__init__.py")
        result = checker.file_path_to_module_path(init_file)
        assert result == "mypackage.subpackage", (
            f"Expected 'mypackage.subpackage', got '{result}'"
        )

        # Test file outside package
        standalone_file = os.path.join(temp_dir, "standalone.py")
        with open(standalone_file, "w") as f:
            f.write("")
        result = checker.file_path_to_module_path(standalone_file)
        assert result is None, f"Expected None for standalone file, got '{result}'"

    print("✅ File path to module path tests passed!")


if __name__ == "__main__":
    test_relative_import_resolution()
    test_file_path_to_module_path()
    test_module_import_checker()
    print("🎉 All tests passed!")
