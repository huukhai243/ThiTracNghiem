"""Rút đề ngẫu nhiên từ ngân hàng câu hỏi, trộn phương án và chấm điểm."""
import json
import random
import re
from datetime import timedelta

from .db import now_iso, now_utc, to_iso

GRACE_SECONDS = 15                  # bù độ trễ mạng khi trình duyệt tự nộp bài lúc hết giờ
_rng = random.SystemRandom()
# Phương án nhắc tới vị trí phương án khác ("Cả A và B", "Tất cả các đáp án trên") thì giữ nguyên thứ tự
_POSITIONAL = re.compile(r'(?i)tất cả|các (?:đáp án|phương án|ý|câu) (?:trên|đều)|không có (?:đáp án|phương án) nào'
                         r'|(?:cả|đáp án|phương án)\s+(?-i:[A-H])\b|\b(?-i:[A-H])\s*(?:và|,|hoặc)\s*(?-i:[A-H])\b')


def keeps_order(option_texts):
    return any(_POSITIONAL.search(t) for t in option_texts)


def pick_items(db, exam):
    """Rút ngẫu nhiên num_questions câu (thứ tự ngẫu nhiên) và trộn phương án cho một lượt thi.
    Trả về [(vị trí, id câu hỏi, JSON thứ tự id phương án)]."""
    ids = [r['id'] for r in db.execute('SELECT id FROM questions WHERE exam_id=?', (exam['id'],))]
    items = []
    for pos, qid in enumerate(_rng.sample(ids, min(exam['num_questions'], len(ids))), 1):
        opts = db.execute('SELECT id, text FROM options WHERE question_id=? ORDER BY id', (qid,)).fetchall()
        order = [o['id'] for o in opts]
        if exam['shuffle_options'] and not keeps_order([o['text'] for o in opts]): _rng.shuffle(order)
        items.append((pos, qid, json.dumps(order)))
    return items


def item_points(selected, correct, mode):
    """Điểm một câu (0..1). Câu nhiều đáp án: 'all' = đúng hết mới có điểm,
    'partial' = (số đáp án đúng đã chọn - số đáp án sai đã chọn) / số đáp án đúng, không âm."""
    sel, cor = set(selected), set(correct)
    if mode != 'partial' or len(cor) < 2: return 1.0 if sel == cor else 0.0
    return max(0.0, (len(sel & cor) - len(sel - cor)) / len(cor))


def grade(db, attempt_id, mode):
    """Chấm (hoặc chấm lại) một lượt thi theo thang 10. Gọi bên trong một transaction."""
    rows = db.execute("SELECT position, selected, (SELECT group_concat(id) FROM options o WHERE o.question_id = ai.question_id "
                      "AND o.is_correct = 1) AS correct FROM attempt_items ai WHERE attempt_id=?", (attempt_id,)).fetchall()
    total, right = 0.0, 0
    for r in rows:
        pts = item_points(json.loads(r['selected']), [int(x) for x in (r['correct'] or '').split(',') if x], mode)
        db.execute('UPDATE attempt_items SET points=? WHERE attempt_id=? AND position=?', (pts, attempt_id, r['position']))
        total += pts
        right += pts == 1.0
    score = round(total / len(rows) * 10, 2) if rows else 0.0
    db.execute('UPDATE attempts SET score=?, correct=? WHERE id=?', (score, right, attempt_id))
    return score


def finish(db, attempt, status, mode):
    """Kết thúc lượt thi (status 'submitted' = sinh viên nộp, 'timeout' = hết giờ) rồi chấm điểm.
    Chỉ tác dụng với lượt đang làm, nên hai yêu cầu nộp cùng lúc không chấm hai lần."""
    at = min(now_iso(), attempt['deadline']) if status == 'timeout' else now_iso()
    with db:
        cur = db.execute("UPDATE attempts SET status=?, submitted_at=? WHERE id=? AND status='doing'", (status, at, attempt['id']))
        if cur.rowcount: grade(db, attempt['id'], mode)


def finish_expired(db, exam_id=None):
    """Chấm các lượt đã quá giờ mà trình duyệt chưa kịp nộp (sinh viên tắt máy, mất mạng...)."""
    limit = to_iso(now_utc() - timedelta(seconds=GRACE_SECONDS))
    sql = ("SELECT a.*, e.multi_mode FROM attempts a JOIN exams e ON e.id = a.exam_id "
           "WHERE a.status='doing' AND a.deadline < ?")
    args = [limit]
    if exam_id is not None:
        sql += ' AND a.exam_id=?'
        args.append(exam_id)
    for a in db.execute(sql, args).fetchall(): finish(db, a, 'timeout', a['multi_mode'])
