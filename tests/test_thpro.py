# -*- coding: utf-8 -*-
"""
ชุดทดสอบภาษา TH-Programming

    python -m unittest discover -s tests -v
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from thpro import compile_source, check_source                    # noqa: E402
from thpro.pipeline import run                                    # noqa: E402
from thpro.errors import CompileError, RuntimeThaiError           # noqa: E402
from thpro.diagnostics import Code                                # noqa: E402
from thpro.compiler import tcc                                    # noqa: E402


def codes(src):
    """คืนรหัสข้อผิดพลาด/คำเตือนทั้งหมดที่คอมไพเลอร์รายงาน"""
    return [d.code for d in check_source(src, "<test>")]


def py(src, optimize=0):
    """คืนเฉพาะเนื้อโปรแกรม Python (ตัดหัวไฟล์และ helper ออก)

    ค่าเริ่มต้นปิดการปรับให้เหมาะที่สุด เพื่อทดสอบตัวสร้างโค้ดตรง ๆ
    """
    program = compile_source(src, "<test>", optimize_level=optimize)
    lines = program.python.splitlines()
    start = min(program.linemap) - 1 if program.linemap else 0
    return "\n".join(l for l in lines[start:] if l.strip()).strip()


def expr_py(expression, names=("ก", "ข", "ค")):
    """คอมไพล์นิพจน์เดี่ยว ๆ โดยประกาศตัวแปรที่ใช้บ่อยไว้ให้ก่อน

    "รายชื่อ" ต้องเป็นรายการจริง ๆ ไม่ใช่ตัวเลข มิฉะนั้นตัวตรวจชนิดจะฟ้อง
    (ถูกต้องแล้ว เพราะ ความยาว(1) พังตอนรันจริง)
    """
    setup = "".join(f"ให้ {n} เป็น 1\n" for n in names)
    setup += 'ให้ รายชื่อ เป็น ["ก", "ข"]\n'
    return py(setup + f"ให้ ผล เป็น {expression}").splitlines()[-1]


def out(src, stdin=None):
    program = compile_source(src, "<test>")
    buf, saved = io.StringIO(), sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with redirect_stdout(buf):
            run(program, show_warnings=False, stream=io.StringIO())
    finally:
        sys.stdin = saved
    return buf.getvalue()


# ====================================================== การตัดคำภาษาไทย
class TestSegmentation(unittest.TestCase):
    """หัวใจของภาษา: เขียนติดกันเป็นประโยคยาวแล้วต้องตีความถูก"""

    def test_no_space_print(self):
        self.assertEqual(py('แสดง"สวัสดีชาวโลก!"'), 'print("สวัสดีชาวโลก!")')

    def test_no_space_assign(self):
        self.assertEqual(py("ให้ราคาเป็น250"), "ราคา = 250")

    def test_keyword_not_swallowed_into_name(self):
        # "ให้ชื่อ" ต้องไม่กลายเป็นชื่อตัวแปรเดียว
        self.assertEqual(py('ให้ชื่อเป็น"ก"'), 'ชื่อ = "ก"')

    def test_name_not_chopped_by_inner_keyword(self):
        # "ผลบวก" มีคำว่า "ลบ" ซ่อนอยู่ ต้องไม่ถูกซอยเป็น ผ|ลบ|วก
        self.assertEqual(py("ให้ผลบวกเป็น0"), "ผลบวก = 0")

    def test_long_operator_not_fragmented(self):
        self.assertEqual(py("ให้ก เป็น 1\nให้ผลเป็นกน้อยกว่าหรือเท่ากับ10")
                         .splitlines()[-1], "ผล = ก <= 10")

    def test_full_sentence(self):
        src = "ให้ราคาเป็น250\nให้จำนวนชิ้นเป็น3\nให้ราคารวมเป็นราคาคูณจำนวนชิ้น"
        self.assertEqual(py(src).splitlines()[-1], "ราคารวม = ราคา * จำนวนชิ้น")

    def test_learned_names_help_later_lines(self):
        src = "ให้ยอดสะสมเป็น0\nเพิ่มยอดสะสมอีก5\nแสดงยอดสะสม"
        self.assertEqual(out(src), "5\n")

    def test_loop_variable_known_inside_body(self):
        self.assertEqual(out("นับตัวนับจาก1ถึง3\n    แสดงตัวนับคูณ2"),
                         "2\n4\n6\n")

    def test_function_params_known_inside_body(self):
        src = ("ฟังก์ชันบวกเลขรับตัวแรกและตัวหลัง\n"
               "    คืนค่าตัวแรกบวกตัวหลัง\n"
               "แสดงบวกเลข(2,3)\n")
        self.assertEqual(out(src), "5\n")

    def test_spaces_still_work(self):
        self.assertEqual(py('ให้ ราคา เป็น 250'), "ราคา = 250")

    def test_mixed_spacing(self):
        self.assertEqual(py('ให้ราคา เป็น  250'), "ราคา = 250")

    def test_decimal_inside_sentence(self):
        src = "ให้อุณหภูมิเป็น38\nถ้าอุณหภูมิมากกว่าหรือเท่ากับ37.5ให้แสดง\"ไข้\""
        self.assertEqual(out(src), "ไข้\n")


class TestTCC(unittest.TestCase):
    def test_leading_vowel_stays_with_consonant(self):
        self.assertIn("เก", tcc.clusters("เกาะ")[0])

    def test_mai_han_akat_not_split(self):
        self.assertEqual(tcc.clusters("ตั")[0], "ตั")

    def test_boundaries_cover_whole_text(self):
        text = "ให้ราคาเป็น"
        self.assertEqual(tcc.boundaries(text)[-1], len(text))


# ====================================================== พื้นฐาน
class TestBasics(unittest.TestCase):
    def test_hello(self):
        self.assertEqual(py('แสดง "Hello World!"'), 'print("Hello World!")')

    def test_print_synonyms(self):
        for word in ["แสดง", "พิมพ์", "บอก", "โชว์", "แสดงผล", "รายงาน"]:
            self.assertEqual(py(f'{word}"ก"'), 'print("ก")', word)

    def test_print_multiple(self):
        self.assertEqual(py('แสดง"ก",1,จริง'), 'print("ก", 1, True)')

    def test_filler_words_ignored(self):
        self.assertEqual(py('แสดงว่า"ก"นะครับ'), 'print("ก")')

    def test_polite_particle_only_dropped_at_the_end(self):
        """"คะ" ต้องไม่กินพยางค์แรกของชื่อตัวแปร ("คะแนน" -> "แนน")"""
        self.assertEqual(py("คะแนน เท่ากับ 10"), "คะแนน = 10")
        self.assertEqual(py("ให้คะแนนความอร่อยเป็น10"), "คะแนนความอร่อย = 10")
        self.assertEqual(py("ให้สิบเป็น10"), "สิบ = 10")

    def test_polite_particle_still_dropped_when_trailing(self):
        for src in ('แสดง"ก"ครับ', 'แสดง"ก"นะ', 'แสดง"ก"หน่อยนะครับ'):
            with self.subTest(src=src):
                self.assertEqual(py(src), 'print("ก")')

    def test_assign_forms(self):
        for src in ["ให้ค่าเป็น5", "กำหนดให้ค่าคือ5", "ตั้งค่าเท่ากับ5",
                    "ค่า=5", "ค่ามีค่าเป็น5", "เก็บ5ไว้ในค่า"]:
            self.assertEqual(py(src), "ค่า = 5", src)

    def test_thai_digits(self):
        self.assertEqual(py("ให้เลขเป็น๑๒๓"), "เลข = 123")

    def test_inc_dec_forms(self):
        base = "ให้แต้มเป็น0\n"
        self.assertEqual(py(base + "เพิ่มแต้มอีก3").splitlines()[-1], "แต้ม += 3")
        self.assertEqual(py(base + "ลดแต้มลง2").splitlines()[-1], "แต้ม -= 2")
        self.assertEqual(py(base + "เพิ่มแต้ม").splitlines()[-1], "แต้ม += 1")
        self.assertEqual(py(base + "บวก5เข้ากับแต้ม").splitlines()[-1], "แต้ม += 5")
        self.assertEqual(py(base + "ลบ5ออกจากแต้ม").splitlines()[-1], "แต้ม -= 5")

    def test_comments(self):
        self.assertEqual(py("หมายเหตุ อธิบายเฉย ๆ\nแสดง1 # ท้ายบรรทัด"),
                         "print(1)")

    def test_thai_trailing_comment(self):
        """คอมเมนต์ท้ายบรรทัดเขียนเป็นภาษาไทยได้ ไม่ต้องใช้ # เท่านั้น"""
        for src in ("แสดง1    หมายเหตุ อธิบาย",
                    "แสดง1    อธิบาย ว่าทำอะไร",
                    "แสดง1    คอมเมนต์ อะไรก็ได้"):
            with self.subTest(src=src):
                self.assertEqual(py(src), "print(1)")

    def test_comment_word_inside_a_name_is_not_a_comment(self):
        """ต้องมีช่องว่างนำหน้าเท่านั้น มิฉะนั้นชื่อตัวแปรจะถูกตัดกลางคำ"""
        self.assertEqual(out("ให้หมายเหตุสำคัญเป็น 5\nแสดงหมายเหตุสำคัญ"), "5\n")


# ====================================================== นิพจน์
class TestExpressions(unittest.TestCase):
    def test_word_and_symbol_operators(self):
        self.assertEqual(expr_py("7บวก3คูณ2"), "ผล = 7 + 3 * 2")
        self.assertEqual(expr_py("7 + 3 * 2"), "ผล = 7 + 3 * 2")

    def test_parentheses(self):
        self.assertEqual(expr_py("(7บวก3)คูณ2"), "ผล = (7 + 3) * 2")

    def test_comparisons(self):
        cases = {"มากกว่า": ">", "น้อยกว่า": "<", "เท่ากับ": "==",
                 "ไม่เท่ากับ": "!=", "มากกว่าหรือเท่ากับ": ">=",
                 "ไม่เกิน": "<=", "ไม่น้อยกว่า": ">="}
        for thai, op in cases.items():
            self.assertEqual(expr_py(f"ก{thai}ข"), f"ผล = ก {op} ข", thai)

    def test_logic(self):
        self.assertEqual(expr_py("กและไม่ขหรือค"), "ผล = ก and not ข or ค")

    def test_power_associativity(self):
        self.assertEqual(expr_py("2ยกกำลัง3ยกกำลัง2"), "ผล = 2 ** 3 ** 2")
        self.assertEqual(expr_py("(2ยกกำลัง3)ยกกำลัง2"), "ผล = (2 ** 3) ** 2")

    def test_collections(self):
        self.assertEqual(py("ให้ผลเป็น[1,2,3]"), "ผล = [1, 2, 3]")
        self.assertEqual(py('ให้ผลเป็น{"ก":1}'), 'ผล = {"ก": 1}')
        self.assertEqual(expr_py("รายชื่อ[0]"), "ผล = รายชื่อ[0]")

    def test_of_call_form(self):
        self.assertEqual(expr_py("ความยาวของรายชื่อ"), "ผล = len(รายชื่อ)")

    def test_command_word_cannot_be_a_value(self):
        with self.assertRaises(CompileError):
            compile_source("ให้ผลเป็นแสดงบวก1")

    def test_math_results(self):
        self.assertEqual(out("แสดง7หาร2,7หารลงตัว2,7เศษ2"), "3.5 3 1\n")


# ====================================================== เงื่อนไข
class TestConditions(unittest.TestCase):
    def test_if_elif_else(self):
        src = ("ให้เลขเป็น5\n"
               "ถ้าเลขมากกว่า10แล้ว\n"
               "    แสดง\"ใหญ่\"\n"
               "ไม่งั้นถ้าเลขมากกว่า3\n"
               "    แสดง\"กลาง\"\n"
               "ไม่งั้น\n"
               "    แสดง\"เล็ก\"\n")
        self.assertEqual(out(src), "กลาง\n")
        self.assertIn("elif เลข > 3:", py(src))

    def test_inline_if(self):
        self.assertEqual(out('ให้เลขเป็น9\nถ้าเลขมากกว่า5ให้แสดง"ใหญ่"'),
                         "ใหญ่\n")

    def test_inline_else(self):
        src = ('ให้เลขเป็น1\n'
               'ถ้าเลขมากกว่า5ให้แสดง"ใหญ่"\n'
               'ไม่งั้นให้แสดง"เล็ก"\n')
        self.assertEqual(out(src), "เล็ก\n")

    def test_nested_if(self):
        src = ("ให้เลขเป็น8\n"
               "ถ้าเลขมากกว่า5\n"
               "    ถ้าเลขเศษ2เท่ากับ0\n"
               "        แสดง\"คู่และใหญ่\"\n")
        self.assertEqual(out(src), "คู่และใหญ่\n")

    def test_else_without_if_fails(self):
        with self.assertRaises(CompileError):
            compile_source('ไม่งั้น\n    แสดง1')


# ====================================================== ลูป
class TestLoops(unittest.TestCase):
    def test_repeat(self):
        self.assertEqual(out('ทำซ้ำ3ครั้ง\n    แสดง"x"'), "x\nx\nx\n")

    def test_repeat_inline(self):
        self.assertEqual(out('ทำซ้ำ2ครั้งให้แสดง"y"'), "y\ny\n")

    def test_count(self):
        self.assertEqual(out("นับดัชนีจาก1ถึง3\n    แสดงดัชนี"), "1\n2\n3\n")

    def test_count_step_down(self):
        self.assertEqual(out("นับดัชนีจาก3ถึง1ทีละ-1\n    แสดงดัชนี"),
                         "3\n2\n1\n")

    def test_foreach(self):
        self.assertEqual(out("สำหรับแต่ละสมาชิกใน[1,2]\n    แสดงสมาชิก"),
                         "1\n2\n")

    def test_while(self):
        src = "ให้เลขเป็น3\nตราบใดที่เลขมากกว่า0\n    แสดงเลข\n    ลดเลขลง1\n"
        self.assertEqual(out(src), "3\n2\n1\n")

    def test_until(self):
        src = "ให้เลขเป็น0\nทำซ้ำจนกว่าเลขเท่ากับ3\n    แสดงเลข\n    เพิ่มเลข\n"
        self.assertEqual(out(src), "0\n1\n2\n")

    def test_break_continue(self):
        src = ("นับเลขจาก1ถึง10\n"
               "    ถ้าเลขเท่ากับ2ให้ข้าม\n"
               "    ถ้าเลขมากกว่า4ให้หยุด\n"
               "    แสดงเลข\n")
        self.assertEqual(out(src), "1\n3\n4\n")

    def test_append_into_list(self):
        src = ("ให้ตะกร้าเป็น[]\n"
               "นับดัชนีจาก1ถึง3\n"
               "    เพิ่มดัชนีคูณดัชนีเข้าไปในตะกร้า\n"
               "แสดงตะกร้า\n")
        self.assertEqual(out(src), "[1, 4, 9]\n")

    def test_break_outside_loop_fails(self):
        with self.assertRaises(CompileError):
            compile_source("หยุด")


# ====================================================== ฟังก์ชัน
class TestFunctions(unittest.TestCase):
    def test_define_and_call(self):
        src = ('ฟังก์ชันทักทายรับชื่อคน\n'
               '    แสดง"สวัสดี",ชื่อคน\n'
               'เรียกทักทายด้วย"ก"\n')
        self.assertEqual(out(src), "สวัสดี ก\n")

    def test_return_value(self):
        src = ("ฟังก์ชันคูณสองรับเลข\n    คืนค่าเลขคูณ2\nแสดงคูณสอง(21)\n")
        self.assertEqual(out(src), "42\n")

    def test_param_separators(self):
        for sep in [",", "และ"]:
            src = (f"ฟังก์ชันรวมเลขรับตัวแรก{sep}ตัวหลัง\n"
                   "    คืนค่าตัวแรกบวกตัวหลัง\n"
                   "แสดงรวมเลข(2,3)\n")
            self.assertEqual(out(src), "5\n", sep)

    def test_recursion(self):
        src = ("ฟังก์ชันแฟกรับเลข\n"
               "    ถ้าเลขน้อยกว่าหรือเท่ากับ1ให้คืนค่า1\n"
               "    คืนค่าเลขคูณแฟก(เลขลบ1)\n"
               "แสดงแฟก(5)\n")
        self.assertEqual(out(src), "120\n")

    def test_no_param_function(self):
        self.assertEqual(out('ฟังก์ชันเมนู\n    แสดง"เมนู"\nเรียกเมนู'), "เมนู\n")

    def test_named_form(self):
        src = ('ฟังก์ชันชื่อว่าทักทาย\n    แสดง"ไง"\nเรียกทักทาย\n')
        self.assertEqual(out(src), "ไง\n")

    def test_wrong_arity(self):
        src = ("ฟังก์ชันรวมเลขรับตัวแรกและตัวหลัง\n"
               "    คืนค่าตัวแรกบวกตัวหลัง\n"
               "แสดงรวมเลข(1)\n")
        with self.assertRaises(CompileError):
            compile_source(src)

    def test_unknown_function(self):
        with self.assertRaises(CompileError):
            compile_source("แสดงฟังก์ชันที่ไม่มีจริง(1)")

    def test_return_outside_function(self):
        with self.assertRaises(CompileError):
            compile_source("คืนค่า1")


# ====================================================== รับค่า / ฟังก์ชันสำเร็จรูป
class TestIOAndBuiltins(unittest.TestCase):
    def test_ask(self):
        self.assertEqual(out('ถาม"ชื่อ: "เก็บในชื่อคน\nแสดงชื่อคน', stdin="ก\n"),
                         "ชื่อ: ก\n")

    def test_ask_with_cast(self):
        src = 'ถาม"อายุ: "เก็บในอายุเป็นตัวเลข\nแสดงอายุบวก1'
        self.assertEqual(out(src, stdin="20\n"), "อายุ: 21\n")

    def test_builtins(self):
        cases = {
            "แสดงความยาว([1,2,3])": "3\n",
            "แสดงผลรวม([1,2,3])": "6\n",
            "แสดงค่าเฉลี่ย([1,2,3])": "2.0\n",
            "แสดงมากสุด(1,9,4)": "9\n",
            "แสดงรากที่สอง(16)": "4.0\n",
            'แสดงชนิด("ก")': "ข้อความ\n",
            'แสดงตัวเลข("42")บวก1': "43\n",
            'แสดงต่อข้อความ(["a","b"],"-")': "a-b\n",
            "แสดงเรียงลำดับ([3,1,2])": "[1, 2, 3]\n",
        }
        for src, expected in cases.items():
            self.assertEqual(out(src), expected, src)

    def test_builtin_not_shadowed_by_variable(self):
        self.assertEqual(out("ให้ผลรวมเป็น0\nเพิ่มผลรวมอีก5\nแสดงผลรวม"), "5\n")


# ====================================================== เขียนตามหลักไวยากรณ์ไทย
class TestThaiOrthography(unittest.TestCase):
    """เขียนเป็นประโยคภาษาไทยจริง ๆ ตามหลักการเขียน

        คะแนนเท่ากับ 10        ← คำในวลีเดียวกันเขียนติดกัน
                                  เว้นวรรคหน้าตัวเลข/ข้อความ

    ภาษาไทยไม่เว้นวรรคระหว่างคำในวลีเดียวกัน จะเว้นก็ต่อเมื่อขึ้นอนุประโยคใหม่
    หรือหน้าตัวเลข/เครื่องหมายคำพูด  นี่คือสไตล์หลักที่ภาษานี้ต้องรองรับ
    """

    def test_assign(self):
        for src in ("คะแนนเท่ากับ 10", "ให้คะแนนเป็น 10",
                    "กำหนดให้คะแนนคือ 10", "มีคะแนน 10"):
            with self.subTest(src=src):
                self.assertEqual(py(src), "คะแนน = 10")

    def test_print(self):
        self.assertEqual(out('ให้ยอดเงินเป็น 1\nแสดง "ค่า:", ยอดเงิน'),
                         "ค่า: 1\n")

    def test_expression_statement(self):
        src = ("ให้ราคาเป็น 50\n"
               "ให้จำนวนชิ้นเป็น 3\n"
               "ให้ราคารวมเป็นราคาคูณจำนวนชิ้น\n"
               "แสดงราคารวม")
        self.assertEqual(out(src), "150\n")

    def test_condition(self):
        src = ('ให้คะแนนเป็น 80\n'
               'ถ้าคะแนนมากกว่าหรือเท่ากับ 50\n'
               '    แสดง "ผ่าน"\n'
               'ไม่งั้น\n'
               '    แสดง "ไม่ผ่าน"')
        self.assertEqual(out(src), "ผ่าน\n")

    def test_inline_condition(self):
        self.assertEqual(
            out('คะแนนเท่ากับ 85\nถ้าคะแนนมากกว่าหรือเท่ากับ 80 แล้วแสดง "ผ่าน"'),
            "ผ่าน\n")

    def test_loops(self):
        self.assertEqual(out('ทำซ้ำ 3 ครั้ง\n    แสดง "ฮา"'), "ฮา\nฮา\nฮา\n")
        self.assertEqual(out("นับรอบจาก 1 ถึง 3\n    แสดงรอบ"), "1\n2\n3\n")
        self.assertEqual(
            out("ให้เงินเป็น 4\nตราบใดที่เงินมากกว่า 0\n"
                "    ลดเงินลง 2\nแสดงเงิน"), "0\n")

    def test_function(self):
        src = ("ฟังก์ชันบวกเลขรับตัวแรกและตัวหลัง\n"
               "    คืนค่าตัวแรกบวกตัวหลัง\n"
               "แสดงบวกเลข(2, 3)")
        self.assertEqual(out(src), "5\n")

    def test_collections(self):
        src = 'ให้เมนูเป็น ["ก", "ข"]\nแสดงความยาวของเมนู'
        self.assertEqual(out(src), "2\n")


# ====================================================== ตัด/หยิบชิ้นส่วน
class TestSlicing(unittest.TestCase):
    """ตัดข้อความและรายการได้ยืดหยุ่นแบบ Python โดยไม่ต้องรู้จักไวยากรณ์สไลซ์"""

    TEXT = 'ให้ชื่อเป็น "สมชาย"\n'
    LIST = "ให้เมนูเป็น [1,2,3,4]\n"

    def test_drop_from_the_end(self):
        self.assertEqual(out(self.TEXT + "แสดงตัดท้าย(ชื่อ)"), "สมชา\n")
        self.assertEqual(out(self.TEXT + "แสดงตัดท้าย(ชื่อ,2)"), "สมช\n")

    def test_drop_from_the_front(self):
        self.assertEqual(out(self.TEXT + "แสดงตัดตัวแรก(ชื่อ)"), "มชาย\n")
        self.assertEqual(out(self.TEXT + "แสดงตัดหน้า(ชื่อ,2)"), "ชาย\n")

    def test_first_and_last(self):
        self.assertEqual(out(self.TEXT + "แสดงตัวแรก(ชื่อ)"), "ส\n")
        self.assertEqual(out(self.TEXT + "แสดงตัวสุดท้าย(ชื่อ)"), "ย\n")

    def test_slice_range(self):
        self.assertEqual(out(self.TEXT + "แสดงตัดเอา(ชื่อ,1,3)"), "มช\n")

    def test_delete_characters(self):
        self.assertEqual(out(self.TEXT + 'แสดงลบตัวอักษร(ชื่อ,"ช")'), "สมาย\n")

    def test_count_occurrences(self):
        self.assertEqual(out(self.TEXT + 'แสดงนับจำนวน(ชื่อ,"ม")'), "1\n")

    def test_same_words_work_on_lists(self):
        """คำเดียวกันใช้กับรายการได้ด้วย — ยืดหยุ่นแบบ Python"""
        self.assertEqual(out(self.LIST + "แสดงตัดท้าย(เมนู)"), "[1, 2, 3]\n")
        self.assertEqual(out(self.LIST + "แสดงตัวแรก(เมนู)"), "1\n")
        self.assertEqual(out(self.LIST + "แสดงลบทุกตัวที่เป็น(เมนู,2)"),
                         "[1, 3, 4]\n")

    def test_zero_is_not_treated_as_everything(self):
        """ตัดท้าย 0 ตัว ต้องได้ของเดิม ไม่ใช่ค่าว่าง (กับดักของ seq[:-0])"""
        self.assertEqual(out(self.TEXT + "แสดงตัดท้าย(ชื่อ,0)"), "สมชาย\n")

    def test_negative_index_still_works(self):
        self.assertEqual(out(self.TEXT + "แสดงชื่อ[-1]"), "ย\n")

    def test_hint_points_at_the_right_tool(self):
        """เขียน ข้อความ ลบ เลข ต้องได้คำแนะนำที่ใช้งานได้จริง"""
        found = errors(self.TEXT + "แสดงชื่อลบ 1")
        self.assertEqual(len(found), 1)
        self.assertIn("ตัดท้าย", found[0].hint)

    def test_ask(self):
        self.assertEqual(py('ถามว่า "ชื่อ?" เก็บในชื่อ'),
                         'ชื่อ = input("ชื่อ?")')

    def test_inc_dec(self):
        self.assertEqual(py("ให้คะแนนเป็น 1\nเพิ่มคะแนนอีก 10").splitlines()[-1],
                         "คะแนน += 10")
        self.assertEqual(py("ให้เงินเป็น 1\nลดเงินลง 45").splitlines()[-1],
                         "เงิน -= 45")

    def test_split_clauses(self):
        self.assertEqual(
            out("ให้เงินเป็น 500 แล้วลดเงินลง 45 แล้วแสดงเงิน"), "455\n")

    def test_have_with_unit_and_clauses(self):
        self.assertEqual(
            out("มีเงิน 500 บาท แล้วลดเงินลง 45 แล้วแสดงเงิน"), "455\n")

    def test_spacing_before_number_is_optional(self):
        """เว้นวรรคหน้าตัวเลขหรือไม่เว้น ต้องได้โค้ดเดียวกันเป๊ะ"""
        pairs = [("ให้ราคาเป็น250", "ให้ราคาเป็น 250"),
                 ("มีเงิน500บาท", "มีเงิน 500 บาท"),
                 ("เพิ่มคะแนนอีก10", "เพิ่มคะแนนอีก 10"),
                 ("ทำซ้ำ3ครั้ง\n    แสดง1", "ทำซ้ำ 3 ครั้ง\n    แสดง 1")]
        for tight, spaced in pairs:
            with self.subTest(spaced=spaced):
                self.assertEqual(py(tight), py(spaced))


# ====================================================== หน่วยและลักษณนาม
class TestUnits(unittest.TestCase):
    """หน่วยที่ตามหลังตัวเลขต้องถูกตัดทิ้ง แต่ต้องไม่แตะชื่อตัวแปร"""

    def test_unit_after_number_dropped(self):
        self.assertEqual(py("ให้ราคาเป็น50บาท"), "ราคา = 50")

    def test_unit_with_spaces(self):
        self.assertEqual(py("ให้เวลาเป็น 90 นาที"), "เวลา = 90")

    def test_decimal_with_unit(self):
        self.assertEqual(py("ให้น้ำหนักเป็น52.5กิโลกรัม"), "น้ำหนัก = 52.5")

    def test_unit_word_still_usable_as_name(self):
        """ให้ชิ้นเป็น5 — "ชิ้น" ไม่ได้ตามหลังตัวเลข จึงเป็นชื่อตัวแปรตามปกติ"""
        self.assertEqual(py("ให้ชิ้นเป็น5"), "ชิ้น = 5")
        self.assertEqual(out("ให้คนเป็น3\nแสดงคน"), "3\n")

    def test_times_keyword_is_not_a_unit(self):
        """"ครั้ง" ต้องยังเป็นคีย์เวิร์ดของ ทำซ้ำ ไม่ใช่หน่วยที่ถูกตัดทิ้ง"""
        self.assertEqual(out('ทำซ้ำ2ครั้ง\n    แสดง"ฮา"'), "ฮา\nฮา\n")

    def test_percent_is_still_modulo(self):
        self.assertEqual(out("แสดง10 % 3"), "1\n")

    def test_unit_does_not_fragment_names(self):
        """"ตัว" เป็นหน่วย แต่ "ตัวแรก" ต้องไม่ถูกซอยเป็น ตัว|แรก"""
        self.assertEqual(out("ให้ตัวแรกเป็น9\nแสดงตัวแรก"), "9\n")

    def test_multisyllable_unit_not_chopped(self):
        """"คะแนน" เคยถูกซอยเป็น "คะ"(คำเสริม) + "แนน" """
        self.assertEqual(out("มีคะแนน 80 คะแนน\nแสดงคะแนน"), "80\n")


# ====================================================== ประโยคบอกเล่า "มี"
class TestHaveStatement(unittest.TestCase):

    def test_have_with_unit(self):
        self.assertEqual(py("มีเงิน 0 บาท"), "เงิน = 0")

    def test_have_without_space(self):
        self.assertEqual(py("มีเงิน100บาท"), "เงิน = 100")

    def test_have_with_be(self):
        self.assertEqual(py("มีเงินเป็น50"), "เงิน = 50")

    def test_have_synonyms(self):
        for src in ("มีนักเรียน 30 คน", "มีทั้งหมดนักเรียน30คน",
                    "เริ่มด้วยนักเรียน30คน"):
            with self.subTest(src=src):
                self.assertEqual(py(src), "นักเรียน = 30")

    def test_have_expression(self):
        self.assertEqual(out("มีราคา45บาท\nมียอดรวมราคาคูณ3\nแสดงยอดรวม"),
                         "135\n")

    def test_contains_builtin_not_broken_by_have(self):
        """"มีอยู่" ต้องยังเป็นฟังก์ชันสำเร็จรูป ไม่ถูกซอยเป็น "มี" + "อยู่" """
        self.assertEqual(out('แสดงมีอยู่([1,2,3],2)'), "True\n")


# ====================================================== การตัดประโยค
class TestSentenceSplitting(unittest.TestCase):
    """หนึ่งบรรทัดมีได้หลายคำสั่ง"""

    def test_split_on_semicolon(self):
        self.assertEqual(out("ให้เงินเป็น0; แสดงเงิน"), "0\n")

    def test_split_on_laeo(self):
        self.assertEqual(out("ให้เงินเป็น0 แล้วแสดงเงิน"), "0\n")

    def test_split_no_spaces_at_all(self):
        self.assertEqual(out("มีเงิน100บาทแล้วลดเงินลง45แล้วแสดงเงิน"), "55\n")

    def test_split_on_other_separators(self):
        self.assertEqual(out("ให้aเป็น2 จากนั้น แสดงa"), "2\n")
        self.assertEqual(out("ให้aเป็น2 หลังจากนั้น แสดงa"), "2\n")

    def test_many_statements_one_line(self):
        src = ("ให้aเป็น1 แล้วให้bเป็น2 แล้วให้cเป็น3 "
               "แล้วให้dเป็น4 แล้วให้eเป็น5 แล้วแสดงaบวกe")
        self.assertEqual(out(src), "6\n")

    def test_split_without_separator_word(self):
        """ตัดที่คำขึ้นต้นคำสั่งได้ แม้ไม่มีตัวคั่น"""
        self.assertEqual(out('แสดง"ก" แสดง"ข"'), "ก\nข\n")

    def test_split_inside_block(self):
        src = 'ถ้าจริง\n    ให้aเป็น7 แล้ว แสดงa'
        self.assertEqual(out(src), "7\n")

    def test_append_and_show(self):
        src = "มีตะกร้าเป็น[] แล้ว เพิ่ม5เข้าไปในตะกร้า แล้ว แสดงตะกร้า"
        self.assertEqual(out(src), "[5]\n")

    def test_name_learned_within_the_same_line(self):
        """ประโยคหลังต้องตัดคำชื่อที่ประโยคแรกเพิ่งประกาศได้ถูกต้อง

        "รายการโปรด" จะถูกตัดผิดเป็น "ในรายการ|โปรด" ถ้าไม่เรียนรู้ชื่อ
        จากประโยคแรกก่อน
        """
        src = ('มีรายการโปรดเป็น[] แล้ว เพิ่ม"ลาเต้"เข้าไปในรายการโปรด'
               ' แล้ว แสดงรายการโปรด')
        self.assertEqual(out(src), "['ลาเต้']\n")

    def test_single_statement_always_wins(self):
        """"แล้ว" ในรูปประโยคเงื่อนไขต้องยังเป็น THEN ไม่ใช่ตัวคั่นประโยค"""
        self.assertEqual(py('ถ้า5มากกว่า3แล้วแสดง"ใช่"'),
                         'if 5 > 3:\n    print("ใช่")')

    def test_block_opener_cannot_be_split_target(self):
        """คำสั่งที่ต้องมีบล็อกของตัวเอง ห้ามถูกตัดมาต่อท้ายบรรทัด

        ต้องฟ้อง ไม่ใช่เงียบ ๆ สร้างบล็อกที่ไม่มีเนื้อใน
        """
        for src in ('แสดง"ก" แล้ว ทำซ้ำ2ครั้ง', 'แสดง"ก" แล้ว ถ้า5มากกว่า3'):
            with self.subTest(src=src):
                self.assertTrue(codes(src), "ควรรายงานข้อผิดพลาด")


# ====================================================== คำสงวน vs ชื่อที่ตั้งเอง
class TestReservedWords(unittest.TestCase):
    """เส้นแบ่งระหว่าง "คำของภาษา" กับ "ชื่อที่ผู้ใช้ตั้ง" """

    def test_soft_keywords_can_be_names(self):
        """คำเชื่อมที่คนไทยเอาไปตั้งชื่อบ่อย ต้องตั้งได้ — ตำแหน่งเป็นตัวตัดสิน"""
        for word in ("รอบ", "ใน", "ถึง", "ด้วย", "จาก", "ครั้ง"):
            with self.subTest(word=word):
                self.assertEqual(out(f"ให้{word}เป็น 3\nแสดง{word}"), "3\n")

    def test_builtins_can_be_shadowed(self):
        self.assertEqual(out("ให้ยอดรวมเป็น 3\nแสดงยอดรวม"), "3\n")

    def test_hard_keywords_are_rejected_not_swallowed(self):
        """ตั้งชื่อชนตัวดำเนินการ/คำสั่ง ต้อง *ฟ้อง*

        ห้ามเงียบแล้วกลืนคีย์เวิร์ดเข้าไปเป็นชื่อ (ให้บวก = 3)
        เพราะผู้ใช้จะไม่มีทางรู้ว่าเกิดอะไรขึ้น
        """
        for word in ("บวก", "คูณ", "แสดง", "ถ้า"):
            with self.subTest(word=word):
                found = errors(f"ให้{word}เป็น 3")
                self.assertEqual([d.code for d in found],
                                 [Code.RESERVED_AS_NAME])
                self.assertIn(word, found[0].message)

    def test_names_containing_keywords_are_fine(self):
        """ชื่อที่มีคำสงวนซ่อนอยู่ข้างใน ต้องไม่ถูกแตะ"""
        for name in ("ผลบวก", "นับถอยหลัง", "มีเงิน", "ทำงาน", "ตัวแรก",
                     "ราคารวม", "ลดราคา", "เก็บของ"):
            with self.subTest(name=name):
                self.assertEqual(errors(f"ให้{name}เป็น 3\nแสดง{name}"), [])


# ====================================================== ตัวตรวจชนิดข้อมูล
def errors(src):
    return [d for d in check_source(src, "<test>") if d.severity == "error"]


def check_source_with(src, predefined):
    """ตรวจโดยประกาศชื่อ (และชนิด) ไว้ล่วงหน้า — จำลองโหมดโต้ตอบ"""
    try:
        return compile_source(src, "<test>", predefined).diagnostics
    except CompileError as err:
        return err.bag


class TestTypeChecker(unittest.TestCase):
    """จับการใช้ผิดชนิดตั้งแต่ตอนคอมไพล์ แทนที่จะไประเบิดตอนรัน"""

    def test_string_arithmetic_rejected(self):
        cases = [
            ('ให้ชื่อเป็น "สมชาย"\nแสดงชื่อลบ 1', Code.BAD_OPERAND),
            ('ให้ชื่อเป็น "ก"\nแสดงชื่อบวก 1', Code.BAD_OPERAND),
            ('ให้ชื่อเป็น "ก"\nแสดงลบชื่อ', Code.BAD_OPERAND),
            ('ให้เมนูเป็น [1]\nแสดง 10 หารเมนู', Code.BAD_OPERAND),
        ]
        for src, code in cases:
            with self.subTest(src=src):
                self.assertEqual([d.code for d in errors(src)], [code])

    def test_comparing_different_types_rejected(self):
        src = 'ให้ชื่อเป็น "ก"\nถ้าชื่อมากกว่า 5\n    แสดง 1'
        self.assertEqual([d.code for d in errors(src)], [Code.BAD_OPERAND])

    def test_indexing_a_number_rejected(self):
        src = "ให้เลขเป็น 5\nแสดงเลข[0]"
        self.assertEqual([d.code for d in errors(src)], [Code.NOT_INDEXABLE])

    def test_builtin_argument_type_checked(self):
        for src in ("ให้เลขเป็น 5\nแสดงความยาวของเลข",
                    'ให้ชื่อเป็น "ก"\nแสดงผลรวม(ชื่อ)'):
            with self.subTest(src=src):
                self.assertEqual([d.code for d in errors(src)],
                                 [Code.BAD_ARGUMENT_TYPE])

    # ---------------------------------------------------------- ต้องไม่ฟ้องผิด
    def test_valid_python_semantics_allowed(self):
        """สิ่งที่ Python ทำได้จริง ต้องไม่ถูกฟ้อง"""
        ok = [
            'ให้กเป็น "ก"\nให้ขเป็น "ข"\nแสดงกบวกข',        # ต่อข้อความ
            'ให้กเป็น "ก"\nแสดงกคูณ 3',                      # ทำซ้ำข้อความ
            "ให้กเป็น [1]\nให้ขเป็น [2]\nแสดงกบวกข",        # ต่อรายการ
            "ให้กเป็นจริง\nแสดงกบวก 1",                      # bool คำนวณได้
            'ให้กเป็น "abc"\nแสดงก[0]',                      # ดัชนีข้อความ
            'ให้กเป็น {"x":1}\nแสดงก["x"]',                  # ดัชนีพจนานุกรม
            "ให้กเป็น 1.5\nถ้ากมากกว่า 1\n    แสดง 1",       # ทศนิยม vs เต็ม
        ]
        for src in ok:
            with self.subTest(src=src):
                self.assertEqual(errors(src), [])

    def test_unknown_types_stay_silent(self):
        """เดาชนิดไม่ได้ = ต้องเงียบ ไม่ใช่เดาสุ่มแล้วฟ้อง"""
        quiet = [
            # พารามิเตอร์ไม่มีชนิด
            "ฟังก์ชันทดสอบรับค่า\n    แสดงค่าลบ 1\nเรียกทดสอบด้วย 5",
            # ตัวแปรถูกกำหนดค่าสองชนิด -> ไม่ทราบ
            'ให้กเป็น 1\nให้กเป็น "ข"\nแสดงกบวก "ค"',
            # ฟังก์ชันคืนหลายชนิด -> ไม่ทราบ
            'ฟังก์ชันฟรับก\n    ถ้ากมากกว่า 1\n        คืนค่า "ข"\n'
            "    คืนค่า 1\nแสดงฟ(2)บวก 1",
            # สมาชิกในรายการไม่ตามชนิด
            "ให้เมนูเป็น [1,2]\nสำหรับแต่ละตัวในเมนู\n    แสดงตัวบวก 1",
        ]
        for src in quiet:
            with self.subTest(src=src):
                self.assertEqual(errors(src), [])

    def test_inference_through_ask_and_calls(self):
        self.assertEqual(
            errors("ถามว่า \"อายุ\" เก็บในอายุเป็นตัวเลข\nแสดงอายุบวก 1"), [])
        self.assertEqual(
            errors("ฟังก์ชันสองรับก\n    คืนค่ากคูณ 2\nแสดงสอง(3)บวก 1"), [])

    def test_user_variable_shadows_builtin_signature(self):
        """ตั้งชื่อตัวแปรทับฟังก์ชันสำเร็จรูปได้ ต้องไม่เอาลายเซ็นไปตรวจ"""
        self.assertEqual(errors("ให้ยอดรวมเป็น 5\nแสดงยอดรวมบวก 1"), [])

    def test_repl_style_predefined_types(self):
        """โหมดโต้ตอบส่งชนิดที่รู้แน่นอนมาให้ได้ (เพราะมีค่าจริงอยู่ในมือ)

        ต้องตรวจได้เข้มเท่ากับตอนคอมไพล์ทั้งไฟล์ ไม่ใช่ปล่อยไปพังตอนรัน
        """
        from thpro.compiler.typecheck import type_of_value

        self.assertEqual(type_of_value("ก"), "ข้อความ")
        self.assertEqual(type_of_value(5), "จำนวนเต็ม")
        self.assertEqual(type_of_value([1]), "รายการ")
        self.assertIsNone(type_of_value(object()))

        bag = check_source_with(("แสดงชื่อลบ 1"), {"ชื่อ": "ข้อความ"})
        self.assertEqual([d.code for d in bag.errors], [Code.BAD_OPERAND])
        # ไม่บอกชนิด = ไม่ทราบ = ต้องเงียบ
        self.assertEqual(check_source_with("แสดงชื่อลบ 1", {"ชื่อ"}).errors, [])

    def test_error_points_at_the_right_line(self):
        src = 'แสดง "เริ่ม"\nให้ชื่อเป็น "ก"\nแสดงชื่อลบ 1'
        found = errors(src)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].line, 3)


# ====================================================== ชั้น NLP
class TestNLPLayer(unittest.TestCase):
    def test_typo_repair(self):
        program = compile_source('แสด "ก"')
        self.assertEqual(program.python.strip().splitlines()[-1], 'print("ก")')
        self.assertTrue(any("แสดง" in w for w in program.warnings))

    def test_undefined_variable_suggestion(self):
        with self.assertRaises(CompileError) as ctx:
            compile_source("ให้ ราคา เป็น 1\nแสดง ราค")
        self.assertIn("ราคา", ctx.exception.bag.errors[0].hint)

    def test_predefined_names_for_repl(self):
        with self.assertRaises(CompileError):
            compile_source("แสดงเลข")
        self.assertEqual(
            compile_source("แสดงเลข", predefined={"เลข"}).python
            .strip().splitlines()[-1], "print(เลข)")


# ====================================================== ข้อผิดพลาดขณะทำงาน
class TestRuntimeErrors(unittest.TestCase):
    def test_divide_by_zero_maps_to_thai_line(self):
        src = "ให้ตัวตั้งเป็น1\nให้ตัวหารเป็น0\nแสดงตัวตั้งหารตัวหาร"
        with self.assertRaises(RuntimeThaiError) as ctx:
            out(src)
        self.assertEqual(ctx.exception.line, 3)
        self.assertIn("หารด้วยศูนย์", ctx.exception.message)

    def test_index_error(self):
        with self.assertRaises(RuntimeThaiError) as ctx:
            out("ให้รายการเป็น[1]\nแสดงรายการ[5]")
        self.assertEqual(ctx.exception.line, 2)


# ====================================================== ตัวอย่างทั้งหมด
class TestExampleFiles(unittest.TestCase):
    def test_all_examples_compile(self):
        folder = Path(__file__).resolve().parent.parent / "examples"
        files = sorted(folder.glob("*.th"))
        self.assertGreater(len(files), 0, "ไม่พบไฟล์ตัวอย่าง")
        for path in files:
            with self.subTest(file=path.name):
                compile_source(path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
