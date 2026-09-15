"""Check that no two installed distributions write the same file (e.g. httpx vs httpx2 module dirs)."""
import collections
import importlib.metadata as md

owners = collections.defaultdict(set)
tops = {}
for d in md.distributions():
    name = d.metadata["Name"]
    top = set()
    for f in d.files or []:
        p = str(f).replace("\\", "/")
        if p.startswith("..") or ".dist-info/" in p or p.startswith("__pycache__"):
            continue
        owners[p].add(name)
        top.add(p.split("/")[0])
    tops[name] = sorted(t for t in top if not t.endswith(".pth"))
dups = {p: sorted(n) for p, n in owners.items() if len(n) > 1}
print("files owned by more than one distribution:", len(dups))
for p, n in list(dups.items())[:20]:
    print("  ", p, n)
for name in ["httpx", "httpx2", "httpcore", "httpcore2", "openai", "gradio", "gradio_client", "hf-gradio", "safehttpx"]:
    print(name, "->", [t for t in tops.get(name, []) if t != "bin"][:6])
