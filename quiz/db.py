import sqlite3
import threading
from datetime import datetime, timezone

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS teachers(
    id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exams(
    id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL REFERENCES teachers(id), title TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL, source_file TEXT, import_notes TEXT NOT NULL DEFAULT '{}',
    num_questions INTEGER NOT NULL, duration_min INTEGER NOT NULL,
    shuffle_options INTEGER NOT NULL DEFAULT 1, multi_mode TEXT NOT NULL DEFAULT 'all',   -- all | partial
    is_open INTEGER NOT NULL DEFAULT 0, start_at TEXT, end_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS questions(
    id INTEGER PRIMARY KEY, exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    number INTEGER NOT NULL, text TEXT NOT NULL, multi INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS options(
    id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    label TEXT NOT NULL, text TEXT NOT NULL, is_correct INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(
    id INTEGER PRIMARY KEY, exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    student_code TEXT NOT NULL, student_name TEXT NOT NULL, class_name TEXT,
    token TEXT NOT NULL, allow_resume INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL, deadline TEXT NOT NULL, submitted_at TEXT,
    status TEXT NOT NULL DEFAULT 'doing',                                                 -- doing | submitted | timeout
    score REAL, correct INTEGER, total INTEGER NOT NULL, ip TEXT, UNIQUE(exam_id, student_code));
CREATE TABLE IF NOT EXISTS attempt_items(
    attempt_id INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE, position INTEGER NOT NULL,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    option_ids TEXT NOT NULL,                       -- thứ tự phương án hiển thị cho sinh viên này (JSON)
    selected TEXT NOT NULL DEFAULT '[]', points REAL, PRIMARY KEY(attempt_id, position));
CREATE INDEX IF NOT EXISTS idx_questions_exam ON questions(exam_id);
CREATE INDEX IF NOT EXISTS idx_options_question ON options(question_id);
CREATE INDEX IF NOT EXISTS idx_items_question ON attempt_items(question_id);
"""


_write_lock = threading.RLock()


class Connection(sqlite3.Connection):
    """`with con:` là một transaction ghi. Các luồng trong server xếp hàng lần lượt bằng khóa này, thay vì để SQLite
    tự chờ khóa kiểu thử lại (busy timeout): khi 50 sinh viên cùng ghi, cách đó làm vài người phải chờ tới vài giây."""

    def __enter__(self):
        _write_lock.acquire()
        try:
            return super().__enter__()
        except BaseException:
            _write_lock.release()
            raise

    def __exit__(self, *exc):
        try:
            return super().__exit__(*exc)
        finally:
            _write_lock.release()


def connect(path):
    con = sqlite3.connect(path, timeout=15, factory=Connection)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def init_db(path):
    con = connect(path)
    con.execute('PRAGMA journal_mode = WAL')     # nhiều sinh viên đọc/ghi cùng lúc không khóa nhau
    con.executescript(SCHEMA)
    con.close()


def get_db():
    if 'db' not in g: g.db = connect(current_app.config['DATABASE'])
    return g.db


def close_db(_exc=None):
    con = g.pop('db', None)
    if con is not None: con.close()


def now_utc():
    return datetime.now(timezone.utc)


def to_iso(dt):
    """Lưu thời gian dạng ISO theo UTC, độ dài cố định nên so sánh chuỗi được."""
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds')


def now_iso():
    return to_iso(now_utc())


def from_iso(s):
    return datetime.fromisoformat(s) if s else None
