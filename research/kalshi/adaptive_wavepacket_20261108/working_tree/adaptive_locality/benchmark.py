"""Offline CPU-first benchmark: no production data, no scientific reuse claims."""
from __future__ import annotations
import json
import math
import random
import tempfile
from pathlib import Path
from time import perf_counter
from .core import Observation, MetricContract, _digest
from .index import ExactGridIndex
from .disk_index import DiskGridIndex


def benchmark(*, centers: int = 2000, queries: int = 200, seed: int = 1729) -> dict:
    if type(centers) is not int or type(queries) is not int or not 1 <= centers <= 10000 or not 1 <= queries <= 2000:
        raise ValueError("bounded benchmark: centers 1..10000, queries 1..2000")
    metric=MetricContract(("x","y"),(1.,1.),(1.,1.),"benchmark-frozen")
    rng=random.Random(seed)
    # E-8: mixed directions and INTERLEAVED clocks (centres on even ticks, queries on odd ticks
    # spread through the same range) so the direction/historical filters are exercised, not vacuous.
    span=2*(centers+queries)
    radius=10.
    # Box sized to the centre count so a query averages ~2 in-radius centres before filtering.
    half=max(radius,math.sqrt(math.pi*radius**2*centers/2)/2)
    observations=[
        Observation(f"c{i}", "P" if i%3 else "X",
                    {"x":rng.uniform(-half,half),"y":rng.uniform(-half,half)},
                    2*i,"synthetic-benchmark",direction="AB" if i%4 else "BA") for i in range(centers)]
    targets=[
        Observation(f"q{i}", "P" if i%2 else "X",
                    {"x":rng.uniform(-half,half),"y":rng.uniform(-half,half)},
                    min(span,2*((i*centers)//max(queries,1))+1),"synthetic-benchmark",
                    direction="AB" if i%3 else "BA") for i in range(queries)]
    t0=perf_counter()
    expected=[]
    filtered_out=0  # in-radius same-family centres removed by the direction/clock filters
    for target in targets:
        hits=sorted(((metric.distance(target,c),c.event_id) for c in observations
                     if c.family==target.family and c.event_clock<=target.event_clock
                     and c.direction==target.direction),key=lambda v:(v[0],v[1]))
        expected.append(tuple(cid for distance,cid in hits if distance<=radius)[:8])
        filtered_out+=sum(1 for c in observations if c.family==target.family
                          and metric.distance(target,c)<=radius
                          and (c.direction!=target.direction or c.event_clock>target.event_clock))
    brute_seconds=perf_counter()-t0
    index=ExactGridIndex(metric,radius)
    for c in observations:
        index.add(c)
    t0=perf_counter()
    for target,wanted in zip(targets,expected):
        actual=tuple(h.center_id for h in index.candidates(target,max_neighbors=8))
        if actual!=wanted:
            raise AssertionError("in-memory index differential failure")
    memory_query_seconds=perf_counter()-t0
    with tempfile.TemporaryDirectory() as folder:
        with DiskGridIndex(Path(folder)/"index.sqlite",metric,radius,source_identity="synthetic") as disk:
            for c in observations:
                disk.add(c)
            t0=perf_counter()
            for target,wanted in zip(targets,expected):
                actual=tuple(h.center_id for h in disk.candidates(target,max_neighbors=8))
                if actual!=wanted:
                    raise AssertionError("disk index differential failure")
            disk_query_seconds=perf_counter()-t0
    nonempty=sum(1 for wanted in expected if wanted)
    return {"benchmark_schema":1,"source":"DETERMINISTIC_SYNTHETIC_ONLY",
            "metric_identity":metric.identity(),"centers":centers,"queries":queries,
            "queries_with_hits":nonempty,
            "in_radius_centers_filtered_by_direction_or_clock":filtered_out,
            "filters_exercised":{"mixed_directions":True,"interleaved_clocks":True},
            "baseline_seconds":brute_seconds,
            "memory_index_query_seconds":memory_query_seconds,
            "disk_index_query_seconds":disk_query_seconds,
            "all_exact_results_match":True,"scientific_jobs_eliminated":0,
            "claims":"timing is local reference only; no real-science runtime inference"}


if __name__=="__main__":
    print(json.dumps(benchmark(),sort_keys=True,indent=2))
