# ⚡ NETPULSE - Branch Bogor Sukabumi
> **Assurance Command Center & Daily Ticket Monitoring System**  
> Sistem otomasi penarikan data tiket, forwarder OTP Telegram, dan Dashboard Telemetri Realtime terintegrasi Google Sheet.

![NETPULSE Logo](dashboard/static/logo.jpg)

---

## 📌 Fitur Utama

### 1. 📊 Web Dashboard Telemetri Realtime (`/dashboard`)
* **Format Persis Google Sheet**: Menampilkan Blok 1 (Tiket GGN, LIS, Service Availability), Blok 2 (Tiket GGN, Tiket GAUL, Assurance Guarantee), dan Blok 3 (TTR Comply per STO).
* **Live Google Sheet Sync**: Sinkronisasi data otomatis di latar belakang setiap 1–5 menit tanpa perlu reload browser.
* **Tampilan Fleksibel**:
  * `↔️ Side-by-Side`: Format berdampingan persis Google Sheet (Service Area kiri & STO kanan).
  * `↕️ Full-Width`: Format bertingkat satu layar penuh yang nyaman di layar laptop.
* **Smart SLA Heatmap**: Pilihan skema warna dinamis berbasis ambang batas SLA (Hijau $\ge 99.85\%$, Kuning, dan Merah).
* **Executive Analytics**: 6 grafik visual interaktif (Stacked GGN, Service Availability dengan SLA target line, Tiket GAUL, Assurance Guarantee, dan Donut Komposisi HVC/Reguler).
* **🚨 Top 10 STO Alert**: Peringkat otomatis 10 STO dengan tiket gangguan tertinggi untuk mitigasi teknisi lapangan prioritas.
* **🌙 Dark Mode & ⛶ Fullscreen**: Mode tampilan ruang kontrol (NOC/War Room) dengan penyimpanan preferensi tema.

---

### 2. 🤖 Otomasi Telegram OTP Forwarder (`forwarder.py`)
* Menggunakan MTProto (**Telethon**) untuk mengintercept pesan OTP otomatis dari `@assurancebot`.
* Meneruskan kode PIN 4-digit secara instan ke bot Telegram teknisi.
* Otomatis memicu ekstraksi file arsip bertingkat Nonatero (`wsa_*.zip` -> `.tar` -> `.txt`) yang terunduh di folder `~/Downloads`.

### 3. 📦 Ekstraktor Arsip Nonatero (`extract_all.py`)
* Menangani dekompresi arsip bertingkat Nonatero yang terenkripsi PIN password secara otomatis.
* Mengatasi masalah *magic bytes* arsip `.tar` yang sebenarnya berformat ZIP.

---

## 🚀 Panduan Menjalankan

### Persyaratan Sistem
* Python 3.8+
* Koneksi internet untuk Google Sheet & Telegram MTProto

### Instalasi Dependensi
```bash
pip install telethon cryptg requests
```

### Menjalankan Dashboard Web
```bash
cd dashboard
python3 server.py
```
Buka browser di: **`http://localhost:8765`**  
*(Atau cukup klik dua kali file `JALANKAN_DASHBOARD.command` di macOS).*

### Menjalankan OTP Forwarder Telegram
```bash
python3 forwarder.py
```
*(Atau cukup klik dua kali file `JALANKAN_FORWARDER.command` di macOS).*

---

## 📁 Struktur Direktori

```text
MONITORING ASSURANCE/
├── dashboard/
│   ├── server.py                   # HTTP server & sinkronisasi Google Sheet
│   ├── snapshot.csv                # Snapshot data fallback lokal
│   ├── JALANKAN_DASHBOARD.command  # Launcher sekali klik macOS
│   └── static/
│       ├── index.html              # Frontend Web Dashboard NETPULSE
│       └── logo.jpg                # Logo resmi NETPULSE
├── forwarder.py                    # Otomasi listener MTProto & OTP forwarder
├── extract_all.py                  # Script manual ekstraksi arsip tiket
├── JALANKAN_FORWARDER.command      # Launcher sekali klik macOS
├── EKSTRAK_TIKET.command           # Launcher sekali klik macOS
├── .env.example                    # Template konfigurasi variabel lingkungan
├── .gitignore                      # Proteksi session token & file data mentah
└── README.md                       # Dokumentasi proyek
```

---

## 🔒 Keamanan & Privasi
* Kunci sesi Telegram (`*.session`) dan data mentah tiket pelanggan (`*.txt`, `wsa_*`) dikecualikan dari repository publik melalui `.gitignore`.
* Kunci API dan token bot dapat dikonfigurasi melalui variabel lingkungan (`.env`).

---

**NETPULSE - Branch Bogor Sukabumi** &bull; *Ensuring Network Reliability & Service Excellence.*

