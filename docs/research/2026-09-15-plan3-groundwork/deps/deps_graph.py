"""Print Requires-Dist of the key packages and who requires httpx / httpx2 (installed metadata only)."""
import importlib.metadata as md
import re

KEY = ["gradio", "gradio_client", "hf-gradio", "openai", "httpx", "httpx2", "httpcore", "httpcore2",
       "huggingface_hub", "safehttpx", "fastapi", "starlette", "anyio", "pydantic", "bm25s", "numpy", "pandas", "uvicorn"]
for name in KEY:
    d = md.distribution(name)
    reqs = [r for r in (d.requires or []) if "extra ==" not in r]
    print(f"== {d.metadata['Name']} {d.version}  Requires-Python: {d.metadata.get('Requires-Python')}")
    for r in reqs:
        print("   ", r)

print("\n== reverse deps")
wanted = {"httpx", "httpx2", "httpcore", "httpcore2", "anyio", "pydantic", "huggingface-hub", "websockets", "numpy"}
rev = {w: [] for w in wanted}
for d in md.distributions():
    for r in d.requires or []:
        if "extra ==" in r:
            continue
        base = re.split(r"[ ;<>=!~\[(]", r, 1)[0].lower().replace("_", "-")
        if base in rev:
            rev[base].append(f"{d.metadata['Name']} ({r})")
for k in sorted(rev):
    print(k, "<-", rev[k])
try:
    print("websockets installed:", md.version("websockets"))
except md.PackageNotFoundError:
    print("websockets installed: NO")
