"""This test package is named like the real `strategies` package, and pytest imports it under that name when the
tests directory has no __init__.py above it. The real package's folder is added to this one's search path so that
`import strategies.paper` still finds the code under test."""
from pathlib import Path

__path__.append(str(Path(__file__).resolve().parents[2] / 'strategies'))
