// sebbi for OpenTelemetry (ESM). See otel.cjs for the full notes.
import m from "./otel.cjs";
export const { SebbiSpanProcessor, SebbiSpanExporter, spanKind, spanLabel, spanPayload, spanFingerprints, buildPayload, ATTR_ID, ATTR_URL } = m;
export default m;
