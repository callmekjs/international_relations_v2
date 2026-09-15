import json, urllib.request, sys
def get(url):
    with urllib.request.urlopen(url, timeout=30) as r: return json.load(r)
out={}
for name in ["gradio","openai","httpx2","numpy","bm25s","pydantic","pydantic-core","fsspec","datasets","mcp","huggingface-hub","spaces","gradio-client","httpx","starlette","fastapi","hf-gradio"]:
    d=get(f"https://pypi.org/pypi/{name}/json")
    info=d["info"]
    rel=d["releases"]
    latest=info["version"]
    up=[f["upload_time_iso_8601"] for f in rel.get(latest,[])]
    out[name]={"latest":latest,"requires_python":info.get("requires_python"),"uploaded":min(up) if up else None,"yanked":info.get("yanked")}
    print(name, out[name])
json.dump(out,open("pypi_latest.json","w"),indent=1)
