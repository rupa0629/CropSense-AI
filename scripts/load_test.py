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
    parser.add_argument("--max-failure-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=2000)
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
    failure_rate = failures / max(1, len(results))
    if failure_rate > args.max_failure_rate:
        raise SystemExit(
            f"Failure rate {failure_rate:.2%} exceeded {args.max_failure_rate:.2%}"
        )
    if p95 * 1000 > args.max_p95_ms:
        raise SystemExit(
            f"p95 {p95 * 1000:.1f}ms exceeded {args.max_p95_ms:.1f}ms"
        )


if __name__ == "__main__":
    main()
