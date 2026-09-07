"""Process-level parallel execution with a deterministic sequential fallback.

Etapa 1 of PROMPT_EXECUCAO_PLANET9: the pipeline previously ran every
candidate / Monte Carlo point / robustness variation sequentially even though
each unit is independent (each branch builds its own fresh REBOUND
Simulation, there is no shared global physical state, and checkpoints are
keyed per candidate).

Contract
--------
- Workers run pure computation and return *picklable payloads only*.
- Every shared-file write (result cache, status CSV, manifests, reports,
  events) stays in the parent process so the final on-disk bytes are
  identical no matter how many workers were used.
- The number of workers is configurable via the ``max_workers`` argument or
  the ``PLANET9_MAX_WORKERS`` environment variable. A value of 1 forces the
  original sequential code path.
- If the process pool cannot be created (e.g. a platform without usable
  multiprocessing), execution transparently falls back to sequential.
"""

from __future__ import annotations

import logging
import os
import pickle
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any, Callable, Sequence, TypeVar

logger = logging.getLogger("planet9lab.parallel")

T = TypeVar("T")
R = TypeVar("R")

_WORKERS_ENV = "PLANET9_MAX_WORKERS"
_MAX_DEFAULT_WORKERS = 16


def resolve_max_workers(max_workers: int | None = None) -> int:
    """Resolve the worker count. Priority: explicit argument, then the
    ``PLANET9_MAX_WORKERS`` env var, then the machine's CPU count (capped to
    keep modest hardware and sandboxes from oversubscribing memory)."""
    if max_workers is not None:
        return max(1, int(max_workers))
    override = os.environ.get(_WORKERS_ENV)
    if override:
        try:
            return max(1, int(override))
        except ValueError:
            logger.warning("%s=%r is not an int; ignoring it", _WORKERS_ENV, override)
    return max(1, min(os.cpu_count() or 1, _MAX_DEFAULT_WORKERS))


def run_parallel_map(
    fn: Callable[[T], R],
    items: Sequence[T],
    max_workers: int | None = None,
    initializer: Callable[..., None] | None = None,
    initargs: tuple[Any, ...] = (),
) -> list[R]:
    """Map ``fn`` over ``items`` in a process pool, preserving input order.

    Results are returned in the same order as ``items`` (the same semantic as
    ``map``), which is what keeps every downstream ranking/report
    deterministic regardless of worker scheduling. A task-level exception is
    *not* swallowed here - worker functions are expected to encode their own
    failure cases in the returned payload. Fallback to sequential happens only
    when the pool itself cannot be started.
    """
    workers = resolve_max_workers(max_workers)
    if workers <= 1:
        if initializer is not None:
            initializer(*initargs)
        return [fn(item) for item in items]
    try:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=initializer,
            initargs=initargs,
        ) as executor:
            futures = [executor.submit(fn, item) for item in items]
            return [future.result() for future in futures]
    except (BrokenProcessPool, OSError, pickle.PicklingError) as exc:
        logger.warning(
            "parallel pool unavailable (%s: %s); falling back to sequential",
            type(exc).__name__,
            exc,
        )
        if initializer is not None:
            initializer(*initargs)
        return [fn(item) for item in items]
