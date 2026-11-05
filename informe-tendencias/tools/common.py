import subprocess, hashlib, os, re, json, html as _html
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMGDIR = os.path.join(HERE, 'images')
CACHE = os.path.join(HERE, 'pagecache')
os.makedirs(IMGDIR, exist_ok=True); os.makedirs(CACHE, exist_ok=True)

def fetch(url, binary=False, timeout=30):
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    p = os.path.join(CACHE, key + ('.bin' if binary else '.html'))
    if os.path.exists(p) and os.path.getsize(p) > 500:
        return p, 200, url
    r = subprocess.run(['curl', '-sL', '--compressed', '--max-time', str(timeout), '-A', UA,
                        '-H', 'Accept-Language: es-ES,es;q=0.9,en;q=0.8',
                        '-o', p, '-w', '%{http_code} %{url_effective}', url], capture_output=True, text=True)
    out = (r.stdout or '0 ' + url).split(' ', 1)
    code = int(out[0]) if out[0].isdigit() else 0
    return p, code, out[1] if len(out) > 1 else url

def meta(html_text, prop):
    for pat in (rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]+content=["\']([^"\']*)["\']',
                rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{prop}["\']'):
        m = re.search(pat, html_text, re.I)
        if m:
            return _html.unescape(m.group(1))
    return None
