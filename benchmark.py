"""
Benchmark Evaluation Harness — READ-ONLY during autoresearch experiments.

Runs Liouvillian recovery against spin-boson benchmark datasets and reports
R², residuals, and runtime in the standard output format.

Usage:
    python benchmark.py > run.log 2>&1
"""

import os
import sys
import time
import traceback
import numpy as np
import tracemalloc

import od_engine


def load_dataset(path):
    """
    Load a benchmark dataset.

    Supports two formats:
    1. Dict-in-npy: {"t": ..., "x": ..., "ground_truth": ..., "name": ...}
    2. Raw spin-boson npy: (n_t, 5) array where col 0 = time, cols 1-4 = rho elements

    Note: allow_pickle=True is required for dict-in-npy format.
    These are our own generated/curated benchmark datasets, not untrusted data.
    """
    data = np.load(path, allow_pickle=True)

    # Check if it's a dict (wrapped format)
    if data.dtype == object:
        data = data.item()
        return data

    # Raw spin-boson format: (n_t, 5) complex array
    if data.ndim == 2 and data.shape[1] == 5:
        times = data[:, 0].real
        name = os.path.splitext(os.path.basename(path))[0]
        return {
            "t": times,
            "x": data,
            "ground_truth": None,  # No ground truth L for real data
            "name": name,
        }

    raise ValueError(f"Unknown data format: shape={data.shape}, dtype={data.dtype}")


def compute_r_squared_trajectory(x_true, x_pred):
    """
    Compute R² for density matrix trajectory reconstruction.

    Compares real parts of population elements (diagonal: rho_00, rho_11)
    and real+imag parts of coherence elements (off-diagonal: rho_01, rho_10).

    x_true, x_pred: (n_t, 5) where col 0 = time, cols 1-4 = rho elements
    """
    # Extract density matrix elements (skip time column)
    # Populations are real, coherences are complex
    rho_true = x_true[:, 1:].astype(complex)
    rho_pred = x_pred[:, 1:].astype(complex)

    # Flatten real and imaginary parts for R² computation
    y_true = np.concatenate([rho_true.real.flatten(), rho_true.imag.flatten()])
    y_pred = np.concatenate([rho_pred.real.flatten(), rho_pred.imag.flatten()])

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

    if ss_tot == 0:
        return 0.0
    return 1.0 - (ss_res / ss_tot)


def compute_holdout_r_squared(x_true, x_pred, split_frac=0.8):
    """Compute R² on the holdout (last 20%) portion."""
    n = len(x_true)
    split = int(n * split_frac)
    return compute_r_squared_trajectory(x_true[split:], x_pred[split:])


def run_benchmark(dataset_path):
    """Run a single benchmark evaluation and return metrics dict."""
    dataset = load_dataset(dataset_path)

    t = np.asarray(dataset["t"], dtype=np.float64)
    x = np.asarray(dataset["x"])

    # Track memory
    tracemalloc.start()

    # Run recovery
    start_time = time.time()
    result = od_engine.recover(t, x)
    runtime = time.time() - start_time

    # Get peak memory
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_memory_mb = peak_memory / (1024 * 1024)

    x_pred = np.asarray(result["x_predicted"])

    # Ensure x has the right format for comparison
    if x.ndim == 2 and x.shape[1] == 5:
        x_compare = x
    else:
        raise ValueError(f"Unexpected x shape for comparison: {x.shape}")

    # Metrics
    r_squared = compute_r_squared_trajectory(x_compare, x_pred)
    r_squared_holdout = compute_holdout_r_squared(x_compare, x_pred)

    # Residuals on population elements (most physically meaningful)
    pop_true = np.column_stack([x_compare[:, 1].real, x_compare[:, 4].real])
    pop_pred = np.column_stack([x_pred[:, 1].real, x_pred[:, 4].real])
    residuals = pop_true - pop_pred
    residual_mean = float(np.mean(np.abs(residuals)))
    residual_max = float(np.max(np.abs(residuals)))

    return {
        "r_squared": r_squared,
        "r_squared_holdout": r_squared_holdout,
        "residual_mean": residual_mean,
        "residual_max": residual_max,
        "runtime_seconds": runtime,
        "peak_memory_mb": peak_memory_mb,
        "n_points": len(t),
        "dataset": dataset["name"],
        "operator": result["operator"],
        "coefficients": result["coefficients"],
    }


def print_results(metrics):
    """Print results in the standard output format."""
    print("---")
    print(f"r_squared:         {metrics['r_squared']:.6f}")
    print(f"r_squared_holdout: {metrics['r_squared_holdout']:.6f}")
    print(f"residual_mean:     {metrics['residual_mean']:.6f}")
    print(f"residual_max:      {metrics['residual_max']:.6f}")
    print(f"runtime_seconds:   {metrics['runtime_seconds']:.3f}")
    print(f"peak_memory_mb:    {metrics['peak_memory_mb']:.1f}")
    print(f"n_points:          {metrics['n_points']}")
    print(f"dataset:           {metrics['dataset']}")
    print("---")
    print(f"operator:          {metrics['operator']}")
    print(f"coefficients:      {metrics['coefficients']}")


def main():
    benchmark_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_data")

    if not os.path.isdir(benchmark_dir):
        print(f"ERROR: benchmark_data/ directory not found at {benchmark_dir}", file=sys.stderr)
        sys.exit(1)

    datasets = sorted([
        os.path.join(benchmark_dir, f)
        for f in os.listdir(benchmark_dir)
        if f.endswith(".npy")
    ])

    if not datasets:
        print("ERROR: No .npy datasets found in benchmark_data/", file=sys.stderr)
        sys.exit(1)

    for dataset_path in datasets:
        try:
            metrics = run_benchmark(dataset_path)
            print_results(metrics)
        except Exception as e:
            print(f"ERROR running {dataset_path}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
