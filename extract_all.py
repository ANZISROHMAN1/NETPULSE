#!/usr/bin/env python3
import os
import glob
import zipfile
import tarfile
import sys

DOWNLOADS_DIR = os.path.expanduser("~/Downloads")
TARGET_DIR = "/Users/macbook/Documents/MONITORING ASSURANCE"

def extract_nested_zip(zip_path, password):
    pwd_bytes = password.encode('utf-8')
    with zipfile.ZipFile(zip_path, 'r') as zf:
        inner_name = zf.namelist()[0]
        temp_extracted = os.path.join(TARGET_DIR, inner_name)
        zf.extract(inner_name, path=TARGET_DIR, pwd=pwd_bytes)

    extracted_txt = None
    if zipfile.is_zipfile(temp_extracted):
        with zipfile.ZipFile(temp_extracted, 'r') as inner_zf:
            inner_zf.extractall(TARGET_DIR)
            extracted_txt = inner_zf.namelist()[0]
        os.remove(temp_extracted)
    elif tarfile.is_tarfile(temp_extracted):
        with tarfile.open(temp_extracted, 'r:*') as tf:
            tf.extractall(path=TARGET_DIR)
            extracted_txt = tf.getnames()[0]
        os.remove(temp_extracted)
    else:
        extracted_txt = inner_name

    final_path = os.path.join(TARGET_DIR, extracted_txt)
    size_mb = os.path.getsize(final_path) / (1024 * 1024)
    print(f"  🎉 SUKSES! {os.path.basename(zip_path)} -> {extracted_txt} ({size_mb:.2f} MB)")
    
    # Salin juga ke folder Downloads
    dl_copy = os.path.join(DOWNLOADS_DIR, extracted_txt)
    with open(final_path, 'rb') as f_src, open(dl_copy, 'wb') as f_dst:
        f_dst.write(f_src.read())
    return final_path

def main():
    print("========================================")
    print("📦 Ekstraktor Otomatis Tiket Nonatero")
    print("========================================")
    
    zips = sorted(glob.glob(os.path.join(DOWNLOADS_DIR, "wsa_*.zip")), key=os.path.getmtime, reverse=True)
    if not zips:
        print("❌ Tidak ada file wsa_*.zip di folder Downloads.")
        return

    # Ambil zip yang didownload hari ini / terbaru
    print(f"Ditemukan {len(zips)} file ZIP di folder Downloads:")
    for i, z in enumerate(zips[:5], 1):
        print(f"  {i}. {os.path.basename(z)}")

    pwd_input = input("\nMasukkan password dari assurancebot (pisahkan dengan spasi jika banyak): ").strip()
    if not pwd_input:
        print("Password tidak boleh kosong!")
        return

    passwords = [p.strip() for p in pwd_input.replace(',', ' ').split() if p.strip()]

    for zip_path in zips[:5]:
        extracted = False
        for p in passwords:
            try:
                extract_nested_zip(zip_path, p)
                extracted = True
                break
            except Exception:
                pass
        if not extracted:
            print(f"  ⚠️ Tidak dapat membuka {os.path.basename(zip_path)} dengan password yang dimasukkan.")

    print("\n✅ Selesai! Semua file .txt sudah siap di folder kerja & Downloads.")

if __name__ == '__main__':
    main()
