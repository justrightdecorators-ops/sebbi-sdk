# sebbi SDK — a receipt for every AI agent action

Open-source clients for [sebbi.pro](https://sebbi.pro/receipts). Add one line and every action your AI agent takes gets a sealed, publicly checkable receipt.

| Language | Install | Source |
|---|---|---|
| Python | `pip install sebbi` | [`python/`](python) |
| JavaScript / TypeScript | `npm install sebbi` | [`js/`](js) |

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
