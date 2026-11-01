export declare const VERSION: string;
export declare class Receipt {
  id: string; label: string; inputHash: string; outputHash: string; ts: number; outcome: string;
  sealed: boolean; error: string | null; blockIndex: number | null; merkleRoot: string | null; reverses: string | null;
  readonly url: string;
  wait(ms?: number): Promise<Receipt>;
  toJSON(): Record<string, unknown>;
}
export declare function receipt<F extends (...a: any[]) => any>(fn: F): F;
export declare function receipt<F extends (...a: any[]) => any>(label: string, fn: F): F;
export declare function receipt(label: string): <F extends (...a: any[]) => any>(fn: F) => F;
export declare function seal(input: unknown, output: unknown, label?: string, outcome?: "ok" | "error"): Promise<Receipt>;
export declare function reverse(original: Receipt | string, reason: string, output?: unknown, label?: string): Promise<Receipt>;
export declare function wrapTools<T>(tools: T, prefix?: string): T;
export declare function last(): Promise<Receipt | null>;
export declare function flush(ms?: number): Promise<boolean>;
export declare function configure(o: { apiKey?: string; endpoint?: string; enabled?: boolean; client?: string }): void;
export declare function stats(): { queued: number; sealed: number; failed: number; pending: number; endpoint: string; keyed: boolean; notice: string | null };
export declare function fingerprint(value: unknown): Promise<string>;
export declare function check(id: string): Promise<Record<string, any>>;
declare const _default: {
  receipt: typeof receipt; seal: typeof seal; reverse: typeof reverse; wrapTools: typeof wrapTools; last: typeof last;
  flush: typeof flush; configure: typeof configure; stats: typeof stats; fingerprint: typeof fingerprint; check: typeof check;
};
export default _default;
