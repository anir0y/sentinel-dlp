# dlp-tui

Data Loss Prevention TUI for Windows and macOS.

Requirements
- Python 3.10+

Install (recommended inside a virtualenv)

- From source (editable):

  python -m venv .venv && source .venv/bin/activate  # on macOS/Linux
  python -m pip install --upgrade pip
  python -m pip install -e .

- With optional Windows extras:

  python -m pip install -e .[windows]

Running

- Run the TUI via the console entry point:

  dlp

- Or with the module runner:

  python -m dlp

Development & tests

- Install dev dependencies and run tests:

  python -m pip install -e .[dev]
  pytest

Notes
- The project depends on platform-specific features; some monitors require elevated privileges on the host platform.
- See pyproject.toml for package metadata and optional extras.
