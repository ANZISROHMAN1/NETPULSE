import csv
import io
import json
import time
import urllib.request
from http.server import BaseHTTPRequestHandler

SHEET_ID = "1Pu8n4tt0TiPec1_j31HJ5FgZdCPCuBwH6SWrEiXg7Bg"
GID_DASHBOARD = "1357353552"
GID_CACHE = "366740069"
GID_SA = "821202101"

def fetch_csv(gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8", errors="replace")

def num(s):
    s = (s or "").strip()
    if not s: return None
    pct = s.endswith("%")
    s = s.replace(",", "").rstrip("%")
    try: v = float(s)
    except ValueError: return None
    if pct: return round(v, 2)
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
        if not a and not b: break
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
        if len(r) > 17 and r[7] == '0':
            tickets.append([
                r[1].strip() or r[0].strip(),
                r[2].strip(),
                r[3].strip(),
                r[4].strip(),
                r[5].strip(),
                r[8].strip(),
                r[9].strip(),
                r[10].strip(),
                r[11].strip(),
                r[12].strip(),
                r[14].strip(),
                r[15].strip(),
                r[16].strip(),
                r[17].strip(),
                r[18].strip() if len(r) > 18 else '',
                r[19].strip() if len(r) > 19 else '',
                r[13].strip() if len(r) > 13 else '',  # 16: manja_flag
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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            text_dash = fetch_csv(GID_DASHBOARD)
            text_cache = fetch_csv(GID_CACHE)
            text_sa = fetch_csv(GID_SA)

            dash_data = parse_sheet(text_dash)
            tickets = parse_tickets(text_cache)
            lis_map = parse_lis(text_sa)

            dates = sorted(list(set(t[0] for t in tickets)), reverse=True)
            districts = sorted(list(set(t[2] for t in tickets if t[2])))
            service_areas = sorted(list(set(t[3] for t in tickets if t[3])))
            jenis_options = sorted(list(set(t[7] for t in tickets if t[7])))

            payload = {
                "source": "live-vercel",
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
