"use strict";
/*
 * sebbi - a receipt for every AI agent action.  https://sebbi.pro/receipts
 *
 *   npm install sebbi
 *
 *   const { receipt, last } = require("sebbi");      // or: import { receipt } from "sebbi"
 *   const decide = receipt("refund-decision", async (order) => ({ refund: true }));
 *   await decide({ id: 7 });
 *   console.log((await last()).url);                // https://sebbi.pro/r/...
 *
 * Inputs and outputs are fingerprinted (SHA-256 of canonical JSON) where your
 * code runs. Only fingerprints, a short label and a timestamp are sent.
 * Sealing runs in the background in batches and never throws into your code.
 * Zero dependencies. Node 18+, Deno, Bun, edge runtimes and browsers.
 */

const VERSION = "1.3.1";
const SITE = "https://sebbi.pro";
const env = (k) => (typeof process !== "undefined" && process.env ? process.env[k] || "" : "");

const cfg = {
  apiKey: env("SEBBI_API_KEY"),
  endpoint: env("SEBBI_ENDPOINT") || SITE + "/v1/receipts",
  enabled: !["1", "true", "yes", "on"].includes(env("SEBBI_DISABLED").toLowerCase()),
  client: "sebbi-js/" + VERSION,
};

function configure(o = {}) {
  if (o.apiKey !== undefined) cfg.apiKey = o.apiKey;
  if (o.endpoint !== undefined) cfg.endpoint = o.endpoint;
  if (o.enabled !== undefined) cfg.enabled = !!o.enabled;
  if (o.client !== undefined) cfg.client = o.client;
}

// ------------------------------------------------------------ fingerprints
const subtle = () => (globalThis.crypto && globalThis.crypto.subtle) || require("node:crypto").webcrypto.subtle;
const hex = (buf) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
const enc = (s) => new TextEncoder().encode(s);

function canonical(v, depth = 0) {
  if (depth > 32) return "__sebbi_deep__";
  if (v === null || v === undefined) return null;
  const t = typeof v;
  if (t === "string" || t === "boolean") return v;
  if (t === "number") return Number.isFinite(v) ? v : String(v);
  if (t === "bigint") return v.toString();
  if (t === "function" || t === "symbol") return { __type__: t };
  if (v instanceof Date) return v.toISOString();
  if (Array.isArray(v)) return v.map((x) => canonical(x, depth + 1));
  if (v instanceof Map) return canonical(Object.fromEntries(v), depth + 1);
  if (v instanceof Set) return canonical([...v], depth + 1);
  if (typeof v.toJSON === "function") return canonical(v.toJSON(), depth + 1);
  const out = {};
  for (const k of Object.keys(v)) out[k] = canonical(v[k], depth + 1);
  return out;
}

function stringify(v) {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(stringify).join(",") + "]";
  return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + stringify(v[k])).join(",") + "}";
}

const ascii = (s) => s.replace(/[\u007f-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));

async function fingerprint(value) {
  return hex(await subtle().digest("SHA-256", enc(ascii(stringify(canonical(value))))));
}

// ------------------------------------------------------------- ownership
// Each receipt commits to a secret only this installation holds, so only you
// can reverse your own receipts. Per-receipt secrets are derived from one
// master, so revealing one to reverse a receipt reveals nothing else.
let masterP = null;
function master() {
  if (masterP) return masterP;
  masterP = (async () => {
    const e = env("SEBBI_OWNER_SECRET");
    if (e) return e;
    const rnd = () => hex(globalThis.crypto ? globalThis.crypto.getRandomValues(new Uint8Array(32)) : require("node:crypto").randomBytes(32));
    try {
      const fs = require("node:fs"), path = require("node:path"), os = require("node:os");
      const p = path.join(os.homedir(), ".sebbi", "owner_secret");
      try { const v = fs.readFileSync(p, "utf8").trim(); if (v.length >= 32) return v; } catch (_) {}
      const v = rnd();
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, v, { mode: 0o600, flag: "wx" });
      return v;
    } catch (_) {
      return rnd(); // browsers, edge, read-only disks: this process can still reverse what it sealed
    }
  })();
  return masterP;
}

async function secretFor(id) {
  const key = await subtle().importKey("raw", enc(await master()), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await subtle().sign("HMAC", key, enc("sebbi-owner|" + id)));
}

const sha = async (s) => hex(await subtle().digest("SHA-256", enc(s)));
const newId = () => "r" + hex(globalThis.crypto ? globalThis.crypto.getRandomValues(new Uint8Array(12)) : require("node:crypto").randomBytes(12)).slice(0, 23);

// ------------------------------------------------------------------ receipt
class Receipt {
  constructor(label, inputHash, outputHash, outcome) {
    this.id = newId();
    this.label = String(label || "").slice(0, 80);
    this.inputHash = inputHash;
    this.outputHash = outputHash;
    this.ts = Date.now() / 1000;
    this.outcome = outcome || "ok";
    this.sealed = false;
    this.error = null;
    this.blockIndex = null;
    this.merkleRoot = null;
    this.reverses = null;
    this.reason = "";
    this._done = new Promise((r) => (this._resolve = r));
  }
  get url() { return SITE + "/r/" + this.id; }
  /** Resolves once sealed (or failed). */
  wait(ms = 15000) { kick(); return Promise.race([this._done, new Promise((r) => setTimeout(() => r(this), ms))]); }
  async wire() {
    const ih = this.inputHash, oh = this.outputHash;
    const d = { local_id: this.id, label: this.label, input_hash: ih, output_hash: oh, hash: await sha(ih + ":" + oh),
      ts: this.ts, outcome: this.outcome, owner: await sha(await secretFor(this.id)) };
    if (this.reverses) Object.assign(d, { reverses: this.reverses, reason: this.reason, owner_secret: await secretFor(this.reverses) });
    return d;
  }
  toJSON() {
    return { id: this.id, url: this.url, label: this.label, inputHash: this.inputHash, outputHash: this.outputHash, ts: this.ts,
      outcome: this.outcome, sealed: this.sealed, error: this.error, blockIndex: this.blockIndex, merkleRoot: this.merkleRoot,
      reverses: this.reverses };
  }
}

// ------------------------------------------------------------------ sender
const queue = [];
const counts = { queued: 0, sealed: 0, failed: 0 };
let notice = null, timer = null, inflight = 0;

function kick(delay = 0) {
  if (timer) { if (delay) return; clearTimeout(timer); }
  timer = setTimeout(drain, delay);
  if (timer && typeof timer.unref === "function" && delay) timer.unref();
}

async function drain() {
  timer = null;
  while (queue.length) {
    const batch = queue.splice(0, 100);
    inflight += batch.length;
    try { await send(batch); } finally { inflight -= batch.length; }
  }
}

async function send(batch) {
  let err = null;
  const body = JSON.stringify({ records: await Promise.all(batch.map((r) => r.wire())), sdk: cfg.client });
  const headers = { "Content-Type": "application/json", Accept: "application/json" };
  if (cfg.apiKey) headers.Authorization = "Bearer " + cfg.apiKey;
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const res = await fetch(cfg.endpoint, { method: "POST", headers, body });
      const doc = await res.json().catch(() => ({}));
      if (doc.message) notice = doc.message;
      if (res.ok) return apply(batch, doc);
      err = "http_" + res.status + (doc.error ? ":" + doc.error : "");
      if (res.status < 500 && res.status !== 429) break;
    } catch (e) {
      err = (e && e.name) || "network";
    }
    await new Promise((r) => setTimeout(r, Math.min(8000, 500 * 2 ** attempt)));
  }
  for (const r of batch) { r.error = err; counts.failed++; r._resolve(r); }
}

function apply(batch, doc) {
  const by = {};
  for (const x of doc.records || []) if (x && x.local_id) by[x.local_id] = x;
  for (const r of batch) {
    const x = by[r.id];
    if (x) {
      r.id = x.id || r.id; r.sealed = true; r.blockIndex = x.block_index; r.merkleRoot = x.merkle_root; counts.sealed++;
    } else { r.error = "not_in_response"; counts.failed++; }
    r._resolve(r);
  }
}

let lastP = Promise.resolve(null);

function enqueue(r) {
  if (!cfg.enabled) { r.error = "disabled"; r._resolve(r); return r; }
  queue.push(r); counts.queued++; kick(400);
  return r;
}

/** Seal one action. Resolves to its Receipt (url usable at once; .wait() for the seal). */
function seal(input, output, label = "", outcome = "ok") {
  const p = (async () => enqueue(new Receipt(label, await fingerprint(input), await fingerprint(output), outcome)))();
  lastP = p;
  p.catch(() => {});
  return p;
}

/** Internal: seal already-computed fingerprints, optionally under a chosen id (used by sebbi/otel). */
function _sealHashes(inputHash, outputHash, label = "", outcome = "ok", id = null) {
  const r = new Receipt(label, inputHash, outputHash, outcome);
  if (id) r.id = id;
  lastP = Promise.resolve(r);
  return enqueue(r);
}

/**
 * Reverse an action you sealed earlier. Nothing is deleted: the original stays
 * sealed and is shown as REVERSED, linked to the new reversal receipt. The
 * reason is public on both. Only whoever sealed the original can reverse it.
 */
function reverse(original, reason, output = null, label = "") {
  const oid = typeof original === "string" ? original : original && original.id;
  if (!oid) return Promise.reject(new Error("reverse(original, reason): original receipt or id required"));
  if (!reason) return Promise.reject(new Error("a reversal needs a reason; it is shown on both receipts"));
  const p = (async () => {
    const r = new Receipt(label || "reversal of " + oid, await fingerprint({ reverses: oid }), await fingerprint(output), "reversal");
    r.reverses = oid; r.reason = String(reason).slice(0, 300);
    return enqueue(r);
  })();
  lastP = p;
  return p;
}

/** Wrap a function (sync or async). receipt(fn) or receipt("label", fn). */
function receipt(label, fn) {
  if (typeof label === "function") { fn = label; label = fn.name || "action"; }
  if (typeof fn !== "function") return (f) => receipt(label, f);
  const name = label || fn.name || "action";
  const wrapped = function (...args) {
    const input = args.length === 1 ? args[0] : args;
    let out;
    try { out = fn.apply(this, args); } catch (e) { seal(input, { error_type: (e && e.name) || "Error" }, name, "error"); throw e; }
    if (out && typeof out.then === "function") {
      return out.then((v) => { seal(input, v, name); return v; },
        (e) => { seal(input, { error_type: (e && e.name) || "Error" }, name, "error"); throw e; });
    }
    seal(input, out, name);
    return out;
  };
  Object.defineProperty(wrapped, "name", { value: fn.name });
  return wrapped;
}

/**
 * Vercel AI SDK, Mastra, LangChain.js tool objects, MCP handlers: wraps every
 * tool's `execute` (or `func` / `invoke`) so each tool call gets a receipt.
 *   tools: wrapTools({ getWeather, sendEmail })
 */
function wrapTools(tools, prefix = "") {
  const wrapOne = (name, t) => {
    if (typeof t === "function") return receipt(prefix + name, t);
    if (!t || typeof t !== "object") return t;
    const c = Object.assign(Object.create(Object.getPrototypeOf(t)), t);
    for (const m of ["execute", "func", "invoke"]) {
      if (typeof t[m] === "function") { c[m] = receipt(prefix + (t.name || name), t[m].bind(t)); break; }
    }
    return c;
  };
  if (Array.isArray(tools)) return tools.map((t, i) => wrapOne((t && t.name) || "tool" + i, t));
  const out = {};
  for (const k of Object.keys(tools || {})) out[k] = wrapOne(k, tools[k]);
  return out;
}

/** Most recent receipt created in this process (a Promise). */
const last = () => lastP;

/** Send everything queued now. */
async function flush(ms = 5000) {
  const end = Date.now() + ms;
  kick();
  while (Date.now() < end) {
    if (!queue.length && !inflight) return true;
    await new Promise((r) => setTimeout(r, 50));
  }
  return false;
}

const stats = () => Object.assign({}, counts, { pending: queue.length, endpoint: cfg.endpoint, keyed: !!cfg.apiKey, notice });

/** Check a receipt by id. Anyone can, no key. */
async function check(id) {
  const res = await fetch(SITE + "/v1/receipts/" + encodeURIComponent(id));
  return res.json();
}

if (typeof process !== "undefined" && typeof process.on === "function") {
  process.on("beforeExit", () => { if (queue.length) kick(); });
}

module.exports = { receipt, seal, reverse, wrapTools, last, flush, configure, stats, fingerprint, check, Receipt, VERSION, _sealHashes };
