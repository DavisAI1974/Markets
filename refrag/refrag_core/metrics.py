import time
from contextlib import contextmanager


@contextmanager
def timer():
    start = time.perf_counter()
    data = {"elapsed_s": 0.0}
    try:
        yield data
    finally:
        data["elapsed_s"] = time.perf_counter() - start


def tokens_per_second(tokens: int, elapsed_s: float) -> float:
    if elapsed_s <= 0:
        return 0.0
    return float(tokens) / elapsed_s
