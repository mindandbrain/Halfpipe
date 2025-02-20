# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:


import networkx as nx
from nipype.pipeline import plugins as nip
from nipype.pipeline.engine.utils import topological_sort

from ..logging import logger


class SimplePlugin(nip.LinearPlugin):
    """Execute workflow in series"""

    def run(self, graph, config, updatehash=False):
        """Executes a pre-defined pipeline in a serial order.
        Parameters
        ----------
        graph : networkx digraph
            defines order of execution
        """

        if not isinstance(graph, nx.DiGraph):
            raise ValueError("Input must be a networkx digraph object")

        nodes, _ = topological_sort(graph)

        for node in nodes:
            logger.warning(f"Running node: {node}")
            node.run(updatehash=updatehash)
