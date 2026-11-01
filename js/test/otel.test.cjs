// node --test test/   (uses the real OpenTelemetry SDK when installed, duck-typed spans otherwise)
"use strict";
process.env.SEBBI_OWNER_SECRET = process.env.SEBBI_OWNER_SECRET || "test-owner-secret";
const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const sebbi = require("../index.cjs");
const otel = require("../otel.cjs");

const STORE = {};
let server;

test.before(async () => {
  server = http.createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const doc = JSON.parse(body);
      const records = doc.records.map((r) => { STORE[r.local_id] = r; return { local_id: r.local_id, id: r.local_id, block_index: 1, merkle_root: "0".repeat(64) }; });
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ records, lane: "free" }));
    });
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  sebbi.configure({ endpoint: "http://127.0.0.1:" + server.address().port + "/v1/receipts", enabled: true });
});
test.after(() => server.close());

// Same inputs and expected hashes as the Python test_golden_fingerprint.
test("golden fingerprints match the Python client", async () => {
  const { input, output } = otel.buildPayload({
    name: "execute_tool refund", traceId: "0af7651916cd43dd8448eb211c80319c", spanId: "b7ad6b7169203331", parentSpanId: "00f067aa0ba902b7",
    start: "1700000000000000000", end: [1700000000, 250000000],
    attributes: { "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "refund", "gen_ai.request.temperature": 0.7,
      n: 3, flag: true, list: ["a", "b"], price: 42.0, note: "café ✓", "gen_ai.tool.call.result": "ok", "sebbi.receipt.id": "rignored" },
    statusCode: 2, statusMessage: "declined", events: [{ name: "approved", time: 1700000000100000000n, attributes: { limit: 100.5 } }],
  });
  assert.equal(await sebbi.fingerprint(input), "415e9100aeb21d0485892753c40ab29949a553ab3ed9d311531d4ebcc9417bb1");
  assert.equal(await sebbi.fingerprint(output), "3897a8979b60b7ccc3862798504666a3d939da71b3c6c020815253c7ff02febc");
});

test("span kinds and labels", () => {
  const k = otel.spanKind;
  assert.equal(k("ai.toolCall", { "ai.toolCall.name": "w" }), "tool");
  assert.equal(k("ai.streamText", {}), "agent");
  assert.equal(k("ai.streamText.doStream", {}), "llm");
  assert.equal(k("x", { "gen_ai.operation.name": "execute_tool" }), "tool");
  assert.equal(k("x", { "openinference.span.kind": "agent" }), "agent");
  assert.equal(k("x", { "sebbi.seal": true }), "marked");
  assert.equal(k("GET /", {}), null);
  assert.equal(otel.spanLabel("ai.toolCall", { "ai.toolCall.name": "getWeather" }, "tool", "shop/"), "shop/tool:getWeather");
});

// A minimal span with the OpenTelemetry JS ReadableSpan shape.
function fakeSpan(name, attributes, status = { code: 0 }) {
  const s = { name, attributes: { ...attributes }, status, events: [], startTime: [1700000000, 1], endTime: [1700000000, 9],
    parentSpanContext: undefined, spanContext: () => ({ traceId: "0af7651916cd43dd8448eb211c80319c", spanId: "b7ad6b7169203331" }),
    setAttribute(k, v) { this.attributes[k] = v; return this; } };
  return s;
}

test("processor stamps, seals and matches fingerprints", async () => {
  const got = [];
  const p = new otel.SebbiSpanProcessor({ onReceipt: (s, r) => got.push(r) });
  const s = fakeSpan("ai.toolCall", { "ai.toolCall.name": "refund", "ai.toolCall.args": '{"order":7}' });
  p.onStart(s);
  const id = s.attributes[otel.ATTR_ID];
  assert.match(id, /^r[0-9a-f]{23}$/);
  assert.equal(s.attributes[otel.ATTR_URL], "https://sebbi.pro/r/" + id);
  s.attributes["ai.toolCall.result"] = '{"ok":true}';
  p.onEnd(s);
  const plain = fakeSpan("db", {});
  p.onStart(plain); p.onEnd(plain);
  await p.forceFlush();
  const rec = STORE[id];
  assert.ok(rec, "sealed under the id written on the span");
  const fp = await otel.spanFingerprints(s);
  assert.equal(rec.input_hash, fp.inputHash);
  assert.equal(rec.output_hash, fp.outputHash);
  assert.equal(rec.label, "tool:refund");
  assert.equal(got.length, 1);
  assert.equal(plain.attributes[otel.ATTR_ID], undefined);
});

test("error status and exporter mode", async () => {
  const e = new otel.SebbiSpanExporter();
  const s = fakeSpan("x", { "openinference.span.kind": "TOOL", "tool.name": "pay" }, { code: 2, message: "declined" });
  let result;
  e.export([s], (r) => (result = r));
  await e.forceFlush();
  assert.equal(result.code, 0);
  const rec = Object.values(STORE).find((r) => r.label === "tool:pay");
  assert.equal(rec.outcome, "error");
});

test("real OpenTelemetry SDK", async (t) => {
  let base;
  try { base = require("@opentelemetry/sdk-trace-base"); } catch (_) { return t.skip("@opentelemetry/sdk-trace-base not installed"); }
  const proc = new otel.SebbiSpanProcessor();
  const ended = [];
  const collect = { onStart() {}, onEnd(s) { ended.push(s); }, forceFlush: async () => {}, shutdown: async () => {} };
  const provider = new base.BasicTracerProvider({ spanProcessors: [proc, collect] }); // OpenTelemetry JS 2.x
  if (typeof provider.addSpanProcessor === "function") { provider.addSpanProcessor(proc); provider.addSpanProcessor(collect); } // 1.x
  const tracer = provider.getTracer("t");
  const span = tracer.startSpan("ai.toolCall", { attributes: { "ai.toolCall.name": "lookup", "ai.toolCall.args": "{}" } });
  span.setAttribute("ai.toolCall.result", "42");
  span.end();
  await proc.forceFlush();
  const s = ended[0];
  const id = s.attributes[otel.ATTR_ID];
  assert.ok(id, "receipt id on the real span");
  const fp = await otel.spanFingerprints(s);
  assert.equal(STORE[id].input_hash, fp.inputHash);
  assert.equal(STORE[id].output_hash, fp.outputHash);
});
