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

sys.path ordering -- read before touching this file
----------------------------------------------------
Two things need to both be true on sys.path:
  1. `pipeline` (model2-analytics/pipeline/) needs to be importable, or
     recorded.py's `from pipeline.video_worker import ...` fails at
     import time -- main.py's dynamic loader swallows that silently
     (see its own comments) and just never mounts recorded.py's
     router, so every recorded.py endpoint 404s instead of enforcing
     auth. This is what MODEL2_ROOT below is for.
  2. `app` must resolve to *model1-registry's* `app` package, not
     model2-analytics's -- both are top-level packages literally named
     `app` (finding 5). grid.py and recorded.py both do plain
     `from app.auth... import ...`, which is ambiguous the moment both
     model1-registry and model2-analytics are on sys.path at once --
     it silently picks whichever one is found first.

These two pull in opposite directions (MODEL2_ROOT has to be on
sys.path for (1), but must not shadow `app` for (2)), so MODEL1_ROOT is
inserted *after* MODEL2_ROOT below, unconditionally, so it always ends
up first. "Unconditionally" matters: an earlier version of this file
(and of test_is_safe_url.py) used `if p not in sys.path: insert(0, p)`
guards, which check *presence*, not *position* -- when this repo's
tests are run in one combined session (e.g. plain `pytest` from the
repo root, which collects model1-registry/tests/ too), model1-registry's
own conftest.py has usually *already* put MODEL1_ROOT/REPO_ROOT
somewhere in sys.path by the time this file runs, so the guard sees
them as "already there" and skips re-inserting -- leaving MODEL2_ROOT
sitting ahead of them from the insert just below. That's exactly how
`app` resolved to the wrong package the one time both suites were
collected together (reproduced locally: `pytest` from the repo root,
121 items, `ModuleNotFoundError: No module named 'app.auth'` while
collecting test_is_safe_url.py). Plain, unconditional inserts fix it;
sys.path entries can safely repeat.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL1_ROOT = REPO_ROOT / "model1-registry"
MODEL2_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(MODEL2_ROOT))   # for `pipeline` -- see docstring
sys.path.insert(0, str(MODEL1_ROOT))   # for `app` -- must win over MODEL2_ROOT
sys.path.insert(0, str(REPO_ROOT))     # for `shared`

_MODEL1_CONFTEST_PATH = MODEL1_ROOT / "tests" / "conftest.py"

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
