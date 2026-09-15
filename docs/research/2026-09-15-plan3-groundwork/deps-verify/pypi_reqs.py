import json, urllib.request
def get(url):
    with urllib.request.urlopen(url, timeout=30) as r: return json.load(r)
for name,ver in [("gradio","6.27.0"),("openai","3.14.0"),("httpx2","2.13.0"),("datasets","5.0.1"),("spaces","0.51.3"),("mcp","1.30.0"),("pydantic","2.12.5"),("pydantic","2.13.5"),("bm25s","0.3.11"),("hf-gradio","0.4.1"),("huggingface-hub","1.31.0")]:
    d=get(f"https://pypi.org/pypi/{name}/{ver}/json")
    print("=====",name,ver,d["info"].get("requires_python"))
    for r in d["info"].get("requires_dist") or []:
        if name in("gradio","openai","httpx2","datasets","spaces","mcp","bm25s","hf-gradio") or "core" in r:
            if name=="datasets" and "extra" in r: continue
            if name=="huggingface-hub" and "extra" in r: continue
            print("  ",r)
d=get("https://pypi.org/pypi/numpy/2.5.3/json")
print([u["filename"] for u in d["urls"] if "manylinux" in u["filename"] and "x86_64" in u["filename"]])
