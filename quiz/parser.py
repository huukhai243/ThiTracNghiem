"""Đọc ngân hàng câu hỏi trắc nghiệm từ file Word (.docx).

Định dạng mỗi câu:
    Câu 1: Nội dung câu hỏi (có thể nhiều dòng)
    A. Phương án A
    B. Phương án B          (nhiều phương án trên một dòng thì cách nhau bằng phím Tab)
    C. Phương án C
    D. Phương án D
    Đáp án: A               (nhiều đáp án đúng: "Đáp án: A, C")

Phần chữ trước câu đầu tiên (tiêu đề, hướng dẫn) và lời giải viết sau dòng "Đáp án" được bỏ qua.
Câu hỏi/phương án dùng đánh số tự động của Word (1. 2. 3. / A. B. C.) cũng đọc được.
"""
import re
import unicodedata
from dataclasses import dataclass, field

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

LETTERS = 'ABCDEFGH'
Q_RE = re.compile(r'^(?:câu(?:\s*hỏi)?|cau|question)\s*(\d+)\s*(?:\([^)]*\))?\s*[:.)\-–]?\s*(.*)$', re.I)
NUM_RE = re.compile(r'^(\d+)\s*[.)]\s+(.*)$')
OPT_RE = re.compile(r'^([A-H])\s*[.):/]\s*(.*)$')
ANS_RE = re.compile(r'^(?:đáp\s*án|dap\s*an|answer)(?:\s*(?:đúng|dung))?(?:\s*là)?\s*([:：\-]?)\s*(.*)$', re.I)
INLINE_SPLIT = re.compile(r'(?:\t+|\s{2,})(?=[A-H]\s*[.):/]\s)')     # "A. 1<Tab>B. 2<Tab>C. 3"


@dataclass
class Question:
    number: int
    text: str = ''
    options: list = field(default_factory=list)      # [[ký hiệu, nội dung], ...]
    answers: list = field(default_factory=list)      # ký hiệu đáp án đúng, vd ['A', 'C']
    answer_line: str | None = None
    has_media: bool = False
    errors: list = field(default_factory=list)

    @property
    def multi(self):
        return len(self.answers) > 1


@dataclass
class ParseResult:
    questions: list          # các câu hợp lệ
    errors: list             # câu bị bỏ qua và lý do
    warnings: list           # câu vẫn dùng được nhưng nên kiểm tra
    found: int               # số câu tìm thấy, kể cả câu lỗi


def parse_answer(text):
    """'A' / 'A, C' / 'A và C' / 'AC' -> ['A', 'C']; không đọc được -> []."""
    s = re.sub(r'(?i)\b(?:và|and|hoặc)\b|[\s,;/&+.()\[\]]', '', text).upper()
    return sorted(set(s)) if re.fullmatch(r'[A-H]+', s) else []


def parse_lines(lines):
    """lines: [(dòng chữ, kiểu đánh số tự động của Word: None | 'q' | 'opt', có hình/công thức)]."""
    lines = [(unicodedata.normalize('NFC', t).replace('\xa0', ' ').strip(), k, m) for t, k, m in lines]
    use_num = not any(Q_RE.match(t) for t, _, _ in lines)      # đề không viết "Câu 1:" thì nhận "1." là câu hỏi
    qs, cur = [], None
    for text, kind, media in lines:
        if cur is not None and media and cur.answer_line is None: cur.has_media = True
        if not text: continue
        between = cur is None or cur.answer_line is not None       # đang ở giữa hai câu hỏi
        m = Q_RE.match(text) or (NUM_RE.match(text) if use_num and between else None)
        if m or (kind == 'q' and between):
            if cur: qs.append(cur)
            cur = Question(int(m.group(1)) if m else len(qs) + 1, has_media=media)
            cur.text = m.group(2).strip() if m else text
            continue
        if cur is None or cur.answer_line is not None: continue   # tiêu đề/hướng dẫn, hoặc lời giải sau đáp án
        a = ANS_RE.match(text)
        if a and (a.group(1) or parse_answer(a.group(2))):
            cur.answer_line, cur.answers = a.group(2), parse_answer(a.group(2))
            continue
        parts = [p.strip() for p in INLINE_SPLIT.split(text)]
        if OPT_RE.match(parts[0]):
            for p in parts:
                o = OPT_RE.match(p)
                cur.options.append([o.group(1), o.group(2).strip()])
        elif kind == 'opt':
            cur.options.append([LETTERS[min(len(cur.options), len(LETTERS) - 1)], text])
        elif cur.options:                                            # phương án viết tiếp sang dòng sau
            cur.options[-1][1] = (cur.options[-1][1] + '\n' + text).strip()
        else:
            cur.text = (cur.text + '\n' + text).strip()
    if cur: qs.append(cur)
    return _validate(qs)


def _validate(qs):
    good, errors, warnings, seen = [], [], [], {}
    for q in qs:
        labels = [label for label, _ in q.options]
        if not q.text: q.errors.append('thiếu nội dung câu hỏi')
        if len(q.options) < 2: q.errors.append('cần ít nhất 2 phương án (A. B. ...)')
        elif len(set(labels)) != len(labels): q.errors.append('ký hiệu phương án bị trùng')
        if any(not t for _, t in q.options): q.errors.append('có phương án để trống')
        if q.answer_line is None: q.errors.append("thiếu dòng 'Đáp án: ...'")
        elif not q.answers:
            q.errors.append(f"không đọc được đáp án '{q.answer_line}' (viết như 'Đáp án: A' hoặc 'Đáp án: A, C')")
        elif set(q.answers) - set(labels):
            q.errors.append(f"đáp án {', '.join(sorted(set(q.answers) - set(labels)))} không có trong các phương án")
        if q.errors:
            errors.append(f'Câu {q.number}: ' + '; '.join(q.errors) + '.')
            continue
        good.append(q)
        key = ' '.join(q.text.lower().split())
        if key in seen: warnings.append(f'Câu {q.number} trùng nội dung với câu {seen[key]}.')
        seen.setdefault(key, q.number)
        if q.has_media: warnings.append(f'Câu {q.number} có hình ảnh hoặc công thức: hiện chỉ hiển thị phần chữ.')
    if not qs: errors.append("Không tìm thấy câu hỏi nào. Mỗi câu phải bắt đầu bằng 'Câu 1:', 'Câu 2:'...")
    return ParseResult(good, errors, warnings, len(qs))


# ------------------------------------------------------------------ đọc file .docx
def parse_docx(stream):
    return parse_lines(read_docx(stream))


def read_docx(stream):
    doc = Document(stream)
    formats = _numbering_formats(doc)
    lines = []
    for p in _paragraphs(doc):
        kind = _list_kind(p, formats)
        media = bool(p._p.xpath('.//*[local-name()="drawing" or local-name()="pict" or local-name()="oMath"]'))
        for i, piece in enumerate(p.text.split('\n')):        # xuống dòng mềm (Shift+Enter) trong cùng đoạn
            lines.append((piece, kind if i == 0 else None, media and i == 0))
    return lines


def _paragraphs(doc):
    """Các đoạn văn theo đúng thứ tự trong file, kể cả đoạn nằm trong bảng."""
    for child in doc.element.body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, doc)
        elif child.tag == qn('w:tbl'):
            seen = set()
            for row in Table(child, doc).rows:
                for cell in row.cells:
                    if cell._tc in seen: continue                 # ô gộp được trả về nhiều lần
                    seen.add(cell._tc)
                    yield from cell.paragraphs


def _numbering_formats(doc):
    """numId -> {cấp: kiểu đánh số} lấy từ phần numbering của file Word."""
    try:
        root = doc.part.numbering_part.element
    except (KeyError, NotImplementedError):
        return {}
    abstract = {}
    for a in root.findall(qn('w:abstractNum')):
        levels = {}
        for lvl in a.findall(qn('w:lvl')):
            fmt = lvl.find(qn('w:numFmt'))
            levels[lvl.get(qn('w:ilvl'))] = fmt.get(qn('w:val')) if fmt is not None else None
        abstract[a.get(qn('w:abstractNumId'))] = levels
    out = {}
    for n in root.findall(qn('w:num')):
        aid = n.find(qn('w:abstractNumId'))
        if aid is not None: out[n.get(qn('w:numId'))] = abstract.get(aid.get(qn('w:val')), {})
    return out


def _list_kind(p, formats):
    ppr = p._p.pPr
    num = ppr.numPr if ppr is not None else None
    if num is None or num.numId is None or num.numId.val == 0: return None
    level = num.ilvl.val if num.ilvl is not None else 0
    fmt = formats.get(str(num.numId.val), {}).get(str(level))
    return 'opt' if fmt in ('upperLetter', 'lowerLetter') else 'q' if fmt in ('decimal', 'decimalZero') else None
