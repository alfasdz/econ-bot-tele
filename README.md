# 💰 Telegram Bot Pencatat Keuangan Pribadi (Multi-Rekening)

Bot Telegram pribadi untuk mencatat pemasukan, pengeluaran, dan transfer antar rekening secara real-time, menggunakan **Python (`python-telegram-bot` v21+)** dan **PostgreSQL (Neon)**.

---

## ✨ Fitur Utama

- **Navigasi Tombol Interaktif Penuh (`ReplyKeyboardMarkup` + `InlineKeyboardMarkup`)**
  - `💳 Saldo` — Lihat saldo per rekening + total aset + tombol pintas transaksi
  - `➖ Keluar` & `➕ Masuk` — Pilih rekening → pilih kategori cepat → ketik nominal & catatan
  - `🔄 Transfer` — Pindah saldo antar rekening secara atomik (tidak dihitung sebagai income/expense)
  - `🏦 Kelola Akun` — Tambah akun baru, edit saldo akun, dan hapus akun dengan konfirmasi
  - `📊 Laporan` — Rekap pemasukan, pengeluaran, surplus/defisit, dan persentase per kategori (`Bulan Ini`, `Bulan Lalu`, atau `YYYY-MM`)
  - `📜 Riwayat` — Daftar transaksi terakhir (waktu lokal WIB) + tombol `↩️ Undo Transaksi Terakhir`
- **Input Fleksibel Tanpa `/`**
  - Bisa ketik langsung tanpa garis miring: `keluar 35k makan gopay nasi padang`, `masuk 3jt gaji bca`, `transfer 200k bca gopay`, `saldo`, `laporan 2026-10`, `riwayat`, `bantuan`
  - Mendukung format nominal singkat: `50000`, `50.000`, `50k`, `2.5jt`, `1m`
  - Perintah dengan `/` tetap didukung sebagai cadangan
- **Keamanan & Reliabilitas**
  - Whitelist akses khusus `ALLOWED_USER_ID` (user lain diabaikan diam-diam)
  - Connection pool PostgreSQL + transaksi database atomik (`COMMIT` / `ROLLBACK`)
  - Inisialisasi tabel `accounts` & `transactions` otomatis saat bot start

---

## 📁 Struktur Proyek

```text
├── main.py             # Entry point & registrasi handler
├── config.py           # Konfigurasi environment variables & logging
├── db.py               # Connection pool PostgreSQL, auto-init tabel, query atomik
├── formatters.py       # Format rupiah, parser nominal, & template pesan HTML
├── keyboards.py        # Menu tombol bawah & inline keyboard konfirmasi
├── handlers.py         # Alur interaktif (ConversationHandler) & perintah teks
├── requirements.txt    # Dependensi Python
├── Procfile            # Konfigurasi worker untuk deploy cloud (Railway/Render/Heroku)
├── runtime.txt         # Versi Python runtime
├── .env.example        # Contoh environment variables (tanpa kredensial asli)
└── .gitignore          # Mengabaikan .env, __pycache__, venv, dll.
```

---

## 🚀 Menjalankan di Lokal

1. **Clone repository ini:**
   ```bash
   git clone <url-repo-github-kamu>
   cd <nama-folder-repo>
   ```
2. **Install dependensi:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Buat file `.env` dari `.env.example`:**
   ```env
   TELEGRAM_BOT_TOKEN=token_dari_botfather
   ALLOWED_USER_ID=1091497145
   DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
   TZ_OFFSET_HOURS=7
   ```
4. **Jalankan bot:**
   ```bash
   python main.py
   ```

---

## ☁️ Deploy 24 Jam (Railway / Render)

1. Push repository ini ke **GitHub** (file `.env` otomatis diabaikan oleh `.gitignore`).
2. Hubungkan repository ke **Railway** atau **Render** (pilih tipe **Background Worker**).
3. Isi **Environment Variables** di dashboard hosting:
   - `TELEGRAM_BOT_TOKEN`
   - `ALLOWED_USER_ID` (contoh: `1091497145`)
   - `DATABASE_URL` (connection string PostgreSQL dari Neon)
   - `TZ_OFFSET_HOURS` (`7` untuk WIB)
4. Platform akan otomatis menjalankan `worker: python main.py` dari `Procfile`.
