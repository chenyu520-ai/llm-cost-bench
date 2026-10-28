# llm-cost-bench

**Price lists tell you dollars per million tokens. They don't tell you what a request costs.**

Models emit wildly different numbers of tokens for the same prompt. A model that
costs 5× more per million can be cheaper per request, because it answers in 60
tokens instead of 500. The only way to know is to measure.

This is a ~170-line, dependency-free script that does exactly that: it runs the
same prompts N times against each model on any OpenAI-compatible endpoint, reads
the `usage` fields the API returns, and prints the median cost per request.

## Why this exists

I measured nine model-task combinations and found that the cheapest model per
million tokens was the **most expensive per request** on the code task — 509
output tokens against 68 for a model that costs 5× more on paper.

The full write-up: [The cheapest model per million tokens was the most expensive per request](https://dev.to/chenyu-ai/the-cheapest-model-per-million-tokens-was-the-most-expensive-per-request-2cc6)

## Usage

No dependencies. Python 3.7+.

```bash
export OPENAI_API_KEY=sk-...
python3 bench.py \
  --base-url https://api.example.com/v1 \
  --models deepseek-flash,glm-5.3,kimi-k2.6 \
  --prices prices.json
```

Example output (median of 1 run, three task shapes):

```
model              task          out     secs   cost/request     $10 buys
deepseek-flash     short          90      1.1       0.000275       36,403
deepseek-flash     code          634      3.5       0.001775        5,634
deepseek-flash     long          136      1.6       0.000686       14,574
glm-5.3            short          42      1.7       0.000539       18,552
glm-5.3            code           63      1.5       0.000791       12,642
glm-5.3            long           73      1.7       0.002350        4,255
kimi-k2.6          short          32      1.3       0.000311       32,159
kimi-k2.6          code           61      1.3       0.000589       16,975
kimi-k2.6          long           55      1.2       0.000682       14,667
```

## Options

| Flag | Meaning |
|---|---|
| `--base-url` | Any OpenAI-compatible base URL (`/v1` suffix included) |
| `--api-key` | Or set `OPENAI_API_KEY` |
| `--models` | Comma-separated model ids |
| `--prices` | JSON file with your provider's rates (see `prices.json`) |
| `--reps` | Repetitions per cell, median reported (default 3) |
| `--tasks` | Your own prompts, as JSON: `[{"name": "...", "prompt": "..."}]` |
| `--sleep` | Pause between requests (default 1.0s) |
| `--markdown` | Print a markdown table, handy for pasting into a post |

## Measuring your own workload

The three built-in tasks are generic shapes (short answer, small generation,
input-heavy summary). They are a starting point, not a verdict.

**The number that matters is your own.** Export three prompts that represent the
bulk of your traffic and pass them in:

```json
[
  { "name": "classify", "prompt": "Is this review positive or negative? Reply with one word.\n\n<review>" },
  { "name": "extract",  "prompt": "Extract every email address from the text below. Return JSON only.\n\n<text>" },
  { "name": "summarise","prompt": "Summarise the following ticket in two sentences.\n\n<long ticket>" }
]
```

```bash
python3 bench.py --base-url ... --models ... --prices prices.json --tasks my-tasks.json --reps 5
```

## Caveats

- **Variance is real.** On one model the same prompt varied 2.5× in output tokens
  across consecutive runs. Use `--reps 5` before you trust a number.
- **Cost is not price.** Rates in `prices.json` are whatever you were quoted at
  the time you ran it; update them.
- **One endpoint, one moment.** Cache behaviour, load and routing all move the
  numbers. Re-run when your provider changes anything.
- **Token counts are the provider's.** This reads `usage` from the response; it
  does not count tokens itself.

## License

MIT

---

Built by [@chenyu](https://dev.to/chenyu-ai). I run [SwitchLLM](https://switchllm.net),
an OpenAI-compatible endpoint for DeepSeek, GLM and Kimi — the endpoint these
measurements came from. The script works against any OpenAI-compatible provider;
point it at whoever you use.
