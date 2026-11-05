#!/usr/bin/env python3
"""Markdown report -> designed HTML -> PDF (Chromium via Playwright), two passes for TOC page numbers.

Usage: python3 build.py report.md out.pdf [--keep-html]
Conventions understood in the markdown (see writer brief):
  # Resumen ejecutivo                -> chapter (new page)
  # 01 · Denim                       -> department chapter with number
  Enfoque: ...                       -> department lede (first paragraph after dept h1)
  Estado: [VIGENTE FW26] [EMERGENTE SS27]  -> status badges
  Paleta: Nombre #RRGGBB; Nombre #RRGGBB   -> swatches
  > **Recomendación:** ... / > **Hecho observado:** ... / > **No verificado:** ... / > **Novedad ...:** ...
  Tables: header with "Qué muestra" -> reference cards; first header "Prenda" -> proposal cards;
          headers with "Producto" + "Enlace" -> product cards; other tables -> styled tables.
"""
import sys, re, os, html, subprocess, hashlib, json
from urllib.parse import urlparse
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup, Tag, NavigableString

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, 'node_modules', '@fontsource')

# Defaults (edition of 5 Nov 2026). Override with --meta meta.json:
# {"date": "9 de noviembre de 2026", "subtitle": "...", "edition": "Actualización semanal",
#  "coverage": ["línea 1", "línea 2"], "footer": "...", "img_max": [540, 810], "img_q": 80}
META = {
    'date': '5 de noviembre de 2026',
    'subtitle': 'Informe ejecutivo para diseño y desarrollo de producto',
    'edition': '',
    'coverage': ['Novedades de la semana del 29 de octubre al 5 de noviembre de 2026',
                 'Otoño-Invierno 2026 (en tienda) · Primavera-Verano 2027 (pasarelas de junio de 2026)'],
    'footer': 'Tendencias de moda masculina · Informe del 5 de noviembre de 2026',
    'img_max': [540, 810], 'img_q': 80,
}


def slug(s, used):
    s0 = re.sub(r'[^a-z0-9]+', '-', s.lower().translate(str.maketrans('áéíóúüñ', 'aeiouun'))).strip('-')[:60] or 'x'
    s1, i = s0, 2
    while s1 in used:
        s1 = f'{s0}-{i}'; i += 1
    used.add(s1)
    return s1


def badge_class(t):
    u = t.upper()
    if 'NOVEDAD' in u: return 'b-nov'
    if 'EMERGENTE' in u: return 'b-emer'
    if 'DECLIVE' in u or 'SATURA' in u: return 'b-dec'
    if 'VIGENTE' in u: return 'b-vig'
    return 'b-gen'


def preprocess(md):
    out = []
    lines = md.replace('\r\n', '\n').split('\n')
    for ln in lines:
        m = re.match(r'^\s*Estado:\s*(.+)$', ln)
        if m:
            tags = re.findall(r'\[([^\]]+)\]', m.group(1))
            if tags:
                out.append('')
                out.append('<div class="estado">' + ''.join(
                    f'<span class="badge {badge_class(t)}">{html.escape(t.strip())}</span>' for t in tags) + '</div>')
                out.append('')
                continue
        m = re.match(r'^\s*Paleta(?:\s+orientativa)?\s*:\s*(.+)$', ln)
        if m:
            chips = []
            for it in [x.strip() for x in m.group(1).split(';') if x.strip()]:
                mm = re.match(r'(.+?)\s*\(?\s*(#[0-9A-Fa-f]{6})\s*\)?\s*\.?$', it)
                if mm:
                    chips.append((mm.group(1).strip(' :-–'), mm.group(2).upper()))
            if chips:
                out.append('')
                out.append('<div class="paleta"><div class="paleta-t">Paleta orientativa · aproximación visual de los colores citados, no son códigos oficiales de las marcas</div><div class="chips">' + ''.join(
                    f'<div class="chip"><span class="sw" style="background:{h}"></span><span class="cn">{html.escape(n)}</span><span class="ch">{h}</span></div>' for n, h in chips) + '</div></div>')
                out.append('')
                continue
        out.append(ln)
    return '\n'.join(out)


def cell_link(td):
    """Return (href, text) of the first link in a cell, or a URL in plain text."""
    a = td.find('a')
    if a and a.get('href'):
        return a['href'], a.get_text(' ', strip=True)
    t = td.get_text(' ', strip=True)
    m = re.search(r'https?://\S+', t)
    if m:
        return m.group(0).rstrip(').,;'), t
    return None, t


def norm(h):
    return h.lower().strip().translate(str.maketrans('áéíóúüñ', 'aeiouun'))


def table_rows(table):
    heads = [th.get_text(' ', strip=True) for th in table.find_all('th')]
    rows = []
    body = table.find('tbody') or table
    for tr in body.find_all('tr'):
        tds = tr.find_all('td')
        if not tds:
            continue
        rows.append({norm(heads[i]) if i < len(heads) else f'c{i}': tds[i] for i in range(len(tds))})
    return heads, rows


def find_key(row, *cands):
    for c in cands:
        for k in row:
            if c in k:
                return row[k]
    return None


def inner(td):
    return ''.join(str(x) for x in td.contents).strip() if td is not None else ''


def short_url(u):
    try:
        p = urlparse(u)
        d = p.netloc.replace('www.', '')
        return d
    except Exception:
        return u[:40]


def img_local(url, imgdir):
    if not url or not imgdir:
        return None
    url = url.strip()
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    for ext in ('.jpg', '.jpeg', '.png', '.webp'):
        p = os.path.join(imgdir, h + ext)
        if os.path.exists(p) and os.path.getsize(p) > 2000:
            return optimized(p)
    return None


def optimized(p):
    from PIL import Image
    od = os.path.join(HERE, 'images_opt'); os.makedirs(od, exist_ok=True)
    q = os.path.join(od, os.path.splitext(os.path.basename(p))[0] + '.jpg')
    if not os.path.exists(q) or os.path.getmtime(q) < os.path.getmtime(p) or OPT_FORCE[0]:
        im = Image.open(p).convert('RGB'); im.thumbnail(tuple(META['img_max']))
        im.save(q, 'JPEG', quality=int(META['img_q']), optimize=True, progressive=True)
    USED_IMGS.add(p)
    return q


USED_IMGS = set()
OPT_FORCE = [False]


def build_ref_cards(soup, table, imgdir):
    heads, rows = table_rows(table)
    grid = soup.new_tag('div', attrs={'class': 'ref-grid'})
    any_img = False
    for r in rows:
        marca = find_key(r, 'marca')
        temp = find_key(r, 'coleccion', 'temporada')
        look = find_key(r, 'look')
        desc = find_key(r, 'que muestra')
        cred = find_key(r, 'credito')
        imgc = find_key(r, 'imagen', 'foto')
        pagc = find_key(r, 'pagina', 'fuente', 'galeria')
        img_href, _ = cell_link(imgc) if imgc is not None else (None, '')
        pag_href, _ = cell_link(pagc) if pagc is not None else (None, '')
        local = img_local(img_href, imgdir)
        card = soup.new_tag('div', attrs={'class': 'ref-card'})
        lk = look.get_text(' ', strip=True) if look is not None else ''
        lk = '' if lk in ('—', '-', '', 'n/d', 'N/D', 's/n') else lk
        meta = (temp.get_text(' ', strip=True) if temp is not None else '')
        if lk:
            meta += (' · ' if meta else '') + ('Look ' + lk if not lk.lower().startswith('look') else lk)
        top = ''
        if local:
            any_img = True
            top = f'<a class="ref-img" href="{html.escape(pag_href or img_href)}"><img src="file://{local}" alt=""></a>'
        else:
            target = img_href or pag_href
            if target:
                top = (f'<a class="ref-band" href="{html.escape(target)}"><span class="ref-band-k">Foto en la fuente</span>'
                       f'<span class="ref-band-d">{html.escape(short_url(target))} ↗</span></a>')
            else:
                top = '<div class="ref-band ref-band-none"><span class="ref-band-k">Sin enlace a la foto</span></div>'
        links = []
        if img_href:
            links.append(f'<a href="{html.escape(img_href)}">Abrir foto ↗</a>')
        if pag_href and pag_href != img_href:
            links.append(f'<a href="{html.escape(pag_href)}">Ver en {html.escape(short_url(pag_href))} ↗</a>')
        card_html = (top + '<div class="ref-body">'
                     f'<div class="ref-brand">{inner(marca)}</div>'
                     f'<div class="ref-meta">{html.escape(meta)}</div>'
                     f'<div class="ref-desc">{inner(desc)}</div>'
                     f'<div class="ref-credit">{inner(cred)}</div>'
                     f'<div class="ref-links">{"".join(links)}</div></div>')
        card.append(BeautifulSoup(card_html, 'html.parser'))
        if local:
            card['class'] = ['ref-card', 'with-img']
        grid.append(card)
    if any_img:
        grid['class'] = ['ref-grid', 'has-img']
        for c in grid.find_all('div', class_='ref-card'):
            if 'with-img' in c.get('class', []):
                continue
            band = c.find(class_='ref-band')
            href = band.get('href') if band is not None else None
            ph = BeautifulSoup((f'<a class="ref-img ref-ph" href="{html.escape(href)}">' if href else '<div class="ref-img ref-ph">') +
                               '<span>Foto disponible en la fuente</span><b>Ver foto ↗</b>' + ('</a>' if href else '</div>'), 'html.parser')
            if band is not None:
                band.replace_with(ph)
            c['class'] = ['ref-card', 'with-img']
    table.replace_with(grid)


IMGDIR_GLOBAL = [None]


def build_prod_cards(soup, table):
    heads, rows = table_rows(table)
    grid = soup.new_tag('div', attrs={'class': 'prod-grid'})
    for r in rows:
        trend = find_key(r, 'tendencia')
        marca = find_key(r, 'marca')
        prod = find_key(r, 'producto', 'modelo')
        precio = find_key(r, 'precio')
        tela = find_key(r, 'tela', 'material')
        enl = find_key(r, 'enlace', 'url')
        ver = find_key(r, 'verific', 'estado')
        imgc = find_key(r, 'imagen', 'foto')
        href, _ = cell_link(enl) if enl is not None else (None, '')
        img_href, _ = cell_link(imgc) if imgc is not None else (None, '')
        local = img_local(img_href, IMGDIR_GLOBAL[0])
        parts = []
        if local:
            parts.append(f'<a class="prod-img" href="{html.escape(href or img_href)}"><img src="file://{local}" alt=""></a>')
        if trend is not None and trend.get_text(strip=True):
            parts.append(f'<div class="prod-trend">{inner(trend)}</div>')
        parts.append(f'<div class="prod-brand">{inner(marca)}</div>')
        parts.append(f'<div class="prod-name">{inner(prod)}</div>')
        info = []
        if tela is not None and tela.get_text(strip=True) not in ('', '—', '-'):
            info.append(inner(tela))
        if precio is not None and precio.get_text(strip=True) not in ('', '—', '-'):
            info.append(f'<b>{inner(precio)}</b>')
        if info:
            parts.append('<div class="prod-info">' + ' · '.join(info) + '</div>')
        if ver is not None and ver.get_text(strip=True):
            parts.append(f'<div class="prod-ver">{inner(ver)}</div>')
        if href:
            parts.append(f'<a class="prod-link" href="{html.escape(href)}">Ver producto en {html.escape(short_url(href))} ↗</a>')
        card = BeautifulSoup('<div class="prod-card">' + ''.join(parts) + '</div>', 'html.parser')
        grid.append(card)
    table.replace_with(grid)


def build_prop_cards(soup, table, kind):
    heads, rows = table_rows(table)
    grid = soup.new_tag('div', attrs={'class': f'prop-grid {kind}'})
    for r in rows:
        keys = list(r.keys())
        title = r[keys[0]]
        dl = ''
        for i, k in enumerate(keys[1:], start=1):
            label = heads[i] if i < len(heads) else k
            val = inner(r[k])
            if val and val not in ('—', '-'):
                dl += f'<dt>{html.escape(label)}</dt><dd>{val}</dd>'
        tag = {'comercial': 'Comercial', 'arriesgada': 'Arriesgada'}.get(kind, '')
        card_html = (f'<div class="prop-card"><div class="prop-head">'
                     + (f'<span class="prop-tag">{tag}</span>' if tag else '')
                     + f'<div class="prop-title">{inner(title)}</div></div><dl>{dl}</dl></div>')
        grid.append(BeautifulSoup(card_html, 'html.parser'))
    table.replace_with(grid)


def build_row_cards(soup, table):
    heads = [th.get_text(' ', strip=True) for th in table.find_all('th')]
    datey = norm(heads[0]).startswith('fecha') if heads else False
    grid = soup.new_tag('div', attrs={'class': 'row-grid'})
    body = table.find('tbody') or table
    for tr in body.find_all('tr'):
        tds = tr.find_all('td')
        if not tds:
            continue
        first = inner(tds[0])
        parts = [f'<div class="row-k">{first}</div>' if datey else f'<div class="row-t">{first}</div>']
        for i, td in enumerate(tds[1:], start=1):
            v = inner(td)
            if not v or v in ('—', '-'):
                continue
            lab = heads[i] if i < len(heads) else ''
            if datey and i == 1:
                parts.append(f'<div class="row-t">{v}</div>')
            else:
                parts.append(f'<div class="row-f"><span class="row-l">{html.escape(lab)}</span> {v}</div>')
        grid.append(BeautifulSoup('<div class="row-card">' + ''.join(parts) + '</div>', 'html.parser'))
    table.replace_with(grid)


def prev_heading_text(el):
    for p in el.find_all_previous(['h2', 'h3', 'h4']):
        return p.get_text(' ', strip=True).lower()
    return ''


def transform(body_html, imgdir):
    soup = BeautifulSoup(body_html, 'html.parser')
    # tables
    for table in list(soup.find_all('table')):
        heads = [norm(th.get_text(' ', strip=True)) for th in table.find_all('th')]
        if not heads:
            continue
        if any('que muestra' in h for h in heads):
            build_ref_cards(soup, table, imgdir)
        elif heads[0].startswith('prenda'):
            ph = prev_heading_text(table)
            kind = 'arriesgada' if 'arriesg' in ph else ('comercial' if 'comercial' in ph else '')
            build_prop_cards(soup, table, kind)
        elif any(h.startswith('producto') or h.startswith('modelo') for h in heads) and any('enlace' in h or h == 'url' for h in heads):
            build_prod_cards(soup, table)
        else:
            n = len(table.find_all('tr'))
            if n > 9:
                build_row_cards(soup, table)
            else:
                wrap = soup.new_tag('div', attrs={'class': 'tbl tbl-keep'})
                table.wrap(wrap)
    # callouts
    for bq in soup.find_all('blockquote'):
        st = bq.find('strong')
        t = norm(st.get_text(' ', strip=True)) if st else ''
        cls = 'callout'
        if 'recomend' in t or 'que adaptar' in t or 'vale la pena' in t or 'oportunidad' in t or 'que hacer' in t:
            cls += ' c-reco'
        elif 'no verificado' in t or 'limitacion' in t or 'sin confirmar' in t or 'advertencia' in t or 'no se pudo' in t:
            cls += ' c-warn'
        elif 'novedad' in t or 'esta semana' in t:
            cls += ' c-news'
        elif 'hecho' in t or 'observado' in t or 'dato' in t:
            cls += ' c-obs'
        elif 'latam' in t or 'latinoam' in t or 'clima' in t:
            cls += ' c-latam'
        else:
            cls += ' c-gen'
        bq.name = 'div'
        bq['class'] = cls
    # paragraphs with lead labels "Hecho observado:" / "Recomendación:" (not in blockquote)
    for p in soup.find_all('p'):
        st = p.find('strong')
        if st and p.contents and p.contents[0] == st:
            t = norm(st.get_text(' ', strip=True))
            if t.startswith('hecho') or t.startswith('observado'):
                p['class'] = p.get('class', []) + ['lab-obs']
            elif t.startswith('recomend') or t.startswith('lectura'):
                p['class'] = p.get('class', []) + ['lab-reco']
    # long raw URLs in link text
    for a in soup.find_all('a'):
        txt = a.get_text()
        if re.match(r'^https?://', txt.strip()) and len(txt) > 60:
            u = urlparse(txt.strip())
            path = u.path.rstrip('/')
            last = path.split('/')[-1] if path else ''
            a.string = (u.netloc.replace('www.', '') + ('/…/' + last[:38] if last else ''))
    return soup


def sectionize(soup):
    """Group content into chapters by h1; mark departments; collect TOC entries."""
    used = set()
    chapters = []
    cur = None
    container = BeautifulSoup('', 'html.parser')
    for el in list(soup.contents):
        if isinstance(el, Tag) and el.name == 'h1':
            cur = container.new_tag('section', attrs={'class': 'chapter'})
            container.append(cur)
            chapters.append(cur)
        if cur is None:
            cur = container.new_tag('section', attrs={'class': 'chapter pre'})
            container.append(cur)
            chapters.append(cur)
        cur.append(el.extract() if isinstance(el, Tag) else el)
    toc = []
    for sec in chapters:
        h1 = sec.find('h1')
        if not h1:
            continue
        text = h1.get_text(' ', strip=True)
        hid = slug(text, used)
        m = re.match(r'^(\d{1,2})\s*[·\.\-–:]\s*(.+)$', text)
        entry = {'id': hid, 'text': text, 'level': 1, 'children': []}
        if m:
            num, name = m.group(1).zfill(2), m.group(2)
            sec['class'] = sec.get('class', []) + ['dept']
            head = BeautifulSoup(
                f'<header class="dept-head"><div class="dept-num">{num}</div><div class="dept-titles">'
                f'<div class="dept-kicker">Departamento {num}</div><h1 id="{hid}">{html.escape(name)}</h1></div></header>', 'html.parser')
            # lede
            nxt = h1.find_next_sibling()
            h1.replace_with(head)
            if nxt is not None and nxt.name == 'p' and re.match(r'^\s*(<strong>)?\s*Enfoque\s*:', str(nxt.decode_contents())):
                nxt['class'] = ['dept-lede']
                st = nxt.find('strong')
                if st:
                    st.string = 'Enfoque · '
            entry.update({'num': num, 'text': name})
        else:
            h1['id'] = hid
        # trend h3 under a "Tendencias" h2
        in_trends = False
        for h in sec.find_all(['h2', 'h3']):
            if h.name == 'h2':
                in_trends = 'tendencia' in norm(h.get_text())
                if not m:  # non-department chapters: list h2 in toc
                    h['id'] = slug(h.get_text(' ', strip=True), used)
                    entry['children'].append({'id': h['id'], 'text': h.get_text(' ', strip=True)})
                else:
                    h['id'] = slug(text + '-' + h.get_text(' ', strip=True), used)
            elif h.name == 'h3':
                h['id'] = slug(text + '-' + h.get_text(' ', strip=True), used)
                if m and in_trends:
                    entry['children'].append({'id': h['id'], 'text': h.get_text(' ', strip=True)})
        toc.append(entry)
    return container, toc


def toc_html(toc, pages):
    def pg(i):
        return str(pages.get(i, '00'))
    out = ['<section class="toc"><div class="toc-kicker">Contenido</div><h1 class="toc-title">Índice</h1><div class="toc-list">']
    for e in toc:
        if 'num' in e:
            out.append(f'<div class="toc-e toc-dept"><a href="#{e["id"]}"><span class="toc-n">{e["num"]}</span>'
                       f'<span class="toc-t">{html.escape(e["text"])}</span><span class="toc-dots"></span><span class="toc-p">{pg(e["id"])}</span></a>')
        else:
            out.append(f'<div class="toc-e toc-ch"><a href="#{e["id"]}"><span class="toc-n"></span>'
                       f'<span class="toc-t">{html.escape(e["text"])}</span><span class="toc-dots"></span><span class="toc-p">{pg(e["id"])}</span></a>')
        if e['children'] and 'num' in e:
            out.append('<div class="toc-sub">' + ''.join(
                f'<a href="#{c["id"]}"><span class="toc-st">{html.escape(c["text"])}</span><span class="toc-sp">{pg(c["id"])}</span></a>'
                for c in e['children']) + '</div>')
        out.append('</div>')
    out.append('</div></section>')
    return ''.join(out)


def font_face(family, folder, weights, styles=('normal',)):
    css = []
    for w in weights:
        for s in styles:
            f = os.path.join(FONTS, folder, 'files', f'{folder}-latin-{w}-{s}.woff2')
            if os.path.exists(f):
                css.append(f"@font-face{{font-family:'{family}';src:url('file://{f}') format('woff2');font-weight:{w};font-style:{s};}}")
            fe = os.path.join(FONTS, folder, 'files', f'{folder}-latin-ext-{w}-{s}.woff2')
            if os.path.exists(fe):
                css.append(f"@font-face{{font-family:'{family}';src:url('file://{fe}') format('woff2');font-weight:{w};font-style:{s};unicode-range:U+0100-024F,U+1E00-1EFF;}}")
    return '\n'.join(css)


def cover_html(meta):
    depts = ''.join(f'<li><span>{e["num"]}</span>{html.escape(e["text"])}</li>' for e in meta['toc'] if 'num' in e)
    return f'''<section class="cover">
<div class="cover-top"><div class="cover-kicker">Dirección de tendencias · Moda masculina</div>
<div class="cover-date">{html.escape(META['edition']) + '<br>' if META['edition'] else ''}Fecha del informe<br><b>{html.escape(META['date'])}</b></div></div>
<div class="cover-main"><h1 class="cover-title">Tendencias<br>de moda<br><i>masculina</i></h1>
<div class="cover-sub">{html.escape(META['subtitle'])}<br>Equipo de diseño · marcas de ropa de caballero en Latinoamérica</div></div>
<div class="cover-bottom"><div class="cover-seasons"><div class="cs-k">Cobertura</div>
{''.join('<div>' + html.escape(c) + '</div>' for c in META['coverage'])}</div>
<ol class="cover-depts">{depts}</ol></div></section>'''


CSS = r'''
:root{--ink:#17171a;--ink2:#3b3b42;--mute:#6f6c66;--line:#d9d3c8;--paper:#ffffff;--sand:#f3eee6;--sand2:#e8e0d2;
--acc:#a4482a;--acc-l:#f6e6de;--ind:#2f4166;--ind-l:#e5e9f1;--amb:#8a6411;--amb-l:#f7efd9;--grn:#3d6b4f;--grn-l:#e3eee7;}
@page{size:A4;margin:17mm 15mm 18mm 15mm;
 @bottom-left{content:"FOOTER_LEFT";font:7.2pt InterW, Inter;color:#8a857c;}
 @bottom-right{content:counter(page);font:600 7.5pt InterW, Inter;color:#17171a;}}
@page cover{margin:0; @bottom-left{content:none} @bottom-right{content:none}}
@page toc{@bottom-left{content:none}}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font-family:InterW,Inter,sans-serif;font-size:9.1pt;line-height:1.5;color:var(--ink);background:#fff;font-feature-settings:"ss01","cv11";}
a{color:var(--ind);text-decoration:none;border-bottom:0.5pt solid rgba(47,65,102,.35)}
p{margin:0 0 6pt;orphans:3;widows:3}
ul,ol{margin:0 0 7pt;padding-left:13pt}
li{margin:0 0 2.5pt}
li>p{margin:0}
strong{font-weight:600}
em{font-style:italic}
code{font-family:'JetBrains Mono';font-size:8pt;background:var(--sand);padding:0 2pt;border-radius:2pt}
hr{border:0;border-top:0.6pt solid var(--line);margin:10pt 0}
/* cover */
.cover{page:cover;height:297mm;width:210mm;box-sizing:border-box;background:var(--ink);color:#f3eee6;padding:20mm 18mm 18mm;display:flex;flex-direction:column;justify-content:space-between;break-after:page}
.cover-top{display:flex;justify-content:space-between;align-items:flex-start;font-size:8.5pt;letter-spacing:.14em;text-transform:uppercase;color:#cfc6b6}
.cover-date{text-align:right;letter-spacing:.08em}.cover-date b{color:#fff;font-weight:600;letter-spacing:.04em}
.cover-title{font-family:'Bodoni Moda',serif;font-weight:500;font-size:68pt;line-height:.98;margin:0 0 14pt;color:#fff;letter-spacing:-.01em}
.cover-title i{color:#e2a07f;font-weight:400}
.cover-sub{font-size:11pt;line-height:1.5;color:#d9d1c3;max-width:130mm;border-left:2pt solid #e2a07f;padding-left:10pt}
.cover-bottom{display:grid;grid-template-columns:1fr 1fr;gap:12mm;border-top:0.6pt solid #4a4a52;padding-top:8mm}
.cover-seasons{font-size:8.6pt;color:#d9d1c3;line-height:1.6}.cs-k,.cover-depts:before{font-size:7.5pt;letter-spacing:.16em;text-transform:uppercase;color:#e2a07f;margin-bottom:4pt;display:block}
.cover-depts{list-style:none;margin:0;padding:0;font-size:9pt;line-height:1.75;color:#fff;columns:1}
.cover-depts:before{content:"Departamentos"}
.cover-depts span{display:inline-block;width:18pt;color:#e2a07f;font-weight:600;font-size:8pt}
/* toc */
.toc{page:toc;break-after:page}
.toc-kicker,.dept-kicker,.ch-kicker{font-size:7.5pt;letter-spacing:.18em;text-transform:uppercase;color:var(--acc);font-weight:600}
.toc-title{font-family:'Bodoni Moda',serif;font-weight:500;font-size:28pt;margin:2pt 0 8pt;line-height:1}
.toc-e{break-inside:avoid;border-top:0.6pt solid var(--line);padding:3pt 0 2.5pt}
.toc-e>a{display:flex;align-items:baseline;border:0;color:var(--ink)}
.toc-n{width:22pt;font-weight:600;color:var(--acc);font-size:9pt;flex:none}
.toc-t{font-family:'Bodoni Moda',serif;font-size:13pt;font-weight:500}
.toc-ch .toc-t{font-size:12pt}
.toc-dots{flex:1;border-bottom:0.6pt dotted #b9b2a6;margin:0 6pt;transform:translateY(-3pt)}
.toc-p{font-weight:600;font-size:9pt;min-width:14pt;text-align:right}
.toc-sub{display:grid;grid-template-columns:1fr 1fr 1fr;column-gap:12pt;row-gap:0.5pt;margin:1.5pt 0 1.5pt 22pt}
.toc-sub a{display:flex;justify-content:space-between;gap:6pt;border:0;color:var(--ink2);font-size:7pt;line-height:1.3}
.toc-sp{color:var(--mute);flex:none}
/* chapters */
.chapter{break-before:page}
.chapter.pre{break-before:auto}
.chapter>h1{font-family:'Bodoni Moda',serif;font-weight:500;font-size:26pt;line-height:1.05;margin:0 0 10pt;padding-bottom:8pt;border-bottom:1.2pt solid var(--ink);position:relative}
.dept-head{display:flex;gap:12pt;align-items:flex-end;border-bottom:1.2pt solid var(--ink);padding-bottom:8pt;margin-bottom:9pt}
.dept-num{font-family:'Bodoni Moda',serif;font-size:54pt;line-height:.8;color:var(--acc);font-weight:500}
.dept-head h1{font-family:'Bodoni Moda',serif;font-weight:500;font-size:30pt;line-height:1;margin:3pt 0 0;position:relative}
.dept-lede{font-size:10.2pt;line-height:1.5;color:var(--ink2);background:var(--sand);padding:8pt 10pt;border-left:2.5pt solid var(--acc);margin:0 0 10pt}
.dept-lede strong{color:var(--acc);text-transform:uppercase;font-size:7.6pt;letter-spacing:.14em}
h2{font-family:'Bodoni Moda',serif;font-weight:500;font-size:16.5pt;line-height:1.15;margin:14pt 0 6pt;break-after:avoid;position:relative}
h3{font-family:InterW,Inter;font-weight:700;font-size:11.2pt;line-height:1.25;margin:13pt 0 4pt;break-after:avoid;position:relative;padding-top:6pt;border-top:0.6pt solid var(--line)}
h4{font-family:InterW,Inter;font-weight:600;font-size:7.8pt;letter-spacing:.14em;text-transform:uppercase;color:var(--mute);margin:9pt 0 4pt;break-after:avoid}
h2+h3{border-top:0;padding-top:0}
.estado{margin:0 0 5pt;display:flex;flex-wrap:wrap;gap:4pt;break-after:avoid}
.badge{font-size:6.6pt;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:1.6pt 5pt;border-radius:2pt;border:0.6pt solid}
.b-vig{background:var(--ink);color:#fff;border-color:var(--ink)}
.b-emer{background:var(--acc-l);color:var(--acc);border-color:var(--acc)}
.b-nov{background:var(--acc);color:#fff;border-color:var(--acc)}
.b-dec{background:#eee;color:#666;border-color:#aaa}
.b-gen{background:var(--ind-l);color:var(--ind);border-color:var(--ind)}
/* callouts */
.callout{break-inside:avoid;padding:7pt 10pt;margin:6pt 0 8pt;border-left:2.5pt solid;border-radius:0 3pt 3pt 0;font-size:8.9pt}
.callout p:last-child{margin-bottom:0}
.c-reco{background:var(--acc-l);border-color:var(--acc)}.c-reco strong:first-child{color:var(--acc)}
.c-obs{background:var(--ind-l);border-color:var(--ind)}.c-obs strong:first-child{color:var(--ind)}
.c-warn{background:var(--amb-l);border-color:var(--amb)}.c-warn strong:first-child{color:var(--amb)}
.c-news{background:#fff;border:0.8pt solid var(--acc);border-left:2.5pt solid var(--acc)}.c-news strong:first-child{color:var(--acc)}
.c-latam{background:var(--grn-l);border-color:var(--grn)}.c-latam strong:first-child{color:var(--grn)}
.c-gen{background:var(--sand);border-color:var(--ink2)}
.lab-obs strong:first-child{color:var(--ind)}
.lab-reco strong:first-child{color:var(--acc)}
/* tables */
.tbl{margin:4pt 0 9pt}
.tbl-keep{break-inside:avoid}
table{border-collapse:collapse;width:100%;font-size:7.8pt;line-height:1.38}
thead{display:table-header-group}
th{text-align:left;font-weight:600;font-size:6.9pt;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);border-bottom:1pt solid var(--ink);padding:3pt 5pt}
td{border-bottom:0.5pt solid var(--line);padding:3.5pt 5pt;vertical-align:top}
tr{break-inside:avoid}
tbody tr:nth-child(even) td{background:#faf8f4}
td a{word-break:break-word}
/* reference cards */
.ref-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6pt;margin:4pt 0 9pt}
.ref-card{break-inside:avoid;border:0.6pt solid var(--line);border-radius:3pt;overflow:hidden;background:#fff;display:flex;flex-direction:column}
.ref-grid.has-img{grid-template-columns:repeat(4,1fr);gap:5pt}
.ref-img{display:block;border:0;background:var(--sand);aspect-ratio:2/3;width:100%;overflow:hidden}
.ref-img img{width:100%;height:100%;object-fit:contain;display:block}
.with-img .ref-body{padding:4pt 5pt 5pt}
.ref-ph{display:flex !important;flex-direction:column;align-items:center;justify-content:center;gap:4pt;text-align:center;color:var(--mute);font-size:7pt;padding:8pt}
.ref-ph b{color:var(--ind);font-size:7.4pt}
.with-img .ref-brand{font-size:8pt}
.with-img .ref-desc{font-size:7.1pt}
.prod-img{display:block;border:0;background:#f7f5f1;aspect-ratio:4/5;width:100%;margin:-1pt 0 3pt;overflow:hidden}
.prod-img img{width:100%;height:100%;object-fit:contain;display:block}
.ref-band{display:flex;justify-content:space-between;align-items:center;gap:4pt;background:var(--sand);border:0;border-bottom:0.6pt solid var(--line);padding:4pt 6pt;color:var(--ink)}
.ref-band-k{font-size:6.3pt;letter-spacing:.14em;text-transform:uppercase;font-weight:700;color:var(--acc)}
.ref-band-d{font-size:6.6pt;color:var(--ind);font-weight:600}
.ref-band-none .ref-band-k{color:var(--mute)}
.ref-body{padding:5pt 6pt 6pt;display:flex;flex-direction:column;gap:2pt;flex:1}
.ref-brand{font-weight:700;font-size:8.6pt;line-height:1.2}
.ref-meta{font-size:7pt;color:var(--acc);font-weight:600;letter-spacing:.02em}
.ref-desc{font-size:7.5pt;line-height:1.38;color:var(--ink2)}
.ref-credit{font-size:6.5pt;color:var(--mute);font-style:italic;line-height:1.3;margin-top:auto;padding-top:2pt}
.ref-links{display:flex;flex-wrap:wrap;gap:3pt 7pt;font-size:6.8pt;font-weight:600}
.ref-desc p,.ref-credit p{margin:0}
/* product cards */
.prod-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:5pt;margin:4pt 0 9pt}
.prod-card{break-inside:avoid;border:0.6pt solid var(--line);border-top:2pt solid var(--ind);border-radius:2pt;padding:5pt 6pt 6pt;display:flex;flex-direction:column;gap:1.5pt;background:#fff}
.prod-trend{font-size:6.3pt;letter-spacing:.12em;text-transform:uppercase;color:var(--mute);font-weight:600}
.prod-brand{font-weight:700;font-size:8.4pt}
.prod-name{font-size:7.8pt;line-height:1.3}
.prod-info{font-size:7.2pt;color:var(--ink2)}
.prod-ver{font-size:6.5pt;color:var(--mute);font-style:italic;line-height:1.3}
.prod-link{margin-top:auto;padding-top:2pt;font-size:6.9pt;font-weight:600;border:0}
/* proposal cards */
.prop-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7pt;margin:4pt 0 10pt}
.prop-card{break-inside:avoid;border:0.6pt solid var(--line);border-radius:3pt;background:#fff;overflow:hidden}
.prop-head{background:var(--sand);padding:5pt 8pt;border-bottom:0.6pt solid var(--line)}
.arriesgada .prop-head{background:var(--ink);color:#fff}
.prop-tag{font-size:6.2pt;letter-spacing:.16em;text-transform:uppercase;font-weight:700;color:var(--acc)}
.arriesgada .prop-tag{color:#e2a07f}
.prop-title{font-weight:700;font-size:9.4pt;line-height:1.25}
.prop-card dl{margin:0;padding:5pt 8pt 7pt;display:grid;grid-template-columns:auto 1fr;column-gap:7pt;row-gap:2.5pt;font-size:7.7pt;line-height:1.38}
.prop-card dt{font-size:6.4pt;letter-spacing:.1em;text-transform:uppercase;color:var(--mute);font-weight:700;padding-top:1pt}
.prop-card dd{margin:0}
/* palette */
.paleta{break-inside:avoid;margin:6pt 0 10pt;border:0.6pt solid var(--line);border-radius:3pt;padding:6pt 8pt}
.paleta-t{font-size:6.6pt;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);font-weight:600;margin-bottom:5pt}
.chips{display:flex;flex-wrap:wrap;gap:6pt}
.chip{display:flex;flex-direction:column;width:21mm}
.sw{display:block;height:12mm;border-radius:2pt;border:0.5pt solid rgba(0,0,0,.12)}
.cn{font-size:7pt;font-weight:600;margin-top:2pt;line-height:1.2}
.ch{font-size:6.3pt;color:var(--mute);font-family:'JetBrains Mono'}
/* sources */
.sources ul{columns:2;column-gap:14pt;font-size:7.1pt;line-height:1.38;padding-left:9pt}
.sources li{break-inside:avoid;margin-bottom:2.5pt}
.sources h2{font-size:13pt;margin-top:10pt}
.sources a{white-space:nowrap}
.row-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:5pt;margin:4pt 0 9pt}
.row-card{break-inside:avoid;border:0.6pt solid var(--line);border-left:2pt solid var(--ind);border-radius:2pt;padding:4.5pt 7pt 5pt;font-size:7.7pt;line-height:1.38;display:flex;flex-direction:column;gap:1.5pt}
.row-k{font-size:6.8pt;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:var(--acc)}
.row-t{font-weight:600;font-size:8pt;line-height:1.33}
.row-l{font-size:6.2pt;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:var(--mute)}
.row-card p{margin:0}
p:has(+ .tbl-keep),p:has(+ .row-grid),p:has(+ .ref-grid),p:has(+ .prod-grid),p:has(+ .prop-grid){break-after:avoid}
.t1{font-size:8.85pt}.t1 h3{margin-top:10pt}.t1 h2{margin-top:11pt}.t1 .ref-grid,.t1 .prod-grid{gap:4.5pt}.t1 .callout{margin:5pt 0 6pt}
.t2{font-size:8.65pt;line-height:1.45}.t2 p{margin-bottom:4.5pt}.t2 h3{margin-top:8pt}.t2 h2{margin-top:9pt}.t2 .ref-desc{font-size:7.3pt}.t2 .callout{padding:5pt 8pt}.t2 .prop-card dl{row-gap:1.5pt}
.t2 .ref-img,.t3 .ref-img{aspect-ratio:3/4}.t2 .prod-img,.t3 .prod-img{aspect-ratio:1/1}
.t3{font-size:8.45pt;line-height:1.42}.t3 p{margin-bottom:4pt}.t3 li{margin-bottom:1.5pt}.t3 h3{margin-top:7pt;padding-top:4pt}.t3 .ref-grid,.t3 .prod-grid,.t3 .prop-grid{gap:4pt;margin-bottom:6pt}.t3 .ref-desc{font-size:7.1pt}.t3 .callout{padding:4.5pt 7pt}
.pgmark{position:absolute;left:0;top:0;font-size:2px;color:#fff;white-space:nowrap}
'''


def page_fill(pdf, n):
    from PIL import Image
    base = os.path.join(HERE, '_fill')
    subprocess.run(['pdftoppm', '-r', '30', '-f', str(n), '-l', str(n), '-png', '-singlefile', pdf, base], check=True)
    im = Image.open(base + '.png').convert('L'); w, h = im.size
    box = im.crop((int(w * .06), int(h * .05), int(w * .94), int(h * .92))); px = box.load(); W, H = box.size
    rows = [y for y in range(H) if any(px[x, y] < 235 for x in range(0, W, 2))]
    return (max(rows) / H) if rows else 0.0


def main():
    src, out = sys.argv[1], sys.argv[2]
    keep_html = '--keep-html' in sys.argv
    if '--meta' in sys.argv:
        META.update(json.load(open(sys.argv[sys.argv.index('--meta') + 1], encoding='utf-8')))
        OPT_FORCE[0] = True
    imgdir = os.path.join(HERE, 'images')
    md = open(src, encoding='utf-8').read()
    # drop a leading title block the writer may add (we render our own cover)
    md = preprocess(md)
    mdi = MarkdownIt('commonmark', {'html': True, 'linkify': True, 'typographer': False}).enable(['table', 'strikethrough', 'linkify'])
    mdi.linkify.set({'fuzzy_link': False, 'fuzzy_email': False, 'fuzzy_ip': False})
    body = mdi.render(md)
    IMGDIR_GLOBAL[0] = imgdir
    soup = transform(body, imgdir)
    container, toc = sectionize(soup)
    # mark sources chapter
    for sec in container.find_all('section', class_='chapter'):
        h1 = sec.find('h1')
        if h1 and 'fuentes' in norm(h1.get_text()):
            sec['class'] = sec.get('class', []) + ['sources']
    # skip a 'pre' section that only holds the writer's own title
    for sec in container.find_all('section', class_='pre'):
        sec.decompose()
    fonts = (font_face('Bodoni Moda', 'bodoni-moda', [400, 500, 600, 700], ('normal', 'italic')) + font_face('InterW', 'inter', [400, 500, 600, 700], ('normal', 'italic')))
    css = fonts + CSS.replace('FOOTER_LEFT', META['footer'].replace('"', "'"))

    def page(pages, markers):
        c = BeautifulSoup(str(container), 'html.parser')
        if markers:
            for i, e in enumerate(toc):
                for ent in [e] + e['children']:
                    el = c.find(id=ent['id'])
                    if el is not None:
                        sp = c.new_tag('span', attrs={'class': 'pgmark'})
                        sp.string = f'QZX{ent["id"].replace("-", "")[:40]}QZX'
                        el.insert(0, sp)
        return ('<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Tendencias de moda masculina · noviembre 2026</title>'
                f'<style>{css}</style></head><body>' + cover_html({'toc': toc}) + toc_html(toc, pages) + str(c) + '</body></html>')

    tmp_html = os.path.join(HERE, 'report.html')
    tmp_pdf = os.path.join(HERE, 'pass1.pdf')
    chapters = container.find_all('section', class_='chapter')
    tight = {}

    def marker_pass():
        for i, sec in enumerate(chapters):
            cl = [c for c in sec.get('class', []) if c not in ('t1', 't2', 't3')]
            if tight.get(i):
                cl.append('t%d' % tight[i])
            sec['class'] = cl
        open(tmp_html, 'w', encoding='utf-8').write(page({}, True))
        subprocess.run(['node', os.path.join(HERE, 'render.js'), tmp_html, tmp_pdf], check=True)
        txt = subprocess.run(['pdftotext', tmp_pdf, '-'], capture_output=True, text=True).stdout
        pages_txt = [t.replace(' ', '').replace('\n', '') for t in txt.split('\f')]
        pg = {}
        for e in toc:
            for ent in [e] + e['children']:
                key = f'QZX{ent["id"].replace("-", "")[:40]}QZX'
                for pi, ptxt in enumerate(pages_txt):
                    if key in ptxt:
                        pg[ent['id']] = pi + 1
                        break
        npages = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', tmp_pdf], capture_output=True, text=True).stdout).group(1))
        return pg, npages

    for it in range(4):
        pages, npages = marker_pass()
        starts = [pages.get(e['id']) for e in toc]
        changed = False
        for i, st in enumerate(starts):
            if st is None:
                continue
            nxt = next((x for x in starts[i + 1:] if x), npages + 1)
            last = nxt - 1
            if last <= st:
                continue
            f = page_fill(tmp_pdf, last)
            if f < 0.30 and tight.get(i, 0) < 3:
                tight[i] = tight.get(i, 0) + 1
                changed = True
                print(f'  chapter {toc[i]["text"][:30]!r}: last page {last} fill {f:.2f} -> t{tight[i]}', file=sys.stderr)
        if not changed:
            break
    missing = [ent['id'] for e in toc for ent in [e] + e['children'] if ent['id'] not in pages]
    if missing:
        print('WARN toc pages not found for:', missing[:10], file=sys.stderr)
    open(tmp_html, 'w', encoding='utf-8').write(page(pages, False))
    subprocess.run(['node', os.path.join(HERE, 'render.js'), tmp_html, out], check=True)
    if keep_html:
        print('html:', tmp_html)
    json.dump({'toc': toc, 'pages': pages}, open(os.path.join(HERE, 'toc.json'), 'w'), ensure_ascii=False, indent=1)
    print('ok', out)


if __name__ == '__main__':
    main()
