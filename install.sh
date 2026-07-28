#!/usr/bin/env sh
# ตัวติดตั้ง TH-Programming สำหรับ macOS / Linux
set -e
cd "$(dirname "$0")"

echo
echo "=== TH-Programming : ติดตั้ง ==="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ไม่ผ่าน] ไม่พบ python3 — ติดตั้งก่อนจาก https://www.python.org/downloads/"
    exit 1
fi

echo "[ผ่าน] พบ $(python3 --version)"
echo "กำลังติดตั้งคำสั่ง thprog ..."
python3 -m pip install --disable-pip-version-check -e . >/dev/null

echo
thprog doctor
echo
echo "ติดตั้งเสร็จแล้ว ลองพิมพ์:  thprog examples/demo.th"
