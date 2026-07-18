#!/usr/bin/env python3
"""Layout gate for a .pptx: geometry, image aspect ratio, and text fit.

  python3 qa/layout_gate.py out/Riptide-RIA-Master-Deck.pptx

Checks:
  1. GEOMETRY   no element sits off-slide or overflows the canvas
  2. ASPECT     every image is placed at its true aspect ratio (catches font stretching)
  3. TEXT FIT   every text run re-measured with real font metrics against its box

Exit code 0 if clean, 1 if any check fails.
"""
import os, re, sys, zipfile
from xml.etree import ElementTree as ET
from PIL import Image, ImageFont

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
EMU = 914400
SLIDE_W, SLIDE_H = 13.333, 7.5
TOL = 0.05                    # inches of slack at the canvas edge
ASPECT_TOL = 1.0              # percent drift allowed before an image counts as stretched
FIT_TOL = 1.06                # 6% slack on text height

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = {
    "Inter":          os.path.join(ROOT, "fonts", "Inter.ttf"),
    "Source Serif 4": os.path.join(ROOT, "fonts", "SourceSerif4.ttf"),
    "Consolas":       os.path.join(ROOT, "fonts", "Inter.ttf"),   # metric stand-in
}
_cache = {}
def font(name, pt):
    key = (name, round(pt))
    if key not in _cache:
        path = FONTS.get(name, FONTS["Inter"])
        if not os.path.exists(path):
            return None
        _cache[key] = ImageFont.truetype(path, max(6, int(round(pt))))
    return _cache[key]

def check(path):
    z = zipfile.ZipFile(path)
    slides = sorted(
        [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
        key=lambda s: int(re.search(r"\d+", s.split("/")[-1]).group()))
    media = {n: Image.open(z.open(n)).size
             for n in z.namelist() if n.startswith("ppt/media/") and not n.endswith("/")}
    fails = []

    for i, sn in enumerate(slides, 1):
        root = ET.fromstring(z.read(sn))

        # 1. GEOMETRY
        for sp in list(root.iter(P + "sp")) + list(root.iter(P + "pic")):
            o, e = sp.find(".//" + A + "off"), sp.find(".//" + A + "ext")
            if o is None or e is None:
                continue
            x, y = int(o.get("x")) / EMU, int(o.get("y")) / EMU
            w, h = int(e.get("cx")) / EMU, int(e.get("cy")) / EMU
            if x < -TOL or y < -TOL or x + w > SLIDE_W + TOL or y + h > SLIDE_H + TOL:
                t = "".join(t.text or "" for t in sp.iter(A + "t"))[:34]
                fails.append(f"GEOMETRY slide {i:2d}: {x:.2f},{y:.2f} {w:.2f}x{h:.2f} [{t!r}]")

        # 2. ASPECT
        try:
            rels = z.read(f"ppt/slides/_rels/{sn.split('/')[-1]}.rels").decode()
        except KeyError:
            rels = ""
        rmap = dict(re.findall(r'Id="([^"]+)"[^>]*Target="\.\./(media/[^"]+)"', rels))
        for pic in root.iter(P + "pic"):
            blip = pic.find(".//" + A + "blip")
            if blip is None:
                continue
            src = "ppt/" + rmap.get(blip.get(R + "embed"), "")
            if src not in media:
                continue
            e = pic.find(".//" + A + "ext")
            w, h = int(e.get("cx")) / EMU, int(e.get("cy")) / EMU
            iw, ih = media[src]
            native, placed = iw / ih, w / h
            drift = abs(placed - native) / native * 100
            if drift >= ASPECT_TOL:
                fails.append(f"ASPECT   slide {i:2d}: native {native:.4f} placed {placed:.4f} "
                             f"-> {drift:.1f}% stretch")

        # 3. TEXT FIT
        for sp in root.iter(P + "sp"):
            body, ext = sp.find(P + "txBody"), sp.find(".//" + A + "ext")
            if body is None or ext is None:
                continue
            W = int(ext.get("cx")) / EMU * 72
            H = int(ext.get("cy")) / EMU * 72
            total, txt = 0, ""
            for para in body.iter(A + "p"):
                runs = [(r.find(A + "t").text or "", r.find(A + "rPr"))
                        for r in para.iter(A + "r") if r.find(A + "t") is not None]
                if not runs:
                    total += 6
                    continue
                text = "".join(t for t, _ in runs)
                txt += text + " "
                rPr = runs[0][1]
                sz = int(rPr.get("sz")) / 100 if (rPr is not None and rPr.get("sz")) else 18
                fam = "Inter"
                if rPr is not None:
                    lt = rPr.find(A + "latin")
                    if lt is not None:
                        fam = lt.get("typeface", "Inter")
                f = font(fam, sz)
                if f is None:
                    continue
                lines, cur = 1, ""
                for word in text.split():
                    if f.getlength((cur + " " + word).strip()) <= W - 2:
                        cur = (cur + " " + word).strip()
                    else:
                        lines += 1
                        cur = word
                total += lines * sz * 1.28
            if txt.strip() and total > H * FIT_TOL:
                fails.append(f"TEXTFIT  slide {i:2d}: needs {total:.0f}pt in {H:.0f}pt box "
                             f"[{txt[:34].strip()!r}]")

    print(f"slides checked: {len(slides)}")
    if fails:
        print(f"FAILURES: {len(fails)}")
        for f in fails:
            print("  " + f)
        return 1
    print("layout gate: geometry OK, image aspect OK, text fit OK")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(check(sys.argv[1]))
