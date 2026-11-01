"""
OpenTelemetry: a sealed receipt for every agent and tool span you already trace.

    pip install "sebbi[otel]"

    from sebbi.integrations.otel import instrument
    instrument()                       # adds sebbi to your global TracerProvider

That is the whole setup. Every span that is an agent run or a tool call gets a
receipt, and the span itself carries the link as two attributes, so it shows
up in Jaeger, Grafana Tempo, Honeycomb, Datadog, Langfuse, Phoenix or whatever
already receives your traces:

    sebbi.receipt.id   r3f9c...
    sebbi.receipt.url  https://sebbi.pro/r/r3f9c...

Recognised out of the box:
  * OpenTelemetry GenAI conventions (gen_ai.operation.name = execute_tool,
    invoke_agent, chat, ...): OpenAI, Anthropic, Bedrock, Vertex, LangChain,
    LlamaIndex, CrewAI, Pydantic AI / Logfire, OpenLLMetry, OpenLIT
  * OpenInference (openinference.span.kind = TOOL, AGENT, LLM): Arize Phoenix
  * Vercel AI SDK span names (ai.toolCall, ai.generateText, ...)
  * any span you mark yourself: span.set_attribute("sebbi.seal", True)

What leaves your process: two SHA-256 fingerprints per span, a short label and
a timestamp. Span names, attributes, prompts and tool results never do.

Anyone holding the trace can prove it matches its receipt, without trusting
sebbi.pro or you:

    sebbi verify-otlp traces.json      # OTLP/JSON from the Collector file exporter

Fingerprint rules (identical in the JavaScript client) are in span_payload().
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import sebbi

try:
    from opentelemetry import trace as _trace_api
    from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
except Exception as _e:  # pragma: no cover
    raise ImportError(
        "sebbi.integrations.otel needs the OpenTelemetry SDK: pip install \"sebbi[otel]\""
    ) from _e

__all__ = [
    "instrument", "SebbiSpanProcessor", "SebbiSpanExporter",
    "span_kind", "span_label", "span_payload", "span_fingerprints",
    "payload_from_otlp", "verify_otlp",
]

ATTR_ID = "sebbi.receipt.id"
ATTR_URL = "sebbi.receipt.url"
ATTR_MARK = "sebbi.seal"
SPEC = "sebbi-otel-span/1"

# Attribute keys that describe what a span produced. Everything else describes
# what went in. Keys starting "sebbi." are never fingerprinted.
OUTPUT_PREFIXES = (
    "gen_ai.output.", "gen_ai.completion", "gen_ai.response.", "gen_ai.usage.", "gen_ai.tool.call.result",
    "output.", "llm.output_messages", "llm.token_count.",
    "ai.response.", "ai.toolCall.result", "ai.result.", "ai.usage.",
)

_GENAI = {"execute_tool": "tool", "invoke_agent": "agent", "create_agent": "agent",
          "chat": "llm", "text_completion": "llm", "generate_content": "llm"}
_OPENINF = {"TOOL": "tool", "AGENT": "agent", "LLM": "llm"}
_VERCEL_AGENT = ("ai.generateText", "ai.streamText", "ai.generateObject", "ai.streamObject")


# ------------------------------------------------------------ classification
def span_kind(name: str, attributes: Optional[Mapping[str, Any]]) -> Optional[str]:
    """'tool', 'agent', 'llm', 'marked' or None, from the span's name and attributes."""
    a = attributes or {}
    if a.get(ATTR_MARK) in (True, "true", "1", 1):
        return "marked"
    op = a.get("gen_ai.operation.name")
    if isinstance(op, str) and op in _GENAI:
        return _GENAI[op]
    oi = a.get("openinference.span.kind")
    if isinstance(oi, str) and oi.upper() in _OPENINF:
        return _OPENINF[oi.upper()]
    vid = a.get("ai.operationId") or name or ""
    if vid == "ai.toolCall":
        return "tool"
    if vid in _VERCEL_AGENT:
        return "agent"
    if vid.startswith("ai.") and (vid.endswith(".doGenerate") or vid.endswith(".doStream")):
        return "llm"
    return None


def span_label(name: str, attributes: Optional[Mapping[str, Any]], kind: Optional[str], prefix: str = "") -> str:
    a = attributes or {}

    def first(*keys: str) -> str:
        for k in keys:
            v = a.get(k)
            if isinstance(v, str) and v:
                return v
        return name or "span"

    if kind == "tool":
        s = "tool:" + first("gen_ai.tool.name", "tool.name", "ai.toolCall.name")
    elif kind == "agent":
        s = "agent:" + first("gen_ai.agent.name", "agent.name", "ai.telemetry.functionId")
    elif kind == "llm":
        s = "llm:" + first("gen_ai.request.model", "llm.model_name", "ai.model.id")
    else:
        s = name or "span"
    return (prefix + s)[:80]


# ---------------------------------------------------------------- payloads
def _num(x: Any) -> Any:
    """Numbers, written the same way in Python and JavaScript."""
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return x if abs(x) < 2 ** 53 else str(x)
    if isinstance(x, float):
        if math.isnan(x):
            return "NaN"
        if math.isinf(x):
            return "Infinity" if x > 0 else "-Infinity"
        if x.is_integer():
            if abs(x) < 2 ** 53:
                return int(x)
            if abs(x) < 1e21:
                return str(int(x))
        r = repr(x)
        if "e" in r:
            m, e = r.split("e")
            sign = "-" if e.startswith("-") else "+"
            r = m + "e" + sign + e.lstrip("+-").lstrip("0")
        return r
    return x


def _val(v: Any) -> Any:
    if isinstance(v, (list, tuple)):
        return [_val(x) for x in v]
    if isinstance(v, (bool, int, float)):
        return _num(v)
    if v is None or isinstance(v, str):
        return v
    return str(v)


def _attrs(a: Optional[Mapping[str, Any]], want_output: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (a or {}).items():
        k = str(k)
        if k.startswith("sebbi."):
            continue
        if k.startswith(OUTPUT_PREFIXES) == want_output:
            out[k] = _val(v)
    return out


def _status_name(code: Any) -> str:
    if isinstance(code, int):
        return {0: "UNSET", 1: "OK", 2: "ERROR"}.get(code, "UNSET")
    s = str(getattr(code, "name", code) or "UNSET").upper()
    s = s.replace("STATUS_CODE_", "")
    return s if s in ("UNSET", "OK", "ERROR") else "UNSET"


def build_payload(name: str, trace_id: str, span_id: str, parent_span_id: Optional[str],
                  start_ns: Any, end_ns: Any, attributes: Optional[Mapping[str, Any]],
                  status_code: Any, status_message: Optional[str],
                  events: Iterable[Tuple[str, Any, Optional[Mapping[str, Any]]]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The two documents a span's receipt fingerprints. Same rules in every sebbi client."""
    inp = {
        "spec": SPEC,
        "name": name or "",
        "trace_id": (trace_id or "").lower(),
        "span_id": (span_id or "").lower(),
        "parent_span_id": (parent_span_id or "").lower() or None,
        "start_time_unix_nano": str(int(start_ns or 0)),
        "attributes": _attrs(attributes, False),
    }
    out = {
        "end_time_unix_nano": str(int(end_ns or 0)),
        "status": _status_name(status_code),
        "status_message": status_message or "",
        "attributes": _attrs(attributes, True),
        "events": [{"name": n or "", "time_unix_nano": str(int(t or 0)), "attributes": {**_attrs(ea, False), **_attrs(ea, True)}}
                   for (n, t, ea) in events],
    }
    return inp, out


def span_payload(span: ReadableSpan) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(input, output) documents for a finished SDK span."""
    ctx = span.context
    parent = span.parent
    return build_payload(
        span.name,
        format(ctx.trace_id, "032x") if ctx else "",
        format(ctx.span_id, "016x") if ctx else "",
        format(parent.span_id, "016x") if parent is not None else None,
        span.start_time, span.end_time, span.attributes,
        span.status.status_code if span.status else 0,
        span.status.description if span.status else "",
        [(e.name, e.timestamp, e.attributes) for e in (span.events or ())],
    )


def span_fingerprints(span: ReadableSpan) -> Tuple[str, str]:
    """(input_hash, output_hash) a span's receipt must carry."""
    i, o = span_payload(span)
    return sebbi.fingerprint(i), sebbi.fingerprint(o)


# ----------------------------------------------------------------- sealing
def _new_id() -> str:
    return "r" + uuid.uuid4().hex[:23]


def _put(rid: Optional[str], ih: str, oh: str, label: str, outcome: str) -> sebbi.Receipt:
    r = sebbi.Receipt(label, ih, oh, outcome)
    if rid:
        r.id = rid
    sebbi._last[0] = r
    if sebbi._cfg.enabled:
        sebbi._sender.put(r)
    else:
        r.error = "disabled"
        r._event.set()
    return r


class _Policy:
    def __init__(self, llm: bool, all_spans: bool, filter: Optional[Callable[[Any], bool]], prefix: str) -> None:
        self.llm, self.all_spans, self.filter, self.prefix = llm, all_spans, filter, prefix

    def wants(self, span: Any) -> Optional[str]:
        """The span's kind if it should be sealed, else None."""
        kind = span_kind(span.name, span.attributes)
        if self.filter is not None:
            try:
                return (kind or "span") if self.filter(span) else None
            except Exception:
                return None
        if self.all_spans:
            return kind or "span"
        if kind in ("tool", "agent", "marked") or (kind == "llm" and self.llm):
            return kind
        return None

    def seal(self, span: ReadableSpan, kind: str, rid: Optional[str]) -> sebbi.Receipt:
        ih, oh = span_fingerprints(span)
        code = _status_name(span.status.status_code if span.status else 0)
        return _put(rid, ih, oh, span_label(span.name, span.attributes, kind, self.prefix),
                    "error" if code == "ERROR" else "ok")


class SebbiSpanProcessor(SpanProcessor):
    """
    Seals agent and tool spans as they end, and stamps each one with its
    receipt link (sebbi.receipt.id / sebbi.receipt.url) when it starts.

    llm=True       also seal every model call
    all_spans=True seal every span (watch your daily volume)
    filter=fn      your own rule: fn(span) -> bool, asked at start and at end;
                   the answer at end decides
    prefix="..."   put in front of every receipt label
    on_receipt=fn  fn(span, receipt) after each span is queued for sealing
    """

    def __init__(self, llm: bool = False, all_spans: bool = False, filter: Optional[Callable[[Any], bool]] = None,
                 prefix: str = "", on_receipt: Optional[Callable[[ReadableSpan, sebbi.Receipt], None]] = None) -> None:
        self._p = _Policy(llm, all_spans, filter, prefix)
        self._on_receipt = on_receipt

    def on_start(self, span: Span, parent_context: Any = None) -> None:
        try:
            if self._p.wants(span):
                rid = _new_id()
                span.set_attribute(ATTR_ID, rid)
                span.set_attribute(ATTR_URL, sebbi.SITE + "/r/" + rid)
        except Exception:
            pass

    def on_end(self, span: ReadableSpan) -> None:
        try:
            kind = self._p.wants(span)
            if not kind:
                return
            rid = (span.attributes or {}).get(ATTR_ID)
            r = self._p.seal(span, kind, rid if isinstance(rid, str) else None)
            if self._on_receipt:
                self._on_receipt(span, r)
        except Exception:
            pass

    def shutdown(self) -> None:
        sebbi.flush(3.0)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return sebbi.flush(timeout_millis / 1000.0)


class SebbiSpanExporter(SpanExporter):
    """
    The same sealing as an exporter, for pipelines that already batch spans:
        provider.add_span_processor(BatchSpanProcessor(SebbiSpanExporter()))
    Exporters see spans after they end, so the receipt link is not written
    onto the span. Use SebbiSpanProcessor (or instrument()) to get that.
    Never fails your pipeline: export always reports success.
    """

    def __init__(self, llm: bool = False, all_spans: bool = False, filter: Optional[Callable[[Any], bool]] = None,
                 prefix: str = "", on_receipt: Optional[Callable[[ReadableSpan, sebbi.Receipt], None]] = None) -> None:
        self._p = _Policy(llm, all_spans, filter, prefix)
        self._on_receipt = on_receipt

    def export(self, spans: Sequence[ReadableSpan]) -> "SpanExportResult":
        for s in spans:
            try:
                kind = self._p.wants(s)
                if kind:
                    rid = (s.attributes or {}).get(ATTR_ID)
                    r = self._p.seal(s, kind, rid if isinstance(rid, str) else None)
                    if self._on_receipt:
                        self._on_receipt(s, r)
            except Exception:
                pass
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        sebbi.flush(3.0)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return sebbi.flush(timeout_millis / 1000.0)


def instrument(tracer_provider: Optional[TracerProvider] = None, **options: Any) -> SebbiSpanProcessor:
    """
    Add sebbi to a TracerProvider (the global one by default; one is created
    and set globally if the app has none yet). Options as SebbiSpanProcessor.
    """
    tp = tracer_provider
    if tp is None:
        tp = _trace_api.get_tracer_provider()
        if not hasattr(tp, "add_span_processor"):
            tp = TracerProvider()
            _trace_api.set_tracer_provider(tp)
            tp = _trace_api.get_tracer_provider()
    if not hasattr(tp, "add_span_processor"):
        raise TypeError("sebbi needs an OpenTelemetry SDK TracerProvider (opentelemetry.sdk.trace.TracerProvider)")
    proc = SebbiSpanProcessor(**options)
    tp.add_span_processor(proc)
    return proc


# ------------------------------------------------------------ verification
def _otlp_value(v: Mapping[str, Any]) -> Any:
    if not isinstance(v, Mapping):
        return v
    if "stringValue" in v:
        return v["stringValue"]
    if "boolValue" in v:
        return bool(v["boolValue"])
    if "intValue" in v:
        return int(v["intValue"])
    if "doubleValue" in v:
        d = v["doubleValue"]
        return float(d) if not isinstance(d, str) else float(d.replace("Infinity", "inf"))
    if "arrayValue" in v:
        return [_otlp_value(x) for x in (v["arrayValue"] or {}).get("values", [])]
    if "bytesValue" in v:
        return v["bytesValue"]
    return None


def _otlp_attrs(lst: Any) -> Dict[str, Any]:
    return {a["key"]: _otlp_value(a.get("value") or {}) for a in (lst or []) if isinstance(a, dict) and "key" in a}


def _otlp_id(s: Any) -> str:
    s = s or ""
    if len(s) in (16, 32):
        try:
            int(s, 16)
            return s.lower()
        except ValueError:
            pass
    import base64  # OTLP/protobuf-JSON from some tools base64-encodes ids
    try:
        return base64.b64decode(s).hex()
    except Exception:
        return str(s).lower()


def _otlp_spans(doc: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    docs = doc if isinstance(doc, list) else [doc]
    for d in docs:
        for rs in (d or {}).get("resourceSpans", []) or []:
            for ss in rs.get("scopeSpans", rs.get("instrumentationLibrarySpans", [])) or []:
                out.extend(ss.get("spans", []) or [])
    return out


def payload_from_otlp(span: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(input, output) documents for one span from an OTLP/JSON export."""
    st = span.get("status") or {}
    return build_payload(
        span.get("name", ""), _otlp_id(span.get("traceId")), _otlp_id(span.get("spanId")),
        _otlp_id(span.get("parentSpanId")) or None,
        span.get("startTimeUnixNano", 0), span.get("endTimeUnixNano", 0), _otlp_attrs(span.get("attributes")),
        st.get("code", 0), st.get("message", ""),
        [(e.get("name", ""), e.get("timeUnixNano", 0), _otlp_attrs(e.get("attributes"))) for e in span.get("events", []) or []],
    )


def _fetch(rid: str, timeout: float = 15.0) -> Dict[str, Any]:
    req = urllib.request.Request(sebbi.SITE + "/v1/receipts/" + rid, headers={"Accept": "application/json", "User-Agent": sebbi._UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"error": "http_%d" % e.code}
    except Exception as e:
        return {"error": type(e).__name__}


def verify_otlp(doc: Any, fetch: Callable[[str], Dict[str, Any]] = _fetch) -> List[Dict[str, Any]]:
    """
    Check every span in an OTLP/JSON export that carries a sebbi receipt:
    recompute both fingerprints from the trace and compare them with the
    sealed receipt. Returns one result per span: ok True only when the
    receipt is valid and both fingerprints match.
    """
    results = []
    for s in _otlp_spans(doc):
        attrs = _otlp_attrs(s.get("attributes"))
        rid = attrs.get(ATTR_ID)
        if not isinstance(rid, str):
            continue
        i, o = payload_from_otlp(s)
        ih, oh = sebbi.fingerprint(i), sebbi.fingerprint(o)
        rec = fetch(rid)
        in_ok = rec.get("input_hash") == ih
        out_ok = rec.get("output_hash") == oh
        results.append({
            "span": s.get("name", ""), "receipt": rid, "url": sebbi.SITE + "/r/" + rid,
            "receipt_valid": bool(rec.get("valid")), "input_matches": in_ok, "output_matches": out_ok,
            "reversed": bool(rec.get("reversal") or rec.get("status") == "reversed"),
            "ok": bool(rec.get("valid")) and in_ok and out_ok, "error": rec.get("error"),
        })
    return results


def _cli_verify(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    try:
        doc: Any = json.loads(text)
    except ValueError:  # the Collector file exporter writes one JSON document per line
        doc = [json.loads(line) for line in text.splitlines() if line.strip()]
    res = verify_otlp(doc)
    if not res:
        print("no spans with a sebbi receipt in %s" % path)
        return 1
    bad = 0
    for r in res:
        flag = "MATCH   " if r["ok"] else "MISMATCH"
        bad += 0 if r["ok"] else 1
        extra = "" if r["ok"] else "  (receipt valid=%s input=%s output=%s%s)" % (
            r["receipt_valid"], r["input_matches"], r["output_matches"], (" " + r["error"]) if r["error"] else "")
        print("%s %s  %s%s%s" % (flag, r["url"], r["span"], "  REVERSED" if r["reversed"] else "", extra))
    print("%d of %d spans match their sealed receipts" % (len(res) - bad, len(res)))
    return 0 if bad == 0 else 1
