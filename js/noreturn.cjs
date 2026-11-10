"use strict";
/**
 * sebbi/noreturn - Point of No Return: the safety gate for AI agent actions that cannot be undone.
 * https://sebbi.pro/point-of-no-return
 *
 *   const { noReturn, clear, done, NoReturnStop } = require("sebbi/noreturn");
 *
 *   const refund = noReturn({ agent: "billing-agent", action: "refund payment",
 *                             wayBack: { type: "hold", seconds: 900 } }, async (order, amount) => { ... });
 *
 * The function only runs when the gate says GO. HOLD and NEEDS_HUMAN wait for the window or
 * the person. STOP, a refusal, a cancellation, no answer or no connection all throw
 * NoReturnStop: if the gate cannot be reached the action does not happen. No dependencies.
 */
const crypto = require("crypto");

const env = (k) => (typeof process !== "undefined" && process.env && process.env[k]) || "";
const gate = () => env("SEBBI_GATE") || "https://sebbi.pro";

class NoReturnStop extends Error {
  constructor(message, answer) {
    super(message);
    this.name = "NoReturnStop";
    this.answer = answer || null;
  }
}

async function post(path, body, key) {
  key = key || env("SEBBI_API_KEY") || env("SEBBI_KEY");
  let res;
  try {
    res = await fetch(gate() + "/x/noreturn/" + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + key, "User-Agent": "sebbi-js-noreturn" },
      body: JSON.stringify(body),
      signal: typeof AbortSignal !== "undefined" && AbortSignal.timeout ? AbortSignal.timeout(20000) : undefined,
    });
  } catch (e) {
    throw new NoReturnStop("gate not reachable: " + (e && e.message));
  }
  try {
    return await res.json();
  } catch (e) {
    throw new NoReturnStop("gate answered " + res.status);
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Ask the gate. Resolves with the PN- code once the answer is GO, otherwise throws NoReturnStop. */
async function clear(o = {}) {
  const body = {};
  for (const [k, v] of Object.entries({ agent: o.agent, action: o.action, target: o.target, summary: o.summary, amount: o.amount,
    currency: o.currency, way_back: o.wayBack || o.way_back, irreversible: o.irreversible })) {
    if (v !== undefined && v !== null) body[k] = v;
  }
  const wait = o.wait !== false, poll = o.poll || 15, maxWait = o.maxWait || 86400;
  let r = await post("check", body, o.key);
  const start = Date.now();
  for (;;) {
    const v = r.verdict;
    if (v === "GO") return r.code;
    if ((v !== "HOLD" && v !== "NEEDS_HUMAN") || !wait) throw new NoReturnStop(r.message || r.why || r.error || String(v), r);
    if (o.onWait) o.onWait(r);
    if ((Date.now() - start) / 1000 > maxWait) throw new NoReturnStop("waited too long for " + v, r);
    await sleep(1000 * Math.max(1, Math.min(poll, Math.floor(r.seconds_to_wait || poll))));
    r = Object.assign({}, r, await post("release", { code: r.code }, o.key));
  }
}

/** Seal that the action went ahead. result is fingerprinted here and never sent. */
async function done(code, result, key) {
  const body = { code };
  if (result !== undefined && result !== null) {
    let text;
    try { text = JSON.stringify(result); } catch (e) { text = String(result); }
    body.result_sha256 = crypto.createHash("sha256").update(String(text)).digest("hex");
  }
  try { return await post("done", body, key); } catch (e) { return null; }
}

/** Seal that the backup or undo was used. */
function undo(code, note, key) {
  return post("undo", { code, note }, key);
}

/** Wrap a function: it runs only when the gate says GO. target, summary, amount and wayBack may be functions of the call's arguments. */
function noReturn(o, fn) {
  return async function (...args) {
    const val = (v) => (typeof v === "function" ? v(...args) : v);
    const code = await clear(Object.assign({}, o, { target: val(o.target), summary: val(o.summary), amount: val(o.amount),
      wayBack: val(o.wayBack || o.way_back) }));
    const out = await fn.apply(this, args);
    await done(code, out, o.key);
    return out;
  };
}

module.exports = { noReturn, clear, done, undo, NoReturnStop };
