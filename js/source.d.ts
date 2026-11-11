export interface GateInput { domain: string; data?: unknown; hash?: string; label?: string }
export interface InputVerdict { domain: string; sha256: string | null; verdict: "GENUINE" | "TAMPERED" | "UNVERIFIED" | "UNKNOWN"; why: string;
  action: "admit" | "hold" | "refuse"; vouched_as?: string; vouched_on?: string; stale?: boolean; [k: string]: unknown }
export interface GateAnswer { verdict?: "ADMIT" | "HOLD" | "REFUSE"; why?: string; code?: string; inputs?: InputVerdict[]; manifest_sha256?: string;
  sealed_block?: number; sealed_utc?: string; record?: string; message?: string; error?: string; [k: string]: unknown }
export interface GateOptions { ref?: string; allowHold?: boolean; key?: string }
export class GarbageIn extends Error { answer: GateAnswer }
/** SHA-256 of the data, with line endings and outer whitespace tidied the way the gate does. */
export function fingerprint(data: unknown): string;
/** Ask the gate and resolve with its whole answer, whatever the verdict. */
export function check(agent: string, inputs: GateInput[], options?: GateOptions): Promise<GateAnswer>;
/** Resolve with the GI- code when the gate says ADMIT. Throw GarbageIn on anything else. */
export function admit(agent: string, inputs: GateInput[], options?: GateOptions): Promise<string>;
