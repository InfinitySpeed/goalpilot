"""Run independent, read-only verification preflights concurrently once per test process."""
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache


@lru_cache(maxsize=1)
def reference_preflights():
    from evaluation.ambitious.preflight import run as ambitious
    from evaluation.general.preflight import run as general
    from evaluation.native_goals.preflight import run as native_goals
    from evaluation.reference_oracles import preflight as oracle
    from evaluation.reference_oracles_v21 import preflight as oracle_v21

    # Each preflight writes only to its own temporary directory and returns an
    # immutable report. Run independent workloads together; every calling test
    # still asserts its own report below.
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(work) for work in
                   (ambitious, native_goals, general, oracle, oracle_v21)]
        return tuple(future.result() for future in futures)
