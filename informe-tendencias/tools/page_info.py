#!/usr/bin/env python3
"""Open web pages and report status, title, publication date, main image (og:image) and price hints.
Usage: python3 page_info.py <URL> [more URLs...]   (add --text to also print ~3000 chars of visible text)
Use it to verify links, find publication dates and get a product's or article's main photo URL."""
import sys, os, re, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import fetch, meta
show_text = '--text' in sys.argv
for url in [a for a in sys.argv[1:] if not a.startswith('--')]:
    p, code, final = fetch(url)
    s = open(p, encoding='utf-8', errors='ignore').read()
    t = re.search(r'<title[^>]*>(.*?)</title>', s, re.S)
    date = (meta(s, 'article:published_time') or meta(s, 'datePublished') or
            (re.search(r'"datePublished"\s*:\s*"([^"]+)"', s) or [None, None])[1] or
            (re.search(r'"dateModified"\s*:\s*"([^"]+)"', s) or [None, None])[1])
    price = (meta(s, 'product:price:amount') or meta(s, 'og:price:amount') or
             (re.search(r'"price"\s*:\s*"?([0-9][0-9.,]*)"?', s) or [None, None])[1])
    cur = meta(s, 'product:price:currency') or meta(s, 'og:price:currency') or (re.search(r'"priceCurrency"\s*:\s*"([A-Z]{3})"', s) or [None, None])[1]
    print(f'URL: {url}\n  status: {code}  final: {final}\n  title: {html.unescape(t.group(1).strip())[:160] if t else "?"}')
    print(f'  og:title: {meta(s, "og:title")}\n  date: {date}\n  og:image: {meta(s, "og:image")}\n  price: {price} {cur or ""}  size: {len(s)} bytes')
    if show_text:
        txt = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', s, flags=re.S)
        txt = html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', txt)))
        print('  text:', txt[:3000])
