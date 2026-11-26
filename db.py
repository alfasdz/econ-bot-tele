"""
db.py — PostgreSQL connection pool, auto-init tabel, dan helper query.

Setiap mutasi saldo menggunakan transaksi atomik (COMMIT / ROLLBACK).
"""

from contextlib import contextmanager

from psycopg2 import pool

from config import DATABASE_URL, logger

# ───────────────── Connection Pool ─────────────────

_pool: pool.SimpleConnectionPool | None = None


def _get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = pool.SimpleConnectionPool(1, 10, DATABASE_URL)
        logger.info("Connection pool dibuat (1–10 koneksi)")
    return _pool


@contextmanager
def get_conn():
    """Context manager: ambil koneksi dari pool, kembalikan setelah selesai."""
    p = _get_pool()
    conn = p.getconn()
    try:
        yield conn
    finally:
        p.putconn(conn)


@contextmanager
def atomic():
    """Context manager untuk transaksi atomik. Auto-COMMIT / ROLLBACK."""
    with get_conn() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


# ───────────────── Schema Init ─────────────────

def init_db():
    """Buat tabel jika belum ada (idempotent)."""
    with atomic() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id         SERIAL PRIMARY KEY,
                    name       VARCHAR(50) UNIQUE NOT NULL,
                    balance    BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id             SERIAL PRIMARY KEY,
                    type           VARCHAR(10) NOT NULL
                                       CHECK (type IN ('income','expense','transfer')),
                    amount         BIGINT NOT NULL,
                    category       VARCHAR(100),
                    account_name   VARCHAR(50) NOT NULL,
                    target_account VARCHAR(50),
                    note           TEXT,
                    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
    logger.info("Tabel accounts & transactions siap ✔")


# ───────────────── Account Helpers ─────────────────

def add_account(name: str, balance: int) -> bool:
    """Tambah akun baru. Return True jika berhasil."""
    with atomic() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO accounts (name, balance) VALUES (%s, %s) "
                "ON CONFLICT (name) DO NOTHING RETURNING id;",
                (name, balance),
            )
            return cur.fetchone() is not None


def update_account_balance(name: str, new_balance: int) -> bool:
    """Perbarui saldo akun secara langsung. Return True jika akun ditemukan."""
    with atomic() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = %s WHERE name = %s RETURNING id;",
                (new_balance, name),
            )
            return cur.fetchone() is not None


def delete_account(name: str) -> bool:
    """Hapus akun dari tabel accounts. Return True jika akun ditemukan & terhapus."""
    with atomic() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM accounts WHERE name = %s RETURNING id;",
                (name,),
            )
            return cur.fetchone() is not None


def get_account(name: str) -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, balance FROM accounts WHERE name = %s;", (name,))
            row = cur.fetchone()
            return {"name": row[0], "balance": row[1]} if row else None


def get_all_accounts() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, balance FROM accounts ORDER BY name;")
            return [{"name": r[0], "balance": r[1]} for r in cur.fetchall()]


# ───────────────── Atomic Mutations ─────────────────

def record_income(amount: int, category: str, account: str, note: str | None):
    """Tambah saldo + catat transaksi income — atomik."""
    with atomic() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance + %s WHERE name = %s;",
                (amount, account),
            )
            cur.execute(
                "INSERT INTO transactions (type,amount,category,account_name,note) "
                "VALUES ('income',%s,%s,%s,%s);",
                (amount, category, account, note),
            )


def record_expense(amount: int, category: str, account: str, note: str | None):
    """Kurangi saldo + catat transaksi expense — atomik."""
    with atomic() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance - %s WHERE name = %s;",
                (amount, account),
            )
            cur.execute(
                "INSERT INTO transactions (type,amount,category,account_name,note) "
                "VALUES ('expense',%s,%s,%s,%s);",
                (amount, category, account, note),
            )


def record_transfer(amount: int, src: str, dst: str, note: str | None):
    """Transfer antar akun — atomik (satu transaksi DB)."""
    with atomic() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance - %s WHERE name = %s;",
                (amount, src),
            )
            cur.execute(
                "UPDATE accounts SET balance = balance + %s WHERE name = %s;",
                (amount, dst),
            )
            cur.execute(
                "INSERT INTO transactions (type,amount,category,account_name,target_account,note) "
                "VALUES ('transfer',%s,'transfer',%s,%s,%s);",
                (amount, src, dst, note),
            )


# ───────────────── Transaction Queries ─────────────────

def get_last_transaction() -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,type,amount,category,account_name,target_account,note,created_at "
                "FROM transactions ORDER BY id DESC LIMIT 1;"
            )
            row = cur.fetchone()
            if not row:
                return None
            return dict(zip(
                ("id", "type", "amount", "category", "account_name",
                 "target_account", "note", "created_at"),
                row,
            ))


def delete_and_rollback(tx: dict):
    """Hapus transaksi terakhir dan kembalikan saldo — atomik."""
    with atomic() as conn:
        with conn.cursor() as cur:
            if tx["type"] == "income":
                cur.execute(
                    "UPDATE accounts SET balance = balance - %s WHERE name = %s;",
                    (tx["amount"], tx["account_name"]),
                )
            elif tx["type"] == "expense":
                cur.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE name = %s;",
                    (tx["amount"], tx["account_name"]),
                )
            elif tx["type"] == "transfer":
                cur.execute(
                    "UPDATE accounts SET balance = balance + %s WHERE name = %s;",
                    (tx["amount"], tx["account_name"]),
                )
                cur.execute(
                    "UPDATE accounts SET balance = balance - %s WHERE name = %s;",
                    (tx["amount"], tx["target_account"]),
                )
            cur.execute("DELETE FROM transactions WHERE id = %s;", (tx["id"],))


def get_recent_transactions(limit: int = 10) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,type,amount,category,account_name,target_account,note,created_at "
                "FROM transactions ORDER BY id DESC LIMIT %s;",
                (limit,),
            )
            cols = ("id", "type", "amount", "category", "account_name",
                    "target_account", "note", "created_at")
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_monthly_report(year: int, month: int) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            where = ("EXTRACT(YEAR FROM created_at) = %s "
                     "AND EXTRACT(MONTH FROM created_at) = %s")

            cur.execute(
                f"SELECT COALESCE(SUM(amount),0) FROM transactions "
                f"WHERE type='income' AND {where};", (year, month),
            )
            total_income = cur.fetchone()[0]

            cur.execute(
                f"SELECT COALESCE(SUM(amount),0) FROM transactions "
                f"WHERE type='expense' AND {where};", (year, month),
            )
            total_expense = cur.fetchone()[0]

            cur.execute(
                f"SELECT COALESCE(SUM(amount),0) FROM transactions "
                f"WHERE type='transfer' AND {where};", (year, month),
            )
            total_transfer = cur.fetchone()[0]

            cur.execute(
                f"SELECT category, SUM(amount) FROM transactions "
                f"WHERE type='income' AND {where} "
                f"GROUP BY category ORDER BY SUM(amount) DESC;",
                (year, month),
            )
            income_cats = cur.fetchall()

            cur.execute(
                f"SELECT category, SUM(amount) FROM transactions "
                f"WHERE type='expense' AND {where} "
                f"GROUP BY category ORDER BY SUM(amount) DESC;",
                (year, month),
            )
            expense_cats = cur.fetchall()

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "total_transfer": total_transfer,
        "income_categories": income_cats,
        "expense_categories": expense_cats,
    }
