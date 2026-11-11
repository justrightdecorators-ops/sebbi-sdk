# sebbi SDK — a receipt for every AI agent action

Open-source clients for [sebbi.pro](https://sebbi.pro/receipts). Add one line and every action your AI agent takes gets a sealed, publicly checkable receipt.

| Language | Install | Source |
|---|---|---|
| Python | `pip install sebbi` | [`python/`](python) |
| JavaScript / TypeScript | `npm install sebbi` | [`js/`](js) |

## Provable AI compliance

sebbi.pro is the provable AI compliance platform: every AI decision sealed, timestamped into Bitcoin and verifiable by anyone, without trusting the organisation or sebbi.pro. Prove it yourself in a minute, no account: https://sebbi.pro/provable-ai-compliance

- [The Independent Check Rule: letters of 10 November 2026](independent-check-rule), published in full with Bitcoin-timestamped fingerprints
- Point of No Return, the safety gate for AI agent actions that cannot be undone: `from sebbi.noreturn import no_return` / `import { noReturn } from "sebbi/noreturn"`

## Garbage in, caught at the door

A sealed record proves nothing was changed afterwards. The Input Gate proves what went in was genuine to begin with. Before your AI uses third-party data, each input is checked against the file its source hosts on its own domain (`/.well-known/sebbi-source.json`), and the answer is sealed with the decision.

```python
from sebbi.source import admit            # pip install sebbi

code = admit("pricing-agent", [
    {"domain": "your-supplier.com", "data": price_list, "label": "Q4 price list"},
], ref="quote-10482")
```

```js
import { admit } from "sebbi/source";     // npm install sebbi
```

Each input comes back GENUINE, TAMPERED, UNVERIFIED or UNKNOWN; the gate answers ADMIT, HOLD or REFUSE and returns a `GI-` code to keep with the decision. The data is fingerprinted on your machine: only the fingerprint is sent. Try it without an account: https://sebbi.pro/garbage-in

sebbi.pro vouches for its own published texts the same way. Check the Independent Check Rule against https://sebbi.pro/.well-known/sebbi-source.json, change one word, and check again.

## What leaves your process

Only what you can see in the code here: a SHA-256 fingerprint of each input and output, a short label, a timestamp, an owner commitment (a SHA-256 of a per-receipt secret, so only you can reverse your receipts) and, if you set one, your API key. The data itself is fingerprinted locally and never sent:

- Python: [`python/src/sebbi/__init__.py`](python/src/sebbi/__init__.py), see `fingerprint()` and `Receipt.wire()`
- JavaScript: [`js/index.cjs`](js/index.cjs), see `fingerprint()` and `Receipt.wire()`

Neither client has any runtime dependencies. The OpenTelemetry integration needs the OpenTelemetry SDK you already run: `sebbi[otel]` in Python, your own `@opentelemetry/*` packages in JavaScript.

## OpenTelemetry

`pip install "sebbi[otel]"` / `import { SebbiSpanProcessor } from "sebbi/otel"`: every agent and tool span you already trace gets a receipt, with the link written onto the span. `sebbi verify-otlp traces.json` proves an exported trace matches its receipts. Details in [`python/`](python#opentelemetry) and [`js/`](js#opentelemetry).

## Releases

Python releases are published to PyPI from this public repository by [`.github/workflows/release.yml`](.github/workflows/release.yml), using Trusted Publishing. Every file carries a PyPI publish attestation naming this repository, that workflow and the exact commit it was built from, and nothing is uploaded unless the full test suite passes. Pin the version you reviewed, and for the strictest installs pin the file's sha256 with `pip install --require-hashes`.

## Docs

- Overview and all frameworks: https://sebbi.pro/receipts
- Vercel AI SDK guide: https://sebbi.pro/receipts/ai-sdk
- Receipt API: `GET https://sebbi.pro/v1/receipts/<id>`

MIT licence. Made by Monop Content.
