"""
Shared fixtures for model2-analytics/tests/.

model2's routers get mounted at runtime into *model1-registry's*
FastAPI app object (see model1-registry/app/main.py's dynamic
importlib loader, added for AuditReport2.md finding 5's duplicate-
`app`-package situation) -- there is no separate model2 app to spin up.
That means the DB-backed fixtures model1-registry/tests/conftest.py
already built (real Postgres+PostGIS `sentinel_test`, one transaction
+ SAVEPOINT per test, a TestClient per seeded role) are exactly the
right fixtures for testing model2's endpoints too, not a different set
that would have to be kept behaviorally identical to them.

Rather than forking/duplicating that ~300-line fixture file (and
risking the two drifting out of sync the same way finding 5 itself
warns about), this loads it by file path and re-exports its names into
this module's namespace, so pytest sees the same fixtures here as it
does under model1-registry/tests/. Loaded under a distinct module name
(not "conftest") deliberately -- this file is *also* named conftest.py,
so a plain `from conftest import *` would resolve to itself (already
mid-import in sys.modules) instead of model1-registry's copy.

Requires the same local setup as model1-registry/tests: a reachable
Postgres server, `sentinel`/`sentinel_test` bootstrapped per
model1-registry/README.md's Testing section (or `PSQL_PATH` set).

Also puts model2-analytics itself on sys.path (see MODEL2_ROOT below).
Without it, recorded.py's `from pipeline.video_worker import ...`
fails at import time the moment anything here triggers `from app.main
import app` (main.py's dynamic loader -- see its own comments -- swallows
that ImportError, prints a warning, and just never mounts recorded.py's
router, so every recorded.py endpoint 404s instead of enforcing auth).
This only ever went unnoticed locally because `python -m pytest`
happens to prepend the current directory to sys.path on its own, which
masks the gap -- a bare `pytest` invocation (what CI, and most people's
muscle memory, actually run) does not, and hits it every time.
Confirmed by reproducing both invocations locally: identical test file,
`python -m pytest` all green, bare `pytest` 9 of these same tests
404-ing. Setting sys.path explicitly here removes the dependence on
which of the two happens to be running pytest.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL2_ROOT = Path(__file__).resolve().parents[1]
if str(MODEL2_ROOT) not in sys.path:
    sys.path.insert(0, str(MODEL2_ROOT))

_MODEL1_CONFTEST_PATH = REPO_ROOT / "model1-registry" / "tests" / "conftest.py"

_spec = importlib.util.spec_from_file_location("model1_registry_conftest", _MODEL1_CONFTEST_PATH)
_model1_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_model1_conftest)

# Re-export everything public (pytest fixtures, the _login/unique_camera_name
# helpers, SEED_PASSWORD, etc.) into this module's namespace so pytest picks
# up the fixtures when collecting tests under model2-analytics/tests/.
for _name in dir(_model1_conftest):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_model1_conftest, _name)
del _name, _spec
