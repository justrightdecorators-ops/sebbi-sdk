"use strict";
/**
 * sebbi/source - the Input Gate: garbage in, caught at the door.
 * https://sebbi.pro/garbage-in
 *
 *   const { admit } = require("sebbi/source");
 *   const code = await admit("pricing-agent", [{ domain: "supplier.com", data: priceList, label: "Q4 price list" }], { ref: "quote-10482" });
 *
 * Each input is fingerprinted on your machine; only the fingerprint, the source domain and the
 * label are sent. ADMIT resolves with the GI- code. HOLD, REFUSE or no connection throw GarbageIn:
 * if the gate cannot be reached the data is not used. No dependencies.
 */
const crypto = require("crypto");

const gate = () => process.env.SEBBI_GATE || "https://sebbi.pro";

class GarbageIn extends Error {
  constructor(message, answer) { super(message); this.name = "GarbageIn"; this.answer = answer || {}; }
}

function fingerprint(data) {
  if (Buffer.isBuffer(data) || data instanceof Uint8Array) return crypto.createHash("sha256").update(data).digest("hex");
  if (typeof data !== "string") data = canonical(data);
  return crypto.createHash("sha256").update(data.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim(), "utf8").digest("hex");
}

function canonical(v) {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(canonical).join(",") + "]";
  return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canonical(v[k])).join(",") + "}";
}

async function post(path, body, key) {
  key = key || process.env.SEBBI_API_KEY || process.env.SEBBI_KEY || "";
  let r;
  try {
    r = await fetch(gate() + "/x/garbagegate/" + path, { method: "POST", body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + key, "User-Agent": "sebbi-js-source" } });
  } catch (e) { throw new GarbageIn("gate not reachable: " + (e && e.message)); }
  try { return await r.json(); } catch (e) { throw new GarbageIn("gate answered " + r.status); }
}

function wire(inputs) {
  return (inputs || []).map((i) => {
    const w = { domain: i.domain || i.source, hash: i.hash || i.sha256 || fingerprint(i.data) };
    if (i.label) w.label = i.label;
    return w;
  });
}

/** Ask the gate and resolve with its whole answer, whatever the verdict. */
async function check(agent, inputs, options) {
  const o = options || {};
  const body = { agent, inputs: wire(inputs) };
  if (o.ref) body.ref = o.ref;
  return post("admit", body, o.key);
}

/** Resolve with the GI- code when the gate says ADMIT. Throw GarbageIn on anything else. */
async function admit(agent, inputs, options) {
  const o = options || {};
  const r = await check(agent, inputs, o);
  if (r.verdict === "ADMIT" || (r.verdict === "HOLD" && o.allowHold)) return r.code;
  throw new GarbageIn(r.why || r.message || r.error || "not admitted", r);
}

module.exports = { admit, check, fingerprint, GarbageIn };
