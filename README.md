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

Neither client has any runtime dependencies.

## Releases

The version in `python/pyproject.toml` and `js/package.json` on `main` is the version published to PyPI and npm, so you can read exactly what a release contains before installing. Pin the version you have reviewed, for example `pip install "sebbi==1.1.1"`.

## Docs

- Overview and all frameworks: https://sebbi.pro/receipts
- Vercel AI SDK guide: https://sebbi.pro/receipts/ai-sdk
- Receipt API: `GET https://sebbi.pro/v1/receipts/<id>`

MIT licence. Made by Monop Content.
