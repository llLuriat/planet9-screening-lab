"""Test isolation: every test run writes under pytest's tmp_path instead of the
project's real runs/ tree.

default_paths() still resolves catalogs/configs from the real project ROOT, so
monkeypatching RUNS_DIR (the run destination only) is sufficient - it never
redirects data lookup and never pollutes runs/latest_run.txt in the repo.
"""

import pytest

# Plugin do NiceGUI para a simulação de usuário (fixture ``user``):
# fornece user/user_navigation etc. e lê a ini ``main_file`` (definida no
# pyproject.toml como dashboard/app.py — as rotas do dashboard registram no
# import; main() não é chamado).
pytest_plugins = ["nicegui.testing.user_plugin"]


@pytest.fixture(autouse=True)
def isolated_runs(tmp_path, monkeypatch):
    import planet9lab.run as run_module

    monkeypatch.setattr(run_module, "RUNS_DIR", tmp_path)
    return tmp_path
