#!/bin/bash
cd "$(dirname "$0")"
echo "Menjalankan Dashboard Monitoring Tiket Harian..."
(sleep 2 && open "http://localhost:8765") &
python3 server.py

