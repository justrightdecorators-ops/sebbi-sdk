"use strict";
/*
 * sebbi for OpenTelemetry: a sealed receipt for every agent and tool span you
 * already trace, with the receipt link written onto the span itself.
 *
 *   const { SebbiSpanProcessor } = require("sebbi/otel");
 *   new NodeSDK({ spanProcessors: [new SebbiSpanProcessor(), ...yourProcessors] }).start();
 *
 * Vercel AI SDK: turn on experimental_telemetry: { isEnabled: true } and every
 * ai.toolCall / ai.generateText span gets a receipt. Also recognised: the
 * OpenTelemetry GenAI conventions (gen_ai.operation.name), OpenInference
 * (openinference.span.kind) and any span with attribute sebbi.seal = true.
 *
 * Only two SHA-256 fingerprints, a short label and a timestamp leave your
 * process. Fingerprints follow the same rules as the Python client, so
 * `sebbi verify-otlp traces.json` checks spans from either.
 */
const core = require("./index.cjs");

const ATTR_ID = "sebbi.receipt.id";
const ATTR_URL = "sebbi.receipt.url";
const ATTR_MARK = "sebbi.seal";
const SPEC = "sebbi-otel-span/1";
const SITE = "https://sebbi.pro";

const OUTPUT_PREFIXES = [
  "gen_ai.output.", "gen_ai.completion", "gen_ai.response.", "gen_ai.usage.", "gen_ai.tool.call.result",
  "output.", "llm.output_messages", "llm.token_count.",
  "ai.response.", "ai.toolCall.result", "ai.result.", "ai.usage.",
];
const GENAI = { execute_tool: "tool", invoke_agent: "agent", create_agent: "agent", chat: "llm", text_completion: "llm", generate_content: "llm" };
const OPENINF = { TOOL: "tool", AGENT: "agent", LLM: "llm" };
const VERCEL_AGENT = ["ai.generateText", "ai.streamText", "ai.generateObject", "ai.streamObject"];

function spanKind(name, attributes) {
  const a = attributes || {};
  if ([true, "true", "1", 1].includes(a[ATTR_MARK])) return "marked";
  const op = a["gen_ai.operation.name"];
  if (typeof op === "string" && GENAI[op]) return GENAI[op];
  const oi = a["openinference.span.kind"];
  if (typeof oi === "string" && OPENINF[oi.toUpperCase()]) return OPENINF[oi.toUpperCase()];
  const vid = a["ai.operationId"] || name || "";
  if (vid === "ai.toolCall") return "tool";
  if (VERCEL_AGENT.includes(vid)) return "agent";
  if (vid.startsWith("ai.") && (vid.endsWith(".doGenerate") || vid.endsWith(".doStream"))) return "llm";
  return null;
}

function spanLabel(name, attributes, kind, prefix = "") {
  const a = attributes || {};
  const first = (...keys) => { for (const k of keys) if (typeof a[k] === "string" && a[k]) return a[k]; return name || "span"; };
  let s;
  if (kind === "tool") s = "tool:" + first("gen_ai.tool.name", "tool.name", "ai.toolCall.name");
  else if (kind === "agent") s = "agent:" + first("gen_ai.agent.name", "agent.name", "ai.telemetry.functionId");
  else if (kind === "llm") s = "llm:" + first("gen_ai.request.model", "llm.model_name", "ai.model.id");
  else s = name || "span";
  return (prefix + s).slice(0, 80);
}

// Numbers, written the same way in Python and JavaScript.
function num(x) {
  if (!Number.isFinite(x)) return Number.isNaN(x) ? "NaN" : x > 0 ? "Infinity" : "-Infinity";
  if (Number.isInteger(x)) return Math.abs(x) < 2 ** 53 ? (x === 0 ? 0 : x) : String(x);
  return String(x);
}
function val(v) {
  if (Array.isArray(v)) return v.map(val);
  if (typeof v === "number") return num(v);
  if (v === undefined || v === null) return null;
  if (typeof v === "string" || typeof v === "boolean") return v;
  return String(v);
}
function attrs(a, wantOutput) {
  const out = {};
  for (const k of Object.keys(a || {})) {
    if (k.startsWith("sebbi.")) continue;
    if (OUTPUT_PREFIXES.some((p) => k.startsWith(p)) === wantOutput) out[k] = val(a[k]);
  }
  return out;
}
function nanos(t) {
  if (Array.isArray(t)) return (BigInt(t[0]) * 1000000000n + BigInt(t[1])).toString();
  if (typeof t === "bigint") return t.toString();
  if (typeof t === "string") return BigInt(t || "0").toString();
  return BigInt(Math.trunc(Number(t) || 0)).toString();
}
const statusName = (c) => (typeof c === "number" ? { 0: "UNSET", 1: "OK", 2: "ERROR" }[c] || "UNSET"
  : (["UNSET", "OK", "ERROR"].includes(String(c || "").toUpperCase().replace("STATUS_CODE_", "")) ? String(c).toUpperCase().replace("STATUS_CODE_", "") : "UNSET"));

/** The two documents a span's receipt fingerprints. Same rules in every sebbi client. */
function buildPayload(p) {
  const input = {
    spec: SPEC,
    name: p.name || "",
    trace_id: String(p.traceId || "").toLowerCase(),
    span_id: String(p.spanId || "").toLowerCase(),
    parent_span_id: String(p.parentSpanId || "").toLowerCase() || null,
    start_time_unix_nano: nanos(p.start || 0),
    attributes: attrs(p.attributes, false),
  };
  const output = {
    end_time_unix_nano: nanos(p.end || 0),
    status: statusName(p.statusCode || 0),
    status_message: p.statusMessage || "",
    attributes: attrs(p.attributes, true),
    events: (p.events || []).map((e) => ({ name: e.name || "", time_unix_nano: nanos(e.time || 0),
      attributes: Object.assign(attrs(e.attributes, false), attrs(e.attributes, true)) })),
  };
  return { input, output };
}

/** { input, output } documents for a finished OpenTelemetry JS span. */
function spanPayload(span) {
  const ctx = typeof span.spanContext === "function" ? span.spanContext() : span._spanContext || {};
  const parent = (span.parentSpanContext && span.parentSpanContext.spanId) || span.parentSpanId || null;
  return buildPayload({
    name: span.name, traceId: ctx.traceId, spanId: ctx.spanId, parentSpanId: parent,
    start: span.startTime, end: span.endTime, attributes: span.attributes,
    statusCode: span.status ? span.status.code : 0, statusMessage: span.status ? span.status.message : "",
    events: (span.events || []).map((e) => ({ name: e.name, time: e.time, attributes: e.attributes })),
  });
}

async function spanFingerprints(span) {
  const { input, output } = spanPayload(span);
  return { inputHash: await core.fingerprint(input), outputHash: await core.fingerprint(output) };
}

function policy(o = {}) {
  return (span) => {
    const kind = spanKind(span.name, span.attributes);
    if (typeof o.filter === "function") { try { return o.filter(span) ? kind || "span" : null; } catch (_) { return null; } }
    if (o.allSpans) return kind || "span";
    if (kind === "tool" || kind === "agent" || kind === "marked" || (kind === "llm" && o.llm)) return kind;
    return null;
  };
}

const newId = () => {
  const b = globalThis.crypto ? globalThis.crypto.getRandomValues(new Uint8Array(12)) : require("node:crypto").randomBytes(12);
  return "r" + Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("").slice(0, 23);
};

/**
 * Seals agent and tool spans as they end, and stamps each with its receipt
 * link (sebbi.receipt.id / sebbi.receipt.url) when it starts.
 * Options: { llm, allSpans, filter(span), prefix, onReceipt(span, receipt) }
 */
class SebbiSpanProcessor {
  constructor(options = {}) {
    this._o = options;
    this._wants = policy(options);
    this._pending = new Set();
  }
  onStart(span) {
    try {
      if (this._wants(span)) {
        const id = newId();
        span.setAttribute(ATTR_ID, id);
        span.setAttribute(ATTR_URL, SITE + "/r/" + id);
      }
    } catch (_) {}
  }
  onEnd(span) {
    let kind;
    try { kind = this._wants(span); } catch (_) { return; }
    if (!kind) return;
    const p = (async () => {
      const { inputHash, outputHash } = await spanFingerprints(span);
      const id = span.attributes && typeof span.attributes[ATTR_ID] === "string" ? span.attributes[ATTR_ID] : null;
      const outcome = statusName(span.status ? span.status.code : 0) === "ERROR" ? "error" : "ok";
      const r = core._sealHashes(inputHash, outputHash, spanLabel(span.name, span.attributes, kind, this._o.prefix || ""), outcome, id);
      if (typeof this._o.onReceipt === "function") this._o.onReceipt(span, r);
      return r;
    })().catch(() => null).finally(() => this._pending.delete(p));
    this._pending.add(p);
  }
  async forceFlush() { await Promise.all([...this._pending]); await core.flush(30000); }
  async shutdown() { await this.forceFlush(); }
}

/**
 * The same sealing as a SpanExporter, for pipelines that already batch spans:
 *   new BatchSpanProcessor(new SebbiSpanExporter())
 * Exporters see spans after they end, so the link is not written onto the
 * span; use SebbiSpanProcessor for that. Always reports success.
 */
class SebbiSpanExporter {
  constructor(options = {}) { this._proc = new SebbiSpanProcessor(options); }
  export(spans, resultCallback) {
    for (const s of spans || []) this._proc.onEnd(s);
    resultCallback({ code: 0 });
  }
  forceFlush() { return this._proc.forceFlush(); }
  shutdown() { return this._proc.shutdown(); }
}

module.exports = { SebbiSpanProcessor, SebbiSpanExporter, spanKind, spanLabel, spanPayload, spanFingerprints, buildPayload, ATTR_ID, ATTR_URL };
