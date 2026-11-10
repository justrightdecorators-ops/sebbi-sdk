export type WayBack =
  | { type: "backup"; sha256: string; taken: string; where?: string; restore_tested?: boolean }
  | { type: "undo"; how: string; until?: string }
  | { type: "hold"; seconds: number };
export interface GateAnswer { code?: string; verdict?: "GO" | "HOLD" | "NEEDS_HUMAN" | "STOP"; why?: string; message?: string;
  human_link?: string; cancel_link?: string; seconds_to_wait?: number; record?: string; [k: string]: unknown }
export interface ClearOptions<A extends unknown[] = unknown[]> {
  agent: string; action: string;
  target?: string | ((...args: A) => string); summary?: string | ((...args: A) => string);
  amount?: number | ((...args: A) => number); currency?: string;
  wayBack?: WayBack | ((...args: A) => WayBack); irreversible?: boolean;
  wait?: boolean; poll?: number; maxWait?: number; onWait?: (answer: GateAnswer) => void; key?: string;
}
export class NoReturnStop extends Error { answer: GateAnswer | null }
/** Ask the gate. Resolves with the PN- code once the answer is GO, otherwise throws NoReturnStop. */
export function clear(options: ClearOptions): Promise<string>;
/** Seal that the action went ahead. result is fingerprinted locally and never sent. */
export function done(code: string, result?: unknown, key?: string): Promise<GateAnswer | null>;
/** Seal that the backup or undo was used. */
export function undo(code: string, note?: string, key?: string): Promise<GateAnswer>;
/** Wrap a function: it runs only when the gate says GO. */
export function noReturn<A extends unknown[], R>(options: ClearOptions<A>, fn: (...args: A) => R | Promise<R>): (...args: A) => Promise<R>;
