# sebbi: a receipt for every AI agent action

Your agent refunds a customer, sends an email, moves money or answers a patient.
Add one line and every one of those actions gets a **sealed receipt with a public link anyone can check**:
your customer, your auditor, your insurer, a regulator.

```bash
pip install sebbi
```

```python
import sebbi

@sebbi.receipt("refund-decision")
def decide_refund(order):
    return {"refund": True, "amount": 42}

decide_refund({"id": 7})
print(sebbi.last().url)   # https://sebbi.pro/r/...  anyone can check it
```

No account needed to start. Zero dependencies. Python 3.8+.

**Provable AI compliance.** sebbi.pro is the provable AI compliance platform: every AI decision sealed, timestamped into Bitcoin and verifiable by anyone, without trusting you or us. Prove it yourself in a minute, no account: https://sebbi.pro/provable-ai-compliance

## Why teams add it

- **Proof, not logs.** Each receipt sits in a Merkle tree sealed into the sebbi.pro chain, witnessed by independent chains, timestamped into Bitcoin and signed post-quantum. Nobody can quietly edit it afterwards.
- **Your data stays yours.** Inputs and outputs are fingerprinted (SHA-256) on your machine. Only fingerprints, a short label and a timestamp are sent.
- **Never slows your agent.** Sealing runs on a background thread in batches. If the network is down, your code carries on.
- **A link anyone can check.** `receipt.url` works straight away. Put it in the email, the ticket or the audit file.
- **Ready for the EU AI Act and UK GDPR.** Record-keeping, logging and the right to an explanation all start with being able to show what your AI actually did.

## Your framework, one line

**LangChain / LangGraph**
```python
from sebbi.integrations.langchain import SebbiCallbackHandler
agent.invoke({"input": "..."}, config={"callbacks": [SebbiCallbackHandler()]})
```

**CrewAI**
```python
from sebbi.integrations.crewai import step_callback, task_callback
crew = Crew(agents=[...], tasks=[...], step_callback=step_callback, task_callback=task_callback)
```

**OpenAI Agents SDK**
```python
from sebbi.integrations.openai_agents import SebbiRunHooks
result = await Runner.run(agent, "...", hooks=SebbiRunHooks())
```

**MCP servers**
```python
from sebbi.integrations.mcp import sealed

@mcp.tool()
@sealed("lookup_customer")
def lookup_customer(customer_id: str) -> dict: ...
```

**Anything else**
```python
r = sebbi.seal(input=request, output=result, label="send-invoice")
r.wait()            # optional: block until sealed
print(r.url, r.sealed, r.block_index)
```

Async functions work with the same decorator. Exceptions are sealed with outcome `error` and re-raised unchanged.

## OpenTelemetry

Already tracing your agents? One line seals every agent run and tool call you trace, and writes the receipt link onto the span, so it shows up in Jaeger, Tempo, Honeycomb, Datadog, Langfuse or Phoenix next to the span itself.

```bash
pip install "sebbi[otel]"
```

```python
from sebbi.integrations.otel import instrument
instrument()   # adds sebbi to your global TracerProvider
```

Each sealed span gets two attributes: `sebbi.receipt.id` and `sebbi.receipt.url`. Recognised out of the box: the OpenTelemetry GenAI conventions (`gen_ai.operation.name` = `execute_tool`, `invoke_agent`), OpenInference (`openinference.span.kind`), Vercel AI SDK spans, and any span you mark with `span.set_attribute("sebbi.seal", True)`. Options: `llm=True` (also seal model calls), `all_spans=True`, `filter=fn`, `prefix="..."`, `on_receipt=fn`. Already batching spans? `BatchSpanProcessor(SebbiSpanExporter())` does the same without the link on the span.

Only two fingerprints per span leave your process: never span names, attributes, prompts or tool results.

**Prove a trace matches its receipts.** Export spans as OTLP/JSON (for example the Collector `file` exporter) and run:

```bash
sebbi verify-otlp traces.json
# MATCH    https://sebbi.pro/r/r3f9...  execute_tool refund
# 2 of 2 spans match their sealed receipts
```

Anyone holding the trace can run this, without trusting you or sebbi.pro. Change one attribute and that span shows `MISMATCH`. The fingerprint rules are in `span_payload()` and are identical in the JavaScript client.

## Reversing an action

```python
r = sebbi.seal(order, refund, "refund")
...
sebbi.reverse(r, "Customer cancelled; refund issued")
```

Refunds, cancellations and withdrawn decisions happen. A reversal never deletes anything: the original receipt stays sealed and valid, and its page shows **Reversed**, the reason and a link to the sealed reversal receipt. Only whoever sealed the original (this installation, or the same account key) can reverse it, and a reversal cannot itself be reversed.

## Run the MCP connector as a local command

```
uvx sebbi mcp
```

For AI clients and MCP marketplaces that start servers as a local command (stdio). A thin bridge to `https://sebbi.pro/mcp`; nothing is stored locally. 中文说明: https://github.com/justrightdecorators-ops/sebbi-sdk/blob/main/README.zh-CN.md

## Input Gate: garbage in, caught at the door

A sealed record proves nothing was changed afterwards. The Input Gate proves what went in was genuine to begin with. Each input is checked against the file its source hosts on its own domain, before your AI uses it.

```python
from sebbi.source import admit, GarbageIn

code = admit("pricing-agent", [
    {"domain": "your-supplier.com", "data": price_list, "label": "Q4 price list"},
], ref="quote-10482")
# reaches here only when every input is vouched for by its source
```

The data is fingerprinted on your machine and only the fingerprint is sent. `ADMIT` returns a `GI-` code to keep with the decision; `HOLD`, `REFUSE` or no connection raise `GarbageIn`. https://sebbi.pro/garbage-in

## Point of No Return: the safety gate

Some agent actions never come back: delete, pay, send, publish, sign. Put the gate in front of them.

```python
from sebbi.noreturn import no_return

@no_return(agent="billing-agent", action="refund payment",
           way_back={"type": "hold", "seconds": 900},
           amount=lambda order, amount: amount)
def refund(order, amount):
    ...   # runs only when the gate says GO
```

An irreversible action goes ahead with a way back (a fresh backup fingerprint, an exact undo, or a waiting window anyone responsible can cancel) or with a named person's approval on their phone. No answer means no, and if the gate cannot be reached the action does not happen. Every answer is sealed and timestamped into Bitcoin, with a public record page per action. Needs `SEBBI_API_KEY`. Rules, limits and the per-agent safety report: https://sebbi.pro/point-of-no-return

## Settings

| Environment | Meaning |
|---|---|
| `SEBBI_API_KEY` | Your key from https://sebbi.pro/connect. Optional. |
| `SEBBI_DISABLED=1` | Turn every receipt into a no-op (tests, local dev). |
| `SEBBI_ENDPOINT` | Override the API address. |
| `SEBBI_OWNER_SECRET` | Fix the owner secret (serverless, several machines). |

Or in code: `sebbi.configure(api_key="...")`.

## Pricing

- **Free lane:** 1,000 receipts a day, no account, no key.
- **With a sebbi.pro account:** up to 100,000 a day, receipts tied to your account and your evidence packs. 7 days free, then 50p per device per month.
- **Checking any receipt is always free.**

## Command line

```bash
sebbi seal "hello world" my-label   # prints the receipt link
sebbi check r3f9...                 # VALID / INVALID
```

## Check a receipt yourself

`GET https://sebbi.pro/v1/receipts/<id>` returns the leaf, the RFC 6962 inclusion path, the Merkle root and the chain block. The receipt page re-runs every check and lets anyone paste the original data to confirm it matches, fingerprinted in their own browser.

Docs: https://sebbi.pro/receipts · MCP server: https://sebbi.pro/mcp · Made by Monop Content.
