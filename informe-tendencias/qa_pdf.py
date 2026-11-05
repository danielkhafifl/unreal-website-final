#!/usr/bin/env python3
"""Control de calidad del PDF.
Uso: python3 qa_pdf.py <informe.pdf> <informe.md> <carpeta_salida>
- Lista páginas casi vacías (fracción de altura usada < 0.45).
- Genera hojas de contacto (12 páginas por hoja) en <carpeta_salida>/contact-NN.png para revisarlas con Read.
- Comprueba que cada enlace externo del PDF aparece tal cual en el Markdown (ningún enlace inventado por el conversor).
- Cuenta imágenes incrustadas y tamaño del archivo."""
import sys, os, re, glob, subprocess
from PIL import Image, ImageDraw
import pypdf
pdf, md, out = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
for f in glob.glob(os.path.join(out, 'p-*.png')): os.remove(f)
subprocess.run(['pdftoppm', '-r', '40', '-png', pdf, os.path.join(out, 'p')], check=True)
files = sorted(glob.glob(os.path.join(out, 'p-*.png')), key=lambda f: int(re.findall(r'(\d+)\.png$', f)[0]))
low = []
for f in files:
    im = Image.open(f).convert('L'); w, h = im.size
    box = im.crop((int(w * .06), int(h * .05), int(w * .94), int(h * .92))); px = box.load(); W, H = box.size
    rows = [y for y in range(H) if any(px[x, y] < 235 for x in range(0, W, 2))]
    fill = (max(rows) / H) if rows else 0
    n = int(re.findall(r'(\d+)\.png$', f)[0])
    if fill < 0.45: low.append((n, round(fill, 2)))
print('páginas:', len(files), '| casi vacías (pág, fracción usada):', low)
per, cols = 12, 6
for s in range(0, len(files), per):
    ims = [Image.open(f) for f in files[s:s + per]]; w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (w + 8), rows * (h + 22)), '#777'); d = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x = (i % cols) * (w + 8); y = (i // cols) * (h + 22)
        sheet.paste(im, (x, y + 18)); d.text((x + 4, y + 3), str(s + i + 1), fill='white')
    sheet.save(os.path.join(out, f'contact-{s // per + 1:02d}.png'))
r = pypdf.PdfReader(pdf); mdt = open(md, encoding='utf-8').read()
ext = set(); n_img = 0
for pg in r.pages:
    for a in pg.get('/Annots') or []:
        a = a.get_object(); act = a.get('/A')
        if act and act.get_object().get('/URI'): ext.add(str(act.get_object()['/URI']))
    try:
        n_img += len(pg.images)
    except Exception:
        pass
missing = [u for u in ext if u not in mdt and u.rstrip('/') not in mdt]
print('enlaces externos:', len(ext), '| no presentes en el Markdown:', len(missing), missing[:10])
print('imágenes incrustadas:', n_img, '| tamaño MB:', round(os.path.getsize(pdf) / 1e6, 1))
print('hojas de contacto en', out)
