"""Entrypoint: ``python -m dashboard`` (bind exclusivo em 127.0.0.1:8765)."""
from dashboard.app import main

if __name__ == "__main__":
    raise SystemExit(main())
