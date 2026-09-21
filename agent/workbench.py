"""Compatibility entry point for the shared multi-workbench executor."""
from workbench_parallel import NODES, run_parallel


def run_target(workflow, policy):
    return run_parallel(workflow, policy)
