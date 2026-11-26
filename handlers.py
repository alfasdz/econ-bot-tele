"""
handlers.py — Seluruh handler perintah, alur interaktif (ConversationHandler),
              teks polos tanpa '/', callback query, dan scan struk foto.
"""

import re
from datetime import datetime

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import db
import formatters as F
import keyboards as K
from config import ALLOWED_USER_ID

# ───────────────── Conversation States ─────────────────

(
    EXP_ACC,
    EXP_CAT,
    EXP_CUSTOM_CAT,
    EXP_AMT,
    INC_ACC,
    INC_CAT,
    INC_CUSTOM_CAT,
    INC_AMT,
    TRF_SRC,
    TRF_DST,
    TRF_AMT,
    ACC_MENU,
    ACC_ADD_INPUT,
    ACC_EDIT_PICK,
    ACC_EDIT_AMT,
    ACC_DEL_PICK,
    ACC_DEL_CONFIRM,
    RPT_MENU,
    RPT_CUSTOM_MONTH,
) = range(19)


# ───────────────── Auth Guard ─────────────────

def _is_allowed(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid == ALLOWED_USER_ID


def authorized(func):
    """Decorator: abaikan user yang tidak diizinkan secara diam-diam."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not _is_allowed(update):
            return
        return await func(update, ctx)
    return wrapper


def _parse_amt_and_note(text: str) -> tuple[int | None, str | None]:
    """Parse '<nominal> [catatan...]' dari input polos user."""
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return None, None
    amount = F.parse_amount(parts[0])
    note = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return amount, note


# ───────────────── Core Action Helpers ─────────────────

async def _send_saldo(update: Update):
    accounts = db.get_all_accounts()
    if not accounts:
        await update.effective_message.reply_text(
            "ℹ️ Belum ada akun.\n\n"
            "Tekan <b>🏦 Kelola Akun</b> → <b>➕ Tambah Akun Baru</b>,\n"
            "atau ketik: <code>tambah_akun bca 5jt</code>",
            parse_mode="HTML",
            reply_markup=K.MAIN_MENU,
        )
        return
    await update.effective_message.reply_text(
        F.msg_balance(accounts),
        parse_mode="HTML",
        reply_markup=K.saldo_actions_keyboard(),
    )


async def _send_riwayat(update: Update, limit: int = 10):
    txs = db.get_recent_transactions(limit)
    await update.effective_message.reply_text(
        F.msg_history(txs),
        parse_mode="HTML",
        reply_markup=K.history_actions_keyboard(bool(txs)),
    )


async def _send_report(message, year: int, month: int, edit: bool = False):
    data = db.get_monthly_report(year, month)
    text = F.msg_report(year, month, data)
    if edit:
        await message.edit_text(text, parse_mode="HTML")
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=K.MAIN_MENU)


async def _prompt_delete_last(message):
    tx = db.get_last_transaction()
    if not tx:
        await message.reply_text("ℹ️ Tidak ada transaksi yang bisa dihapus.", reply_markup=K.MAIN_MENU)
        return None
    await message.reply_text(
        F.msg_confirm_delete(tx),
        parse_mode="HTML",
        reply_markup=K.confirm_delete_keyboard(),
    )
    return tx


async def _exec_tambah_akun(update: Update, args: list[str]):
    if len(args) < 2:
        await update.effective_message.reply_text(
            "⚠️ Format: <code>tambah_akun &lt;nama&gt; &lt;saldo_awal&gt;</code>\n"
            "Contoh: <code>tambah_akun bca 5jt</code>",
            parse_mode="HTML",
        )
        return
    name = args[0].lower()
    amount = F.parse_amount(args[1])
    if amount is None or amount < 0:
        await update.effective_message.reply_text("⚠️ Saldo awal tidak valid. Gunakan angka positif.")
        return
    if db.add_account(name, amount):
        await update.effective_message.reply_text(
            F.msg_account_created(name, amount),
            parse_mode="HTML",
            reply_markup=K.MAIN_MENU,
        )
    else:
        await update.effective_message.reply_text(
            F.msg_account_exists(name), parse_mode="HTML", reply_markup=K.MAIN_MENU,
        )


async def _exec_masuk(update: Update, args: list[str]):
    if len(args) < 3:
        await update.effective_message.reply_text(
            "⚠️ Format: <code>masuk &lt;nominal&gt; &lt;kategori&gt; &lt;akun&gt; [catatan]</code>\n"
            "Contoh: <code>masuk 3jt gaji bca bonus</code>",
            parse_mode="HTML",
        )
        return
    amount = F.parse_amount(args[0])
    if amount is None or amount <= 0:
        await update.effective_message.reply_text("⚠️ Nominal harus angka positif.")
        return
    category = args[1].lower()
    account = args[2].lower()
    note = " ".join(args[3:]) if len(args) > 3 else None

    acc = db.get_account(account)
    if not acc:
        await update.effective_message.reply_text(
            f"⚠️ Akun <b>{F.esc(account)}</b> tidak ditemukan.", parse_mode="HTML",
        )
        return

    db.record_income(amount, category, account, note)
    await update.effective_message.reply_text(
        F.msg_income(amount, category, account, note, acc["balance"] + amount),
        parse_mode="HTML",
        reply_markup=K.MAIN_MENU,
    )


async def _exec_keluar(update: Update, args: list[str]):
    if len(args) < 3:
        await update.effective_message.reply_text(
            "⚠️ Format: <code>keluar &lt;nominal&gt; &lt;kategori&gt; &lt;akun&gt; [catatan]</code>\n"
            "Contoh: <code>keluar 35k makan gopay nasi padang</code>",
            parse_mode="HTML",
        )
        return
    amount = F.parse_amount(args[0])
    if amount is None or amount <= 0:
        await update.effective_message.reply_text("⚠️ Nominal harus angka positif.")
        return
    category = args[1].lower()
    account = args[2].lower()
    note = " ".join(args[3:]) if len(args) > 3 else None

    acc = db.get_account(account)
    if not acc:
        await update.effective_message.reply_text(
            f"⚠️ Akun <b>{F.esc(account)}</b> tidak ditemukan.", parse_mode="HTML",
        )
        return
    if acc["balance"] < amount:
        await update.effective_message.reply_text(
            F.msg_insufficient(account, acc["balance"], amount), parse_mode="HTML",
        )
        return

    db.record_expense(amount, category, account, note)
    await update.effective_message.reply_text(
        F.msg_expense(amount, category, account, note, acc["balance"] - amount),
        parse_mode="HTML",
        reply_markup=K.MAIN_MENU,
    )


async def _exec_transfer(update: Update, args: list[str]):
    if len(args) < 3:
        await update.effective_message.reply_text(
            "⚠️ Format: <code>transfer &lt;nominal&gt; &lt;akun_asal&gt; &lt;akun_tujuan&gt; [catatan]</code>\n"
            "Contoh: <code>transfer 200k bca gopay topup</code>",
            parse_mode="HTML",
        )
        return
    amount = F.parse_amount(args[0])
    if amount is None or amount <= 0:
        await update.effective_message.reply_text("⚠️ Nominal harus angka positif.")
        return
    src = args[1].lower()
    dst = args[2].lower()
    note = " ".join(args[3:]) if len(args) > 3 else None

    if src == dst:
        await update.effective_message.reply_text("⚠️ Akun asal dan tujuan tidak boleh sama.")
        return
    src_acc = db.get_account(src)
    if not src_acc:
        await update.effective_message.reply_text(
            f"⚠️ Akun <b>{F.esc(src)}</b> tidak ditemukan.", parse_mode="HTML",
        )
        return
    dst_acc = db.get_account(dst)
    if not dst_acc:
        await update.effective_message.reply_text(
            f"⚠️ Akun <b>{F.esc(dst)}</b> tidak ditemukan.", parse_mode="HTML",
        )
        return
    if src_acc["balance"] < amount:
        await update.effective_message.reply_text(
            F.msg_insufficient(src, src_acc["balance"], amount), parse_mode="HTML",
        )
        return

    db.record_transfer(amount, src, dst, note)
    await update.effective_message.reply_text(
        F.msg_transfer(
            amount, src, dst, note,
            src_acc["balance"] - amount,
            dst_acc["balance"] + amount,
        ),
        parse_mode="HTML",
        reply_markup=K.MAIN_MENU,
    )


# ───────────────── Basic Commands ─────────────────

@authorized
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        F.msg_start(), parse_mode="HTML", reply_markup=K.MAIN_MENU,
    )


@authorized
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        F.msg_help(), parse_mode="HTML", reply_markup=K.MAIN_MENU,
    )


@authorized
async def cmd_saldo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _send_saldo(update)


@authorized
async def cmd_tambah_akun(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _exec_tambah_akun(update, ctx.args or [])


@authorized
async def cmd_masuk(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _exec_masuk(update, ctx.args or [])


@authorized
async def cmd_keluar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _exec_keluar(update, ctx.args or [])


@authorized
async def cmd_transfer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _exec_transfer(update, ctx.args or [])


@authorized
async def cmd_riwayat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    limit = 10
    if ctx.args:
        try:
            limit = min(max(int(ctx.args[0]), 1), 25)
        except ValueError:
            pass
    await _send_riwayat(update, limit)


@authorized
async def cmd_laporan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(F.LOCAL_TZ)
    year, month = now.year, now.month
    if ctx.args:
        m = re.match(r"^(\d{4})-(\d{1,2})$", ctx.args[0])
        if m:
            year, month = int(m.group(1)), int(m.group(2))
            if month < 1 or month > 12:
                await update.effective_message.reply_text("⚠️ Bulan harus 01–12.")
                return
        else:
            await update.effective_message.reply_text(
                "⚠️ Format: <code>laporan YYYY-MM</code>\n"
                "Contoh: <code>laporan 2026-10</code>",
                parse_mode="HTML",
            )
            return
    await _send_report(update.effective_message, year, month)


@authorized
async def cmd_hapus_terakhir(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tx = await _prompt_delete_last(update.effective_message)
    if tx:
        ctx.user_data["pending_delete"] = tx


# ───────────────── Interactive Flow: Entry Points ─────────────────

@authorized
async def start_expense_flow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    accounts = db.get_all_accounts()
    if not accounts:
        await update.effective_message.reply_text(
            "ℹ️ Belum ada rekening. Buat dulu via <b>🏦 Kelola Akun</b> atau ketik:\n"
            "<code>tambah_akun bca 5jt</code>",
            parse_mode="HTML",
            reply_markup=K.MAIN_MENU,
        )
        return ConversationHandler.END

    ctx.user_data.pop("flow", None)
    await update.effective_message.reply_text(
        "📤 <b>Catat Pengeluaran</b>\nPilih rekening yang dipakai:",
        parse_mode="HTML",
        reply_markup=K.accounts_keyboard(accounts, "exp_acc"),
    )
    return EXP_ACC


@authorized
async def start_income_flow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    accounts = db.get_all_accounts()
    if not accounts:
        await update.effective_message.reply_text(
            "ℹ️ Belum ada rekening. Buat dulu via <b>🏦 Kelola Akun</b> atau ketik:\n"
            "<code>tambah_akun bca 5jt</code>",
            parse_mode="HTML",
            reply_markup=K.MAIN_MENU,
        )
        return ConversationHandler.END

    ctx.user_data.pop("flow", None)
    await update.effective_message.reply_text(
        "📥 <b>Catat Pemasukan</b>\nPilih rekening tujuan:",
        parse_mode="HTML",
        reply_markup=K.accounts_keyboard(accounts, "inc_acc"),
    )
    return INC_ACC


@authorized
async def start_transfer_flow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
    accounts = db.get_all_accounts()
    if len(accounts) < 2:
        await update.effective_message.reply_text(
            "⚠️ Minimal butuh <b>2 rekening</b> untuk transfer.\n"
            "Tambahkan rekening lewat <b>🏦 Kelola Akun</b>.",
            parse_mode="HTML",
            reply_markup=K.MAIN_MENU,
        )
        return ConversationHandler.END

    ctx.user_data.pop("flow", None)
    await update.effective_message.reply_text(
        "🔄 <b>Transfer Antar Rekening</b>\nPilih <b>Rekening Asal</b>:",
        parse_mode="HTML",
        reply_markup=K.accounts_keyboard(accounts, "trf_src"),
    )
    return TRF_SRC


@authorized
async def start_manage_accounts_flow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🏦 <b>Kelola Akun / Rekening</b>\nPilih aksi yang diinginkan:",
        parse_mode="HTML",
        reply_markup=K.manage_accounts_keyboard(),
    )
    return ACC_MENU


@authorized
async def start_report_flow(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📊 <b>Laporan Keuangan</b>\nPilih periode laporan:",
        parse_mode="HTML",
        reply_markup=K.report_period_keyboard(),
    )
    return RPT_MENU


# ───────────────── Expense Steps ─────────────────

@authorized
async def exp_pick_acc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    acc_name = q.data.split(":", 1)[1]
    acc = db.get_account(acc_name)
    if not acc:
        await q.edit_message_text("⚠️ Akun tidak ditemukan.")
        return ConversationHandler.END

    ctx.user_data["flow"] = {"account": acc_name, "balance": acc["balance"]}
    await q.edit_message_text(
        f"📤 <b>Catat Pengeluaran</b>\n"
        f"🏦 Akun: <b>{F.esc(acc_name)}</b> ({F.fmt(acc['balance'])})\n\n"
        f"Pilih kategori:",
        parse_mode="HTML",
        reply_markup=K.expense_categories_keyboard(),
    )
    return EXP_CAT


@authorized
async def exp_pick_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cat = q.data.split(":", 1)[1]
    flow = ctx.user_data.get("flow", {})
    if cat == "custom":
        await q.edit_message_text(
            "✍️ Ketik nama kategori pengeluaran (contoh: <code>kesehatan</code>):",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return EXP_CUSTOM_CAT

    flow["category"] = cat
    await q.edit_message_text(
        f"📤 <b>Pengeluaran — {F.esc(flow.get('account', ''))} · {F.esc(cat)}</b>\n\n"
        f"Ketik <b>nominal &amp; catatan opsional</b> tanpa <code>/</code>:\n"
        f"Contoh: <code>35k nasi padang</code> atau <code>50000</code>",
        parse_mode="HTML",
        reply_markup=K.cancel_only_keyboard(),
    )
    return EXP_AMT


@authorized
async def exp_custom_cat_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cat = update.message.text.strip().lower()[:40]
    if not cat:
        await update.message.reply_text("⚠️ Kategori tidak boleh kosong. Ketik nama kategori:")
        return EXP_CUSTOM_CAT
    flow = ctx.user_data.get("flow", {})
    flow["category"] = cat
    await update.message.reply_text(
        f"📤 <b>Pengeluaran — {F.esc(flow.get('account', ''))} · {F.esc(cat)}</b>\n\n"
        f"Ketik <b>nominal &amp; catatan opsional</b> tanpa <code>/</code>:\n"
        f"Contoh: <code>35k kopi</code> atau <code>50000</code>",
        parse_mode="HTML",
        reply_markup=K.cancel_only_keyboard(),
    )
    return EXP_AMT


@authorized
async def exp_amt_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    amount, note = _parse_amt_and_note(update.message.text)
    if amount is None or amount <= 0:
        await update.message.reply_text(
            "⚠️ Nominal tidak valid. Ketik contoh: <code>35k nasi padang</code> atau <code>50000</code>",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return EXP_AMT

    flow = ctx.user_data.get("flow", {})
    account = flow.get("account")
    category = flow.get("category", "lainnya")
    acc = db.get_account(account) if account else None
    if not acc:
        await update.message.reply_text("⚠️ Akun tidak ditemukan.", reply_markup=K.MAIN_MENU)
        return ConversationHandler.END

    if acc["balance"] < amount:
        await update.message.reply_text(
            F.msg_insufficient(account, acc["balance"], amount)
            + "\n\nKetik nominal lain atau tekan Batal:",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return EXP_AMT

    db.record_expense(amount, category, account, note)
    ctx.user_data.pop("flow", None)
    await update.message.reply_text(
        F.msg_expense(amount, category, account, note, acc["balance"] - amount),
        parse_mode="HTML",
        reply_markup=K.MAIN_MENU,
    )
    return ConversationHandler.END


# ───────────────── Income Steps ─────────────────

@authorized
async def inc_pick_acc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    acc_name = q.data.split(":", 1)[1]
    acc = db.get_account(acc_name)
    if not acc:
        await q.edit_message_text("⚠️ Akun tidak ditemukan.")
        return ConversationHandler.END

    ctx.user_data["flow"] = {"account": acc_name, "balance": acc["balance"]}
    await q.edit_message_text(
        f"📥 <b>Catat Pemasukan</b>\n"
        f"🏦 Akun: <b>{F.esc(acc_name)}</b> ({F.fmt(acc['balance'])})\n\n"
        f"Pilih kategori:",
        parse_mode="HTML",
        reply_markup=K.income_categories_keyboard(),
    )
    return INC_CAT


@authorized
async def inc_pick_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cat = q.data.split(":", 1)[1]
    flow = ctx.user_data.get("flow", {})
    if cat == "custom":
        await q.edit_message_text(
            "✍️ Ketik nama kategori pemasukan (contoh: <code>dividen</code>):",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return INC_CUSTOM_CAT

    flow["category"] = cat
    await q.edit_message_text(
        f"📥 <b>Pemasukan — {F.esc(flow.get('account', ''))} · {F.esc(cat)}</b>\n\n"
        f"Ketik <b>nominal &amp; catatan opsional</b> tanpa <code>/</code>:\n"
        f"Contoh: <code>3jt gaji bulan ini</code> atau <code>500k</code>",
        parse_mode="HTML",
        reply_markup=K.cancel_only_keyboard(),
    )
    return INC_AMT


@authorized
async def inc_custom_cat_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cat = update.message.text.strip().lower()[:40]
    if not cat:
        await update.message.reply_text("⚠️ Kategori tidak boleh kosong. Ketik nama kategori:")
        return INC_CUSTOM_CAT
    flow = ctx.user_data.get("flow", {})
    flow["category"] = cat
    await update.message.reply_text(
        f"📥 <b>Pemasukan — {F.esc(flow.get('account', ''))} · {F.esc(cat)}</b>\n\n"
        f"Ketik <b>nominal &amp; catatan opsional</b> tanpa <code>/</code>:\n"
        f"Contoh: <code>500k bonus</code> atau <code>1jt</code>",
        parse_mode="HTML",
        reply_markup=K.cancel_only_keyboard(),
    )
    return INC_AMT


@authorized
async def inc_amt_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    amount, note = _parse_amt_and_note(update.message.text)
    if amount is None or amount <= 0:
        await update.message.reply_text(
            "⚠️ Nominal tidak valid. Ketik contoh: <code>3jt gaji</code> atau <code>500000</code>",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return INC_AMT

    flow = ctx.user_data.get("flow", {})
    account = flow.get("account")
    category = flow.get("category", "lainnya")
    acc = db.get_account(account) if account else None
    if not acc:
        await update.message.reply_text("⚠️ Akun tidak ditemukan.", reply_markup=K.MAIN_MENU)
        return ConversationHandler.END

    db.record_income(amount, category, account, note)
    ctx.user_data.pop("flow", None)
    await update.message.reply_text(
        F.msg_income(amount, category, account, note, acc["balance"] + amount),
        parse_mode="HTML",
        reply_markup=K.MAIN_MENU,
    )
    return ConversationHandler.END


# ───────────────── Transfer Steps ─────────────────

@authorized
async def trf_pick_src(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    src = q.data.split(":", 1)[1]
    src_acc = db.get_account(src)
    if not src_acc:
        await q.edit_message_text("⚠️ Akun asal tidak ditemukan.")
        return ConversationHandler.END

    accounts = db.get_all_accounts()
    ctx.user_data["flow"] = {"src": src}
    await q.edit_message_text(
        f"🔄 <b>Transfer Antar Rekening</b>\n"
        f"📤 Dari: <b>{F.esc(src)}</b> ({F.fmt(src_acc['balance'])})\n\n"
        f"Pilih <b>Rekening Tujuan</b>:",
        parse_mode="HTML",
        reply_markup=K.accounts_keyboard(accounts, "trf_dst", exclude_name=src),
    )
    return TRF_DST


@authorized
async def trf_pick_dst(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    dst = q.data.split(":", 1)[1]
    flow = ctx.user_data.get("flow", {})
    flow["dst"] = dst
    src = flow.get("src", "")

    await q.edit_message_text(
        f"🔄 <b>Transfer: {F.esc(src)} → {F.esc(dst)}</b>\n\n"
        f"Ketik <b>nominal &amp; catatan opsional</b> tanpa <code>/</code>:\n"
        f"Contoh: <code>200k topup</code> atau <code>1jt</code>",
        parse_mode="HTML",
        reply_markup=K.cancel_only_keyboard(),
    )
    return TRF_AMT


@authorized
async def trf_amt_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    amount, note = _parse_amt_and_note(update.message.text)
    if amount is None or amount <= 0:
        await update.message.reply_text(
            "⚠️ Nominal tidak valid. Ketik contoh: <code>200k topup</code> atau <code>500000</code>",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return TRF_AMT

    flow = ctx.user_data.get("flow", {})
    src = flow.get("src")
    dst = flow.get("dst")
    src_acc = db.get_account(src) if src else None
    dst_acc = db.get_account(dst) if dst else None
    if not src_acc or not dst_acc:
        await update.message.reply_text("⚠️ Rekening tidak ditemukan.", reply_markup=K.MAIN_MENU)
        return ConversationHandler.END

    if src_acc["balance"] < amount:
        await update.message.reply_text(
            F.msg_insufficient(src, src_acc["balance"], amount)
            + "\n\nKetik nominal lain atau tekan Batal:",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return TRF_AMT

    db.record_transfer(amount, src, dst, note)
    ctx.user_data.pop("flow", None)
    await update.message.reply_text(
        F.msg_transfer(
            amount, src, dst, note,
            src_acc["balance"] - amount,
            dst_acc["balance"] + amount,
        ),
        parse_mode="HTML",
        reply_markup=K.MAIN_MENU,
    )
    return ConversationHandler.END


# ───────────────── Kelola Akun Steps ─────────────────

@authorized
async def acc_menu_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":", 1)[1]

    if action == "add":
        await q.edit_message_text(
            "➕ <b>Tambah Akun Baru</b>\n\n"
            "Ketik <b>nama akun</b> dan <b>saldo awal</b> tanpa <code>/</code>:\n"
            "Contoh: <code>bca 5000000</code> atau <code>gopay 250k</code>",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return ACC_ADD_INPUT

    accounts = db.get_all_accounts()
    if not accounts:
        await q.edit_message_text("ℹ️ Belum ada rekening yang terdaftar.")
        return ConversationHandler.END

    if action == "edit":
        await q.edit_message_text(
            "✏️ <b>Edit Saldo Akun</b>\nPilih rekening yang saldonya ingin diubah:",
            parse_mode="HTML",
            reply_markup=K.accounts_keyboard(accounts, "acc_edit"),
        )
        return ACC_EDIT_PICK

    if action == "del":
        await q.edit_message_text(
            "🗑️ <b>Hapus Akun</b>\nPilih rekening yang akan dihapus:",
            parse_mode="HTML",
            reply_markup=K.accounts_keyboard(accounts, "acc_del"),
        )
        return ACC_DEL_PICK

    return ConversationHandler.END


@authorized
async def acc_add_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.strip().split()
    if len(parts) < 2:
        await update.message.reply_text(
            "⚠️ Format: <code>&lt;nama_akun&gt; &lt;saldo_awal&gt;</code>\n"
            "Contoh: <code>bca 5jt</code>",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return ACC_ADD_INPUT

    name = parts[0].lower()
    amount = F.parse_amount(parts[1])
    if amount is None or amount < 0:
        await update.message.reply_text(
            "⚠️ Saldo awal harus angka positif (atau 0). Coba lagi:",
            reply_markup=K.cancel_only_keyboard(),
        )
        return ACC_ADD_INPUT

    if db.add_account(name, amount):
        await update.message.reply_text(
            F.msg_account_created(name, amount),
            parse_mode="HTML",
            reply_markup=K.MAIN_MENU,
        )
    else:
        await update.message.reply_text(
            F.msg_account_exists(name), parse_mode="HTML", reply_markup=K.MAIN_MENU,
        )
    return ConversationHandler.END


@authorized
async def acc_edit_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.split(":", 1)[1]
    acc = db.get_account(name)
    if not acc:
        await q.edit_message_text("⚠️ Akun tidak ditemukan.")
        return ConversationHandler.END

    ctx.user_data["flow"] = {"edit_acc": name}
    await q.edit_message_text(
        f"✏️ <b>Edit Saldo: {F.esc(name)}</b>\n"
        f"Saldo saat ini: {F.fmt(acc['balance'])}\n\n"
        f"Ketik <b>saldo baru</b> tanpa <code>/</code> (contoh: <code>2.5jt</code>):",
        parse_mode="HTML",
        reply_markup=K.cancel_only_keyboard(),
    )
    return ACC_EDIT_AMT


@authorized
async def acc_edit_amt_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    amount = F.parse_amount(update.message.text.strip())
    if amount is None or amount < 0:
        await update.message.reply_text(
            "⚠️ Saldo harus angka >= 0 (contoh: <code>2.5jt</code>). Coba lagi:",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return ACC_EDIT_AMT

    name = ctx.user_data.get("flow", {}).get("edit_acc")
    if name and db.update_account_balance(name, amount):
        await update.message.reply_text(
            F.msg_account_updated(name, amount),
            parse_mode="HTML",
            reply_markup=K.MAIN_MENU,
        )
    else:
        await update.message.reply_text("⚠️ Akun tidak ditemukan.", reply_markup=K.MAIN_MENU)
    ctx.user_data.pop("flow", None)
    return ConversationHandler.END


@authorized
async def acc_del_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.split(":", 1)[1]
    acc = db.get_account(name)
    if not acc:
        await q.edit_message_text("⚠️ Akun tidak ditemukan.")
        return ConversationHandler.END

    await q.edit_message_text(
        F.msg_confirm_delete_account(name, acc["balance"]),
        parse_mode="HTML",
        reply_markup=K.confirm_delete_account_keyboard(name),
    )
    return ACC_DEL_CONFIRM


@authorized
async def acc_del_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    name = q.data.split(":", 1)[1]
    if db.delete_account(name):
        await q.edit_message_text(F.msg_account_deleted(name), parse_mode="HTML")
    else:
        await q.edit_message_text("⚠️ Akun sudah tidak ada.")
    return ConversationHandler.END


# ───────────────── Laporan Interactive Steps ─────────────────

@authorized
async def report_period_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    choice = q.data.split(":", 1)[1]
    now = datetime.now(F.LOCAL_TZ)

    if choice == "this":
        await _send_report(q.message, now.year, now.month, edit=True)
        return ConversationHandler.END

    if choice == "last":
        y, m = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        await _send_report(q.message, y, m, edit=True)
        return ConversationHandler.END

    if choice == "custom":
        await q.edit_message_text(
            "🗓️ Ketik bulan laporan dengan format <code>YYYY-MM</code>\n"
            "Contoh: <code>2026-10</code>",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return RPT_CUSTOM_MONTH

    return ConversationHandler.END


@authorized
async def report_custom_month_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    m = re.match(r"^(\d{4})-(\d{1,2})$", raw)
    if not m:
        await update.message.reply_text(
            "⚠️ Format salah. Ketik <code>YYYY-MM</code> (contoh: <code>2026-10</code>):",
            parse_mode="HTML",
            reply_markup=K.cancel_only_keyboard(),
        )
        return RPT_CUSTOM_MONTH

    year, month = int(m.group(1)), int(m.group(2))
    if month < 1 or month > 12:
        await update.message.reply_text(
            "⚠️ Bulan harus antara 01 dan 12. Coba lagi:",
            reply_markup=K.cancel_only_keyboard(),
        )
        return RPT_CUSTOM_MONTH

    await _send_report(update.message, year, month)
    return ConversationHandler.END


# ───────────────── Undo / Delete Callbacks ─────────────────

@authorized
async def callback_undo_from_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tx = db.get_last_transaction()
    if not tx:
        await q.message.reply_text("ℹ️ Tidak ada transaksi untuk dibatalkan.")
        return
    ctx.user_data["pending_delete"] = tx
    await q.message.reply_text(
        F.msg_confirm_delete(tx),
        parse_mode="HTML",
        reply_markup=K.confirm_delete_keyboard(),
    )


@authorized
async def callback_delete_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "delete_cancel":
        ctx.user_data.pop("pending_delete", None)
        await q.edit_message_text("❌ Penghapusan dibatalkan.")
        return

    tx = ctx.user_data.pop("pending_delete", None)
    if not tx:
        await q.edit_message_text("⚠️ Tidak ada transaksi pending untuk dihapus.")
        return

    current_last = db.get_last_transaction()
    if not current_last or current_last["id"] != tx["id"]:
        await q.edit_message_text(
            "⚠️ Transaksi terakhir sudah berubah. Coba <code>hapus_terakhir</code> lagi.",
            parse_mode="HTML",
        )
        return

    db.delete_and_rollback(tx)
    await q.edit_message_text(F.msg_deleted(tx), parse_mode="HTML")


# ───────────────── Cancel & Fallback ─────────────────

@authorized
async def cancel_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data.pop("flow", None)
    await q.edit_message_text("❌ Dibatalkan.")
    return ConversationHandler.END


@authorized
async def cancel_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("flow", None)
    await update.effective_message.reply_text("❌ Dibatalkan.", reply_markup=K.MAIN_MENU)
    return ConversationHandler.END


@authorized
async def exit_to_non_conv_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Keluar dari alur aktif jika user menekan tombol Saldo / Riwayat / Bantuan."""
    ctx.user_data.pop("flow", None)
    text = update.message.text.strip()
    if text == "💳 Saldo":
        await _send_saldo(update)
    elif text == "📜 Riwayat":
        await _send_riwayat(update)
    elif text == "📖 Bantuan":
        await cmd_help(update, ctx)
    return ConversationHandler.END


# ───────────────── Plain Text Handler (Tanpa '/') ─────────────────

@authorized
async def handle_plain_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        return

    # 1. Tombol menu utama non-conversation
    if text == "💳 Saldo":
        await _send_saldo(update)
        return
    if text == "📜 Riwayat":
        await _send_riwayat(update)
        return
    if text == "📖 Bantuan":
        await cmd_help(update, ctx)
        return

    # 2. Perintah teks polos tanpa '/'
    tokens = text.split()
    cmd = tokens[0].lower()
    args = tokens[1:]

    if cmd in ("start", "halo", "hai"):
        await cmd_start(update, ctx)
    elif cmd in ("help", "bantuan", "menu"):
        await cmd_help(update, ctx)
    elif cmd == "saldo":
        await _send_saldo(update)
    elif cmd == "riwayat":
        limit = 10
        if args:
            try:
                limit = min(max(int(args[0]), 1), 25)
            except ValueError:
                pass
        await _send_riwayat(update, limit)
    elif cmd == "laporan":
        ctx.args = args
        await cmd_laporan(update, ctx)
    elif cmd == "hapus_terakhir" or text.lower() == "hapus terakhir":
        await cmd_hapus_terakhir(update, ctx)
    elif cmd == "tambah_akun":
        await _exec_tambah_akun(update, args)
    elif len(tokens) >= 2 and tokens[0].lower() == "tambah" and tokens[1].lower() == "akun":
        await _exec_tambah_akun(update, tokens[2:])
    elif cmd == "masuk":
        await _exec_masuk(update, args)
    elif cmd == "keluar":
        await _exec_keluar(update, args)
    elif cmd == "transfer":
        await _exec_transfer(update, args)
    else:
        await update.message.reply_text(
            "🤔 Perintah tidak dikenali.\n"
            "Gunakan <b>tombol menu</b> di bawah atau ketik <code>bantuan</code>.",
            parse_mode="HTML",
            reply_markup=K.MAIN_MENU,
        )


# ───────────────── ConversationHandler Builder ─────────────────

def build_conversation_handler() -> ConversationHandler:
    non_cmd_text = filters.TEXT & ~filters.COMMAND
    cancel_words = filters.Regex(r"(?i)^(/batal|/cancel|batal)$")
    non_conv_buttons = filters.Regex(r"^(💳 Saldo|📜 Riwayat|📖 Bantuan)$")
    plain_text_input = non_cmd_text & ~cancel_words & ~non_conv_buttons

    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^➖ Keluar$"), start_expense_flow),
            MessageHandler(filters.Regex(r"^➕ Masuk$"), start_income_flow),
            MessageHandler(filters.Regex(r"^🔄 Transfer$"), start_transfer_flow),
            MessageHandler(filters.Regex(r"^🏦 Kelola Akun$"), start_manage_accounts_flow),
            MessageHandler(filters.Regex(r"^📊 Laporan$"), start_report_flow),
            CallbackQueryHandler(start_expense_flow, pattern=r"^flow:keluar$"),
            CallbackQueryHandler(start_income_flow, pattern=r"^flow:masuk$"),
            CallbackQueryHandler(start_transfer_flow, pattern=r"^flow:transfer$"),
        ],
        states={
            EXP_ACC: [CallbackQueryHandler(exp_pick_acc, pattern=r"^exp_acc:")],
            EXP_CAT: [CallbackQueryHandler(exp_pick_cat, pattern=r"^cat:")],
            EXP_CUSTOM_CAT: [MessageHandler(plain_text_input, exp_custom_cat_input)],
            EXP_AMT: [MessageHandler(plain_text_input, exp_amt_input)],

            INC_ACC: [CallbackQueryHandler(inc_pick_acc, pattern=r"^inc_acc:")],
            INC_CAT: [CallbackQueryHandler(inc_pick_cat, pattern=r"^cat:")],
            INC_CUSTOM_CAT: [MessageHandler(plain_text_input, inc_custom_cat_input)],
            INC_AMT: [MessageHandler(plain_text_input, inc_amt_input)],

            TRF_SRC: [CallbackQueryHandler(trf_pick_src, pattern=r"^trf_src:")],
            TRF_DST: [CallbackQueryHandler(trf_pick_dst, pattern=r"^trf_dst:")],
            TRF_AMT: [MessageHandler(plain_text_input, trf_amt_input)],

            ACC_MENU: [CallbackQueryHandler(acc_menu_pick, pattern=r"^acc_act:")],
            ACC_ADD_INPUT: [MessageHandler(plain_text_input, acc_add_input)],
            ACC_EDIT_PICK: [CallbackQueryHandler(acc_edit_pick, pattern=r"^acc_edit:")],
            ACC_EDIT_AMT: [MessageHandler(plain_text_input, acc_edit_amt_input)],
            ACC_DEL_PICK: [CallbackQueryHandler(acc_del_pick, pattern=r"^acc_del:")],
            ACC_DEL_CONFIRM: [CallbackQueryHandler(acc_del_confirm, pattern=r"^acc_del_ok:")],

            RPT_MENU: [CallbackQueryHandler(report_period_pick, pattern=r"^rpt:")],
            RPT_CUSTOM_MONTH: [MessageHandler(plain_text_input, report_custom_month_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_inline, pattern=r"^nav:cancel$"),
            MessageHandler(cancel_words, cancel_text),
            MessageHandler(non_conv_buttons, exit_to_non_conv_menu),
        ],
        allow_reentry=True,
        per_message=False,
    )
