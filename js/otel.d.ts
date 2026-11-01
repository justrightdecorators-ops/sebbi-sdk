import type { Receipt } from "./index";
export interface SebbiOtelOptions {
  /** Also seal every model call (chat / doGenerate spans). */
  llm?: boolean;
  /** Seal every span. Watch your daily volume. */
  allSpans?: boolean;
  /** Your own rule, asked at span start and end; the answer at end decides. */
  filter?: (span: any) => boolean;
  /** Put in front of every receipt label. */
  prefix?: string;
  /** Called after each span is queued for sealing. */
  onReceipt?: (span: any, receipt: Receipt) => void;
}
/** OpenTelemetry SpanProcessor: seals agent and tool spans and writes sebbi.receipt.id / sebbi.receipt.url onto them. */
export declare class SebbiSpanProcessor {
  constructor(options?: SebbiOtelOptions);
  onStart(span: any, parentContext?: any): void;
  onEnd(span: any): void;
  forceFlush(): Promise<void>;
  shutdown(): Promise<void>;
}
/** OpenTelemetry SpanExporter with the same sealing (no link written onto the span). */
export declare class SebbiSpanExporter {
  constructor(options?: SebbiOtelOptions);
  export(spans: any[], resultCallback: (result: { code: number }) => void): void;
  forceFlush(): Promise<void>;
  shutdown(): Promise<void>;
}
export declare function spanKind(name: string, attributes?: Record<string, unknown>): "tool" | "agent" | "llm" | "marked" | null;
export declare function spanLabel(name: string, attributes: Record<string, unknown> | undefined, kind: string | null, prefix?: string): string;
export declare function spanPayload(span: any): { input: Record<string, unknown>; output: Record<string, unknown> };
export declare function spanFingerprints(span: any): Promise<{ inputHash: string; outputHash: string }>;
export declare function buildPayload(p: Record<string, unknown>): { input: Record<string, unknown>; output: Record<string, unknown> };
export declare const ATTR_ID: "sebbi.receipt.id";
export declare const ATTR_URL: "sebbi.receipt.url";
