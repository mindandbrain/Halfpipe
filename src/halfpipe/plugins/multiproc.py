# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import gc
import os
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from threading import Thread
from typing import Any, Callable, cast

import nipype.pipeline.engine as pe
from matplotlib import pyplot as plt
from nipype.pipeline import plugins as nip
from nipype.utils.profiler import get_system_total_memory_gb
from stackprinter import format_current_exception

from ..logging import logger
from ..utils.multiprocessing import get_init_args, mp_context
from .reftracer import PathReferenceTracer


def initializer(
    init_args: tuple[set[int], dict[str, Any], dict[str, str], str],
    plugin_args: dict,
) -> None:
    from ..utils.multiprocessing import initializer

    initializer(*init_args)

    from ..utils.pickle import patch_nipype_unpickler

    patch_nipype_unpickler()

    watchdog = plugin_args.get("watchdog", False)
    if watchdog is True:
        from ..watchdog import init_watchdog

        init_watchdog()

    resource_monitor = plugin_args.get("resource_monitor", False)
    if resource_monitor is True:
        import nipype

        nipype.config.enable_resource_monitor()


# Run node
def run_node(node: pe.Node, updatehash: bool, taskid: int):
    """Function to execute node.run(), catch and log any errors and
    return the result dictionary
    Parameters
    ----------
    node : nipype Node instance
        the node to run
    updatehash : boolean
        flag for updating hash
    taskid : int
        an identifier for this task
    Returns
    -------
    result : dictionary
        dictionary containing the node runtime results and stats
    """

    # Init variables
    result: dict[str, Any] = dict(result=None, traceback=None, taskid=taskid)

    # Try and execute the node via node.run()
    try:
        result["result"] = node.run(updatehash=updatehash)
    except Exception:  # catch all here
        result["traceback"] = format_current_exception()
        result["result"] = node.result

    # Avoid matplotlib memory leak
    plt.close("all")
    gc.collect()

    # Return the result dictionary
    return result


class MultiProcPlugin(nip.MultiProcPlugin):
    def __init__(self, plugin_args: dict):
        # Init variables and instance attributes
        super(nip.MultiProcPlugin, self).__init__(plugin_args=plugin_args)
        self._taskresult: dict = dict()
        self._task_obj: dict = dict()
        self._taskid = 0
        self._rt = None

        # Cache current working directory and make sure we
        # change to it when workers are set up
        self._cwd: str = plugin_args.get("workdir", os.getcwd())

        # Read in options or set defaults.
        self.processors = self.plugin_args.get("n_procs", cpu_count())
        self.memory_gb = self.plugin_args.get(
            "memory_gb",
            get_system_total_memory_gb() * 0.9,  # Allocate 90% of system memory
        )
        self.raise_insufficient = self.plugin_args.get("raise_insufficient", True)

        # Instantiate different thread pools for non-daemon processes
        logger.debug(
            "[MultiProc] Starting (n_procs=%d, mem_gb=%0.2f, cwd=%s)",
            self.processors,
            self.memory_gb,
            self._cwd,
        )

        self.pool = ProcessPoolExecutor(
            max_workers=self.processors,
            initializer=cast(Callable[[], Any], initializer),  # Tell mypy the types
            initargs=(
                get_init_args(),
                plugin_args,
            ),
            mp_context=mp_context,
        )

        self._stats = None
        self._keep = plugin_args.get("keep", "all")
        if self._keep != "all":
            self._rt = PathReferenceTracer(self._cwd)

    def _postrun_check(self):
        shutdown_thread = Thread(target=self.pool.shutdown, kwargs=dict(wait=True), daemon=True)
        shutdown_thread.start()
        shutdown_thread.join(timeout=10)
        if shutdown_thread.is_alive():
            logger.warning(
                "Shutdown of ProcessPoolExecutor timed out. This may lead to errors "
                "when the program closes. These error messages can usually be ignored"
            )

    def _submit_job(self, node, updatehash=False):
        self._taskid += 1

        # Don't allow streaming outputs
        if getattr(node.interface, "terminal_output", "") == "stream":
            node.interface.terminal_output = "allatonce"

        result_future = self.pool.submit(run_node, node, updatehash, self._taskid)
        result_future.add_done_callback(self._async_callback)
        self._task_obj[self._taskid] = result_future

        logger.debug("[MultiProc] Submitted task %s (taskid=%d).", node.fullname, self._taskid)
        return self._taskid

    def _generate_dependency_list(self, graph):
        if self._rt is not None:
            for node in graph.nodes:
                self._rt.add_node(node)
            for node in graph.nodes:
                self._rt.set_node_pending(node)
        super(MultiProcPlugin, self)._generate_dependency_list(graph)

    def _task_finished_cb(self, jobid, cached=False):
        assert self.procs is not None

        if self._rt is not None:
            name = self.procs[jobid].fullname
            unmark = True  # try to delete this when dependencies finish
            if self._keep == "some" and "fmriprep_wf" in name:
                unmark = False  # keep fmriprep if keep is "some"
            if self._keep == "some" and "ica_aroma_components_wf" in name:
                unmark = False
            if hasattr(self.procs[jobid], "keep") and self.procs[jobid].keep is True:
                unmark = False  # always keep feature outputs
            self._rt.set_node_complete(self.procs[jobid], unmark)
        super(MultiProcPlugin, self)._task_finished_cb(jobid, cached=cached)

    def _async_callback(self, args):
        assert self.procs is not None

        try:
            result = args.result()
            self._taskresult[result["taskid"]] = result
        except Exception as e:
            running_tasks = [self.procs[jobid].fullname for _, jobid in self.pending_tasks]
            logger.exception(f"Exception for {args} while running {running_tasks}", exc_info=e)

    def _remove_node_dirs(self):
        """
        Removes directories whose outputs have already been used up
        """
        if self._rt is not None:
            self._rt.collect_and_delete()
