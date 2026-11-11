"""
sebbi.source - the Input Gate: garbage in, caught at the door.
https://sebbi.pro/garbage-in

    pip install sebbi
    export SEBBI_API_KEY=your_key

    from sebbi.source import admit, GarbageIn

    code = admit("pricing-agent", [
        {"domain": "supplier.com", "data": price_list_text, "label": "Q4 price list"},
    ], ref="quote-10482")
    # reaches here only when every input is vouched for by its source

Each input is fingerprinted on your machine. Only the fingerprint, the source domain
and the label are sent: the data itself never leaves. ADMIT returns the GI- code to keep
with the decision. HOLD, REFUSE or no connection raise GarbageIn: if the gate cannot
be reached the data is not used. Standard library only.
"""
import hashlib, json, os, urllib.error, urllib.request

GATE = os.environ.get("SEBBI_GATE", "https://sebbi.pro")

__all__ = ["admit", "check", "fingerprint", "GarbageIn"]


class GarbageIn(Exception):
    """The gate did not admit these inputs. Do not use them."""

    def __init__(self, message, answer=None):
        Exception.__init__(self, message)
        self.answer = answer or {}


def fingerprint(data):
    """SHA-256 of the data, with line endings and outer whitespace tidied the way the gate does."""
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()
    if not isinstance(data, str):
        data = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.replace("\r\n", "\n").replace("\r", "\n").strip().encode("utf-8")).hexdigest()


def _post(path, body, key=None):
    key = key or os.environ.get("SEBBI_API_KEY", "") or os.environ.get("SEBBI_KEY", "")
    req = urllib.request.Request(GATE + "/x/garbagegate/" + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key,
                                          "User-Agent": "sebbi-python-source"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            raise GarbageIn("gate answered %s" % e.code)
    except Exception as e:
        raise GarbageIn("gate not reachable: %s" % e)


def _wire(inputs):
    out = []
    for i in inputs:
        w = {"domain": i.get("domain") or i.get("source"), "label": i.get("label")}
        w["hash"] = i.get("hash") or i.get("sha256") or fingerprint(i.get("data"))
        out.append({k: v for k, v in w.items() if v})
    return out


def check(agent, inputs, ref=None, key=None):
    """Ask the gate and return its whole answer, whatever the verdict."""
    body = {"agent": agent, "inputs": _wire(inputs)}
    if ref:
        body["ref"] = ref
    return _post("admit", body, key)


def admit(agent, inputs, ref=None, allow_hold=False, key=None):
    """Return the GI- code when the gate says ADMIT. Raise GarbageIn on anything else."""
    r = check(agent, inputs, ref, key)
    v = r.get("verdict")
    if v == "ADMIT" or (v == "HOLD" and allow_hold):
        return r.get("code")
    raise GarbageIn(r.get("why") or r.get("message") or r.get("error") or "not admitted", r)
