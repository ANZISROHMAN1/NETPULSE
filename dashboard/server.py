#!/usr/bin/env python3
"""
Dashboard Monitoring Tiket Harian (versi web)
Sumber data : Google Sheet (tab DASHBOARD), harus bisa dilihat siapa saja yang punya link.
Jalankan    : python3 server.py   lalu buka http://localhost:8765
"""
import csv
import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

SHEET_ID = "1Pu8n4tt0TiPec1_j31HJ5FgZdCPCuBwH6SWrEiXg7Bg"
GID = "1357353552"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
PORT = int(os.environ.get("PORT", "8765"))
CACHE_TTL = 30  # detik (agar update dari Google Sheet cepat terdeteksi)

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
CACHE_FILE = os.path.join(BASE, "cache.csv")
SNAPSHOT_FILE = os.path.join(BASE, "snapshot.csv")

_lock = threading.Lock()
_state = {"csv": None, "fetched_at": 0, "source": None, "error": None}


# ----------------------------------------------------------------- download
def download_csv():
    """Ambil CSV dari Google Sheet. Utamakan curl (memakai sertifikat sistem macOS)."""
    try:
        out = subprocess.run(
            ["curl", "-sSL", "-f", "--max-time", "40", EXPORT_URL],
            capture_output=True, timeout=60,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.decode("utf-8", errors="replace")
        err = out.stderr.decode("utf-8", errors="replace").strip()
    except Exception as e:  # curl tidak ada / timeout
        err = str(e)
    try:
        with urllib.request.urlopen(EXPORT_URL, timeout=40) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Gagal mengunduh sheet: {err or e}")


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_csv(force=False):
    """Kembalikan (csv_text, source, fetched_at, error)."""
    with _lock:
        fresh = _state["csv"] and (time.time() - _state["fetched_at"] < CACHE_TTL)
        if fresh and not force:
            return _state["csv"], _state["source"], _state["fetched_at"], _state["error"]
        try:
            text = download_csv()
            if text.lstrip().startswith("<"):
                raise RuntimeError(
                    "Google meminta login. Ubah akses sheet menjadi "
                    "'Siapa saja yang memiliki link' (Viewer)."
                )
            _state.update(csv=text, fetched_at=time.time(), source="live", error=None)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            _state["error"] = str(e)
            if os.path.exists(CACHE_FILE):
                _state.update(csv=read_file(CACHE_FILE), source="cache",
                              fetched_at=os.path.getmtime(CACHE_FILE))
            elif os.path.exists(SNAPSHOT_FILE):
                _state.update(csv=read_file(SNAPSHOT_FILE), source="snapshot",
                              fetched_at=os.path.getmtime(SNAPSHOT_FILE))
            else:
                raise
        return _state["csv"], _state["source"], _state["fetched_at"], _state["error"]


# ------------------------------------------------------------------ parser
def num(s):
    """'1,608' -> 1608 ; '99.75%' -> 99.75 ; '' -> None"""
    s = (s or "").strip()
    if not s:
        return None
    pct = s.endswith("%")
    s = s.replace(",", "").rstrip("%")
    try:
        v = float(s)
    except ValueError:
        return None
    if pct:
        return round(v, 2)
    return int(v) if v.is_integer() else v


def cell(r, i):
    return r[i].strip() if i < len(r) else ""


def quad(r, start):
    return {
        "diamond": num(cell(r, start)),
        "platinum": num(cell(r, start + 1)),
        "reguler": num(cell(r, start + 2)),
        "total": num(cell(r, start + 3)),
    }


def parse_block(rows, header_idx, names):
    """Dua tabel berdampingan: Service Area (kolom 0-12) dan STO (kolom 14-27)."""
    left, right = [], []
    j = header_idx + 2
    while j < len(rows):
        r = rows[j]
        a, b = cell(r, 0), cell(r, 14)
        if not a and not b:
            break
        if a and a != "SERVICE AREA":
            left.append({"name": a, names[0]: quad(r, 1), names[1]: quad(r, 5), names[2]: quad(r, 9)})
        if b:
            right.append({"sto": b, "sa": cell(r, 15),
                          names[0]: quad(r, 16), names[1]: quad(r, 20), names[2]: quad(r, 24)})
        j += 1
    return left, right


def parse_sheet(text):
    text = text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    rows = [r for r in csv.reader(io.StringIO(text))]

    data = {"meta": {}, "cards": {}, "lis": {"sa": [], "sto": []}, "ag": {"sa": [], "sto": []}, "ttr": []}

    for i, r in enumerate(rows):
        c0 = cell(r, 0)
        if c0.startswith("📊"):
            data["meta"]["title"] = c0.replace("📊", "").strip()
        elif c0 == "Tanggal":
            data["meta"].update(tanggal=cell(r, 1), district=cell(r, 3),
                                service_area=cell(r, 5), update=cell(r, 6).replace("Update:", "").strip())
            if i + 1 < len(rows):
                n = rows[i + 1]
                data["meta"]["filters"] = {"IS_GAUL": cell(n, 1), "IS_GAMAS": cell(n, 3),
                                           "JENIS_TIKET2": cell(n, 5), "IS_FFG": cell(n, 7)}
        elif c0 == "TOTAL TIKET" and i + 1 < len(rows):
            v = rows[i + 1]
            data["cards"] = {"total": num(cell(v, 0)), "hvc": num(cell(v, 2)), "reguler": num(cell(v, 4)),
                             "sto_aktif": num(cell(v, 6)), "sa_aktif": num(cell(v, 8))}
        elif c0 == "SERVICE AREA" and "LIS Pelanggan" in r:
            sa, sto = parse_block(rows, i, ["ggn", "lis", "avail"])
            data["lis"] = {"sa": sa, "sto": sto}
        elif c0 == "SERVICE AREA" and "Assurance Guarantee" in r:
            sa, sto = parse_block(rows, i, ["ggn", "gaul", "ag"])
            data["ag"] = {"sa": sa, "sto": sto}
        elif c0 == "TTR COMPLY":
            j = i + 3
            while j < len(rows) and cell(rows[j], 0):
                r2 = rows[j]
                grp = lambda s: {"comply": num(cell(r2, s)), "not_comply": num(cell(r2, s + 1)),
                                 "total": num(cell(r2, s + 2))}
                data["ttr"].append({"sto": cell(r2, 0), "sa": cell(r2, 1), "total": num(cell(r2, 2)),
                                    "diamond": grp(3), "manja": grp(6), "platinum": grp(9), "reguler": grp(12)})
                j += 1
    return data


# ------------------------------------------------------------------ server
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, read_file(os.path.join(STATIC, "index.html")), "text/html; charset=utf-8")
        if url.path in ("/logo.jpg", "/favicon.ico", "/logo.png"):
            logo_path = os.path.join(STATIC, "logo.jpg")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as f:
                    return self._send(200, f.read(), "image/jpeg")
        if url.path == "/api/data":
            force = parse_qs(url.query).get("force", ["0"])[0] == "1"
            try:
                text, source, fetched_at, error = get_csv(force)
                payload = {"source": source, "fetched_at": fetched_at, "error": error,
                           "sheet_url": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={GID}",
                           "data": parse_sheet(text)}
                return self._send(200, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")
            except Exception as e:
                return self._send(500, json.dumps({"error": str(e)}), "application/json; charset=utf-8")
        self._send(404, "Not found", "text/plain")


def main():
    if "--test" in sys.argv:  # uji parser dengan snapshot lokal
        print(json.dumps(parse_sheet(read_file(SNAPSHOT_FILE)), ensure_ascii=False, indent=1)[:3000])
        return
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Dashboard aktif di http://localhost:{PORT}  (Ctrl+C untuk berhenti)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDihentikan.")


if __name__ == "__main__":
    main()

