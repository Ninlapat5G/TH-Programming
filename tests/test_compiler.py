# -*- coding: utf-8 -*-
"""
ชุดทดสอบส่วนที่เป็น "คอมไพเลอร์" โดยเฉพาะ
    ระบบรายงานข้อผิดพลาด · การกู้คืน · ตารางสัญลักษณ์ ·
    ตัวปรับให้เหมาะที่สุด · ตัวจัดรูปแบบ
"""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from thpro import compile_source, check_source                    # noqa: E402
from thpro.pipeline import run                                    # noqa: E402
from thpro.errors import CompileError                             # noqa: E402
from thpro.diagnostics import Code, DiagnosticBag, ERROR          # noqa: E402
from thpro.compiler.symbols import SymbolTable, FUNCTION          # noqa: E402
from thpro.cli import _format                                     # noqa: E402


def codes(src):
    """รหัสข้อผิดพลาด/คำเตือนทั้งหมดที่คอมไพเลอร์รายงาน"""
    return [d.code for d in check_source(src, "<test>")]


def py(src, optimize=0):
    program = compile_source(src, "<test>", optimize_level=optimize)
    lines = program.python.splitlines()
    start = min(program.linemap) - 1 if program.linemap else 0
    return "\n".join(l for l in lines[start:] if l.strip()).strip()


def out(src):
    program = compile_source(src, "<test>")
    buf = io.StringIO()
    with redirect_stdout(buf):
        run(program, show_warnings=False, stream=io.StringIO())
    return buf.getvalue()


# ====================================================== ระบบรายงานข้อผิดพลาด
class TestDiagnostics(unittest.TestCase):
    def test_reports_every_error_in_one_pass(self):
        src = "ให้ราคาเป็น100\nแสดงราค\nแสดงยอดขาย\nหยุด\n"
        found = codes(src)
        self.assertEqual(found.count(Code.UNDEFINED_NAME), 2)
        self.assertIn(Code.BREAK_OUTSIDE_LOOP, found)

    def test_syntax_error_recovery_keeps_going(self):
        src = "ฟังก์ชันบวกรับก,ข\n    คืนค่า1\nหยุด\n"
        found = codes(src)
        self.assertIn(Code.RESERVED_AS_NAME, found)
        self.assertIn(Code.BREAK_OUTSIDE_LOOP, found)

    def test_error_carries_line_column_and_caret(self):
        with self.assertRaises(CompileError) as ctx:
            compile_source("ให้ราคาเป็น1\nแสดงราค", "<test>")
        err = ctx.exception.bag.errors[0]
        self.assertEqual(err.line, 2)
        self.assertEqual(err.col, 4)
        self.assertIn("^", err.render())

    def test_error_message_includes_source_line(self):
        with self.assertRaises(CompileError) as ctx:
            compile_source("แสดงตัวที่ไม่มี", "<test>")
        self.assertIn("แสดงตัวที่ไม่มี", ctx.exception.render())

    def test_unused_variable_warning(self):
        self.assertIn(Code.UNUSED_VARIABLE, codes("ให้ของเหลือเป็น5"))

    def test_unreachable_code_warning(self):
        src = ('ฟังก์ชันลองดูรับเลข\n'
               '    คืนค่าเลข\n'
               '    แสดง"ไม่มีทางถึง"\n'
               'แสดงลองดู(1)\n')
        self.assertIn(Code.UNREACHABLE_CODE, codes(src))

    def test_duplicate_function_warning(self):
        src = ("ฟังก์ชันทำงาน\n    แสดง1\n"
               "ฟังก์ชันทำงาน\n    แสดง2\n"
               "เรียกทำงาน\n")
        self.assertIn(Code.DUPLICATE_FUNCTION, codes(src))

    def test_dangling_else(self):
        self.assertIn(Code.DANGLING_ELSE, codes("ไม่งั้น\n    แสดง1"))

    def test_duplicate_else(self):
        src = ("ถ้าจริง\n    แสดง1\n"
               "ไม่งั้น\n    แสดง2\n"
               "ไม่งั้น\n    แสดง3\n")
        self.assertIn(Code.DUPLICATE_ELSE, codes(src))

    def test_empty_block(self):
        self.assertIn(Code.EMPTY_BLOCK, codes("ถ้าจริง"))

    def test_wrong_arity_points_at_declaration(self):
        src = ("ฟังก์ชันรวมเลขรับตัวแรกและตัวหลัง\n"
               "    คืนค่าตัวแรกบวกตัวหลัง\n"
               "แสดงรวมเลข(1)\n")
        with self.assertRaises(CompileError) as ctx:
            compile_source(src, "<test>")
        err = ctx.exception.bag.errors[0]
        self.assertEqual(err.code, Code.WRONG_ARITY)
        self.assertIn("บรรทัด 1", err.hint)

    def test_user_name_beats_builtin_name(self):
        # "ยอดรวม" เป็นชื่อฟังก์ชันสำเร็จรูป แต่ผู้ใช้ตั้งเป็นตัวแปรได้
        src = "ให้ยอดรวมเป็น10บวก5\nแสดงยอดรวม"
        self.assertEqual(out(src), "15\n")
        self.assertNotIn(Code.UNUSED_VARIABLE, codes(src))

    def test_user_function_beats_builtin_function(self):
        src = ("ฟังก์ชันผลรวมรับรายการ\n"
               "    คืนค่า999\n"
               "แสดงผลรวม([1,2,3])\n")
        self.assertEqual(out(src), "999\n")

    def test_check_source_never_raises(self):
        bag = check_source("อะไรก็ไม่รู้ 12 @@@", "<test>")
        self.assertTrue(bag.has_errors())

    def test_bag_summary(self):
        bag = DiagnosticBag("แสดง1", "<test>")
        bag.error(Code.UNDEFINED_NAME, "ทดสอบ", line=1)
        bag.warning(Code.UNUSED_VARIABLE, "ทดสอบ", line=1)
        self.assertEqual(bag.summary(), "1 ข้อผิดพลาด · 1 คำเตือน")
        self.assertEqual(len(bag.render(only=ERROR).splitlines()), 3)


# ====================================================== ตัวปรับให้เหมาะที่สุด
class TestOptimizer(unittest.TestCase):
    def test_constant_folding(self):
        self.assertEqual(py("ให้วินาทีเป็น60คูณ60คูณ24\nแสดงวินาที",
                            optimize=1).splitlines()[0], "วินาที = 86400")

    def test_algebraic_simplification(self):
        src = "ให้ฐานเป็น1\nให้ผลเป็นฐานบวก0คูณ1\nแสดงผล"
        self.assertEqual(py(src, optimize=1).splitlines()[1], "ผล = ฐาน")

    def test_dead_branch_removed(self):
        src = 'ถ้าเท็จ\n    แสดง"ไม่ทำ"\nไม่งั้น\n    แสดง"ทำ"'
        self.assertEqual(py(src, optimize=1), 'print("ทำ")')

    def test_zero_repeat_removed(self):
        src = 'ทำซ้ำ0ครั้ง\n    แสดง"ไม่ทำ"\nแสดง"จบ"'
        self.assertEqual(py(src, optimize=1), 'print("จบ")')

    def test_result_is_unchanged_by_optimizer(self):
        src = ("ให้ฐานเป็น2ยกกำลัง10\n"
               "ให้รวมเป็นฐานบวก0\n"
               "ถ้าจริง\n    แสดงรวม\n")
        self.assertEqual(out(src), "1024\n")

    def test_division_by_zero_is_not_folded(self):
        # ต้องไม่พับ เพราะจะทำให้คอมไพเลอร์พังแทนที่จะฟ้องตอนรัน
        self.assertIn("1 / 0", py("ให้ผลเป็น1หาร0\nแสดงผล", optimize=1))

    def test_stats_reported(self):
        program = compile_source("ให้วินาทีเป็น60คูณ60\nแสดงวินาที", "<test>")
        self.assertGreaterEqual(program.stats["พับค่าคงที่"], 1)


# ====================================================== ตารางสัญลักษณ์
class TestSymbolTable(unittest.TestCase):
    def test_scope_chain(self):
        table = SymbolTable()
        table.declare("นอก")
        table.enter("ฟังก์ชันหนึ่ง")
        table.declare("ใน")
        self.assertIsNotNone(table.lookup("นอก"))
        self.assertIsNotNone(table.lookup("ใน"))
        table.leave()
        self.assertIsNone(table.lookup("ใน"))

    def test_function_arity_recorded(self):
        table = SymbolTable()
        table.declare_global("รวมเลข", FUNCTION, 1, arity=2)
        self.assertEqual(table.lookup("รวมเลข").arity, 2)

    def test_read_counter(self):
        table = SymbolTable()
        table.declare("ตัวนับ")
        self.assertFalse(table.lookup("ตัวนับ").used)
        table.mark_read("ตัวนับ")
        self.assertTrue(table.lookup("ตัวนับ").used)

    def test_predefined_names(self):
        table = SymbolTable({"มีอยู่ก่อน"})
        self.assertIsNotNone(table.lookup("มีอยู่ก่อน"))


# ====================================================== ตัวจัดรูปแบบ
class TestFormatter(unittest.TestCase):
    def test_indent_normalised(self):
        messy = "ถ้าจริง\n  แสดง1\n     แสดง2\n"
        self.assertEqual(_format(messy), "ถ้าจริง\n    แสดง1\n        แสดง2\n")

    def test_trailing_space_removed(self):
        self.assertEqual(_format("แสดง1   \n"), "แสดง1\n")

    def test_already_formatted_unchanged(self):
        good = "ถ้าจริง\n    แสดง1\n"
        self.assertEqual(_format(good), good)

    def test_dedent_back_to_outer_level(self):
        messy = "ถ้าจริง\n   แสดง1\nแสดง2\n"
        self.assertEqual(_format(messy), "ถ้าจริง\n    แสดง1\nแสดง2\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
