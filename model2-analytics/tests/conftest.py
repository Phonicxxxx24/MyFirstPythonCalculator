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
"""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
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
