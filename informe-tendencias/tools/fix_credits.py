#!/usr/bin/env python3
"""Corrige el crédito de cada foto de Vogue Runway en tablas de referencias, usando el desktopCredit de cada look.
Uso: python3 fix_credits.py <capitulo.md> [más...]   (edita en el sitio e imprime los cambios)"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fetch
CACHE = {}

def credits_for(collection):
    if collection in CACHE:
        return CACHE[collection]
    out = {}
    for suffix in ('/slideshow/collection', '/slideshow/details', ''):
        p, code, _ = fetch(collection + suffix)
        s = open(p, encoding='utf-8', errors='ignore').read()
        m = re.search(r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});\s*</script>', s, re.S)
        if not m:
            continue
        d = json.loads(m.group(1))
        def walk(o):
            if isinstance(o, dict):
                if 'items' in o and isinstance(o['items'], list) and str(o.get('id', '')).startswith('gallery-'):
                    for it in o['items']:
                        cred = it.get('desktopCredit') or it.get('mobileCredit')
                        js = json.dumps(it.get('image') or {})
                        for pid in set(re.findall(r'/photos/([0-9a-f]{24})/', js)):
                            if cred and pid not in out:
                                out[pid] = cred
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(d)
    CACHE[collection] = out
    return out

def es(cred):
    c = cred.replace('\\u002F', '/').strip()
    c = re.sub(r'^Photo:\s*', 'Foto: ', c)
    c = re.sub(r'^Photographed by\s*', 'Foto: ', c)
    c = re.sub(r'^(Foto:\s*)?Courtesy of\s*', 'Cortesía de ', c, flags=re.I)
    return c + ', vía Vogue Runway'

for path in sys.argv[1:]:
    lines = open(path, encoding='utf-8').read().split('\n')
    heads = None; changed = 0; missing = 0
    for i, ln in enumerate(lines):
        if not ln.startswith('|'):
            heads = None; continue
        cells = [c.strip() for c in re.split(r'(?<!\\)\|', ln)[1:-1]]
        if heads is None:
            heads = [c.lower() for c in cells]; continue
        if set(''.join(cells)) <= set('-: '):
            continue
        if not any('qué muestra' in h or 'que muestra' in h for h in heads):
            continue
        try:
            ci = next(k for k, h in enumerate(heads) if 'crédito' in h or 'credito' in h)
            ii = next(k for k, h in enumerate(heads) if h.startswith('imagen'))
            pi = next(k for k, h in enumerate(heads) if 'página' in h or 'pagina' in h)
        except StopIteration:
            continue
        img = cells[ii]
        mp = re.search(r'assets\.vogue\.com/photos/([0-9a-f]{24})/', img)
        mc = re.search(r'(https://www\.vogue\.com/fashion-shows/[^/\s)#]+/[^/\s)#]+)', cells[pi])
        if not mp or not mc:
            continue
        cmap = credits_for(mc.group(1))
        cred = cmap.get(mp.group(1))
        if not cred:
            missing += 1; print(f'  ? sin crédito en Vogue para {mp.group(1)} ({mc.group(1)})'); continue
        new = es(cred)
        if cells[ci] != new:
            print(f'  {cells[ci]!r} -> {new!r}')
            cells[ci] = new; changed += 1
            lines[i] = '| ' + ' | '.join(cells) + ' |'
    open(path, 'w', encoding='utf-8').write('\n'.join(lines))
    print(f'{os.path.basename(path)}: {changed} créditos corregidos, {missing} sin dato')
