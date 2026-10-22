# Measurements

The current public report is [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

It includes whole-invocation time and token measurements for 20 matched Python service missions, original and reviewed completion scores, four previous-skill anchors, uncertainty, research-cost lower bounds and links to retained machine-readable evidence.

Recompute the aggregate arithmetic without model calls:

```bash
python3 tools/check_benchmark.py
```
