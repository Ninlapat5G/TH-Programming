# -*- coding: utf-8 -*-
"""
ไวยากรณ์ของภาษา TH-Programming — คลังรูปประโยค (Semantic Frames)
================================================================

แต่ละคำสั่งถูกอธิบายเป็น "โครงความหมาย" คือลำดับของ

    Kw("IF")            คีย์เวิร์ดที่ต้องมี  (ใส่หลายรหัสได้ = อันไหนก็ได้)
    Opt("THEN")         คีย์เวิร์ดที่จะมีหรือไม่ก็ได้ (คำเชื่อมภาษาพูด)
    Slot("cond", ...)   ช่องที่ต้องเติมความหมาย

ชนิดของช่อง
    expr      นิพจน์ใด ๆ
    target    เป้าหมายที่กำหนดค่าได้ (ชื่อ หรือ ชื่อ[ดัชนี])
    name      ชื่อเดี่ยว ๆ หนึ่งคำ
    type      ชื่อชนิดข้อมูล (ตัวเลข / ทศนิยม / ข้อความ)
    namelist  รายชื่อคั่นด้วย , หรือ "และ"
    exprlist  รายการนิพจน์คั่นด้วย ,
    stmt      คำสั่งเต็มอีกคำสั่งหนึ่ง (ใช้กับรูปแบบเขียนจบในบรรทัดเดียว)

เพิ่มไวยากรณ์ใหม่ = เพิ่ม Pattern หนึ่งบรรทัดในตารางท้ายไฟล์
ตัวจับคู่จะลองตามลำดับจากบนลงล่าง จึงควรวางรูปที่เฉพาะเจาะจงไว้ก่อน
"""

from dataclasses import dataclass
from typing import Callable, List

from ..compiler import ast_nodes as A


# ====================================================== องค์ประกอบของรูปประโยค
@dataclass(frozen=True)
class Kw:
    ids: frozenset

    def __init__(self, *ids):
        object.__setattr__(self, "ids", frozenset(ids))


@dataclass(frozen=True)
class Opt:
    ids: frozenset

    def __init__(self, *ids):
        object.__setattr__(self, "ids", frozenset(ids))


@dataclass(frozen=True)
class Slot:
    name: str
    kind: str


@dataclass
class Pattern:
    name: str
    elems: List[object]
    build: Callable
    block: bool = False        # เปิดบล็อกย่อยที่เยื้องตามหลังหรือไม่
    role: str = "stmt"         # stmt | elif | else


# ====================================================== ตัวสร้างโหนด AST
def _print(s, line, body):
    return A.Print(s["values"], line)


def _ask(s, line, body):
    return A.Ask(s.get("prompt"), s["target"], s.get("cast"), line)


def _let(s, line, body):
    return A.Assign(s["target"], s["value"], None, line)


def _append(s, line, body):
    return A.AppendTo(s["target"], s["value"], line)


def _inc(s, line, body):
    return A.Assign(s["target"], s.get("value") or A.Num(1, line), "PLUS", line)


def _dec(s, line, body):
    return A.Assign(s["target"], s.get("value") or A.Num(1, line), "MINUS", line)


def _if(s, line, body):
    return A.If([(s.get("cond"), body)], None, line)


def _if_inline(s, line, body):
    return A.If([(s.get("cond"), [s["stmt"]])], None, line)


def _repeat(s, line, body):
    return A.RepeatTimes(s["count"], body, line)


def _foreach(s, line, body):
    return A.ForEach(s["var"], s["iterable"], body, line)


def _count(s, line, body):
    return A.CountLoop(s["var"], s["start"], s["end"], s.get("step"), body, line)


def _while(s, line, body):
    return A.While(s["cond"], body, line)


def _until(s, line, body):
    return A.While(A.UnaryOp("NOT", s["cond"], line), body, line)


def _func(s, line, body):
    return A.FuncDef(s["name"], s.get("params", []), body, line)


def _return(s, line, body):
    return A.Return(s.get("value"), line)


def _call(s, line, body):
    return A.ExprStmt(A.Call(A.Name(s["name"], line), s.get("args", []), line), line)


def _exprstmt(s, line, body):
    return A.ExprStmt(s["expr"], line)


def _break(s, line, body):
    return A.Break(line)


def _continue(s, line, body):
    return A.Continue(line)


# ====================================================== ตารางรูปประโยค
PATTERNS = [

    # ---------------------------------------------------------- แสดงผล
    Pattern("แสดง",
            [Kw("PRINT"), Slot("values", "exprlist")], _print),

    # ---------------------------------------------------------- รับค่าเข้า
    Pattern("ถาม+ชนิด",
            [Kw("ASK"), Slot("prompt", "expr"), Kw("STORE_IN"),
             Slot("target", "name"), Kw("BE"), Slot("cast", "type")], _ask),
    Pattern("ถาม",
            [Kw("ASK"), Slot("prompt", "expr"), Kw("STORE_IN"),
             Slot("target", "name")], _ask),
    Pattern("ถามเปล่า+ชนิด",
            [Kw("ASK"), Kw("STORE_IN"), Slot("target", "name"),
             Kw("BE"), Slot("cast", "type")], _ask),
    Pattern("ถามเปล่า",
            [Kw("ASK"), Kw("STORE_IN"), Slot("target", "name")], _ask),

    # ---------------------------------------------------------- รายการ
    Pattern("เพิ่มเข้ารายการ",
            [Kw("INC"), Slot("value", "expr"), Kw("INTO"),
             Slot("target", "target")], _append),

    # ---------------------------------------------------------- เพิ่ม/ลด
    Pattern("เพิ่มค่า",
            [Kw("INC"), Slot("target", "target"), Opt("BY"),
             Slot("value", "expr")], _inc),
    Pattern("เพิ่มหนึ่ง",
            [Kw("INC"), Slot("target", "target")], _inc),
    Pattern("ลดค่า",
            [Kw("DEC"), Slot("target", "target"), Opt("BY"),
             Slot("value", "expr")], _dec),
    Pattern("ลดหนึ่ง",
            [Kw("DEC"), Slot("target", "target")], _dec),
    Pattern("บวกเข้ากับ",
            [Kw("PLUS"), Slot("value", "expr"), Kw("INTO"),
             Slot("target", "target")], _inc),
    Pattern("ลบออกจาก",
            [Kw("MINUS"), Slot("value", "expr"), Kw("FROM"),
             Slot("target", "target")], _dec),

    # ---------------------------------------------------------- กำหนดค่า
    Pattern("ให้ตัวแปรเป็นค่า",
            [Kw("LET"), Opt("VAR"), Slot("target", "target"), Kw("BE"),
             Slot("value", "expr")], _let),
    Pattern("เก็บค่าไว้ในตัวแปร",
            [Kw("LET"), Slot("value", "expr"), Kw("STORE_IN"),
             Slot("target", "target")], _let),

    # ประโยคบอกเล่า:  มีเงิน 100 บาท / มีเงินเป็น100 / เริ่มด้วยคะแนน0
    # หน่วยท้ายเลข ("บาท") ถูกตัดทิ้งไปแล้วตั้งแต่ชั้น normalizer
    Pattern("มีตัวแปรค่า",
            [Kw("HAVE"), Opt("VAR"), Slot("target", "target"), Opt("BE"),
             Slot("value", "expr")], _let),

    # ---------------------------------------------------------- ฟังก์ชัน
    Pattern("ฟังก์ชันมีพารามิเตอร์",
            [Kw("FUNC"), Opt("NAMED"), Slot("name", "name"), Kw("TAKES"),
             Slot("params", "namelist")], _func, block=True),
    Pattern("ฟังก์ชัน",
            [Kw("FUNC"), Opt("NAMED"), Slot("name", "name")],
            _func, block=True),
    Pattern("คืนค่า", [Kw("RETURN"), Slot("value", "expr")], _return),
    Pattern("คืนค่าเปล่า", [Kw("RETURN")], _return),
    Pattern("เรียกพร้อมค่า",
            [Kw("CALL"), Slot("name", "name"), Kw("WITH"),
             Slot("args", "exprlist")], _call),
    Pattern("เรียก", [Kw("CALL"), Slot("name", "name")], _call),

    # ---------------------------------------------------------- เงื่อนไข
    Pattern("ไม่งั้นถ้า",
            [Kw("ELIF"), Slot("cond", "expr"), Opt("THEN")],
            _if, block=True, role="elif"),
    Pattern("ไม่งั้นถ้าบรรทัดเดียว",
            [Kw("ELIF"), Slot("cond", "expr"), Opt("THEN"), Slot("stmt", "stmt")],
            _if_inline, role="elif"),
    Pattern("ไม่งั้น", [Kw("ELSE"), Opt("THEN")], _if, block=True, role="else"),
    Pattern("ไม่งั้นบรรทัดเดียว",
            [Kw("ELSE"), Opt("THEN"), Slot("stmt", "stmt")],
            _if_inline, role="else"),
    Pattern("ถ้า",
            [Kw("IF"), Slot("cond", "expr"), Opt("THEN")], _if, block=True),
    Pattern("ถ้าบรรทัดเดียว",
            [Kw("IF"), Slot("cond", "expr"), Opt("THEN"), Slot("stmt", "stmt")],
            _if_inline),

    # ---------------------------------------------------------- ลูป
    Pattern("ทำซ้ำ",
            [Kw("REPEAT"), Slot("count", "expr"), Kw("TIMES")],
            _repeat, block=True),
    Pattern("ทำซ้ำบรรทัดเดียว",
            [Kw("REPEAT"), Slot("count", "expr"), Kw("TIMES"), Opt("THEN"),
             Slot("stmt", "stmt")],
            lambda s, line, body: A.RepeatTimes(s["count"], [s["stmt"]], line)),
    Pattern("นับทีละ",
            [Kw("COUNT", "FOREACH"), Slot("var", "name"), Kw("FROM"),
             Slot("start", "expr"), Kw("TO"), Slot("end", "expr"),
             Kw("BY"), Slot("step", "expr")], _count, block=True),
    Pattern("นับ",
            [Kw("COUNT", "FOREACH"), Slot("var", "name"), Kw("FROM"),
             Slot("start", "expr"), Kw("TO"), Slot("end", "expr")],
            _count, block=True),
    Pattern("สำหรับแต่ละ",
            [Kw("FOREACH"), Slot("var", "name"), Kw("IN"),
             Slot("iterable", "expr")], _foreach, block=True),
    Pattern("ตราบใดที่",
            [Kw("WHILE"), Slot("cond", "expr"), Opt("THEN")],
            _while, block=True),
    Pattern("จนกว่า",
            [Opt("REPEAT"), Kw("UNTIL"), Slot("cond", "expr"), Opt("THEN")],
            _until, block=True),
    Pattern("หยุด", [Kw("BREAK")], _break),
    Pattern("ข้าม", [Kw("CONTINUE")], _continue),

    # ---------------------------------------------------------- กำหนดค่าแบบสั้น
    Pattern("ตัวแปร=ค่า",
            [Slot("target", "target"), Kw("ASSIGN_OP"),
             Slot("value", "expr")], _let),
    Pattern("ตัวแปรคือค่า",
            [Slot("target", "target"), Kw("BE"), Slot("value", "expr")], _let),

    # ---------------------------------------------------------- นิพจน์เดี่ยว
    Pattern("นิพจน์", [Slot("expr", "expr")], _exprstmt),
]


# รูปประโยคที่ใช้ซ้อนในบรรทัดเดียวได้ (ไม่เปิดบล็อก และไม่ใช่ ไม่งั้น/ไม่งั้นถ้า)
INLINE_PATTERNS = [p for p in PATTERNS if not p.block and p.role == "stmt"]
