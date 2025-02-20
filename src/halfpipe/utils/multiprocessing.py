# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import multiprocessing.pool as mp_pool
import os
from contextlib import nullcontext
from enum import Enum, auto
from functools import partialmethod
from multiprocessing import active_children, get_context
from typing import Any, Callable, ContextManager, Iterable, Iterator, Sized, TypeVar

mp_context = get_context("spawn")


def mock_tqdm(iterable, *args, **kwargs):
    return iterable


def get_init_args() -> tuple[set[int] | None, dict[str, Any], dict[str, str], str]:
    from ..logging.base import LoggingContext

    affinity: set[int] | None = None
    if hasattr(os, "sched_getaffinity"):
        affinity = os.sched_getaffinity(0)

    return (
        affinity,
        LoggingContext.logging_args(),
        dict(os.environ),
        os.getcwd(),
    )


def initializer(
    sched_affinity: set[int] | None,
    logging_kwargs: dict[str, Any],
    host_env: dict[str, str],
    host_cwd: str,
) -> None:
    if sched_affinity is not None:
        if hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(0, sched_affinity)

    os.chdir(host_cwd)

    # Do not show tqdm progress bars from subprocesses as per
    # https://github.com/nsidc/earthaccess/issues/612#issuecomment-2189744434
    from tqdm import tqdm
    from tqdm.auto import tqdm as tqdm_auto

    tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore
    tqdm_auto.__init__ = partialmethod(tqdm_auto.__init__, disable=True)  # type: ignore

    # Make sure we send all logging to the logger process
    from ..logging.base import setup as setup_logging

    setup_logging(**logging_kwargs)

    # Make sure we use the same environment variables as the parent process
    os.environ.update(host_env)


def terminate() -> None:
    for p in active_children():
        p.terminate()
        p.join()


class Pool(mp_pool.Pool):
    def __init__(
        self,
        processes: int | None = None,
        maxtasksperchild: int | None = None,
    ) -> None:
        init_args = get_init_args()
        super().__init__(
            processes=processes,
            initializer=initializer,
            initargs=init_args,
            maxtasksperchild=maxtasksperchild,
            context=mp_context,
        )

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        super().__exit__(exc_type, exc_value, traceback)
        self.join()


class IterationOrder(Enum):
    ORDERED = auto()
    UNORDERED = auto()


T = TypeVar("T")
S = TypeVar("S")


def make_pool_or_null_context(
    iterable: Iterable[T],
    callable: Callable[[T], S],
    num_threads: int = 1,
    chunksize: int | None = 1,
    iteration_order: IterationOrder = IterationOrder.UNORDERED,
) -> tuple[ContextManager, Iterator[S]]:
    if isinstance(iterable, Sized):
        num_threads = min(len(iterable), num_threads)
        # Apply logic from pool.map (multiprocessing/pool.py#L481) here as well
        if chunksize is None:
            chunksize, extra = divmod(len(iterable), num_threads * 4)
            if extra:
                chunksize += 1
    if chunksize is None:
        chunksize = 1

    if num_threads in {0, 1}:
        return nullcontext(), map(callable, iterable)

    pool = Pool(processes=num_threads)
    if iteration_order is IterationOrder.ORDERED:
        map_function = pool.imap
    elif iteration_order is IterationOrder.UNORDERED:
        map_function = pool.imap_unordered
    else:
        raise ValueError(f"Unknown iteration order {iteration_order}")
    output_iterator: Iterator = map_function(callable, iterable, chunksize)
    cm: ContextManager = pool
    return cm, output_iterator
