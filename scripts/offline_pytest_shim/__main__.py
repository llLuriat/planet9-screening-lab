from __future__ import annotations

import importlib.util
import inspect
import tempfile
import traceback
from pathlib import Path


def main() -> int:
    test_files = sorted(Path("tests").glob("test_*.py"))
    total = 0
    failed = 0
    for path in test_files:
        module_name = "local_" + path.stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            print(f"cannot load {path}")
            failed += 1
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, obj in sorted(vars(module).items()):
            if name.startswith("test_") and callable(obj):
                total += 1
                try:
                    kwargs = {}
                    sig = inspect.signature(obj)
                    if "tmp_path" in sig.parameters:
                        with tempfile.TemporaryDirectory() as temp:
                            kwargs["tmp_path"] = Path(temp)
                            obj(**kwargs)
                    else:
                        obj(**kwargs)
                    print(f"{path}::{name} PASSED")
                except Exception:
                    failed += 1
                    print(f"{path}::{name} FAILED")
                    traceback.print_exc()
    print(f"{total - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
