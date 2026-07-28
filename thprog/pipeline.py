# -*- coding: utf-8 -*-
"""
สายพานคอมไพล์ของ TH-Programming
================================

    ไฟล์ .th
      1. tokenize   วิเคราะห์ระดับตัวอักษร  → ชิ้นส่วนของแต่ละบรรทัด
      2. segment    ตัดคำไทย                → เสนอหลายแบบ  (wordseg + tcc)
      3. normalize  ชั้น NLP                → รวมวลี / ตัดคำเสริม / ตัดหน่วย
      4. split      ตัดประโยค               → หนึ่งบรรทัดมีได้หลายคำสั่ง
      5. parse      วิเคราะห์ไวยากรณ์        → AST   (กู้คืนเมื่อพบข้อผิดพลาด)
      6. bind       ผูกชื่อกับสัญลักษณ์       → ตารางสัญลักษณ์ + ตรวจขอบเขต
      7. typecheck  ตรวจชนิดข้อมูล           → เดาชนิด + จับการใช้ผิดชนิด
      8. optimize   ปรับให้เหมาะที่สุด        → พับค่าคงที่ / ตัดโค้ดตาย
      9. codegen    สร้างโค้ด               → Python
     10. run        สั่งทำงาน               → แปลข้อผิดพลาดกลับเป็นบรรทัดไทย

ขั้นที่ 6-7 คือ "ระบบความหมาย" (semantic system) ซึ่งแยกเป็นสองส่วนตามแบบที่
คอมไพเลอร์ระดับโลกทำกัน — ผูกชื่อก่อน แล้วค่อยตรวจชนิด

ขั้นที่ 2-5 ไม่ได้เดินเป็นเส้นตรง แต่ทำงานร่วมกันแบบ "เสนอ-แล้วให้ไวยากรณ์ตัดสิน"
ตัวตัดคำและตัวตัดประโยคเสนอทางเลือกหลายแบบ ตัวแยกวิเคราะห์เลือกแบบที่แปลได้จริง

ทุกเฟสรายงานปัญหาลง DiagnosticBag เดียวกัน คอมไพเลอร์จึงบอกได้ครบในรอบเดียว
"""

import sys
import traceback
from dataclasses import dataclass, field
from typing import Dict

from .diagnostics import Code, DiagnosticBag
from .errors import CompileError, LexError, RuntimeThaiError, ThaiError
from .lang import lexicon
from .lang.builtins import BUILTINS, CAST_TYPES
from .compiler.ast_nodes import ExprStmt as ASTExprStmt
from .compiler.tokenizer import tokenize
from .compiler.wordseg import Segmenter
from .compiler.parser import parse
from .compiler.analyzer import analyze
from .compiler.typecheck import typecheck
from .compiler.optimizer import optimize
from .compiler.codegen import generate


@dataclass
class Program:
    """ผลลัพธ์ของการคอมไพล์หนึ่งไฟล์"""
    python: str = ""
    diagnostics: DiagnosticBag = None
    linemap: Dict[int, int] = field(default_factory=dict)
    ast: object = None
    source: str = ""
    name: str = "<th>"
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def warnings(self):
        """คำเตือนในรูปข้อความ (ใช้กับการแสดงผลแบบย่อ)"""
        return [f"บรรทัดที่ {d.line}: {d.message}" if d.line else d.message
                for d in (self.diagnostics.warnings if self.diagnostics else [])]


def new_segmenter():
    """ตัวตัดคำที่เริ่มจากพจนานุกรมของภาษา แล้วเรียนรู้ชื่อของผู้ใช้เพิ่มเอง

    พจนานุกรมตั้งต้น = คีย์เวิร์ด + ฟังก์ชันสำเร็จรูป + ชื่อชนิดข้อมูล + คำเสริม

    ส่วนหน่วย/ลักษณนามจะเติมเข้าไป **เฉพาะตัวที่จะถูกซอยเป็นเศษ** เท่านั้น
    ("คะแนน" ถูกซอยเป็น "คะ"(คำเสริม) + "แนน" จึงต้องเติม)
    ตัวที่ยืนอยู่ลำพังได้อยู่แล้วอย่าง "บาท" "ตัว" "คน" จะไม่เติม เพราะจะทำให้
    ชื่อตัวแปรที่ขึ้นต้นด้วยคำเหล่านี้ถูกซอยตาม ("ตัวแรก" -> ตัว|แรก)

    หน่วยไม่จำเป็นต้องอยู่ในพจนานุกรมเพื่อให้ถูกตัดทิ้ง เพราะหน่วยตามหลัง
    ตัวเลขเสมอ และตัวเลขบังคับให้ขึ้นก้อนใหม่อยู่แล้ว
    """
    words = set(lexicon.WORD_IDS)
    words |= set(BUILTINS) | set(CAST_TYPES) | lexicon.FILLERS | lexicon.POLITE
    seg = Segmenter(words)
    seg.words |= {unit for unit in lexicon.UNITS if seg.splits(unit)}
    return seg


# ======================================================================
def compile_source(source, name="<th>", predefined=None, segmenter=None,
                   optimize_level=1, auto_show=False):
    """แปลซอร์สภาษาไทยเป็นโค้ด Python

    predefined     : ชื่อที่ถือว่ามีอยู่แล้ว (ใช้ตอนคอมไพล์ทีละบรรทัดในโหมดโต้ตอบ)
    segmenter      : ตัวตัดคำที่ใช้ร่วมกันข้ามการเรียก (ใช้ในโหมดโต้ตอบ)
    optimize_level : 0 = ไม่ปรับ, 1 = พับค่าคงที่และตัดโค้ดตาย
    auto_show      : แสดงค่าของนิพจน์เดี่ยวที่ระดับบนสุดโดยอัตโนมัติ
                     (เปิดเฉพาะโหมดโต้ตอบและ -c เท่านั้น ไฟล์ .th ไม่เปิด)

    โยน CompileError ถ้าพบข้อผิดพลาด โดยข้างในมีรายการปัญหาทั้งหมด
    """
    bag = DiagnosticBag(source, name)

    # ---- 1. วิเคราะห์ระดับตัวอักษร
    try:
        lines = tokenize(source, name)
    except LexError as err:
        bag.record(err)
        raise CompileError(bag, name) from None

    # ---- 2-4. ตัดคำ + ไวยากรณ์ (กู้คืนได้ รายงานได้หลายจุด)
    ast, bag = parse(lines, segmenter or new_segmenter(), bag)

    # เขียนโค้ดสั้น ๆ แล้วอยากเห็นผลทันที เหมือนพิมพ์ในเครื่องคิดเลข
    # ทำเฉพาะระดับบนสุด เพื่อไม่ให้นิพจน์ในลูปหรือในฟังก์ชันพ่นค่าออกมาเอง
    if auto_show:
        for node in ast.body:
            if isinstance(node, ASTExprStmt):
                node.show = True

    # ---- 5. ความหมาย ส่วนที่ 1: ผูกชื่อกับสัญลักษณ์
    # วิเคราะห์ต่อแม้ไวยากรณ์จะพังบางบรรทัด เพื่อรายงานปัญหาให้ครบในรอบเดียว
    # (บรรทัดที่พังถูกข้ามไปแล้ว จึงไม่สร้างข้อผิดพลาดลูกโซ่)
    analyze(ast, bag, predefined, report_unused=not auto_show)

    # ---- 6. ความหมาย ส่วนที่ 2: ชนิดข้อมูล
    # ข้ามเมื่อผูกชื่อไม่ผ่าน เพราะชนิดของชื่อที่ไม่มีจริงย่อมเดาไม่ได้
    # แล้วจะกลายเป็นข้อผิดพลาดลูกโซ่ที่ทำให้ผู้ใช้สับสน
    if not bag.has_errors():
        typecheck(ast, bag, predefined)
    if bag.has_errors():
        raise CompileError(bag, name)

    # ---- 7. ปรับให้เหมาะที่สุด
    stats = {}
    if optimize_level:
        ast, opt = optimize(ast)
        stats = {"พับค่าคงที่": opt.folded, "ตัดโค้ดตาย": opt.removed}

    # ---- 8. สร้างโค้ด
    python, linemap = generate(ast, name)
    stats["บรรทัด Python"] = python.count("\n")

    return Program(python, bag, linemap, ast, source, name, stats)


def check_source(source, name="<th>"):
    """ตรวจอย่างเดียว ไม่โยนข้อผิดพลาด — คืน DiagnosticBag เสมอ"""
    try:
        return compile_source(source, name).diagnostics
    except CompileError as err:
        return err.bag


# ======================================================================
def run_source(source, name="<th>", show_warnings=True, stream=None):
    return run(compile_source(source, name), show_warnings, stream)


def run(program, show_warnings=True, stream=None, color=False):
    """สั่งทำงานโปรแกรมที่คอมไพล์แล้ว"""
    out = stream or sys.stderr
    if show_warnings and program.diagnostics:
        for item in program.diagnostics.warnings:
            print(item.render(color), file=out)

    pyfile = f"<python:{program.name}>"
    code = compile(program.python, pyfile, "exec")
    env = {"__name__": "__main__", "__file__": program.name}
    try:
        exec(code, env)
    except (ThaiError, SystemExit):
        raise
    except BaseException as exc:      # noqa: BLE001 - ดักทุกอย่างเพื่อแปลข้อความ
        sys.stdout.flush()
        raise _translate(exc, program, pyfile) from None
    return env


# ---------------------------------------------------------------- แปลข้อผิดพลาด
_MESSAGES = {
    ZeroDivisionError: ("หารด้วยศูนย์ไม่ได้",
                        "ตรวจว่าตัวหารเป็นศูนย์หรือไม่ก่อนหาร"),
    IndexError: ("อ้างถึงตำแหน่งที่เกินขอบเขตของรายการ",
                 "ตำแหน่งแรกคือ 0 และตำแหน่งสุดท้ายคือ ความยาว(รายการ) ลบ 1"),
    KeyError: ("ไม่พบคีย์นี้ในพจนานุกรม",
               "ลองใช้ มีอยู่(พจนานุกรม, คีย์) ตรวจก่อน"),
    RecursionError: ("เรียกฟังก์ชันซ้อนกันลึกเกินไป",
                     "ฟังก์ชันที่เรียกตัวเองต้องมีเงื่อนไขหยุด"),
    KeyboardInterrupt: ("ผู้ใช้กดหยุดการทำงาน", None),
}


def _translate(exc, program, pyfile):
    src_line = None
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == pyfile:
            src_line = program.linemap.get(frame.lineno)
            break

    raw = None
    if src_line:
        lines = program.source.splitlines()
        if 0 < src_line <= len(lines):
            raw = lines[src_line - 1]

    known = _MESSAGES.get(type(exc))
    if known:
        message, hint = known
    elif isinstance(exc, TypeError):
        message, hint = f"ใช้ค่าผิดชนิด ({exc})", "ลองใช้ ชนิด(ค่า) ตรวจดูก่อน"
    elif isinstance(exc, ValueError):
        message, hint = f"ค่าที่ใส่ไม่ถูกต้อง ({exc})", None
    elif isinstance(exc, NameError):
        message, hint = f"ไม่รู้จักชื่อนี้ ({exc})", None
    else:
        message, hint = f"{type(exc).__name__}: {exc}", None

    return RuntimeThaiError(message, src_line, raw, hint, code=Code.RUNTIME)
