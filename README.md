# flake8-module-import

`flake8-module-import` is a Flake8 plugin designed to enforce module imports instead of direct imports. This helps in maintaining a cleaner and more maintainable import structure in your Python code.

## Installation

You can install the plugin using pip:

```bash
pip install git+https://github.com/berleon/flake8_module_import.git
```

## Usage

Once installed, Flake8 will automatically use `flake8-module-import` during its linting process. Simply run Flake8 as you normally would:

```bash
flake8 your_project/
```

## Configuration

You can configure the maximum line length for Flake8 in your `pyproject.toml` file:

```toml
[tool.flake8]
max-line-length = 80
```

## Example

Given the following code:

```python
from sys import path
from pathlib import Path
from os.path import join
from os import path
```

The plugin will flag the following imports:

```
MIM001 Avoid direct import of 'path' from 'sys', import the module instead
MIM001 Avoid direct import of 'join' from 'os.path', import the module instead
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.