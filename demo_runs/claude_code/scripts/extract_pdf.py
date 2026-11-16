"""Extract chapter 2 (pages 23-35) text and embedded images with captions from the Great Art Explained PDF."""
import json, re, sys
from pathlib import Path
import pymupdf

PDF = "/Users/nhanvu/Documents/code/behind-the-image/books/_OceanofPDF.com_Great_Art_Explained_-_James_Payne.pdf"
OUT = Path(__file__).resolve().parent.parent
IMG = OUT / "assets" / "pdf_images"
IMG.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(PDF)
text_parts, manifest = [], []
for pno in range(22, 35):
    page = doc[pno]
    page_text = page.get_text("text")
    text_parts.append(f"\n\n=== PAGE {pno+1} ===\n{page_text}")
    blocks = page.get_text("dict")["blocks"]
    for img in page.get_images(full=True):
        xref = img[0]
        info = doc.extract_image(xref)
        fn = f"p{pno+1:02d}_x{xref}.{info['ext']}"
        (IMG / fn).write_bytes(info["image"])
        rects = page.get_image_rects(xref)
        rect = list(rects[0]) if rects else None
        # caption = text blocks lying below the image rect (nearest ones)
        cap = ""
        if rect:
            below = [b for b in blocks if b["type"] == 0 and b["bbox"][1] >= rect[3] - 2 and b["bbox"][1] < rect[3] + 90]
            below.sort(key=lambda b: b["bbox"][1])
            cap = " ".join(" ".join(s["text"] for l in b["lines"] for s in l["spans"]) for b in below[:2]).strip()
        manifest.append({"page": pno+1, "file": f"assets/pdf_images/{fn}", "xref": xref,
                         "width": info["width"], "height": info["height"], "ext": info["ext"],
                         "page_rect": rect, "caption_guess": cap})
(OUT / "assets" / "chapter2_text.txt").write_text("".join(text_parts), encoding="utf-8")
(OUT / "manifest.json").write_text(json.dumps({"pdf": PDF, "pages": "23-35", "images": manifest}, indent=2), encoding="utf-8")
print(len(manifest), "images;", sum(len(t.split()) for t in text_parts), "words")
for m in manifest: print(m["page"], m["file"], m["width"], m["height"], "|", m["caption_guess"][:110])
