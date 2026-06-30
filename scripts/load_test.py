"""Small dependency-free HTTP load smoke test for staging."""

from __future__ import annotations

import argparse
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def request(url: str, timeout: float) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, time.perf_counter() - started
    except Exception:
        return 0, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(request, args.url, args.timeout) for _ in range(args.requests)]
        results = [future.result() for future in as_completed(futures)]

    durations = sorted(duration for _, duration in results)
    failures = sum(status < 200 or status >= 400 for status, _ in results)
    p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))]
    print(
        f"requests={len(results)} failures={failures} "
        f"mean_ms={statistics.mean(durations) * 1000:.1f} p95_ms={p95 * 1000:.1f}"
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
