"""
formatters.py — Format angka rupiah, parser nominal fleksibel, dan
                template pesan Telegram (HTML parse mode).
"""

import html
from datetime import datetime, timedelta, timezone

from config import TZ_OFFSET_HOURS

LOCAL_TZ = timezone(timedelta(hours=TZ_OFFSET_HOURS))


# ───────────────── HTML Escaping ─────────────────

def esc(text: str | None) -> str:
    """Escape karakter HTML agar aman untuk parse_mode='HTML'."""
    if text is None:
        return ""
    return html.escape(str(text))


# ───────────────── Number Formatting ─────────────────

def fmt(n: int) -> str:
    """Format angka → 'Rp 5.000.000' atau '-Rp 50.000'."""
    if n < 0:
        return f"-Rp {abs(n):,.0f}".replace(",", ".")
    return f"Rp {n:,.0f}".replace(",", ".")


def parse_amount(raw: str) -> int | None:
    """
    Parser nominal fleksibel:
      '50000'   → 50000
      '50.000'  → 50000
      '50k'     → 50000
      '50rb'    → 50000
      '2.5jt'   → 2500000
      '2,5jt'   → 2500000
      '1m'      → 1000000
    """
    s = raw.strip().lower().replace(",", ".")
    if not s:
        return None

    multipliers = {"jt": 1_000_000, "rb": 1_000, "k": 1_000, "m": 1_000_000}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            num_part = s[: -len(suffix)].strip()
            if not num_part:
                return None
            try:
                return int(round(float(num_part) * mult))
            except ValueError:
                return None

    s = s.replace(".", "")
    try:
        return int(s)
    except ValueError:
        return None


# ───────────────── Datetime ─────────────────

def fmt_datetime(dt: datetime) -> str:
    """Format datetime ke string lokal: '26 Nov 2026, 16:30 WIB'."""
    local = dt.astimezone(LOCAL_TZ)
    bulan = [
        "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
    ]
    tz_label = "WIB" if TZ_OFFSET_HOURS == 7 else f"UTC+{TZ_OFFSET_HOURS}"
    return f"{local.day} {bulan[local.month]} {local.year}, {local:%H:%M} {tz_label}"


# ───────────────── Message Templates ─────────────────

ICON = {
    "income":   "📥",
    "expense":  "📤",
    "transfer": "🔀",
}


def msg_start() -> str:
    return (
        "💰 <b>Bot Keuangan Pribadi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Halo! Catat pemasukan, pengeluaran, dan transfer\n"
        "multi-rekening dengan mudah.\n\n"
        "✨ <b>Cara Pakai Cepat:</b>\n"
        "  • Gunakan <b>tombol menu</b> di bawah 👇\n"
        "  • Atau ketik langsung tanpa <code>/</code>, misal:\n"
        "    <code>keluar 35k makan gopay nasi padang</code>\n\n"
        "Tekan <b>📖 Bantuan</b> atau ketik <code>bantuan</code> untuk panduan lengkap."
    )


def msg_help() -> str:
    return (
        "📖 <b>Panduan Penggunaan</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 <b>Utama — Tombol Menu Bawah</b>\n"
        "  • <b>➖ Keluar</b> / <b>➕ Masuk</b> / <b>🔄 Transfer</b>\n"
        "  • <b>💳 Saldo</b> · <b>📊 Laporan</b> · <b>📜 Riwayat</b>\n"
        "  • <b>🏦 Kelola Akun</b> (tambah, edit saldo, hapus)\n\n"
        "⌨️ <b>Ketik Polos (Tanpa Tanda /)</b>\n"
        "  • <code>keluar 35k makan gopay nasi padang</code>\n"
        "  • <code>masuk 3jt gaji bca bonus</code>\n"
        "  • <code>transfer 200k bca gopay topup</code>\n"
        "  • <code>tambah_akun bca 5jt</code>\n"
        "  • <code>saldo</code> · <code>laporan</code> · <code>laporan 2026-10</code>\n"
        "  • <code>riwayat</code> · <code>riwayat 20</code> · <code>hapus_terakhir</code>\n\n"
        "💡 <i>Nominal fleksibel: 50000, 50.000, 50k, 2.5jt, 1m</i>\n"
        "<i>(Perintah dengan tanda / juga tetap didukung)</i>"
    )


def msg_account_created(name: str, balance: int) -> str:
    return (
        f"✅ <b>Akun Dibuat</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🏦  Nama   :  <b>{esc(name)}</b>\n"
        f"  💵  Saldo  :  {fmt(balance)}"
    )


def msg_account_updated(name: str, new_balance: int) -> str:
    return (
        f"✅ <b>Saldo Akun Diperbarui</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🏦  Akun         :  <b>{esc(name)}</b>\n"
        f"  💰  Saldo Baru   :  {fmt(new_balance)}"
    )


def msg_confirm_delete_account(name: str, balance: int) -> str:
    return (
        f"🗑️ <b>Hapus Akun?</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🏦  Akun   :  <b>{esc(name)}</b>\n"
        f"  💰  Saldo  :  {fmt(balance)}\n\n"
        f"⚠️ <i>Akun akan dihapus permanen dari daftar rekening.</i>"
    )


def msg_account_deleted(name: str) -> str:
    return f"✅ Akun <b>{esc(name)}</b> berhasil dihapus."


def msg_account_exists(name: str) -> str:
    return f"⚠️ Akun <b>{esc(name)}</b> sudah ada."


def msg_balance(accounts: list[dict]) -> str:
    lines = ["💳 <b>Saldo Rekening</b>", "━━━━━━━━━━━━━━━━━━━━━"]
    total = 0
    for acc in accounts:
        lines.append(f"  🏦 <b>{esc(acc['name'])}</b>  ·  {fmt(acc['balance'])}")
        total += acc["balance"]
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  📊 <b>Total Aset</b>  ·  <b>{fmt(total)}</b>")
    return "\n".join(lines)


def msg_income(amount: int, category: str, account: str,
               note: str | None, new_balance: int) -> str:
    return (
        f"✅ <b>Pemasukan Dicatat</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📥  Nominal   :  <b>{fmt(amount)}</b>\n"
        f"  🏷  Kategori  :  {esc(category)}\n"
        f"  🏦  Akun      :  {esc(account)}\n"
        f"  📝  Catatan   :  {esc(note) if note else '-'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  💰  Saldo <b>{esc(account)}</b>  :  {fmt(new_balance)}"
    )


def msg_expense(amount: int, category: str, account: str,
                note: str | None, new_balance: int) -> str:
    return (
        f"✅ <b>Pengeluaran Dicatat</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  📤  Nominal   :  <b>{fmt(amount)}</b>\n"
        f"  🏷  Kategori  :  {esc(category)}\n"
        f"  🏦  Akun      :  {esc(account)}\n"
        f"  📝  Catatan   :  {esc(note) if note else '-'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  💰  Sisa Saldo <b>{esc(account)}</b>  :  {fmt(new_balance)}"
    )


def msg_transfer(amount: int, src: str, dst: str, note: str | None,
                 src_balance: int, dst_balance: int) -> str:
    return (
        f"✅ <b>Transfer Berhasil</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  🔀  Nominal   :  <b>{fmt(amount)}</b>\n"
        f"  📤  Dari      :  {esc(src)}\n"
        f"  📥  Ke        :  {esc(dst)}\n"
        f"  📝  Catatan   :  {esc(note) if note else '-'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  💰  Saldo <b>{esc(src)}</b>  :  {fmt(src_balance)}\n"
        f"  💰  Saldo <b>{esc(dst)}</b>  :  {fmt(dst_balance)}"
    )


def msg_insufficient(account: str, balance: int, needed: int) -> str:
    return (
        f"⚠️ <b>Saldo Tidak Cukup</b>\n\n"
        f"  🏦  Akun     :  {esc(account)}\n"
        f"  💰  Saldo    :  {fmt(balance)}\n"
        f"  💸  Butuh    :  {fmt(needed)}\n"
        f"  📉  Kurang   :  {fmt(needed - balance)}"
    )


def msg_confirm_delete(tx: dict) -> str:
    icon = ICON.get(tx["type"], "📋")
    tipe_label = {"income": "Pemasukan", "expense": "Pengeluaran", "transfer": "Transfer"}
    lines = [
        "🗑 <b>Hapus Transaksi Terakhir?</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"  {icon}  Tipe      :  {tipe_label.get(tx['type'], tx['type'])}",
        f"  💵  Nominal   :  <b>{fmt(tx['amount'])}</b>",
        f"  🏦  Akun      :  {esc(tx['account_name'])}",
    ]
    if tx["type"] == "transfer":
        lines.append(f"  📥  Tujuan    :  {esc(tx['target_account'])}")
    if tx["category"] and tx["type"] != "transfer":
        lines.append(f"  🏷  Kategori  :  {esc(tx['category'])}")
    if tx["note"]:
        lines.append(f"  📝  Catatan   :  {esc(tx['note'])}")
    lines.append(f"  🕐  Waktu     :  {fmt_datetime(tx['created_at'])}")
    lines.append("")
    lines.append("⚠️ <i>Saldo akan dikembalikan (rollback).</i>")
    return "\n".join(lines)


def msg_deleted(tx: dict) -> str:
    icon = ICON.get(tx["type"], "📋")
    return (
        f"✅ <b>Transaksi Dihapus &amp; Saldo Dikembalikan</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"  {icon}  {fmt(tx['amount'])} — {esc(tx['account_name'])}"
    )


def msg_history(txs: list[dict]) -> str:
    if not txs:
        return "📜 Belum ada riwayat transaksi."
    lines = [f"📜 <b>Riwayat {len(txs)} Transaksi Terakhir</b>", "━━━━━━━━━━━━━━━━━━━━━"]
    for i, tx in enumerate(txs, 1):
        icon = ICON.get(tx["type"], "📋")
        sign = "+" if tx["type"] == "income" else "-" if tx["type"] == "expense" else "⇄"
        cat = f" · {esc(tx['category'])}" if tx["category"] and tx["type"] != "transfer" else ""
        target = f" → {esc(tx['target_account'])}" if tx["type"] == "transfer" else ""
        note_part = f"\n        📝 {esc(tx['note'])}" if tx["note"] else ""
        time_str = fmt_datetime(tx["created_at"])
        lines.append(
            f"{icon} <b>{sign}{fmt(tx['amount'])}</b>{cat}\n"
            f"        🏦 {esc(tx['account_name'])}{target}\n"
            f"        🕐 {time_str}{note_part}"
        )
        if i < len(txs):
            lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
    return "\n".join(lines)


def msg_report(year: int, month: int, data: dict) -> str:
    bulan_full = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    title = f"{bulan_full[month]} {year}"
    selisih = data["total_income"] - data["total_expense"]
    sel_label = "Surplus" if selisih >= 0 else "Defisit"
    sel_icon = "🟢" if selisih >= 0 else "🔴"

    lines = [
        f"📊 <b>Laporan Keuangan — {title}</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"  📈  Pemasukan    :  {fmt(data['total_income'])}",
        f"  📉  Pengeluaran  :  {fmt(data['total_expense'])}",
        f"  {sel_icon}  {sel_label:12s}  :  {fmt(abs(selisih))}",
        f"  🔀  Transfer     :  {fmt(data['total_transfer'])}",
    ]

    if data["income_categories"]:
        lines.append("")
        lines.append("📈 <b>Pemasukan per Kategori</b>")
        lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
        ti = data["total_income"] or 1
        for cat, total in data["income_categories"]:
            pct = total / ti * 100
            lines.append(f"  • {esc(cat)}  —  {fmt(total)}  ({pct:.0f}%)")

    if data["expense_categories"]:
        lines.append("")
        lines.append("📉 <b>Pengeluaran per Kategori</b>")
        lines.append("┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
        te = data["total_expense"] or 1
        for cat, total in data["expense_categories"]:
            pct = total / te * 100
            lines.append(f"  • {esc(cat)}  —  {fmt(total)}  ({pct:.0f}%)")

    if not data["income_categories"] and not data["expense_categories"]:
        lines.append("")
        lines.append("ℹ️ <i>Belum ada transaksi bulan ini.</i>")

    return "\n".join(lines)
