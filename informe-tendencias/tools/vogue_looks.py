#!/usr/bin/env python3
"""List the looks of a Vogue Runway collection and make a numbered contact sheet to choose from.
Usage: python3 vogue_looks.py <collection URL, e.g. https://www.vogue.com/fashion-shows/spring-2027-menswear/prada> [--sheet out.png] [--details]
Prints a header (title, publication date, review author) and one line per look:
  LOOK <n> | <direct image URL (w_1280)> | <credit as published> | <alt text>
--sheet writes a JPEG/PNG grid of numbered thumbnails you can open with the Read tool to pick looks visually."""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fetch
url = sys.argv[1].split('?')[0].rstrip('/')
args = sys.argv[2:]
sheet = args[args.index('--sheet') + 1] if '--sheet' in args else None
want_details = '--details' in args
p, code, final = fetch(url + '/slideshow/collection')
s = open(p, encoding='utf-8', errors='ignore').read()
m = re.search(r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});\s*</script>', s, re.S)
if not m:
    print(f'FAIL no gallery data (http {code}) {final}'); sys.exit(1)
d = json.loads(m.group(1))
title = re.search(r'<title>([^<]*)</title>', s)
print('TITLE:', title.group(1) if title else '?', '| URL:', url)
p2, c2, _ = fetch(url)
s2 = open(p2, encoding='utf-8', errors='ignore').read()
pub = re.search(r'"datePublished":"([^"]+)"', s2) or re.search(r'"datePublished":"([^"]+)"', s)
au = re.search(r'"author":\{"items":\[\{[^{}]*?"name":"([^"]+)"', s2)
print('PUBLISHED:', pub.group(1) if pub else 'n/d', '| REVIEW BY:', au.group(1) if au else 'n/d')
looks = []
def walk(o):
    if isinstance(o, dict):
        if 'items' in o and isinstance(o['items'], list) and o.get('id', '').startswith('gallery-'):
            gid = o['id']
            if gid == 'gallery-collection' or want_details:
                for it in o['items']:
                    img = it.get('image') or {}
                    src = (img.get('sources') or {})
                    u = (src.get('lg') or src.get('xl') or src.get('md') or {}).get('url')
                    thumb = (src.get('sm') or {}).get('url')
                    cred = it.get('desktopCredit') or it.get('mobileCredit') or (img.get('credit') if isinstance(img, dict) else None)
                    mn = re.search(r'/(\d{5})-[^/]*$', u or '')
                    ln = it.get('lookNumber') or (str(int(mn.group(1))) if mn and gid == 'gallery-collection' else None) or it.get('caption') or str(len(looks) + 1)
                    looks.append({'gallery': gid, 'look': ln, 'url': u, 'thumb': thumb,
                                  'credit': cred, 'alt': img.get('altText', '')})
            return
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(d)
# credit comes from each look's own desktopCredit; never borrow another gallery's credit
for l in looks:
    cred = (l['credit'] or 'n/d').replace('\\u002F', '/')
    l['credit'] = cred
    tag = '' if l['gallery'] == 'gallery-collection' else '[detalle] '
    print(f"LOOK {str(l['look']).lstrip('0')} | {l['url']} | {cred} | {tag}{l['alt']}")
if sheet and looks:
    from PIL import Image, ImageDraw
    from common import fetch as f2
    thumbs = []
    for l in looks[:80]:
        tp, c, _ = f2(l['thumb'] or l['url'], binary=True)
        try:
            im = Image.open(tp).convert('RGB'); im.thumbnail((150, 225)); thumbs.append((l['look'], im))
        except Exception:
            pass
    cols = 10; w, h = 150, 225
    rows = (len(thumbs) + cols - 1) // cols
    S = Image.new('RGB', (cols * (w + 4), rows * (h + 18)), 'white'); D = ImageDraw.Draw(S)
    for i, (n, im) in enumerate(thumbs):
        x = (i % cols) * (w + 4); y = (i // cols) * (h + 18)
        S.paste(im, (x, y + 16)); D.text((x + 3, y + 2), f'Look {str(n).lstrip("0")}', fill='black')
    S.save(sheet, quality=80); print('SHEET', sheet, len(thumbs), 'thumbs')
