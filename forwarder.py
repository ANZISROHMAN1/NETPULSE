import os
import sys
import re
import urllib.request
import json
import glob
import zipfile
import tarfile
import time
from telethon import TelegramClient, events

# Target bot dan Chat ID Mas Anzis Rohman
BOT_TOKEN = "9248144995:AAGWGVTCLRjSaE4wein45sSH1RfYwRghOK4"
TARGET_CHAT_ID = "6874834483"

# Nomor HP Telegram akun penerima OTP
PHONE_NUMBER = "+628111172205"

# Telegram Desktop official API credentials
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

DOWNLOADS_DIR = os.path.expanduser("~/Downloads")
TARGET_DIR = "/Users/macbook/Documents/MONITORING ASSURANCE"

def send_to_anzis(message_text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TARGET_CHAT_ID,
        "text": message_text,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("[OK] Pesan terkirim ke Telegram Mas Anzis!", flush=True)
    except Exception as e:
        print(f"[ERR] Gagal kirim ke bot: {e}", flush=True)

def try_auto_extract(otp):
    """Mencari file wsa_*.zip terbaru di Downloads dan otomatis mengekstraknya menggunakan OTP"""
    # Tunggu sebentar jika file masih dalam proses download (.crdownload)
    for _ in range(5):
        if glob.glob(os.path.join(DOWNLOADS_DIR, "wsa_*.crdownload")):
            time.sleep(2)
        else:
            break

    recent_zips = sorted(glob.glob(os.path.join(DOWNLOADS_DIR, "wsa_*.zip")), key=os.path.getmtime, reverse=True)
    if not recent_zips:
        return None

    # Periksa zip yang didownload dalam 3 jam terakhir, atau ambil 10 file terbaru
    now = time.time()
    candidates = [z for z in recent_zips if (now - os.path.getmtime(z)) < 10800]
    if not candidates:
        candidates = recent_zips[:10]
    else:
        # Tambahkan cadangan file terbaru
        for z in recent_zips[:5]:
            if z not in candidates:
                candidates.append(z)

    success_files = []
    pwd_bytes = otp.encode('utf-8')

    for zip_path in candidates:
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                inner_name = zf.namelist()[0]
                temp_extracted = os.path.join(TARGET_DIR, inner_name)
                # Tes ekstrak dengan password
                zf.extract(inner_name, path=TARGET_DIR, pwd=pwd_bytes)
                print(f"[AUTO-EXTRACT] ✅ Sukses buka {os.path.basename(zip_path)} dengan OTP {otp}", flush=True)

            # Ekstrak lapisan kedua (yang berakhiran .tar tapi format zip)
            if zipfile.is_zipfile(temp_extracted):
                with zipfile.ZipFile(temp_extracted, 'r') as iz:
                    iz.extractall(TARGET_DIR)
                    txt_name = iz.namelist()[0]
                os.remove(temp_extracted)
            elif tarfile.is_tarfile(temp_extracted):
                with tarfile.open(temp_extracted, 'r:*') as it:
                    it.extractall(TARGET_DIR)
                    txt_name = it.getnames()[0]
                os.remove(temp_extracted)
            else:
                txt_name = inner_name

            # Salin ke Downloads juga agar mudah
            src_file = os.path.join(TARGET_DIR, txt_name)
            dst_file = os.path.join(DOWNLOADS_DIR, txt_name)
            with open(src_file, 'rb') as f_src, open(dst_file, 'wb') as f_dst:
                f_dst.write(f_src.read())

            size_mb = os.path.getsize(src_file) / (1024 * 1024)
            success_files.append((txt_name, size_mb))
            print(f"[AUTO-EXTRACT] 🎉 Berhasil ekstrak TXT: {txt_name} ({size_mb:.2f} MB)", flush=True)
        except Exception:
            pass # Password tidak cocok untuk zip ini, lewati

    return success_files

print("========================================", flush=True)
print("🚀 Telegram OTP Auto-Forwarder & Auto-Unzipper", flush=True)
print(f"Penerima Notifikasi: Mas Anzis ({TARGET_CHAT_ID})", flush=True)
print(f"Akun Telegram: {PHONE_NUMBER}", flush=True)
print("========================================\n", flush=True)

client = TelegramClient('assurance_session', API_ID, API_HASH)

@client.on(events.NewMessage)
async def my_event_handler(event):
    try:
        sender = await event.get_sender()
        sender_name = getattr(sender, 'first_name', '') or getattr(sender, 'title', '') or ''
        sender_username = getattr(sender, 'username', '') or ''
        text = event.raw_text or ''
        
        # Cek apakah pesan berasal dari assurancebot / pentahobot atau memuat kata kunci password file anda
        is_bot = (
            'assurance' in sender_name.lower() or
            'assurance' in sender_username.lower() or
            'pentaho' in sender_username.lower()
        )
        has_pwd = 'password file anda' in text.lower() or ('password' in text.lower() and re.search(r'\b\d{4}\b', text))

        if is_bot or has_pwd:
            match = re.search(r'password file anda\s*:\s*(\d{4})', text, re.IGNORECASE)
            otp = match.group(1) if match else None
            if not otp:
                m2 = re.search(r'\b\d{4}\b', text)
                otp = m2.group(0) if m2 else None

            if otp:
                print(f"\n[FOUND] OTP Diterima dari {sender_name} (@{sender_username}): {otp}", flush=True)
                
                # 1. Kirim notifikasi password ke Mas Anzis
                msg = f"🔔 *OTP NONATERO BARU*\n\n🔑 *Password:* `{otp}`\n\n_{text}_\n\n_Diteruskan otomatis dari assurancebot_"
                send_to_anzis(msg)
                
                # 2. Lakukan AUTO-UNZIP otomatis tanpa perlu ketik manual!
                extracted_list = try_auto_extract(otp)
                if extracted_list:
                    for fname, fsize in extracted_list:
                        confirm_msg = f"🎉 *AUTO-UNZIP BERHASIL!*\n\n📄 *File:* `{fname}`\n📊 *Ukuran:* `{fsize:.2f} MB`\n\n_File .txt bersih sudah tersimpan di folder kerja & Downloads!_"
                        send_to_anzis(confirm_msg)
    except Exception as e:
        print(f"[ERR] Event error: {e}", flush=True)

def main():
    client.start(phone=PHONE_NUMBER)
    
    me = client.loop.run_until_complete(client.get_me())
    user_label = f"{me.first_name} {me.last_name or ''} (@{me.username or me.phone})"
    print(f"\n✅ BERHASIL LOGIN sebagai: {user_label}", flush=True)
    print("🎧 Auto-Forwarder & Auto-Unzipper AKTIF!\n", flush=True)
    
    # Beri notifikasi ke Telegram Mas Anzis bahwa forwarder sudah siap
    send_to_anzis(f"🟢 *BOT WSA / FORWARDER ONLINE*\n\nAkun Telegram: `{user_label}`\nStatus: *Aktif & Siap Menerima OTP* 🎧\n_Setiap ada download Nonatero, OTP otomatis diteruskan dan file langsung di-unzip._")

    client.run_until_disconnected()

if __name__ == '__main__':
    main()
