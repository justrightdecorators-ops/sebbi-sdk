"""
sebbi.noreturn - Point of No Return: the safety gate for AI agent actions that cannot be undone.
https://sebbi.pro/point-of-no-return

    pip install sebbi
    export SEBBI_API_KEY=your_key

    from sebbi.noreturn import no_return, clear, done, NoReturnStop

    @no_return(agent="billing-agent", action="refund payment", way_back={"type": "hold", "seconds": 900})
    def refund(order_id, amount):
        ...

    # or by hand
    code = clear("ops-agent", "delete database table", target="prod.customers",
                 way_back={"type": "backup", "sha256": backup_fingerprint, "taken": "2026-11-10T09:00:00Z"})
    drop_table()
    done(code)

The function only runs when the gate says GO. HOLD and NEEDS_HUMAN wait for the window
or the person. STOP, a refusal, a cancellation, no answer or no connection all raise
NoReturnStop: if the gate cannot be reached the action does not happen.
Standard library only.
"""
import functools, hashlib, json, os, time, urllib.error, urllib.request

GATE = os.environ.get("SEBBI_GATE", "https://sebbi.pro")


__all__ = ["no_return", "clear", "done", "undo", "NoReturnStop"]


class NoReturnStop(Exception):
    """The gate did not clear this action. Do not carry it out."""


def _post(path, body, key=None):
    key = key or os.environ.get("SEBBI_API_KEY", "") or os.environ.get("SEBBI_KEY", "")
    req = urllib.request.Request(GATE + "/x/noreturn/" + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key, "User-Agent": "sebbi-python-noreturn"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            raise NoReturnStop("gate answered %s" % e.code)
    except Exception as e:
        raise NoReturnStop("gate not reachable: %s" % e)


def clear(agent, action, target=None, summary=None, amount=None, currency=None, way_back=None, irreversible=None,
          wait=True, poll=15, max_wait=86400, on_wait=None, key=None):
    """Ask the gate. Returns the PN- code once the answer is GO, otherwise raises NoReturnStop."""
    body = {"agent": agent, "action": action, "target": target, "summary": summary, "amount": amount, "currency": currency,
            "way_back": way_back, "irreversible": irreversible}
    r = _post("check", {k: v for k, v in body.items() if v is not None}, key)
    start = time.time()
    while True:
        v = r.get("verdict")
        if v == "GO":
            return r["code"]
        if v not in ("HOLD", "NEEDS_HUMAN") or not wait:
            raise NoReturnStop(r.get("message") or r.get("why") or r.get("error") or str(v))
        if on_wait:
            on_wait(r)
        if time.time() - start > max_wait:
            raise NoReturnStop("waited too long for " + str(v))
        time.sleep(max(1, min(poll, int(r.get("seconds_to_wait") or poll))))
        r = dict(r, **_post("release", {"code": r["code"]}, key))


def done(code, result=None, key=None):
    """Seal that the action went ahead. result (any JSON value) is fingerprinted here and never sent."""
    body = {"code": code}
    if result is not None:
        body["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    try:
        return _post("done", body, key)
    except NoReturnStop:
        return None


def undo(code, note=None, key=None):
    """Seal that the backup or undo was used."""
    return _post("undo", {"code": code, "note": note}, key)


def no_return(agent, action, way_back=None, target=None, summary=None, amount=None, currency=None, **kw):
    """Decorator: the function runs only when the gate says GO. target, summary and amount may be
    functions of the call's arguments."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*a, **k):
            val = lambda v: v(*a, **k) if callable(v) else v
            code = clear(agent, action, target=val(target), summary=val(summary), amount=val(amount), currency=currency,
                         way_back=val(way_back), **kw)
            out = fn(*a, **k)
            done(code, out, kw.get("key"))
            return out
        return inner
    return wrap
