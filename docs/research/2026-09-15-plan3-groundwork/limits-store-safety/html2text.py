import re, sys, html
from html.parser import HTMLParser
class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.out=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript","svg"): self.skip+=1
        if tag in ("p","li","h1","h2","h3","h4","br","div","tr","section"): self.out.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script","style","noscript","svg"): self.skip=max(0,self.skip-1)
    def handle_data(self, d):
        if not self.skip: self.out.append(d)
for f in sys.argv[1:]:
    p=P(); p.feed(open(f,encoding="utf-8",errors="replace").read())
    t=re.sub(r"[ \t\xa0]+"," ","".join(p.out)); t=re.sub(r"\n\s*\n+","\n",t)
    open(f.rsplit(".",1)[0]+".txt","w",encoding="utf-8").write(t)
    print(f, len(t))
