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
from thpro.compiler.symbols import SymbolTable, FUNCTION          # noqa: E402
from thpro.cli import _format                                     # noqa: E402


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


def expr_py(expression, names=("ก", "ข", "ค", "รายชื่อ")):
    setup = "".join(f"ให้ {n} เป็น 1\n" for n in names)
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
        self.assertEqual(expr_py("ก[0]"), "ผล = ก[0]")

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
