// sebbi for the Vercel AI SDK: tools your agent can call itself, plus wrapTools.
//   import { sebbiTools, wrapTools } from "sebbi/ai-sdk";
import { tool, jsonSchema } from "ai";
import { seal, reverse, check, wrapTools } from "./index.mjs";

const schema = (s) => jsonSchema(s);

const sealTool = () => {
  const inputSchema = schema({
    type: "object",
    properties: {
      action: { type: "string", description: "Short name of what was done, e.g. 'refund issued'. Public on the receipt; no personal data." },
      input: { description: "What the action was based on. Only its SHA-256 fingerprint leaves your system." },
      result: { description: "What the action produced. Only its SHA-256 fingerprint leaves your system." },
    },
    required: ["action"],
  });
  return tool({
    description: "Seal a tamper-evident receipt of an action you just took. Returns a public link anyone can use to check it.",
    inputSchema, parameters: inputSchema,
    execute: async ({ action, input = null, result = null }) => {
      const r = await (await seal(input, result, action)).wait();
      return { sealed: r.sealed, receiptId: r.id, receiptUrl: r.url, error: r.error };
    },
  });
};

const checkTool = () => {
  const inputSchema = schema({ type: "object", properties: { receiptId: { type: "string" } }, required: ["receiptId"] });
  return tool({
    description: "Check a sebbi receipt: is it intact, when was it sealed, and has the action been reversed?",
    inputSchema, parameters: inputSchema,
    execute: async ({ receiptId }) => {
      const d = await check(receiptId);
      return { valid: !!d.valid, status: d.status, action: d.label, sealedAt: d.sealed_at, reversal: d.reversal, error: d.error };
    },
  });
};

const reverseTool = () => {
  const inputSchema = schema({
    type: "object",
    properties: { receiptId: { type: "string" }, reason: { type: "string", description: "Why the action is being reversed. Public on both receipts." } },
    required: ["receiptId", "reason"],
  });
  return tool({
    description: "Reverse an action this app sealed earlier (refund, cancellation, withdrawn decision). The original stays on record, marked REVERSED and linked to a new reversal receipt.",
    inputSchema, parameters: inputSchema,
    execute: async ({ receiptId, reason }) => {
      const r = await (await reverse(receiptId, reason)).wait();
      return { sealed: r.sealed, reversalId: r.id, reversalUrl: r.url, error: r.error };
    },
  });
};

/** The three sebbi tools as an AI SDK ToolSet. */
export function sebbiTools() {
  return { sealReceipt: sealTool(), checkReceipt: checkTool(), reverseReceipt: reverseTool() };
}

export { wrapTools };
