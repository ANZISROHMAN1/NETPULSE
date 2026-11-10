#!/usr/bin/env python3
"""
Dashboard Monitoring Tiket Harian - NETPULSE
Sumber data : Google Sheet (tab DASHBOARD, _DASH_CACHE, Service_Area)
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
GID_DASHBOARD = "1357353552"
GID_CACHE = "366740069"
GID_SA = "821202101"

PORT = int(os.environ.get("PORT", "8765"))
CACHE_TTL = 45  # detik

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
CACHE_FILE = os.path.join(BASE, "cache_payload.json")
SNAPSHOT_FILE = os.path.join(BASE, "snapshot.csv")

_lock = threading.Lock()
_state = {"payload": None, "fetched_at": 0}


# ----------------------------------------------------------------- download
def download_sheet_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    try:
        out = subprocess.run(
            ["curl", "-sSL", "-f", "--max-time", "30", url],
            capture_output=True, timeout=40,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.decode("utf-8", errors="replace")
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Gagal mengunduh sheet gid={gid}: {e}")


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ parser
def num(s):
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


def parse_tickets(cache_text):
    rows = list(csv.reader(io.StringIO(cache_text)))
    tickets = []
    for r in rows[1:]:
        if len(r) > 17 and r[7] == '0':  # WSA_EXCLUDE == 0
            tickets.append([
                r[1].strip() or r[0].strip(),  # 0: date (YYYY-MM-DD)
                r[2].strip(),                  # 1: sto
                r[3].strip(),                  # 2: district
                r[4].strip(),                  # 3: sa
                r[5].strip(),                  # 4: type (HVC / REGULER)
                r[8].strip(),                  # 5: is_gaul (1 / 0)
                r[9].strip(),                  # 6: is_gamas (1 / 0)
                r[10].strip(),                 # 7: jenis_tiket2
                r[11].strip(),                 # 8: is_ffg (1 / 0)
                r[12].strip(),                 # 9: hvc_flag
                r[14].strip(),                 # 10: c3 (1 / 0)
                r[15].strip(),                 # 11: c3m (1 / 0)
                r[16].strip(),                 # 12: c6 (1 / 0)
                r[17].strip(),                 # 13: c24 (1 / 0)
                r[18].strip() if len(r) > 18 else "", # 14: trouble_no
                r[19].strip() if len(r) > 19 else "", # 15: no_inet
            ])
    return tickets


def parse_lis(sa_text):
    rows = list(csv.reader(io.StringIO(sa_text)))
    lis_map = {}
    for r in rows[2:]:
        if len(r) > 6 and r[2]:
            sto = r[2].strip()
            def to_n(val):
                try: return int(val.replace(',', ''))
                except: return 0
            lis_map[sto] = {
                "district": r[0].strip(),
                "sa": r[1].strip(),
                "sto": sto,
                "total": to_n(r[3]),
                "dia": to_n(r[4]),
                "plat": to_n(r[5]),
                "reg": to_n(r[6]),
            }
    return lis_map


def get_payload(force=False):
    with _lock:
        fresh = _state.get("payload") and (time.time() - _state.get("fetched_at", 0) < CACHE_TTL)
        if fresh and not force:
            return _state["payload"]
        try:
            # 1. Download DASHBOARD
            text_dash = download_sheet_csv(GID_DASHBOARD)
            # 2. Download _DASH_CACHE
            text_cache = download_sheet_csv(GID_CACHE)
            # 3. Download Service_Area
            text_sa = download_sheet_csv(GID_SA)

            dash_data = parse_sheet(text_dash)
            tickets = parse_tickets(text_cache)
            lis_map = parse_lis(text_sa)

            dates = sorted(list(set(t[0] for t in tickets)), reverse=True)
            districts = sorted(list(set(t[2] for t in tickets if t[2])))
            service_areas = sorted(list(set(t[3] for t in tickets if t[3])))
            jenis_options = sorted(list(set(t[7] for t in tickets if t[7])))

            payload = {
                "source": "live",
                "fetched_at": time.time(),
                "sheet_url": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={GID_DASHBOARD}",
                "data": dash_data,
                "dates": dates,
                "districts": districts,
                "service_areas": service_areas,
                "jenis_options": jenis_options,
                "lis_map": lis_map,
                "tickets": tickets,
            }
            _state["payload"] = payload
            _state["fetched_at"] = time.time()
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            return payload
        except Exception as e:
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                        payload["source"] = "cache"
                        return payload
                except Exception:
                    pass
            # Fallback snapshot
            if os.path.exists(SNAPSHOT_FILE):
                dash_data = parse_sheet(read_file(SNAPSHOT_FILE))
                return {
                    "source": "snapshot",
                    "fetched_at": time.time(),
                    "sheet_url": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={GID_DASHBOARD}",
                    "data": dash_data,
                    "dates": ["2026-11-02"],
                    "districts": ["BOGOR"],
                    "service_areas": ["BOGOR", "CIBINONG", "CILEUNGSI", "SUKABUMI", "SEMPLAK", "CIAWI", "PAGELARAN", "CIBADAK", "DRAMAGA", "KEDUNGHALANG", "PASIR MAUNG"],
                    "jenis_options": ["FISIK", "LOGIK"],
                    "lis_map": {},
                    "tickets": [],
                }
            raise


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
        self.send_header("Access-Control-Allow-Origin", "*")
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
                payload = get_payload(force)
                return self._send(200, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")
            except Exception as e:
                return self._send(500, json.dumps({"error": str(e)}), "application/json; charset=utf-8")
        self._send(404, "Not found", "text/plain")


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"NETPULSE Server aktif di http://localhost:{PORT}  (Ctrl+C untuk berhenti)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDihentikan.")


if __name__ == "__main__":
    main()
