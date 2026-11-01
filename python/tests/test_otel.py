"""
Tests for sebbi.integrations.otel against the real OpenTelemetry SDK and a
local stand-in for the receipts API (nothing is sent to sebbi.pro).

    pip install -e ".[otel]" opentelemetry-exporter-otlp-proto-common
    python -m unittest discover -s tests -v
"""
import copy
import hashlib
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ.setdefault("SEBBI_OWNER_SECRET", "test-owner-secret")

import sebbi  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.trace import Status, StatusCode  # noqa: E402

from sebbi.integrations import otel  # noqa: E402

STORE = {}


class _API(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, doc):
        b = json.dumps(doc).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        doc = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        out = []
        for r in doc["records"]:
            assert set(r) >= {"local_id", "hash", "input_hash", "output_hash", "label", "ts", "outcome"}
            for k in ("hash", "input_hash", "output_hash"):
                assert len(r[k]) == 64
            STORE[r["local_id"]] = dict(r, valid=True)
            out.append({"local_id": r["local_id"], "id": r["local_id"], "block_index": 1, "merkle_root": "0" * 64})
        self._json(200, {"records": out, "lane": "free"})

    def do_GET(self):
        rid = self.path.rsplit("/", 1)[-1]
        if rid in STORE:
            self._json(200, STORE[rid])
        else:
            self._json(404, {"error": "not_found"})


def _otlp_json(spans):
    """Encode finished spans exactly as an OTLP exporter would, then to OTLP/JSON."""
    from google.protobuf.json_format import MessageToDict
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    return MessageToDict(encode_spans(spans))


class _Collect(SimpleSpanProcessor):
    def __init__(self):
        self.spans = []

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span):
        self.spans.append(span)

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


class OTelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _API)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        sebbi.configure(endpoint=base + "/v1/receipts", enabled=True)
        cls._site = sebbi.SITE
        sebbi.SITE = base  # verify_otlp fetches receipts from here

    @classmethod
    def tearDownClass(cls):
        sebbi.SITE = cls._site
        cls.srv.shutdown()

    def setUp(self):
        STORE.clear()

    def provider(self, **opts):
        tp = TracerProvider()
        proc = otel.instrument(tp, **opts)
        col = _Collect()
        tp.add_span_processor(col)
        return tp.get_tracer("test"), proc, col

    def sealed(self):
        self.assertTrue(sebbi.flush(10))
        return STORE

    # ----------------------------------------------------------- selection
    def test_tool_span_is_sealed_and_linked(self):
        tracer, _, col = self.provider()
        with tracer.start_as_current_span("execute_tool refund", attributes={
                "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "refund",
                "gen_ai.tool.call.arguments": '{"order": 7, "amount": 42}'}) as s:
            s.set_attribute("gen_ai.tool.call.result", '{"ok": true}')
        span = col.spans[-1]
        rid = span.attributes[otel.ATTR_ID]
        self.assertTrue(rid.startswith("r") and len(rid) == 24)
        self.assertEqual(span.attributes[otel.ATTR_URL], sebbi.SITE + "/r/" + rid)
        rec = self.sealed()[rid]
        ih, oh = otel.span_fingerprints(span)
        self.assertEqual((rec["input_hash"], rec["output_hash"]), (ih, oh))
        self.assertEqual(rec["hash"], hashlib.sha256((ih + ":" + oh).encode()).hexdigest())
        self.assertEqual(rec["label"], "tool:refund")
        self.assertEqual(rec["outcome"], "ok")

    def test_plain_and_llm_spans_skipped_by_default(self):
        tracer, _, col = self.provider()
        with tracer.start_as_current_span("db query"):
            pass
        with tracer.start_as_current_span("chat gpt", attributes={"gen_ai.operation.name": "chat",
                                                                  "gen_ai.request.model": "gpt-x"}):
            pass
        self.assertTrue(all(otel.ATTR_ID not in s.attributes for s in col.spans))
        self.assertEqual(self.sealed(), {})

    def test_llm_option(self):
        tracer, _, col = self.provider(llm=True)
        with tracer.start_as_current_span("chat", attributes={"gen_ai.operation.name": "chat",
                                                              "gen_ai.request.model": "claude-x"}):
            pass
        rid = col.spans[-1].attributes[otel.ATTR_ID]
        self.assertEqual(self.sealed()[rid]["label"], "llm:claude-x")

    def test_conventions_detected(self):
        k = otel.span_kind
        self.assertEqual(k("x", {"openinference.span.kind": "TOOL"}), "tool")
        self.assertEqual(k("x", {"openinference.span.kind": "AGENT"}), "agent")
        self.assertEqual(k("ai.toolCall", {"ai.toolCall.name": "w"}), "tool")
        self.assertEqual(k("ai.generateText", {}), "agent")
        self.assertEqual(k("ai.generateText.doGenerate", {}), "llm")
        self.assertEqual(k("x", {"gen_ai.operation.name": "invoke_agent"}), "agent")
        self.assertEqual(k("x", {"sebbi.seal": True}), "marked")
        self.assertIsNone(k("GET /health", {"http.method": "GET"}))
        self.assertEqual(otel.span_label("ai.toolCall", {"ai.toolCall.name": "getWeather"}, "tool", "shop/"),
                         "shop/tool:getWeather")

    def test_error_span_outcome(self):
        tracer, _, col = self.provider()
        with tracer.start_as_current_span("t", attributes={"openinference.span.kind": "TOOL", "tool.name": "pay"}) as s:
            s.set_status(Status(StatusCode.ERROR, "card declined"))
        rid = col.spans[-1].attributes[otel.ATTR_ID]
        self.assertEqual(self.sealed()[rid]["outcome"], "error")

    def test_filter_and_mark(self):
        tracer, _, col = self.provider(filter=lambda s: (s.attributes or {}).get("tenant") == "acme")
        with tracer.start_as_current_span("a", attributes={"tenant": "acme"}):
            pass
        with tracer.start_as_current_span("b", attributes={"tenant": "other", "gen_ai.operation.name": "execute_tool"}):
            pass
        names = sorted(r["label"] for r in self.sealed().values())
        self.assertEqual(names, ["a"])

    def test_on_receipt_callback(self):
        got = []
        tracer, _, _ = self.provider(on_receipt=lambda span, r: got.append((span.name, r.url)))
        with tracer.start_as_current_span("x", attributes={"sebbi.seal": True}):
            pass
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][0], "x")

    def test_exporter_mode(self):
        tp = TracerProvider()
        tp.add_span_processor(SimpleSpanProcessor(otel.SebbiSpanExporter()))
        with tp.get_tracer("t").start_as_current_span("ai.toolCall", attributes={"ai.toolCall.name": "lookup"}):
            pass
        recs = list(self.sealed().values())
        self.assertEqual([r["label"] for r in recs], ["tool:lookup"])

    def test_never_raises_when_api_is_down(self):
        sebbi.configure(endpoint="http://127.0.0.1:9/v1/receipts", timeout=0.2)
        try:
            tracer, _, col = self.provider()
            failed = sebbi.stats()["failed"]
            with tracer.start_as_current_span("t", attributes={"sebbi.seal": True}):
                pass
            self.assertIn(otel.ATTR_ID, col.spans[-1].attributes)
            self.assertTrue(sebbi.flush(20))  # retries run out in the background, nothing raised
            self.assertEqual(sebbi.stats()["failed"], failed + 1)
        finally:
            sebbi.configure(endpoint=sebbi.SITE + "/v1/receipts", timeout=10)
            sebbi.flush(15)

    # ------------------------------------------------------- verification
    def _traced(self):
        tracer, _, col = self.provider()
        with tracer.start_as_current_span("invoke_agent support", attributes={
                "gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "support",
                "gen_ai.request.temperature": 0.7, "gen_ai.request.max_tokens": 512,
                "gen_ai.request.top_p": 1.0, "tags": ("refunds", "uk")}):
            with tracer.start_as_current_span("execute_tool refund", attributes={
                    "gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "refund",
                    "gen_ai.tool.call.arguments": '{"order":7,"amount":42,"currency":"GBP"}'}) as t:
                t.add_event("approved", {"by": "policy-v3", "limit": 100.5})
                t.set_attribute("gen_ai.tool.call.result", '{"refund_id":"rf_1"}')
        self.sealed()
        return col.spans

    def test_otlp_roundtrip_matches(self):
        doc = _otlp_json(self._traced())
        res = otel.verify_otlp(doc)
        self.assertEqual(len(res), 2)
        self.assertTrue(all(r["ok"] for r in res), res)

    def test_otlp_tamper_detected(self):
        doc = _otlp_json(self._traced())
        bad = copy.deepcopy(doc)
        for ss in bad["resourceSpans"][0]["scopeSpans"]:
            for s in ss["spans"]:
                for a in s.get("attributes", []):
                    if a["key"] == "gen_ai.tool.call.arguments":
                        a["value"]["stringValue"] = a["value"]["stringValue"].replace("42", "4200")
        res = {r["span"]: r for r in otel.verify_otlp(bad)}
        self.assertFalse(res["execute_tool refund"]["ok"])
        self.assertFalse(res["execute_tool refund"]["input_matches"])
        self.assertTrue(res["execute_tool refund"]["output_matches"])
        self.assertTrue(res["invoke_agent support"]["ok"])

    def test_otlp_hex_ids_and_cli(self):
        doc = _otlp_json(self._traced())
        for ss in doc["resourceSpans"][0]["scopeSpans"]:
            for s in ss["spans"]:  # Collector file exporter style: hex ids, one document per line
                for k in ("traceId", "spanId", "parentSpanId"):
                    if s.get(k):
                        import base64
                        s[k] = base64.b64decode(s[k]).hex()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(json.dumps(doc) + "\n")
        try:
            self.assertEqual(otel._cli_verify(f.name), 0)
        finally:
            os.unlink(f.name)

    # ------------------------------------------------------ number rules
    def test_numbers_match_javascript(self):
        n = otel._num
        self.assertEqual(n(1.0), 1)
        self.assertEqual(n(-0.0), 0)
        self.assertEqual(n(0.7), "0.7")
        self.assertEqual(n(1e-7), "1e-7")
        self.assertEqual(n(1.5e300), "1.5e+300")
        self.assertEqual(n(1e16), "10000000000000000")
        self.assertEqual(n(1e21), "1e+21")
        self.assertEqual(n(float("nan")), "NaN")
        self.assertEqual(n(float("-inf")), "-Infinity")
        self.assertEqual(n(2 ** 60), str(2 ** 60))
        self.assertIs(n(True), True)

    def test_golden_fingerprint(self):
        """Shared with the JavaScript test: both clients must give these hashes."""
        i, o = otel.build_payload(
            "execute_tool refund", "0af7651916cd43dd8448eb211c80319c", "b7ad6b7169203331", "00f067aa0ba902b7",
            1700000000000000000, 1700000000250000000,
            {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "refund", "gen_ai.request.temperature": 0.7,
             "n": 3, "flag": True, "list": ["a", "b"], "price": 42.0, "note": "café ✓",
             "gen_ai.tool.call.result": "ok", "sebbi.receipt.id": "rignored"},
            2, "declined", [("approved", 1700000000100000000, {"limit": 100.5})])
        self.assertEqual(sebbi.fingerprint(i), GOLDEN_IN)
        self.assertEqual(sebbi.fingerprint(o), GOLDEN_OUT)


GOLDEN_IN = "415e9100aeb21d0485892753c40ab29949a553ab3ed9d311531d4ebcc9417bb1"
GOLDEN_OUT = "3897a8979b60b7ccc3862798504666a3d939da71b3c6c020815253c7ff02febc"

if __name__ == "__main__":
    unittest.main()
