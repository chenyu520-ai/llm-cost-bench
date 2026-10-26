#!/usr/bin/env python3
"""
llm-cost-bench — measure what one API request actually costs.

Price lists give you dollars per million tokens. That number does not tell you
what a request costs, because models emit wildly different numbers of tokens for
the same prompt. This script runs the same prompts N times against each model on
an OpenAI-compatible endpoint and reports the median cost per request.

No dependencies. Python 3.7+.

Usage:
    export OPENAI_API_KEY=sk-...
    python3 bench.py --base-url https://api.example.com/v1 \
                     --models deepseek-flash,glm-5.3,kimi-k2.6 \
                     --prices prices.json

Options:
    --reps N        repetitions per cell (default 3, median reported)
    --tasks FILE    JSON file with your own tasks: [{"name": "...", "prompt": "..."}]
    --sleep SEC     pause between requests (default 1.0, keeps rate limiters happy)
    --markdown      print a markdown table instead of aligned text
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

DEFAULT_TASKS = [
    {
        "name": "short",
        "prompt": "In one sentence, what is a prompt cache?",
    },
    {
        "name": "code",
        "prompt": "Write a Python function that validates an email address with a regex. Only code.",
    },
    {
        "name": "long",
        "prompt": (
            "Summarise the following release notes in three sentences.\n\n"
            + "\n".join("- fix: retry logic now backs off exponentially on 429" for _ in range(30))
        ),
    },
]


def call(base_url, api_key, model, prompt, timeout=180):
    """Send one chat completion. Returns (prompt_tokens, completion_tokens, seconds)."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
    )

    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - started

    usage = payload.get("usage") or {}
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), elapsed


def cost_of(in_tokens, out_tokens, rate):
    return in_tokens / 1_000_000 * rate["in"] + out_tokens / 1_000_000 * rate["out"]


def main():
    ap = argparse.ArgumentParser(description="Measure per-request cost across models.")
    ap.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, e.g. https://api.example.com/v1")
    ap.add_argument("--api-key", default=None, help="API key (defaults to $OPENAI_API_KEY)")
    ap.add_argument("--models", required=True, help="Comma-separated model ids")
    ap.add_argument("--prices", required=True, help="JSON file: {model: {'in': 0.68, 'out': 2.75}}")
    ap.add_argument("--reps", type=int, default=3, help="Repetitions per cell (median reported)")
    ap.add_argument("--tasks", default=None, help="JSON file with your own tasks")
    ap.add_argument("--sleep", type=float, default=1.0, help="Seconds between requests")
    ap.add_argument("--markdown", action="store_true", help="Print a markdown table")
    args = ap.parse_args()

    api_key = args.api_key or __import__("os").environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("error: provide --api-key or set OPENAI_API_KEY")

    with open(args.prices, encoding="utf-8") as fh:
        prices = json.load(fh)

    if args.tasks:
        with open(args.tasks, encoding="utf-8") as fh:
            tasks = json.load(fh)
    else:
        tasks = DEFAULT_TASKS

    models = [m.strip() for m in args.models.split(",") if m.strip()]

    missing = [m for m in models if m not in prices]
    if missing:
        sys.exit("error: no rates for %s — add them to %s" % (", ".join(missing), args.prices))

    rows = []
    for model in models:
        for task in tasks:
            outs, secs, costs = [], [], []
            for rep in range(args.reps):
                try:
                    pin, pout, elapsed = call(args.base_url, api_key, model, task["prompt"])
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", "replace")[:120]
                    print("  ! %s / %s: HTTP %s %s" % (model, task["name"], exc.code, detail),
                          file=sys.stderr)
                    time.sleep(args.sleep * 3)
                    continue
                except Exception as exc:  # noqa: BLE001 - surface anything as a skipped rep
                    print("  ! %s / %s: %s" % (model, task["name"], exc), file=sys.stderr)
                    continue

                outs.append(pout)
                secs.append(elapsed)
                costs.append(cost_of(pin, pout, prices[model]))
                if rep < args.reps - 1:
                    time.sleep(args.sleep)

            if costs:
                rows.append({
                    "model": model,
                    "task": task["name"],
                    "out": int(statistics.median(outs)),
                    "secs": statistics.median(secs),
                    "cost": statistics.median(costs),
                })

    if not rows:
        sys.exit("error: every request failed — check the base URL, key and model ids")

    if args.markdown:
        print("| Model | Task | Output tokens (median) | Median cost/request | $10 buys |")
        print("|---|---|---|---|---|")
        for row in rows:
            buys = int(10 / row["cost"]) if row["cost"] else 0
            print("| %s | %s | %d | $%.6f | ~%s |" % (
                row["model"], row["task"], row["out"], row["cost"], f"{buys:,}"))
    else:
        print("%-18s %-8s %8s %8s %14s %12s" % (
            "model", "task", "out", "secs", "cost/request", "$10 buys"))
        for row in rows:
            buys = int(10 / row["cost"]) if row["cost"] else 0
            print("%-18s %-8s %8d %8.1f %14.6f %12s" % (
                row["model"], row["task"], row["out"], row["secs"], row["cost"], f"{buys:,}"))

    print()
    print("Costs use the rates in %s. Change them to your provider's." % args.prices)


if __name__ == "__main__":
    main()
