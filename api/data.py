import csv
import io
import json
import time
import urllib.request
from http.server import BaseHTTPRequestHandler

SHEET_ID = "1Pu8n4tt0TiPec1_j31HJ5FgZdCPCuBwH6SWrEiXg7Bg"
GID = "1357353552"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            req = urllib.request.Request(EXPORT_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            
            payload = {
                "source": "live-vercel",
                "fetched_at": time.time(),
                "sheet_url": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={GID}",
                "data": parse_sheet(text)
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "s-maxage=30, stale-while-revalidate")
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            err = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(err)
