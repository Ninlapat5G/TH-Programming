# -*- coding: utf-8 -*-
"""
ชุดทดสอบส่วนที่เป็น "คอมไพเลอร์" โดยเฉพาะ
    ระบบรายงานข้อผิดพลาด · การกู้คืน · ตารางสัญลักษณ์ ·
    ตัวปรับให้เหมาะที่สุด · ตัวจัดรูปแบบ
"""

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from thprog import compile_source, check_source                    # noqa: E402
from thprog.pipeline import run, new_segmenter                     # noqa: E402
from thprog.errors import CompileError                             # noqa: E402
from thprog.diagnostics import Code, DiagnosticBag, ERROR          # noqa: E402
from thprog.compiler import sentence                               # noqa: E402
from thprog.compiler.normalizer import normalize                   # noqa: E402
from thprog.compiler.symbols import SymbolTable, FUNCTION          # noqa: E402
from thprog.compiler.tokenizer import candidates, tokenize         # noqa: E402
from thprog.compiler.wordseg import KNOWN_COST                     # noqa: E402
from thprog.cli import _format, main as cli_main                   # noqa: E402


def codes(src):
    """รหัสข้อผิดพลาด/คำเตือนทั้งหมดที่คอมไพเลอร์รายงาน"""
    return [d.code for d in check_source(src, "<test>")]


def py(src, optimize=0):
    program = compile_source(src, "<test>", optimize_level=optimize)
    lines = program.python.splitlines()
    start = min(program.linemap) - 1 if program.linemap else 0
    return "\n".join(l for l in lines[start:] if l.strip()).strip()


def shell_notes(src):
    """ข้อสังเกตที่ได้เมื่อโค้ดมาจากอาร์กิวเมนต์ของเชลล์  thprog "โค้ด" """
    bag = check_source(src, "<คำสั่ง>", shell_arg=True)
    return [d for d in bag if d.code == Code.SHELL_ATE_QUOTES]


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


# ====================================================== ผลลัพธ์ที่เครื่องอ่านได้
class TestMachineReadableOutput(unittest.TestCase):
    """editor และ CI ต้อง parse ผลการตรวจได้ ไม่ใช่อ่านข้อความสวย ๆ อย่างเดียว"""

    def test_json_shape(self):
        bag = check_source('ให้ชื่อเป็น "ก"\nแสดงชื่อลบ 1', "<test>")
        data = json.loads(bag.to_json())
        self.assertEqual(data["ok"], False)
        self.assertEqual(data["errors"], 1)
        self.assertEqual(data["file"], "<test>")
        item = data["diagnostics"][0]
        self.assertEqual(item["code"], Code.BAD_OPERAND)
        self.assertEqual(item["severity"], "error")
        self.assertEqual(item["line"], 2)
        self.assertIsNotNone(item["column"])

    def test_json_columns_are_one_based(self):
        """ภายในเก็บคอลัมน์เริ่มที่ 0 แต่ที่ส่งออกต้องเริ่มที่ 1"""
        bag = check_source('ให้ชื่อเป็น "ก"\nแสดงชื่อลบ 1', "<test>")
        item = bag.sorted_items()[0]
        self.assertEqual(item.to_dict()["column"], item.col + 1)

    def test_json_is_valid_when_clean(self):
        data = json.loads(check_source('แสดง "ก"', "<test>").to_json())
        self.assertEqual(data["ok"], True)
        self.assertEqual(data["diagnostics"], [])

    def test_json_is_utf8_readable_thai(self):
        """ต้องไม่ escape เป็น \\uXXXX มิฉะนั้นคนอ่าน log ไม่รู้เรื่อง"""
        self.assertIn("ข้อความ",
                      check_source('ให้ชื่อเป็น "ก"\nแสดงชื่อลบ 1',
                                   "<test>").to_json())


# ====================================================== ตัวตัดประโยค
class TestSentenceModule(unittest.TestCase):
    """ทดสอบ sentence.cut_points ตรง ๆ — ชั้นที่บอกว่า "ตัดตรงไหนได้บ้าง" """

    @staticmethod
    def _tokens(src):
        lines = tokenize(src, "<test>")
        return normalize(next(candidates(lines[0], new_segmenter())))

    def test_separator_is_dropped(self):
        toks = self._tokens("ให้aเป็น1 แล้ว แสดงa")
        points = sentence.cut_points(toks)
        self.assertTrue(any(drop == 1 for _i, drop in points),
                        "ตัวคั่น 'แล้ว' ต้องถูกทิ้ง")

    def test_command_starter_is_kept(self):
        toks = self._tokens('แสดง"ก" แสดง"ข"')
        points = sentence.cut_points(toks)
        self.assertIn(0, [drop for _i, drop in points],
                      "คำสั่ง 'แสดง' ต้องถูกเก็บไว้เป็นส่วนของประโยคถัดไป")

    def test_no_boundary_in_a_plain_statement(self):
        self.assertEqual(sentence.cut_points(self._tokens("ให้aเป็น1")), [])

    def test_position_zero_is_never_a_boundary(self):
        toks = self._tokens('แสดง"ก" แสดง"ข"')
        self.assertTrue(all(i > 0 for i, _drop in sentence.cut_points(toks)))

    def test_separator_ranks_before_starter(self):
        toks = self._tokens('ให้aเป็น1 แล้ว แสดงa')
        points = sentence.cut_points(toks)
        if len(points) > 1:
            self.assertEqual(points[0][1], 1, "ตัวคั่นชัดเจนต้องมาก่อน")


# ====================================================== พจนานุกรมตัดคำ
class TestSegmenterDictionary(unittest.TestCase):

    def test_units_that_would_fragment_are_added(self):
        """"คะแนน" ถูกซอยเป็น "คะ" + "แนน" จึงต้องถูกเติมเข้าพจนานุกรม"""
        self.assertIn("คะแนน", new_segmenter().words)

    def test_units_that_stand_alone_are_not_added(self):
        """"ตัว" ยืนได้อยู่แล้ว ห้ามเติม มิฉะนั้น "ตัวแรก" จะถูกซอย"""
        words = new_segmenter().words
        for unit in ("ตัว", "คน", "บาท", "วัน"):
            with self.subTest(unit=unit):
                self.assertNotIn(unit, words)

    def test_learned_name_beats_unit(self):
        seg = new_segmenter()
        seg.learn("คะแนน")
        self.assertEqual(seg.cost_of("คะแนน", 3), KNOWN_COST)


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


# ====================================================== รับซอร์สจากหลายทาง
class TestCommandLineSource(unittest.TestCase):
    """thprog -c "โค้ด"  และการรับโค้ดทาง stdin — เทียบเท่า python -c"""

    def _run(self, argv, stdin=None):
        buf, saved_in, saved_out = io.StringIO(), sys.stdin, sys.stdout
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with redirect_stdout(buf):
                status = cli_main(argv)
        finally:
            sys.stdin, sys.stdout = saved_in, saved_out
        return status, buf.getvalue()

    def test_dash_c_runs_code(self):
        status, output = self._run(["-c", 'แสดง "สวัสดี"'])
        self.assertEqual(status, 0)
        self.assertEqual(output, "สวัสดี\n")

    def test_dash_c_multiline(self):
        status, output = self._run(["-c", "ให้ ก เป็น 2\nทำซ้ำ ก ครั้ง\n    แสดง 1"])
        self.assertEqual(status, 0)
        self.assertEqual(output, "1\n1\n")

    def test_dash_c_after_subcommand(self):
        status, output = self._run(["show", "-c", "แสดง 1"])
        self.assertEqual(status, 0)
        self.assertIn("print(1)", output)

    def test_stdin_source(self):
        status, output = self._run(["-"], stdin='แสดง "จาก stdin"\n')
        self.assertEqual(status, 0)
        self.assertEqual(output, "จาก stdin\n")

    def test_check_dash_c_json(self):
        status, output = self._run(["check", "-c", "แสดงกขค", "--json"])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output)["errors"], 1)

    def test_compile_error_reports_exit_code(self):
        status, _ = self._run(["-c", "ไม่ใช่คำสั่งอะไรเลย"])
        self.assertEqual(status, 1)

    # ---------------------------------------------- เขียนสั้นกว่าเดิม
    def test_bare_argument_is_treated_as_code(self):
        """ไม่ต้องพิมพ์ -c — อาร์กิวเมนต์แรกที่ไม่ใช่ไฟล์ถือเป็นโค้ด"""
        status, output = self._run(['แสดง "สวัสดี"'])
        self.assertEqual((status, output), (0, "สวัสดี\n"))

    def test_bare_expression_prints_its_value(self):
        """โหมดพิมพ์สดแสดงค่าให้เลย ไม่ต้องสั่ง แสดง"""
        self.assertEqual(self._run(["2 บวก 3"])[1], "5\n")
        self.assertEqual(self._run(["-c", "รากที่สอง(144)"])[1], "12.0\n")

    def test_void_call_prints_nothing(self):
        """คำสั่งที่ไม่คืนค่าต้องไม่พ่นคำว่า None ออกมา"""
        status, output = self._run(
            ["-c", 'สร้างคำสั่งขีดเส้น\n    แสดง "-"\nเรียกขีดเส้น'])
        self.assertEqual((status, output), (0, "-\n"))

    def test_file_mode_does_not_auto_print(self):
        """ไฟล์ .th ต้องทำงานเหมือนเดิมทุกประการ ไม่มีการแสดงค่าอัตโนมัติ"""
        self.assertNotIn("_th_show", py("ให้ราคาเป็น 5\nราคาบวก 1"))

    def test_existing_file_still_wins_over_code(self):
        example = (Path(__file__).resolve().parent.parent
                   / "examples" / "01_hello.th")
        status, output = self._run([str(example)])
        self.assertEqual(status, 0)
        self.assertIn("สวัสดีชาวโลก!", output)

    def test_missing_th_file_still_reports_not_found(self):
        status, _ = self._run(["ไม่มีไฟล์นี้จริง.th"])
        self.assertEqual(status, 1)

    def test_thai_subcommands(self):
        for thai, english in (("ดูโค้ด", "show"), ("ตรวจ", "check")):
            with self.subTest(cmd=thai):
                thai_out = self._run([thai, "-c", "แสดง 1"])
                english_out = self._run([english, "-c", "แสดง 1"])
                self.assertEqual(thai_out, english_out)

    def test_make_library_skeleton(self):
        status, output = self._run(["สร้างคลัง", "str"])
        self.assertEqual(status, 0)
        self.assertIn("นำเข้าวิธี strip เป็น______", output)

    # ---------------------------------------------- เชลล์กินเครื่องหมายคำพูด
    def test_note_covers_every_kind_of_error(self):
        """ข้อสังเกตอยู่ที่ระดับซอร์ส จึงติดมากับข้อผิดพลาดทุกชนิด ไม่เลือกที่รักมักที่ชัง"""
        cases = {
            "แสดงผลสวัสดี": Code.UNDEFINED_NAME,
            "ให้ชื่อเป็นสมชาย": Code.UNDEFINED_NAME,
            "เพิ่มกเข้าไปในรายชื่อ": Code.UNDEFINED_NAME,
            "อะไรก็ไม่รู้ 12": Code.RESERVED_AS_NAME,
        }
        for src, code in cases.items():
            with self.subTest(src=src):
                bag = check_source(src, "<คำสั่ง>", shell_arg=True)
                self.assertIn(code, [d.code for d in bag])
                self.assertEqual(len(shell_notes(src)), 1)

    def test_no_note_when_quotes_survived(self):
        self.assertEqual(shell_notes('แสดงผล "สวัสดี" บวก ก'), [])

    def test_no_note_when_compiling_a_file(self):
        """ไฟล์ .th และ stdin ไม่ได้ผ่านการแกะอาร์กิวเมนต์ของเชลล์"""
        bag = check_source("แสดงผลสวัสดี", "<test>")
        self.assertNotIn(Code.SHELL_ATE_QUOTES, [d.code for d in bag])

    def test_no_note_when_there_is_no_error(self):
        self.assertEqual(shell_notes("แสดง 1 บวก 2"), [])

    def test_note_is_not_counted_as_error_or_warning(self):
        bag = check_source("แสดงผลสวัสดี", "<คำสั่ง>", shell_arg=True)
        self.assertEqual(bag.summary(), "1 ข้อผิดพลาด")

    def test_make_library_unknown_module(self):
        status, _ = self._run(["สร้างคลัง", "ไม่มีโมดูลนี้_zz"])
        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
