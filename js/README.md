# sebbi: a receipt for every AI agent action

Your agent refunds a customer, sends an email, moves money or answers a patient.
Add one line and every one of those actions gets a **sealed receipt with a public link anyone can check**:
your customer, your auditor, your insurer, a regulator.

```bash
npm install sebbi
```

```js
import { receipt, last } from "sebbi";

const decideRefund = receipt("refund-decision", async (order) => {
  return { refund: true, amount: 42 };
});

await decideRefund({ id: 7 });
console.log((await last()).url);   // https://sebbi.pro/r/...  anyone can check it
```

No account needed to start. Zero dependencies. Node 18+, Bun, Deno, edge runtimes and browsers. ESM and CommonJS. Typed.

**Provable AI compliance.** sebbi.pro is the provable AI compliance platform: every AI decision sealed, timestamped into Bitcoin and verifiable by anyone, without trusting you or us. Prove it yourself in a minute, no account: https://sebbi.pro/provable-ai-compliance

## Why teams add it

- **Proof, not logs.** Each receipt sits in a Merkle tree sealed into the sebbi.pro chain, witnessed by independent chains, timestamped into Bitcoin and signed post-quantum. Nobody can quietly edit it afterwards.
- **Your data stays yours.** Inputs and outputs are fingerprinted (SHA-256) where your code runs. Only fingerprints, a short label and a timestamp are sent.
- **Never slows your agent.** Sealing runs in the background in batches and never throws into your code.
- **Reversals done properly.** Refund, cancel or withdraw an action and the original receipt is shown as reversed, linked to a sealed reversal receipt. Nothing disappears.

## Your framework, one line

**Vercel AI SDK**
```js
import { wrapTools } from "sebbi";
const result = await generateText({ model, prompt, tools: wrapTools({ getWeather, sendEmail }) });
```

**Vercel AI SDK: tools your agent calls itself**
```js
import { generateText, isStepCount } from "ai";
import { sebbiTools } from "sebbi/ai-sdk";

const { text } = await generateText({
  model: "anthropic/claude-sonnet-5.5",
  prompt: "Refund order 7 for £42 and give me the receipt link.",
  tools: { ...myTools, ...sebbiTools() },   // sealReceipt, checkReceipt, reverseReceipt
  stopWhen: isStepCount(5),
});
```

**LangChain.js / Mastra / anything with tool objects**: `wrapTools([...tools])` wraps each tool's `execute`, `func` or `invoke`.

**MCP servers (TypeScript SDK)**
```js
server.tool("lookup_customer", schema, receipt("lookup_customer", async (args) => { ... }));
```

**Anything else**
```js
import { seal } from "sebbi";
const r = await seal(request, result, "send-invoice");
await r.wait();   // optional
console.log(r.url, r.sealed, r.blockIndex);
```

## OpenTelemetry

Already tracing? Add the processor and every agent run and tool call you trace gets a receipt, with the link written onto the span (`sebbi.receipt.id`, `sebbi.receipt.url`).

```js
import { NodeSDK } from "@opentelemetry/sdk-node";
import { SebbiSpanProcessor } from "sebbi/otel";

new NodeSDK({ spanProcessors: [new SebbiSpanProcessor(), /* your exporter's processor */] }).start();
```

**Vercel AI SDK:** turn on telemetry and every `ai.toolCall` and `ai.generateText` span is sealed:

```js
await generateText({ model, tools, prompt, experimental_telemetry: { isEnabled: true } });
```

Also recognised: OpenTelemetry GenAI conventions (`gen_ai.operation.name`), OpenInference (`openinference.span.kind`) and any span with `sebbi.seal = true`. Options: `{ llm, allSpans, filter, prefix, onReceipt }`. `SebbiSpanExporter` does the same inside an existing `BatchSpanProcessor`. Only two fingerprints per span leave your process. Fingerprints match the Python client exactly, so `sebbi verify-otlp traces.json` checks spans from either.

## Reversing an action

```js
import { reverse } from "sebbi";
await reverse(r, "Customer cancelled; refund issued");
```

The original receipt stays sealed and valid, and its page shows **Reversed**, the reason and a link to the reversal receipt. Only whoever sealed the original (this installation, or the same account key) can reverse it, and a reversal cannot itself be reversed.

## Point of No Return: the safety gate

Some agent actions never come back: delete, pay, send, publish, sign. Put the gate in front of them.

```js
import { noReturn } from "sebbi/noreturn";

const refund = noReturn(
  { agent: "billing-agent", action: "refund payment",
    wayBack: { type: "hold", seconds: 900 }, amount: (order, amount) => amount },
  async (order, amount) => { /* runs only when the gate says GO */ });
```

An irreversible action goes ahead with a way back (a fresh backup fingerprint, an exact undo, or a waiting window anyone responsible can cancel) or with a named person's approval on their phone. No answer means no, and if the gate cannot be reached the action does not happen. Every answer is sealed and timestamped into Bitcoin, with a public record page per action. Needs `SEBBI_API_KEY`. Rules, limits and the per-agent safety report: https://sebbi.pro/point-of-no-return

## Settings

| Environment | Meaning |
|---|---|
| `SEBBI_API_KEY` | Your key from https://sebbi.pro/connect. Optional. |
| `SEBBI_DISABLED=1` | Turn every receipt into a no-op. |
| `SEBBI_OWNER_SECRET` | Fix the owner secret (serverless, several machines). |

Or in code: `configure({ apiKey: "..." })`.

## Pricing

- **Free lane:** 1,000 receipts a day, no account, no key.
- **With a sebbi.pro account:** up to 100,000 a day, tied to your account and your evidence packs. 7 days free, then 50p per device per month.
- **Checking any receipt is always free:** `check(id)` or https://sebbi.pro/r/&lt;id&gt;.

Docs: https://sebbi.pro/receipts · MCP server: https://sebbi.pro/mcp · Made by Monop Content.
