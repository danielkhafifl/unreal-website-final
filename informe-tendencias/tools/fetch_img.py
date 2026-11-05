#!/usr/bin/env python3
"""Download a real photo for the report and cache it so the PDF can embed it.
Usage: python3 fetch_img.py <direct image URL> [more URLs...]
Prints: OK <width>x<height> <local path> <url>   or   FAIL <reason> <url>
The PDF builder finds the file by the exact URL you put in the report's 'Imagen' column."""
import sys, os, hashlib, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UA, IMGDIR
from PIL import Image
for url in sys.argv[1:]:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    out = os.path.join(IMGDIR, h + '.jpg')
    if os.path.exists(out) and os.path.getsize(out) > 2000:
        im = Image.open(out); print(f'OK {im.size[0]}x{im.size[1]} {out} {url}'); continue
    tmp = out + '.dl'
    r = subprocess.run(['curl', '-sL', '--max-time', '40', '-A', UA, '-o', tmp, '-w', '%{http_code} %{content_type}', url], capture_output=True, text=True)
    code = r.stdout.split(' ')[0]
    try:
        im = Image.open(tmp); im.load()
        im = im.convert('RGB')
        im.thumbnail((700, 1050))
        im.save(out, 'JPEG', quality=82, optimize=True, progressive=True)
        os.remove(tmp)
        print(f'OK {im.size[0]}x{im.size[1]} {out} {url}')
    except Exception as e:
        if os.path.exists(tmp): os.remove(tmp)
        print(f'FAIL http={code} {type(e).__name__} {url}')
