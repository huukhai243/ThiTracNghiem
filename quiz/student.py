"""Sinh viên: nhập mã phòng thi + họ tên + MSSV, làm bài trong thời gian quy định rồi nộp."""
import json
import re
import secrets
import sqlite3
from datetime import timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from .db import from_iso, get_db, now_utc, to_iso
from .grading import GRACE_SECONDS, finish, pick_items
from .parser import LETTERS

bp = Blueprint('student', __name__)
STUDENT_CODE_RE = re.compile(r'^[A-Z0-9._-]{3,20}$')


def window_error(exam, now):
    """Lý do chưa vào thi được (None = vào được)."""
    if exam is None or not exam['is_open']: return 'Mã phòng thi không đúng hoặc phòng thi chưa mở.'
    if exam['start_at'] and now < from_iso(exam['start_at']):
        return 'Phòng thi mở lúc ' + from_iso(exam['start_at']).astimezone().strftime('%H:%M %d/%m/%Y') + '.'
    if exam['end_at'] and now >= from_iso(exam['end_at']): return 'Phòng thi đã đóng.'
    return None


def _remember(attempt_id, token):
    session.permanent = True        # đóng trình duyệt rồi mở lại vẫn vào tiếp được
    session['attempt'] = {'id': attempt_id, 'token': token}


def current_attempt():
    """Lượt thi gắn với trình duyệt này (kiểm tra token để không mạo danh được bằng cách sửa cookie)."""
    s = session.get('attempt')
    if not s: return None
    a = get_db().execute('SELECT a.*, e.title, e.multi_mode FROM attempts a JOIN exams e ON e.id = a.exam_id WHERE a.id=?',
                         (s.get('id'),)).fetchone()
    if a is None or not secrets.compare_digest(a['token'], s.get('token', '')):
        session.pop('attempt', None)
        return None
    return a


def _overdue(a, grace=0):
    return now_utc() > from_iso(a['deadline']) + timedelta(seconds=grace)


def _store(db, attempt_id, answers):
    """Lưu lựa chọn {vị trí câu: [id phương án]}; bỏ id không thuộc câu đó, câu một đáp án chỉ giữ 1 lựa chọn."""
    rows = {r['position']: r for r in db.execute('SELECT ai.position, ai.option_ids, q.multi FROM attempt_items ai '
                                                 'JOIN questions q ON q.id = ai.question_id WHERE ai.attempt_id=?', (attempt_id,))}
    with db:
        for pos, chosen in answers.items():
            r = rows.get(pos)
            if r is None: continue
            allowed = set(json.loads(r['option_ids']))
            clean = sorted({int(x) for x in chosen if str(x).isdigit() and int(x) in allowed})
            if not r['multi']: clean = clean[:1]
            db.execute('UPDATE attempt_items SET selected=? WHERE attempt_id=? AND position=?', (json.dumps(clean), attempt_id, pos))


@bp.get('/')
def index():
    a = current_attempt()
    return render_template('student/join.html', form={}, current=a if a and a['status'] == 'doing' else None)


@bp.post('/join')
def join():
    f = {k: ' '.join(request.form.get(k, '').split()) for k in ('code', 'name', 'student_code', 'class_name')}
    f['code'] = f['code'].upper().replace(' ', '')
    f['student_code'] = f['student_code'].upper().replace(' ', '')
    db, now = get_db(), now_utc()
    exam = db.execute('SELECT * FROM exams WHERE code=?', (f['code'],)).fetchone()
    error = None
    if not f['name'] or len(f['name']) > 80: error = 'Hãy nhập họ và tên.'
    elif not STUDENT_CODE_RE.match(f['student_code']): error = 'MSSV chỉ gồm chữ và số, dài 3–20 ký tự.'
    error = error or window_error(exam, now)
    if not error:
        a = db.execute('SELECT * FROM attempts WHERE exam_id=? AND student_code=?', (exam['id'], f['student_code'])).fetchone()
        mine = session.get('attempt') or {}
        if a is None:
            return _start(db, exam, f, now)
        if a['status'] != 'doing':
            error = 'MSSV này đã nộp bài thi này rồi.'
        elif mine.get('id') == a['id'] and mine.get('token') == a['token']:
            return redirect(url_for('.exam'))
        elif a['allow_resume']:                     # giáo viên cho vào lại (đổi máy, lỡ đóng trình duyệt)
            token = secrets.token_urlsafe(16)
            with db: db.execute('UPDATE attempts SET token=?, allow_resume=0 WHERE id=?', (token, a['id']))
            _remember(a['id'], token)
            return redirect(url_for('.exam'))
        else:
            error = 'MSSV này đang làm bài trên một máy khác. Nếu bạn bị thoát ra, hãy báo giáo viên bấm "Cho vào lại".'
    flash(error, 'error')
    return render_template('student/join.html', form=f, current=None), 400


def _start(db, exam, f, now):
    deadline = now + timedelta(minutes=exam['duration_min'])
    if exam['end_at']: deadline = min(deadline, from_iso(exam['end_at']))
    items = pick_items(db, exam)
    token = secrets.token_urlsafe(16)
    try:
        with db:
            cur = db.execute('INSERT INTO attempts(exam_id, student_code, student_name, class_name, token, started_at, deadline, '
                             'total, ip) VALUES (?,?,?,?,?,?,?,?,?)',
                             (exam['id'], f['student_code'], f['name'], f['class_name'] or None, token, to_iso(now),
                              to_iso(deadline), len(items), request.remote_addr))
            db.executemany('INSERT INTO attempt_items(attempt_id, position, question_id, option_ids) VALUES (?,?,?,?)',
                           [(cur.lastrowid, *it) for it in items])
    except sqlite3.IntegrityError:                  # cùng MSSV bấm vào thi trên hai máy gần như cùng lúc
        flash('MSSV này vừa vào thi trên một máy khác.', 'error')
        return render_template('student/join.html', form=f, current=None), 400
    _remember(cur.lastrowid, token)
    return redirect(url_for('.exam'))


def _items(db, attempt_id):
    rows = db.execute('SELECT ai.position, ai.option_ids, ai.selected, q.text, q.multi FROM attempt_items ai '
                      'JOIN questions q ON q.id = ai.question_id WHERE ai.attempt_id=? ORDER BY ai.position', (attempt_id,)).fetchall()
    texts = {o['id']: o['text'] for o in db.execute('SELECT o.id, o.text FROM options o JOIN attempt_items ai '
                                                    'ON ai.question_id = o.question_id WHERE ai.attempt_id=?', (attempt_id,))}
    return [{'pos': r['position'], 'text': r['text'], 'multi': bool(r['multi']), 'selected': set(json.loads(r['selected'])),
             'options': [(oid, LETTERS[i], texts[oid]) for i, oid in enumerate(json.loads(r['option_ids']))]} for r in rows]


@bp.get('/exam')
def exam():
    a = current_attempt()
    if a is None:
        flash('Bạn chưa vào phòng thi.', 'error')
        return redirect(url_for('.index'))
    if a['status'] == 'doing' and _overdue(a, GRACE_SECONDS): finish(get_db(), a, 'timeout', a['multi_mode'])
    if a['status'] != 'doing' or _overdue(a, GRACE_SECONDS): return redirect(url_for('.done'))
    remaining = max(0, int((from_iso(a['deadline']) - now_utc()).total_seconds()))
    return render_template('student/exam.html', a=a, items=_items(get_db(), a['id']), remaining=remaining)


@bp.post('/exam/save')
def save():
    """Tự lưu mỗi lần sinh viên chọn đáp án (mất điện, tắt nhầm trình duyệt vẫn còn bài)."""
    a = current_attempt()
    if a is None: return jsonify(ok=False, error='Phiên thi không hợp lệ.'), 403
    if a['status'] != 'doing' or _overdue(a, GRACE_SECONDS):
        if a['status'] == 'doing': finish(get_db(), a, 'timeout', a['multi_mode'])
        return jsonify(ok=False, finished=True, redirect=url_for('.done'))
    data = request.get_json(silent=True) or {}
    pos, chosen = data.get('pos'), data.get('selected')
    if not isinstance(pos, int) or not isinstance(chosen, list): return jsonify(ok=False, error='Dữ liệu không hợp lệ.'), 400
    _store(get_db(), a['id'], {pos: chosen})
    return jsonify(ok=True, remaining=max(0, int((from_iso(a['deadline']) - now_utc()).total_seconds())))


@bp.post('/exam/submit')
def submit():
    a = current_attempt()
    if a is None: return redirect(url_for('.index'))
    if a['status'] == 'doing':
        db = get_db()
        if _overdue(a, GRACE_SECONDS):              # nộp quá muộn: chỉ tính các câu đã tự lưu trước khi hết giờ
            finish(db, a, 'timeout', a['multi_mode'])
        else:
            positions = [r['position'] for r in db.execute('SELECT position FROM attempt_items WHERE attempt_id=?', (a['id'],))]
            _store(db, a['id'], {p: request.form.getlist(f'q{p}') for p in positions})
            finish(db, a, 'timeout' if request.form.get('auto') == '1' else 'submitted', a['multi_mode'])
    return redirect(url_for('.done'))


@bp.get('/done')
def done():
    a = current_attempt()
    if a is None: return redirect(url_for('.index'))
    if a['status'] == 'doing': return redirect(url_for('.exam'))
    answered = get_db().execute("SELECT COUNT(*) FROM attempt_items WHERE attempt_id=? AND selected != '[]'", (a['id'],)).fetchone()[0]
    return render_template('student/done.html', a=a, answered=answered)
