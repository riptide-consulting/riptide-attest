import zipfile, re, sys
from xml.etree import ElementTree as ET
A="{http://schemas.openxmlformats.org/drawingml/2006/main}"; P="{http://schemas.openxmlformats.org/presentationml/2006/main}"
EMU=914400
def lum(h):
    c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    c=[x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4 for x in c]
    return .2126*c[0]+.7152*c[1]+.0722*c[2]
def ratio(a,b):
    L=sorted([lum(a),lum(b)],reverse=True); return (L[0]+0.05)/(L[1]+0.05)
BONE="FAF7F2"; ABYSS="0A1628"; DARK={1,10,18,23,35}  # Attest deck: title, three part dividers, close
# NOTE: update this registry when slides are inserted or removed; positions shift.
z=zipfile.ZipFile(sys.argv[1])
slides=sorted([n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$",n)],
              key=lambda s:int(re.search(r"\d+",s.split("/")[-1]).group()))
bad=[]; checked=0
for i,sn in enumerate(slides,1):
    root=ET.fromstring(z.read(sn)); canvas=ABYSS if i in DARK else BONE
    shapes=[]
    for sp in root.iter(P+"sp"):
        o=sp.find(".//"+A+"off"); e=sp.find(".//"+A+"ext")
        if o is None or e is None: continue
        box=(int(o.get("x"))/EMU,int(o.get("y"))/EMU,int(e.get("cx"))/EMU,int(e.get("cy"))/EMU)
        f=sp.find(P+"spPr/"+A+"solidFill/"+A+"srgbClr")     # p: namespace, not a:
        shapes.append((sp,box,f.get("val") if f is not None else None))
    for idx,(sp,box,_) in enumerate(shapes):
        runs=[r for r in sp.iter(A+"r") if r.find(A+"t") is not None and (r.find(A+"t").text or "").strip()]
        if not runs: continue
        cx,cy=box[0]+box[2]/2, box[1]+box[3]/2
        bg=canvas
        for j,(o2,b2,f2) in enumerate(shapes):
            if j>=idx or not f2: continue
            if b2[0]-0.02<=cx<=b2[0]+b2[2]+0.02 and b2[1]-0.02<=cy<=b2[1]+b2[3]+0.02: bg=f2
        for r in runs:
            rPr=r.find(A+"rPr"); t=r.find(A+"t")
            cf=rPr.find(A+"solidFill/"+A+"srgbClr") if rPr is not None else None
            if cf is None: continue
            col=cf.get("val"); sz=int(rPr.get("sz","1800"))/100; bold=rPr.get("b")=="1"
            need=3.0 if (sz>=18 and bold) else 4.5
            rr=ratio(col,bg); checked+=1
            if rr<need-0.02:
                bad.append(f"slide {i:2d}: #{col} on #{bg} {sz:.0f}pt -> {rr:.2f}:1 (need {need}) [{(t.text or '')[:34]!r}]")
print(f"runs checked: {checked}   failures: {len(bad)}")
for b in bad: print("  "+b)
import sys
sys.exit(1 if bad else 0)  # a gate that cannot fail the build is not a gate
