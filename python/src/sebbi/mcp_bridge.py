"""
sebbi.mcp_bridge - run the sebbi.pro MCP connector as a local command.

    uvx sebbi mcp          (or:  pip install sebbi && sebbi mcp)

Some AI clients and MCP marketplaces only start servers as a local command (stdio).
This is a thin bridge: every message the client writes on stdin is passed to
https://sebbi.pro/mcp and the answer is written to stdout. Nothing is stored locally.
Set SEBBI_MCP_URL to point at a different endpoint. Standard library only.
"""
import json, os, sys, urllib.error, urllib.request

URL = os.environ.get("SEBBI_MCP_URL", "https://sebbi.pro/mcp")


def _post(msg, session):
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": "sebbi-mcp-bridge-python"}
    if session:
        h["Mcp-Session-Id"] = session
    req = urllib.request.Request(URL, data=json.dumps(msg).encode("utf-8"), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read().decode("utf-8", "replace"), r.headers.get("Content-Type", ""), r.headers.get("Mcp-Session-Id")
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace"), e.headers.get("Content-Type", ""), None


def _answers(body, ctype):
    body = (body or "").strip()
    if not body:
        return []
    if "text/event-stream" in ctype:
        return [l[5:].strip() for l in body.splitlines() if l.startswith("data:") and l[5:].strip()]
    return [body]


def main():
    session = None
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        ids = [m.get("id") for m in (msg if isinstance(msg, list) else [msg]) if isinstance(m, dict) and "id" in m and "method" in m]
        try:
            body, ctype, sid = _post(msg, session)
            session = sid or session
            for out in _answers(body, ctype):
                try:
                    json.loads(out)
                except Exception:
                    continue
                sys.stdout.write(out.replace("\n", " ") + "\n")
                sys.stdout.flush()
        except Exception as e:
            for i in ids:
                sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": i, "error": {"code": -32000, "message": "sebbi.pro not reachable: %s" % e}}) + "\n")
                sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
