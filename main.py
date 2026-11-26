#!/usr/bin/env python3
"""
main.py — Entry point: inisialisasi DB, registrasi handler, jalankan polling.
"""

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import db
from config import BOT_TOKEN, logger
from handlers import (
    build_conversation_handler,
    callback_delete_confirm,
    callback_undo_from_history,
    cancel_inline,
    cmd_hapus_terakhir,
    cmd_help,
    cmd_keluar,
    cmd_laporan,
    cmd_masuk,
    cmd_riwayat,
    cmd_saldo,
    cmd_start,
    cmd_tambah_akun,
    cmd_transfer,
    handle_plain_text,
)


def main():
    if not BOT_TOKEN:
        raise SystemExit("❌ TELEGRAM_BOT_TOKEN belum di-set!")
    if not db.DATABASE_URL:
        raise SystemExit("❌ DATABASE_URL belum di-set!")

    # ── Inisialisasi database ──
    logger.info("Inisialisasi database…")
    db.init_db()

    # ── Build application ──
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── 1. Alur interaktif (ConversationHandler) — prioritas utama ──
    app.add_handler(build_conversation_handler())

    # ── 2. Slash command cadangan ──
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("saldo", cmd_saldo))
    app.add_handler(CommandHandler("tambah_akun", cmd_tambah_akun))
    app.add_handler(CommandHandler("masuk", cmd_masuk))
    app.add_handler(CommandHandler("keluar", cmd_keluar))
    app.add_handler(CommandHandler("transfer", cmd_transfer))
    app.add_handler(CommandHandler("riwayat", cmd_riwayat))
    app.add_handler(CommandHandler("laporan", cmd_laporan))
    app.add_handler(CommandHandler("hapus_terakhir", cmd_hapus_terakhir))

    # ── 3. Standalone Callback Queries ──
    app.add_handler(CallbackQueryHandler(callback_undo_from_history, pattern=r"^hist:undo$"))
    app.add_handler(CallbackQueryHandler(callback_delete_confirm, pattern=r"^delete_(confirm|cancel)$"))
    app.add_handler(CallbackQueryHandler(cancel_inline, pattern=r"^nav:cancel$"))

    # ── 4. Teks Polos Tanpa '/' (dijalankan hanya jika tidak sedang di Conversation) ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plain_text))

    # ── Run ──
    logger.info("Bot berjalan… (polling)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
