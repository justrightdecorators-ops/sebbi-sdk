"""
sebbi - a receipt for every AI agent action.

    pip install sebbi

    import sebbi

    @sebbi.receipt("refund-decision")
    def decide_refund(order):
        return {"refund": True}

    decide_refund({"id": 7})
    print(sebbi.last().url)      # https://sebbi.pro/r/...

Every call is fingerprinted on your machine (SHA-256 of canonical JSON).
Only the fingerprints, a short label and a timestamp are sent. The data
itself never leaves your process. Sealing happens on a background thread
in batches, so your code never waits for it and never fails because of it.

Works with no account (free lane). Set SEBBI_API_KEY for full volume and
receipts tied to your sebbi.pro account: https://sebbi.pro/connect

Docs: https://sebbi.pro/receipts
"""

from __future__ import annotations

import atexit
import functools
import hashlib
import hmac
import inspect
import json
import os
import queue
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable, Dict, List, Optional

__version__ = "1.3.0"
__all__ = ["receipt", "seal", "reverse", "last", "flush", "configure", "stats", "fingerprint", "Receipt"]

SITE = "https://sebbi.pro"
_UA = "sebbi-python/" + __version__


# ------------------------------------------------------------------ config
class _Config:
    def __init__(self) -> None:
        e = os.environ.get
        self.api_key: str = e("SEBBI_API_KEY", "")
        self.endpoint: str = e("SEBBI_ENDPOINT", SITE + "/v1/receipts")
        self.enabled: bool = e("SEBBI_DISABLED", "").strip().lower() not in ("1", "true", "yes", "on")
        self.timeout: float = float(e("SEBBI_TIMEOUT", "10"))
        self.client: str = _UA


_cfg = _Config()


# ------------------------------------------------------------- ownership
# Each receipt carries a commitment to a secret only this installation holds,
# so only you can reverse your receipts. The secret per receipt is derived
# from one master secret, so revealing it to reverse one receipt reveals
# nothing about any other.
def _master() -> bytes:
    env = os.environ.get("SEBBI_OWNER_SECRET", "")
    if env:
        return hashlib.sha256(env.encode()).digest()
    path = os.path.join(os.path.expanduser("~"), ".sebbi", "owner_secret")
    try:
        with open(path, "rb") as f:
            v = f.read().strip()
            if len(v) >= 32:
                return v
    except Exception:
        pass
    v = uuid.uuid4().hex.encode() + uuid.uuid4().hex.encode()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(v)
    except Exception:
        pass  # read-only filesystem: this process can still reverse what it sealed
    return v


_MASTER = [b""]


def _secret_for(rid: str) -> str:
    if not _MASTER[0]:
        _MASTER[0] = _master()
    return hmac.new(_MASTER[0], ("sebbi-owner|" + rid).encode(), hashlib.sha256).hexdigest()


def configure(api_key: Optional[str] = None, endpoint: Optional[str] = None,
              enabled: Optional[bool] = None, timeout: Optional[float] = None,
              client: Optional[str] = None) -> None:
    """Override settings in code. Environment: SEBBI_API_KEY, SEBBI_ENDPOINT, SEBBI_DISABLED."""
    if api_key is not None:
        _cfg.api_key = api_key
    if endpoint is not None:
        _cfg.endpoint = endpoint
    if enabled is not None:
        _cfg.enabled = bool(enabled)
    if timeout is not None:
        _cfg.timeout = float(timeout)
    if client is not None:
        _cfg.client = client


# ------------------------------------------------------------ fingerprints
def _canonical(o: Any, depth: int = 0) -> Any:
    if depth > 32:
        return "__sebbi_deep__"
    if o is None or isinstance(o, (bool, int, str)):
        return o
    if isinstance(o, float):
        return o if o == o and o not in (float("inf"), float("-inf")) else str(o)
    if isinstance(o, dict):
        return {str(k): _canonical(v, depth + 1) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_canonical(v, depth + 1) for v in o]
    if isinstance(o, (set, frozenset)):
        return sorted((_canonical(v, depth + 1) for v in o), key=lambda x: json.dumps(x, sort_keys=True))
    if isinstance(o, bytes):
        return {"__bytes_sha256__": hashlib.sha256(o).hexdigest()}
    for attr in ("model_dump", "dict", "to_dict"):
        f = getattr(o, attr, None)
        if callable(f):
            try:
                return _canonical(f(), depth + 1)
            except Exception:
                pass
    if hasattr(o, "__dict__"):
        try:
            return {"__type__": type(o).__name__, **_canonical(vars(o), depth + 1)}
        except Exception:
            pass
    return {"__type__": type(o).__name__}


def fingerprint(value: Any) -> str:
    """SHA-256 hex of the canonical JSON of value (keys sorted, compact, ASCII)."""
    s = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(s.encode("ascii")).hexdigest()


# ------------------------------------------------------------------ receipt
class Receipt:
    """One sealed action. `url` is usable straight away; `wait()` blocks until sealed."""

    __slots__ = ("id", "label", "input_hash", "output_hash", "hash", "ts", "outcome", "sealed", "error",
                 "block_index", "merkle_root", "lane", "reverses", "reason", "_event")

    def __init__(self, label: str, input_hash: str, output_hash: str, outcome: str = "ok") -> None:
        self.id = "r" + uuid.uuid4().hex[:23]
        self.label = (label or "")[:80]
        self.input_hash = input_hash
        self.output_hash = output_hash
        self.hash = hashlib.sha256((input_hash + ":" + output_hash).encode("ascii")).hexdigest()
        self.ts = time.time()
        self.outcome = outcome
        self.sealed = False
        self.error: Optional[str] = None
        self.block_index: Optional[int] = None
        self.merkle_root: Optional[str] = None
        self.lane: Optional[str] = None
        self.reverses: Optional[str] = None
        self.reason: str = ""
        self._event = threading.Event()

    @property
    def url(self) -> str:
        return SITE + "/r/" + self.id

    def wait(self, timeout: float = 15.0) -> "Receipt":
        _sender.kick()
        self._event.wait(timeout)
        return self

    def wire(self) -> Dict[str, Any]:
        d = {"local_id": self.id, "label": self.label, "input_hash": self.input_hash,
             "output_hash": self.output_hash, "hash": self.hash, "ts": self.ts, "outcome": self.outcome,
             "owner": hashlib.sha256(_secret_for(self.id).encode()).hexdigest()}
        if self.reverses:
            d.update(reverses=self.reverses, reason=self.reason, owner_secret=_secret_for(self.reverses))
        return d

    def to_dict(self) -> Dict[str, Any]:
        d = self.wire()
        d.update(id=self.id, url=self.url, sealed=self.sealed, error=self.error, block_index=self.block_index,
                 merkle_root=self.merkle_root, lane=self.lane)
        for k in ("local_id", "owner", "owner_secret"):
            d.pop(k, None)
        return d

    def __repr__(self) -> str:
        return "<Receipt %s %s %s>" % (self.id, self.label or "-", "sealed" if self.sealed else (self.error or "pending"))


# ------------------------------------------------------------------ sender
class _Sender:
    BATCH = 100
    INTERVAL = 1.0

    def __init__(self) -> None:
        self.q: "queue.Queue[Receipt]" = queue.Queue(maxsize=50000)
        self.lock = threading.Lock()
        self.thread: Optional[threading.Thread] = None
        self.wake = threading.Event()
        self.counts = {"queued": 0, "sealed": 0, "failed": 0, "dropped": 0}
        self.notice: Optional[str] = None
        self.inflight = 0

    def start(self) -> None:
        with self.lock:
            if self.thread and self.thread.is_alive():
                return
            self.thread = threading.Thread(target=self._run, name="sebbi-sender", daemon=True)
            self.thread.start()

    def put(self, r: Receipt) -> None:
        self.start()
        try:
            self.q.put_nowait(r)
            self.counts["queued"] += 1
        except queue.Full:
            r.error = "queue_full"
            self.counts["dropped"] += 1
            r._event.set()

    def kick(self) -> None:
        self.wake.set()

    def _run(self) -> None:
        while True:
            self.wake.wait(self.INTERVAL)
            self.wake.clear()
            self._drain()

    def _drain(self) -> None:
        while True:
            batch: List[Receipt] = []
            try:
                while len(batch) < self.BATCH:
                    batch.append(self.q.get_nowait())
            except queue.Empty:
                pass
            if not batch:
                return
            self.inflight += len(batch)
            try:
                self._send(batch)
            finally:
                self.inflight -= len(batch)

    def _send(self, batch: List[Receipt]) -> None:
        body = json.dumps({"records": [r.wire() for r in batch], "sdk": _cfg.client}).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": _cfg.client}
        if _cfg.api_key:
            headers["Authorization"] = "Bearer " + _cfg.api_key
        err = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(_cfg.endpoint, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=_cfg.timeout) as resp:
                    doc = json.loads(resp.read().decode("utf-8", "replace") or "{}")
                self._apply(batch, doc)
                return
            except urllib.error.HTTPError as e:
                err = "http_%d" % e.code
                try:
                    doc = json.loads(e.read().decode("utf-8", "replace") or "{}")
                    if doc.get("error"):
                        err = "%s:%s" % (err, doc["error"])
                    if doc.get("message"):
                        self.notice = doc["message"]
                except Exception:
                    pass
                if e.code < 500 and e.code != 429:
                    break
            except Exception as e:  # network, timeout
                err = type(e).__name__
            time.sleep(min(8.0, 0.5 * (2 ** attempt)))
        for r in batch:
            r.error = err
            r._event.set()
        self.counts["failed"] += len(batch)

    def _apply(self, batch: List[Receipt], doc: Dict[str, Any]) -> None:
        if doc.get("message"):
            self.notice = doc["message"]
        by = {str(x.get("local_id")): x for x in (doc.get("records") or []) if isinstance(x, dict)}
        for r in batch:
            x = by.get(r.id)
            if x:
                r.id = x.get("id") or r.id
                r.sealed = True
                r.block_index = x.get("block_index")
                r.merkle_root = x.get("merkle_root")
                r.lane = doc.get("lane")
                self.counts["sealed"] += 1
            else:
                r.error = "not_in_response"
                self.counts["failed"] += 1
            r._event.set()


_sender = _Sender()
_last: List[Optional[Receipt]] = [None]


def flush(timeout: float = 5.0) -> bool:
    """Send everything queued now. Returns True if the queue emptied in time."""
    if _sender.thread is None:
        return True
    end = time.time() + timeout
    _sender.kick()
    while time.time() < end:
        if _sender.q.empty() and _sender.inflight == 0:
            return True
        time.sleep(0.05)
    return False


atexit.register(lambda: flush(3.0))


def stats() -> Dict[str, Any]:
    d = dict(_sender.counts)
    d.update(pending=_sender.q.qsize(), endpoint=_cfg.endpoint, keyed=bool(_cfg.api_key), notice=_sender.notice)
    return d


def last() -> Optional[Receipt]:
    """The most recent receipt created in this process."""
    return _last[0]


# ------------------------------------------------------------------ API
def seal(input: Any = None, output: Any = None, label: str = "", outcome: str = "ok") -> Receipt:
    """Seal one action. Returns its Receipt immediately; sealing finishes in the background."""
    r = Receipt(label, fingerprint(input), fingerprint(output), outcome)
    _last[0] = r
    if _cfg.enabled:
        _sender.put(r)
    else:
        r.error = "disabled"
        r._event.set()
    return r


def reverse(original: Any, reason: str, output: Any = None, label: str = "") -> Receipt:
    """
    Reverse an action you sealed earlier (a refund, a cancelled payment, a
    withdrawn decision). Nothing is deleted: the original receipt stays sealed
    and is shown as REVERSED, linked to this new reversal receipt. The reason
    is public on both. Only the installation (or account key) that sealed the
    original can reverse it.
    """
    oid = original.id if isinstance(original, Receipt) else str(original)
    if not reason:
        raise ValueError("a reversal needs a reason; it is shown on both receipts")
    r = Receipt(label or ("reversal of " + oid), fingerprint({"reverses": oid}), fingerprint(output), "reversal")
    r.reverses = oid
    r.reason = str(reason)[:300]
    _last[0] = r
    if _cfg.enabled:
        _sender.put(r)
    else:
        r.error = "disabled"
        r._event.set()
    return r


def _inputs(fn: Callable, args: tuple, kwargs: dict) -> Any:
    try:
        b = inspect.signature(fn).bind_partial(*args, **kwargs)
        d = dict(b.arguments)
        d.pop("self", None)
        d.pop("cls", None)
        return d
    except Exception:
        return {"args": list(args), "kwargs": kwargs}


def receipt(label: Any = None) -> Any:
    """
    Decorator. @sebbi.receipt, @sebbi.receipt() or @sebbi.receipt("label").
    Works on plain and async functions. Exceptions are sealed as outcome
    "error" and re-raised unchanged.
    """
    def deco(fn: Callable) -> Callable:
        name = label if isinstance(label, str) and label else getattr(fn, "__name__", "action")

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def aw(*a: Any, **k: Any) -> Any:
                inp = _inputs(fn, a, k)
                try:
                    out = await fn(*a, **k)
                except Exception as e:
                    seal(inp, {"error_type": type(e).__name__}, name, "error")
                    raise
                seal(inp, out, name)
                return out
            return aw

        @functools.wraps(fn)
        def w(*a: Any, **k: Any) -> Any:
            inp = _inputs(fn, a, k)
            try:
                out = fn(*a, **k)
            except Exception as e:
                seal(inp, {"error_type": type(e).__name__}, name, "error")
                raise
            seal(inp, out, name)
            return out
        return w

    if callable(label) and not isinstance(label, str):
        fn, label = label, None
        return deco(fn)
    return deco


def _cli() -> int:
    import sys
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print("sebbi %s - a receipt for every AI agent action\n\n  sebbi seal <text> [label]   seal a fingerprint of <text>, print the receipt link\n"
              "  sebbi check <id>            check a receipt\n"
              "  sebbi verify-otlp <file>    check every span in an OTLP/JSON trace export against its receipt\n\nDocs: %s/receipts" % (__version__, SITE))
        return 0
    if a[0] == "seal" and len(a) > 1:
        r = seal(a[1], None, a[2] if len(a) > 2 else "cli").wait()
        print(r.url if r.sealed else "not sealed: %s %s" % (r.error, _sender.notice or ""))
        return 0 if r.sealed else 1
    if a[0] == "check" and len(a) > 1:
        try:
            with urllib.request.urlopen(SITE + "/v1/receipts/" + a[1], timeout=15) as resp:
                d = json.loads(resp.read().decode())
            print(("VALID" if d.get("valid") else "INVALID") + "  " + json.dumps(d.get("checks")))
            return 0 if d.get("valid") else 1
        except urllib.error.HTTPError as e:
            print("not found (%d)" % e.code)
            return 1
    if a[0] == "verify-otlp" and len(a) > 1:
        try:
            from sebbi.integrations.otel import _cli_verify
        except ImportError as e:
            print(e)
            return 2
        return _cli_verify(a[1])
    print("unknown command; sebbi --help")
    return 2
