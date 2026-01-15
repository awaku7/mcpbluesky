#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import ssl
import json
import time
import threading
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ssl._create_default_https_context = ssl._create_unverified_context

APPVIEW = "https://public.api.bsky.app"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"

_RATE_LOCK = threading.Lock()
_LAST_REQUEST_TS = 0.0
_MIN_INTERVAL = 0.2

def _throttle():
    global _LAST_REQUEST_TS
    with _RATE_LOCK:
        now = time.time()
        dt = now - _LAST_REQUEST_TS
        if dt < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - dt)
            now = time.time()
        _LAST_REQUEST_TS = now

class ZscalerContinueParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.continue_url = None
        self.in_form = False
        self.action = None
        self.hidden = {}
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "form" and "_sm_ctn" in attrs.get("action", ""):
            self.in_form = True
            self.action = attrs["action"]
        elif self.in_form and tag.lower() == "input" and attrs.get("type") == "hidden":
            name = attrs.get("name")
            value = attrs.get("value", "")
            if name: self.hidden[name] = value
    def handle_endtag(self, tag):
        if tag.lower() == "form" and self.in_form:
            self.in_form = False
            if self.action:
                q = urllib.parse.urlencode(self.hidden)
                self.continue_url = f"{self.action}?{q}"

def try_zscaler_continue(html: str) -> str | None:
    if "_sm_ctn" not in html: return None
    parser = ZscalerContinueParser()
    parser.feed(html)
    return parser.continue_url

def _trigger_zscaler_continue(url: str):
    try:
        cj = urllib.request.HTTPCookieProcessor()
        opener = urllib.request.build_opener(cj)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with opener.open(req, timeout=15) as r: pass
    except Exception as e: print(f"Zscaler continue失敗: {e}")

def http_get_json(path: str, params: dict, retries: int = 3, extra_headers: dict = None, base_url: str = APPVIEW) -> dict:
    q = urllib.parse.urlencode(params, doseq=True)
    url = f"{base_url}{path}?{q}"
    headers = {"User-Agent": UA}
    if extra_headers: headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(1, retries + 1):
        try:
            _throttle()
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                if "_sm_ctn" in data:
                    cont_url = try_zscaler_continue(data)
                    if cont_url:
                        _trigger_zscaler_continue(cont_url)
                        time.sleep(2)
                        continue
                return json.loads(data)
        except urllib.error.HTTPError as e:
            try: body = e.read().decode(errors="ignore")
            except: body = ""
            cont_url = try_zscaler_continue(body)
            if cont_url:
                _trigger_zscaler_continue(cont_url)
                time.sleep(2)
                continue
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", 10))
                time.sleep(wait); continue
            elif e.code in (403, 500, 502, 503, 504):
                time.sleep(3); continue
            else: raise
        except Exception as e:
            time.sleep(2)
    raise RuntimeError("HTTPリトライ失敗")

def http_post_json(path: str, payload: dict, retries: int = 3, extra_headers: dict = None, base_url: str = APPVIEW) -> dict:
    url = f"{base_url}{path}"
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = {"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"}
    if extra_headers: headers.update(extra_headers)
    for attempt in range(1, retries + 1):
        try:
            _throttle()
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                if "_sm_ctn" in data:
                    cont_url = try_zscaler_continue(data)
                    if cont_url:
                        _trigger_zscaler_continue(cont_url)
                        time.sleep(2)
                        continue
                return json.loads(data) if data.strip() else {}
        except urllib.error.HTTPError as e:
            try: body = e.read().decode(errors="ignore")
            except: body = ""
            cont_url = try_zscaler_continue(body)
            if cont_url:
                _trigger_zscaler_continue(cont_url)
                time.sleep(2)
                continue
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", 10))
                time.sleep(wait); continue
            elif e.code in (403, 500, 502, 503, 504):
                time.sleep(3); continue
            else: raise
        except Exception as e:
            time.sleep(2)
    raise RuntimeError("HTTPリトライ失敗")
