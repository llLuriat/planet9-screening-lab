"""A tiny local pytest shim for environments without the external package.

Moved out of the project root (was `pytest/`) because a top-level package
named `pytest` shadows a real, pip-installed pytest whenever `python -m
pytest` is run from this directory. See __main__.py for details. Invoke this
shim explicitly with `python scripts/offline_pytest_shim/__main__.py`; do not
rely on it for anything using fixtures, monkeypatch, or pytest.approx.
"""
