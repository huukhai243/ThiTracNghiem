"""Giáo viên: tải ngân hàng câu hỏi (Word), cài đặt đề và thời gian thi, mở/đóng phòng thi, xem và xuất bảng điểm."""
import functools
import json
import os
import secrets
import socket
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import from_iso, get_db, now_iso, now_utc, to_iso
from .export import results_workbook
from .grading import finish_expired, grade
from .parser import parse_docx
from .sample import sample_docx

bp = Blueprint('teacher', __name__, url_prefix='/teacher')
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'       # bỏ 0/O, 1/I cho dễ đọc


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kw):
        if not session.get('teacher_id'): return redirect(url_for('.login', next=request.path))
        return view(**kw)
    return wrapped


def own_exam(exam_id):
    e = get_db().execute('SELECT * FROM exams WHERE id=? AND teacher_id=?', (exam_id, session['teacher_id'])).fetchone()
    if e is None: abort(404)
    return e


def lan_ip():
    """IP của máy này trong mạng LAN (không gửi gói tin nào, chỉ hỏi hệ điều hành chọn card mạng nào)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        return None if ip.startswith('127.') else ip
    except OSError:
        return None


def student_url():
    """(địa chỉ sinh viên gõ vào trình duyệt, đã chắc chắn chưa)."""
    if os.environ.get('PUBLIC_URL'): return os.environ['PUBLIC_URL'].rstrip('/') + '/', True
    host, port = request.host, '80'
    if host.startswith('['): host, _, rest = host[1:].partition(']'); port = rest.lstrip(':') or port     # [::1]:8000
    elif ':' in host: host, port = host.rsplit(':', 1)
    if host not in ('localhost', '127.0.0.1', '::1'): return request.host_url, True
    ip = None if os.path.exists('/.dockerenv') else lan_ip()     # trong Docker chỉ thấy IP nội bộ của container
    port = '' if port == '80' else ':' + port
    return (f'http://{ip}{port}/', True) if ip else (f'http://<IP máy này>{port}/', False)


# ------------------------------------------------------------------ đăng nhập
@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Lần chạy đầu tiên: tạo tài khoản giáo viên."""
    db = get_db()
    if db.execute('SELECT 1 FROM teachers LIMIT 1').fetchone(): return redirect(url_for('.login'))
    if request.method == 'POST':
        user, pw = request.form.get('username', '').strip(), request.form.get('password', '')
        if not 3 <= len(user) <= 40: flash('Tên đăng nhập dài 3–40 ký tự.', 'error')
        elif len(pw) < 6: flash('Mật khẩu phải có ít nhất 6 ký tự.', 'error')
        elif pw != request.form.get('password2'): flash('Hai lần nhập mật khẩu không khớp.', 'error')
        else:
            with db:
                tid = db.execute('INSERT INTO teachers(username, password_hash, created_at) VALUES (?,?,?)',
                                 (user, generate_password_hash(pw), now_iso())).lastrowid
            session.clear()
            session.update(teacher_id=tid, teacher_name=user)
            return redirect(url_for('.dashboard'))
    return render_template('teacher/login.html', setup=True)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    db = get_db()
    if not db.execute('SELECT 1 FROM teachers LIMIT 1').fetchone(): return redirect(url_for('.setup'))
    if request.method == 'POST':
        t = db.execute('SELECT * FROM teachers WHERE username=?', (request.form.get('username', '').strip(),)).fetchone()
        if t and check_password_hash(t['password_hash'], request.form.get('password', '')):
            session.clear()
            session.update(teacher_id=t['id'], teacher_name=t['username'])
            nxt = request.args.get('next', '')
            return redirect(nxt if nxt.startswith('/teacher') else url_for('.dashboard'))
        flash('Sai tên đăng nhập hoặc mật khẩu.', 'error')
    return render_template('teacher/login.html', setup=False)


@bp.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('.login'))


# ------------------------------------------------------------------ danh sách đề, tạo đề
@bp.get('/')
@login_required
def dashboard():
    exams = get_db().execute(
        "SELECT e.*, (SELECT COUNT(*) FROM questions q WHERE q.exam_id = e.id) AS bank, "
        "(SELECT COUNT(*) FROM attempts a WHERE a.exam_id = e.id AND a.status != 'doing') AS done, "
        "(SELECT COUNT(*) FROM attempts a WHERE a.exam_id = e.id AND a.status = 'doing') AS doing "
        "FROM exams e WHERE e.teacher_id=? ORDER BY e.id DESC", (session['teacher_id'],)).fetchall()
    url, url_ok = student_url()
    return render_template('teacher/dashboard.html', exams=exams, join_url=url, url_ok=url_ok)


def read_settings(form):
    """Đọc phần cài đặt đề từ form; trả về (dict, lỗi)."""
    def num(name, lo, hi):
        try: v = int(form.get(name, ''))
        except ValueError: return None
        return v if lo <= v <= hi else None

    def when(name):
        s = form.get(name, '').strip()
        return to_iso(datetime.strptime(s, '%Y-%m-%dT%H:%M').astimezone()) if s else None   # giờ địa phương -> UTC

    s = {'title': ' '.join(form.get('title', '').split()), 'num_questions': num('num_questions', 1, 1000),
         'duration_min': num('duration_min', 1, 600), 'shuffle_options': int(form.get('shuffle_options') == '1'),
         'multi_mode': form.get('multi_mode') if form.get('multi_mode') in ('all', 'partial') else 'all'}
    try: s['start_at'], s['end_at'] = when('start_at'), when('end_at')
    except ValueError: return s, 'Thời gian mở/đóng phòng thi không hợp lệ.'
    if not s['title']: return s, 'Hãy nhập tên đề thi.'
    if s['num_questions'] is None: return s, 'Số câu mỗi sinh viên phải từ 1 đến 1000.'
    if s['duration_min'] is None: return s, 'Thời gian làm bài phải từ 1 đến 600 phút.'
    if s['start_at'] and s['end_at'] and s['end_at'] <= s['start_at']: return s, 'Giờ đóng phải sau giờ mở.'
    return s, None


def read_bank(file):
    """Đọc file Word tải lên; trả về (ParseResult, lỗi)."""
    if file is None or not file.filename: return None, 'Hãy chọn file Word chứa ngân hàng câu hỏi.'
    if not file.filename.lower().endswith('.docx'):
        return None, 'Chỉ nhận file .docx. Với file .doc cũ: mở bằng Word rồi chọn Lưu thành (Save As) → .docx.'
    try: result = parse_docx(file.stream)
    except Exception:                               # file hỏng, không phải Word thật...
        return None, 'Không đọc được file này. Hãy kiểm tra file mở được bằng Word và đã lưu dạng .docx.'
    if not result.questions: return result, 'Không có câu hỏi hợp lệ nào trong file. Xem danh sách lỗi bên dưới.'
    return result, None


def save_bank(db, exam_id, result, filename):
    db.execute('DELETE FROM questions WHERE exam_id=?', (exam_id,))
    for q in result.questions:
        qid = db.execute('INSERT INTO questions(exam_id, number, text, multi) VALUES (?,?,?,?)',
                         (exam_id, q.number, q.text, int(q.multi))).lastrowid
        db.executemany('INSERT INTO options(question_id, label, text, is_correct) VALUES (?,?,?,?)',
                       [(qid, label, text, int(label in q.answers)) for label, text in q.options])
    notes = {'file': filename, 'found': result.found, 'errors': result.errors, 'warnings': result.warnings}
    db.execute('UPDATE exams SET source_file=?, import_notes=? WHERE id=?', (filename, json.dumps(notes, ensure_ascii=False), exam_id))


@bp.route('/exams/new', methods=['GET', 'POST'])
@login_required
def new_exam():
    if request.method == 'GET':
        return render_template('teacher/new_exam.html', s={'num_questions': 40, 'duration_min': 45, 'shuffle_options': 1,
                                                          'multi_mode': 'all'}, result=None)
    s, error = read_settings(request.form)
    result = None
    if not error: result, error = read_bank(request.files.get('file'))
    if error:
        flash(error, 'error')
        return render_template('teacher/new_exam.html', s=s, result=result), 400
    db = get_db()
    code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    while db.execute('SELECT 1 FROM exams WHERE code=?', (code,)).fetchone():
        code = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(6))
    n = len(result.questions)
    with db:
        exam_id = db.execute('INSERT INTO exams(teacher_id, title, code, num_questions, duration_min, shuffle_options, multi_mode, '
                             'start_at, end_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                             (session['teacher_id'], s['title'], code, min(s['num_questions'], n), s['duration_min'],
                              s['shuffle_options'], s['multi_mode'], s['start_at'], s['end_at'], now_iso())).lastrowid
        save_bank(db, exam_id, result, request.files['file'].filename)
    flash(f'Đã đọc {n} câu hỏi. Kiểm tra lại ngân hàng câu hỏi bên dưới rồi bấm "Mở phòng thi".', 'ok')
    if s['num_questions'] > n: flash(f'Ngân hàng chỉ có {n} câu nên mỗi sinh viên làm {n} câu.', 'warn')
    return redirect(url_for('.exam', exam_id=exam_id))


# ------------------------------------------------------------------ một đề thi
@bp.get('/exams/<int:exam_id>')
@login_required
def exam(exam_id):
    e, db = own_exam(exam_id), get_db()
    questions = db.execute('SELECT * FROM questions WHERE exam_id=? ORDER BY id', (exam_id,)).fetchall()
    options = {}
    for o in db.execute('SELECT o.* FROM options o JOIN questions q ON q.id = o.question_id WHERE q.exam_id=? ORDER BY o.id', (exam_id,)):
        options.setdefault(o['question_id'], []).append(o)
    stats = {r['question_id']: r for r in db.execute(
        "SELECT ai.question_id, COUNT(*) AS n, SUM(ai.points) AS pts FROM attempt_items ai JOIN attempts a ON a.id = ai.attempt_id "
        "WHERE a.exam_id=? AND a.status != 'doing' GROUP BY ai.question_id", (exam_id,))}
    attempts = db.execute('SELECT COUNT(*) FROM attempts WHERE exam_id=?', (exam_id,)).fetchone()[0]
    url, url_ok = student_url()
    return render_template('teacher/exam.html', e=e, questions=questions, options=options, stats=stats, attempts=attempts,
                           notes=json.loads(e['import_notes'] or '{}'), join_url=url, url_ok=url_ok)


@bp.post('/exams/<int:exam_id>/settings')
@login_required
def settings(exam_id):
    e, db = own_exam(exam_id), get_db()
    s, error = read_settings(request.form)
    if error:
        flash(error, 'error')
        return redirect(url_for('.exam', exam_id=exam_id))
    bank = db.execute('SELECT COUNT(*) FROM questions WHERE exam_id=?', (exam_id,)).fetchone()[0]
    if s['num_questions'] > bank: flash(f'Ngân hàng chỉ có {bank} câu nên mỗi sinh viên làm {bank} câu.', 'warn')
    with db:
        db.execute('UPDATE exams SET title=?, num_questions=?, duration_min=?, shuffle_options=?, multi_mode=?, start_at=?, end_at=? '
                   'WHERE id=?', (s['title'], min(s['num_questions'], bank), s['duration_min'], s['shuffle_options'],
                                  s['multi_mode'], s['start_at'], s['end_at'], exam_id))
        if s['multi_mode'] != e['multi_mode']:      # đổi cách chấm câu nhiều đáp án -> chấm lại các bài đã nộp
            for a in db.execute("SELECT id FROM attempts WHERE exam_id=? AND status != 'doing'", (exam_id,)).fetchall():
                grade(db, a['id'], s['multi_mode'])
    flash('Đã lưu cài đặt. Thay đổi số câu và thời gian chỉ áp dụng cho sinh viên vào thi sau lúc này.', 'ok')
    return redirect(url_for('.exam', exam_id=exam_id))


@bp.post('/exams/<int:exam_id>/upload')
@login_required
def upload(exam_id):
    e, db = own_exam(exam_id), get_db()
    if db.execute('SELECT 1 FROM attempts WHERE exam_id=? LIMIT 1', (exam_id,)).fetchone():
        flash('Đã có sinh viên làm đề này nên không thay ngân hàng câu hỏi được. Hãy tạo đề thi mới.', 'error')
        return redirect(url_for('.exam', exam_id=exam_id))
    result, error = read_bank(request.files.get('file'))
    if error:
        flash(error, 'error')
        if result: flash(' '.join(result.errors[:10]), 'error')
        return redirect(url_for('.exam', exam_id=exam_id))
    n = len(result.questions)
    with db:
        save_bank(db, exam_id, result, request.files['file'].filename)
        db.execute('UPDATE exams SET num_questions=MIN(num_questions, ?) WHERE id=?', (n, exam_id))
    flash(f'Đã thay ngân hàng câu hỏi: {n} câu.', 'ok')
    return redirect(url_for('.exam', exam_id=exam_id))


@bp.post('/exams/<int:exam_id>/toggle')
@login_required
def toggle(exam_id):
    e, db = own_exam(exam_id), get_db()
    if not e['is_open'] and not db.execute('SELECT 1 FROM questions WHERE exam_id=? LIMIT 1', (exam_id,)).fetchone():
        flash('Ngân hàng câu hỏi đang trống.', 'error')
    else:
        with db: db.execute('UPDATE exams SET is_open=? WHERE id=?', (0 if e['is_open'] else 1, exam_id))
        flash('Đã mở phòng thi. Sinh viên vào được bằng mã ' + e['code'] + '.' if not e['is_open'] else
              'Đã đóng phòng thi. Sinh viên đang làm vẫn làm tiếp đến hết giờ.', 'ok')
    return redirect(request.referrer or url_for('.exam', exam_id=exam_id))


@bp.post('/exams/<int:exam_id>/delete')
@login_required
def delete(exam_id):
    own_exam(exam_id)
    db = get_db()
    with db:
        db.execute('DELETE FROM attempts WHERE exam_id=?', (exam_id,))
        db.execute('DELETE FROM exams WHERE id=?', (exam_id,))
    flash('Đã xóa đề thi và toàn bộ bài làm của đề.', 'ok')
    return redirect(url_for('.dashboard'))


# ------------------------------------------------------------------ bảng điểm
def attempts_of(db, exam_id):
    finish_expired(db, exam_id)
    return db.execute('SELECT * FROM attempts WHERE exam_id=? ORDER BY student_code', (exam_id,)).fetchall()


@bp.get('/exams/<int:exam_id>/results')
@login_required
def results(exam_id):
    e, db = own_exam(exam_id), get_db()
    rows = attempts_of(db, exam_id)
    scores = [r['score'] for r in rows if r['status'] != 'doing']
    buckets = [0] * 10
    for sc in scores: buckets[min(int(sc), 9)] += 1
    now = now_utc()
    remaining = {r['id']: max(0, int((from_iso(r['deadline']) - now).total_seconds() // 60)) for r in rows if r['status'] == 'doing'}
    summary = {'done': len(scores), 'doing': len(remaining),
               'avg': round(sum(scores) / len(scores), 2) if scores else None,
               'max': max(scores) if scores else None, 'min': min(scores) if scores else None}
    return render_template('teacher/results.html', e=e, rows=rows, summary=summary, buckets=buckets, remaining=remaining)


@bp.get('/exams/<int:exam_id>/results/<int:attempt_id>')
@login_required
def attempt(exam_id, attempt_id):
    e, db = own_exam(exam_id), get_db()
    finish_expired(db, exam_id)
    a = db.execute('SELECT * FROM attempts WHERE id=? AND exam_id=?', (attempt_id, exam_id)).fetchone()
    if a is None: abort(404)
    items = []
    for it in db.execute('SELECT ai.*, q.text, q.multi, q.number FROM attempt_items ai JOIN questions q ON q.id = ai.question_id '
                         'WHERE ai.attempt_id=? ORDER BY ai.position', (attempt_id,)):
        opts = {o['id']: o for o in db.execute('SELECT * FROM options WHERE question_id=?', (it['question_id'],))}
        chosen = set(json.loads(it['selected']))
        items.append({'it': it, 'chosen': chosen,
                      'options': [(chr(65 + i), opts[oid], oid in chosen) for i, oid in enumerate(json.loads(it['option_ids']))]})
    return render_template('teacher/attempt.html', e=e, a=a, items=items)


@bp.post('/exams/<int:exam_id>/results/<int:attempt_id>/resume')
@login_required
def allow_resume(exam_id, attempt_id):
    own_exam(exam_id)
    db = get_db()
    with db: db.execute("UPDATE attempts SET allow_resume=1 WHERE id=? AND exam_id=? AND status='doing'", (attempt_id, exam_id))
    flash('Sinh viên có thể vào lại bằng đúng MSSV trên máy bất kỳ. Thời gian vẫn tính tiếp, không cộng thêm.', 'ok')
    return redirect(url_for('.results', exam_id=exam_id))


@bp.post('/exams/<int:exam_id>/results/<int:attempt_id>/reset')
@login_required
def reset(exam_id, attempt_id):
    own_exam(exam_id)
    db = get_db()
    with db: db.execute('DELETE FROM attempts WHERE id=? AND exam_id=?', (attempt_id, exam_id))
    flash('Đã xóa bài làm. Sinh viên có thể vào thi lại từ đầu (đề mới, tính giờ lại).', 'ok')
    return redirect(url_for('.results', exam_id=exam_id))


@bp.get('/exams/<int:exam_id>/results.xlsx')
@login_required
def export(exam_id):
    e, db = own_exam(exam_id), get_db()
    buf = results_workbook(e, attempts_of(db, exam_id))
    return send_file(buf, as_attachment=True, download_name=f'Bang_diem_{e["code"]}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@bp.get('/sample.docx')
def sample():
    return send_file(sample_docx(), as_attachment=True, download_name='Mau_ngan_hang_cau_hoi.docx',
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
