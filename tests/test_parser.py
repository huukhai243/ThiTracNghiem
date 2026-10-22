import unittest
from io import BytesIO

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from quiz.grading import item_points, keeps_order
from quiz.parser import parse_answer, parse_docx, parse_lines
from quiz.sample import sample_docx


def lines(text):
    return [(t, None, False) for t in text.split('\n')]


class ParseText(unittest.TestCase):
    def test_basic_multi_inline_and_notes(self):
        r = parse_lines(lines('ĐỀ KIỂM TRA\n1. Hướng dẫn không phải câu hỏi\n'
                              'Câu 1: Thủ đô của Việt Nam?\nA. Hà Nội\nB. Huế\nĐáp án: A\n'
                              'Câu 2 (0,25đ): Số nguyên tố\ndòng hai\nA. 2\tB. 9\tC. 7\tD. 15\nĐáp án: A, C\nLời giải: bỏ qua\n'
                              'Câu 3. Đáp án nào sau đây đúng?\nA. x\nB. y\n   tiếp dòng của B\nĐáp án đúng là: B'))
        self.assertEqual([q.number for q in r.questions], [1, 2, 3])
        q1, q2, q3 = r.questions
        self.assertEqual((q1.text, q1.options, q1.answers, q1.multi), ('Thủ đô của Việt Nam?', [['A', 'Hà Nội'], ['B', 'Huế']], ['A'], False))
        self.assertEqual((q2.text, len(q2.options), q2.answers, q2.multi), ('Số nguyên tố\ndòng hai', 4, ['A', 'C'], True))
        self.assertEqual((q3.text, q3.options[1][1], q3.answers), ('Đáp án nào sau đây đúng?', 'y\ntiếp dòng của B', ['B']))
        self.assertEqual(r.errors, [])

    def test_errors_are_reported_and_question_skipped(self):
        r = parse_lines(lines('Câu 1: thiếu đáp án\nA. x\nB. y\nCâu 2: sai ký hiệu\nA. x\nB. y\nĐáp án: E\n'
                              'Câu 3: một phương án\nA. x\nĐáp án: A\nCâu 4: đọc không được\nA. x\nB. y\nĐáp án: (vì A đúng)\n'
                              'Câu 5: tốt\nA. x\nB. y\nĐáp án: b'))
        self.assertEqual([q.number for q in r.questions], [5])
        self.assertEqual(r.found, 5)
        self.assertEqual(len(r.errors), 4)
        self.assertIn('thiếu dòng', r.errors[0])
        self.assertIn('đáp án E', r.errors[1])

    def test_plain_numbering_when_no_cau_prefix(self):
        r = parse_lines(lines('1. Một cộng một?\nA) 1\nB) 2\nĐáp án: B\n2. Hai cộng hai?\nA) 4\nB) 5\nĐáp án: A'))
        self.assertEqual([(q.number, q.answers) for q in r.questions], [(1, ['B']), (2, ['A'])])

    def test_duplicate_warning(self):
        r = parse_lines(lines('Câu 1: Giống\nA. x\nB. y\nĐáp án: A\nCâu 2: giống\nA. x\nB. y\nĐáp án: B'))
        self.assertEqual(len(r.questions), 2)
        self.assertIn('trùng nội dung', r.warnings[0])

    def test_parse_answer(self):
        self.assertEqual(parse_answer('A'), ['A'])
        self.assertEqual(parse_answer('C, a'), ['A', 'C'])
        self.assertEqual(parse_answer('A và D'), ['A', 'D'])
        self.assertEqual(parse_answer('BD.'), ['B', 'D'])
        self.assertEqual(parse_answer('xem lời giải'), [])


class ParseWord(unittest.TestCase):
    def test_sample_file_round_trip(self):
        r = parse_docx(sample_docx())
        self.assertEqual(r.errors, [])
        self.assertEqual(len(r.questions), 5)
        self.assertEqual(r.questions[1].answers, ['B'])
        self.assertEqual(len(r.questions[1].options), 4)          # 4 phương án trên một dòng, cách nhau bằng Tab
        self.assertTrue(r.questions[2].multi)
        self.assertIn('print(len(x))', r.questions[4].text)

    def test_word_auto_numbering(self):
        """Câu hỏi đánh số tự động 1. 2. và phương án đánh số tự động A. B. của Word (không có chữ trong đoạn văn)."""
        doc = Document()
        numbering = doc.part.numbering_part.element
        for aid, fmt in (('90', 'decimal'), ('91', 'upperLetter')):
            a = OxmlElement('w:abstractNum'); a.set(qn('w:abstractNumId'), aid)
            lvl = OxmlElement('w:lvl'); lvl.set(qn('w:ilvl'), '0')
            nf = OxmlElement('w:numFmt'); nf.set(qn('w:val'), fmt)
            lvl.append(nf); a.append(lvl); numbering.insert(0, a)
            n = OxmlElement('w:num'); n.set(qn('w:numId'), aid)
            ref = OxmlElement('w:abstractNumId'); ref.set(qn('w:val'), aid)
            n.append(ref); numbering.append(n)

        def para(text, num_id=None):
            p = doc.add_paragraph(text)
            if num_id:
                num = p._p.get_or_add_pPr().get_or_add_numPr()
                num.get_or_add_ilvl().val = 0
                num.get_or_add_numId().val = num_id
        for q, opts, ans in (('Thủ đô Việt Nam?', ['Hà Nội', 'Huế'], 'A'), ('Sông dài nhất?', ['Hồng', 'Mê Kông', 'Đà'], 'B')):
            para(q, 90)
            for o in opts: para(o, 91)
            para(f'Đáp án: {ans}')
        buf = BytesIO(); doc.save(buf); buf.seek(0)
        r = parse_docx(buf)
        self.assertEqual(r.errors, [])
        self.assertEqual([(q.number, q.text, q.options, q.answers) for q in r.questions],
                         [(1, 'Thủ đô Việt Nam?', [['A', 'Hà Nội'], ['B', 'Huế']], ['A']),
                          (2, 'Sông dài nhất?', [['A', 'Hồng'], ['B', 'Mê Kông'], ['C', 'Đà']], ['B'])])


class Scoring(unittest.TestCase):
    def test_item_points(self):
        self.assertEqual(item_points([1], [1], 'all'), 1)
        self.assertEqual(item_points([2], [1], 'partial'), 0)
        self.assertEqual(item_points([1, 3], [1, 3], 'all'), 1)
        self.assertEqual(item_points([1], [1, 3], 'all'), 0)
        self.assertEqual(item_points([1], [1, 3], 'partial'), 0.5)
        self.assertEqual(item_points([1, 2], [1, 3], 'partial'), 0)        # 1 đúng - 1 sai
        self.assertEqual(item_points([], [1, 3], 'partial'), 0)

    def test_keeps_order(self):
        self.assertTrue(keeps_order(['x', 'Cả A và B đều đúng']))
        self.assertTrue(keeps_order(['Tất cả các đáp án trên']))
        self.assertFalse(keeps_order(['Hà Nội', 'Huế']))
        self.assertFalse(keeps_order(['a, b là hai số nguyên']))


if __name__ == '__main__':
    unittest.main()
