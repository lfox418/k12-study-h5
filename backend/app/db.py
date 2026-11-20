"""SQLite 3 WAL 高并发连接管理与初始化模块"""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from . import config


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """获取配置好 WAL / NORMAL / busy_timeout=5000 的 SQLite 连接"""
    target = db_path or config.DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # 关键并发隔离参数：确保每6小时同步脚本写入与前端提交零锁库冲突
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def db_session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """事务上下文管理器：自动提交或异常回滚"""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path: Path | None = None, sql_path: Path | None = None) -> None:
    """执行初始化 SQL（幂等：CREATE TABLE IF NOT EXISTS & INSERT OR IGNORE）"""
    target_db = db_path or config.DB_PATH
    target_sql = sql_path or config.INIT_SQL_PATH
    if not target_sql.exists():
        raise FileNotFoundError(f"初始化 SQL 文件不存在: {target_sql}")

    sql_script = target_sql.read_text(encoding="utf-8")
    conn = get_connection(target_db)
    try:
        conn.executescript(sql_script)
        # 重新确认 WAL 参数生效
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.commit()
    finally:
        conn.close()
