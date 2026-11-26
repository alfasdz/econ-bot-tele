"""
keyboards.py — ReplyKeyboardMarkup (menu utama) & InlineKeyboardMarkup.
"""

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

# ───────────────── Reply Keyboard (Menu Utama) ─────────────────

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["💳 Saldo", "📊 Laporan"],
        ["➖ Keluar", "➕ Masuk"],
        ["🔄 Transfer", "🏦 Kelola Akun"],
        ["📜 Riwayat", "📖 Bantuan"],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Pilih menu atau ketik tanpa / …",
)


# ───────────────── Helper Grid ─────────────────

def _chunk(buttons: list[InlineKeyboardButton], size: int = 2) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + size] for i in range(0, len(buttons), size)]


# ───────────────── Saldo Shortcuts ─────────────────

def saldo_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖ Keluar", callback_data="flow:keluar"),
            InlineKeyboardButton("➕ Masuk", callback_data="flow:masuk"),
            InlineKeyboardButton("🔄 Transfer", callback_data="flow:transfer"),
        ]
    ])


# ───────────────── Account Pickers ─────────────────

def accounts_keyboard(
    accounts: list[dict],
    prefix: str,
    exclude_name: str | None = None,
) -> InlineKeyboardMarkup:
    btns = [
        InlineKeyboardButton(f"🏦 {acc['name']}", callback_data=f"{prefix}:{acc['name']}")
        for acc in accounts
        if acc["name"] != exclude_name
    ]
    rows = _chunk(btns, 2)
    rows.append([InlineKeyboardButton("❌ Batal", callback_data="nav:cancel")])
    return InlineKeyboardMarkup(rows)


# ───────────────── Category Pickers ─────────────────

EXPENSE_CATEGORIES = [
    ("🍔 Makan", "makan"),
    ("🚗 Transport", "transport"),
    ("🧾 Tagihan", "tagihan"),
    ("🛒 Belanja", "belanja"),
    ("🎮 Hiburan", "hiburan"),
    ("✍️ Kategori Lain", "custom"),
]

INCOME_CATEGORIES = [
    ("💼 Gaji", "gaji"),
    ("💻 Freelance", "freelance"),
    ("🎁 Bonus", "bonus"),
    ("📈 Investasi", "investasi"),
    ("✍️ Kategori Lain", "custom"),
]


def expense_categories_keyboard() -> InlineKeyboardMarkup:
    btns = [
        InlineKeyboardButton(label, callback_data=f"cat:{val}")
        for label, val in EXPENSE_CATEGORIES
    ]
    rows = _chunk(btns, 2)
    rows.append([InlineKeyboardButton("❌ Batal", callback_data="nav:cancel")])
    return InlineKeyboardMarkup(rows)


def income_categories_keyboard() -> InlineKeyboardMarkup:
    btns = [
        InlineKeyboardButton(label, callback_data=f"cat:{val}")
        for label, val in INCOME_CATEGORIES
    ]
    rows = _chunk(btns, 2)
    rows.append([InlineKeyboardButton("❌ Batal", callback_data="nav:cancel")])
    return InlineKeyboardMarkup(rows)


# ───────────────── Kelola Akun ─────────────────

def manage_accounts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Tambah Akun Baru", callback_data="acc_act:add")],
        [
            InlineKeyboardButton("✏️ Edit Saldo Akun", callback_data="acc_act:edit"),
            InlineKeyboardButton("🗑️ Hapus Akun", callback_data="acc_act:del"),
        ],
        [InlineKeyboardButton("❌ Batal", callback_data="nav:cancel")],
    ])


def confirm_delete_account_keyboard(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑️ Ya, Hapus Akun", callback_data=f"acc_del_ok:{name}"),
            InlineKeyboardButton("❌ Batal", callback_data="nav:cancel"),
        ]
    ])


# ───────────────── Laporan ─────────────────

def report_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Bulan Ini", callback_data="rpt:this"),
            InlineKeyboardButton("📆 Bulan Lalu", callback_data="rpt:last"),
        ],
        [InlineKeyboardButton("🗓️ Pilih Bulan (YYYY-MM)", callback_data="rpt:custom")],
        [InlineKeyboardButton("❌ Batal", callback_data="nav:cancel")],
    ])


# ───────────────── Riwayat & Undo ─────────────────

def history_actions_keyboard(has_tx: bool) -> InlineKeyboardMarkup | None:
    if not has_tx:
        return None
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ Undo Transaksi Terakhir", callback_data="hist:undo")]
    ])


def confirm_delete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ya, Hapus & Rollback", callback_data="delete_confirm"),
            InlineKeyboardButton("❌ Batal", callback_data="delete_cancel"),
        ]
    ])


# ───────────────── Generic Cancel ─────────────────

def cancel_only_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Batal", callback_data="nav:cancel")]
    ])
