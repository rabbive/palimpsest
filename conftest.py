"""Make the project root importable for tests.

`palimpsest` is an installed package, but `eval/` is a plain top-level package in
the repo and is not part of the wheel. Without this, importing `eval.run_eval`
from a test works only when some earlier-collected module has already put the
project root on sys.path as a side effect -- so the suite passed as a whole while
individual test files failed in isolation.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
