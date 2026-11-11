#!/usr/bin/env node
"use strict";
/**
 * npx -y sebbi mcp   - run the sebbi.pro MCP connector as a local command (stdio).
 * A thin bridge: each message on stdin is passed to https://sebbi.pro/mcp and the answer is
 * written to stdout. Nothing is stored locally. SEBBI_MCP_URL points it somewhere else.
 */
const readline = require("readline");
const URL_ = process.env.SEBBI_MCP_URL || "https://sebbi.pro/mcp";
const cmd = process.argv[2];

if (cmd !== "mcp") {
  console.log("sebbi - the proof layer for AI\n\n  npx -y sebbi mcp    run the sebbi.pro MCP connector as a local command (stdio)\n\nDocs: https://sebbi.pro/connect");
  process.exit(cmd && cmd !== "-h" && cmd !== "--help" ? 1 : 0);
}

let session = null;
let chain = Promise.resolve();

async function pass(line) {
  let msg;
  try { msg = JSON.parse(line); } catch (e) { return; }
  const ids = (Array.isArray(msg) ? msg : [msg]).filter((m) => m && typeof m === "object" && "id" in m && "method" in m).map((m) => m.id);
  try {
    const h = { "Content-Type": "application/json", Accept: "application/json, text/event-stream", "User-Agent": "sebbi-mcp-bridge-js" };
    if (session) h["Mcp-Session-Id"] = session;
    const r = await fetch(URL_, { method: "POST", headers: h, body: JSON.stringify(msg) });
    session = r.headers.get("mcp-session-id") || session;
    const body = (await r.text()).trim();
    if (!body) return;
    const outs = (r.headers.get("content-type") || "").includes("text/event-stream")
      ? body.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).filter(Boolean)
      : [body];
    for (const o of outs) { try { JSON.parse(o); process.stdout.write(o.replace(/\n/g, " ") + "\n"); } catch (e) { /* not JSON: skip */ } }
  } catch (e) {
    for (const id of ids) process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, error: { code: -32000, message: "sebbi.pro not reachable: " + (e && e.message) } }) + "\n");
  }
}

const rl = readline.createInterface({ input: process.stdin });
rl.on("line", (line) => { line = line.trim(); if (line) chain = chain.then(() => pass(line)); });
rl.on("close", () => chain.then(() => process.exit(0)));
