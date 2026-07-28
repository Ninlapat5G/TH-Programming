# -*- coding: utf-8 -*-
"""
ขั้นที่ 7 : ตัวตรวจชนิดข้อมูล (Type Checker)
============================================

ทำไมต้องมี
----------
คอมไพเลอร์ระดับโลกทุกตัวแยก "ระบบความหมาย" ออกเป็นสองส่วน

    Binder / Name resolution  ชื่อนี้หมายถึงอะไร      -> analyzer.py + symbols.py
    Checker  / Type system    ค่านี้เอาไปทำแบบนี้ได้ไหม -> ไฟล์นี้

ทีม TypeScript ระบุไว้ตรง ๆ ว่าสิ่งที่แยก "คอมไพเลอร์จริง" ออกจาก
"ตัวแปลงโค้ดธรรมดา" คือการมีระบบความหมายครบทั้งสองส่วนนี้
ก่อนหน้านี้ภาษาเรามีแต่ส่วนแรก

สิ่งที่ตรวจได้
-------------
    ให้ชื่อเป็น "สมชาย"
    แสดงชื่อลบ 1          ← [TH311] เอาข้อความไปลบไม่ได้

เดิมโปรแกรมนี้คอมไพล์ผ่าน แล้วไประเบิดตอนรันเป็น TypeError ของ Python
ตอนนี้จับได้ตั้งแต่ตอนคอมไพล์ พร้อมชี้บรรทัดและคอลัมน์

หลักการสำคัญ: **ไม่ทราบ ไว้ก่อน**
--------------------------------
ภาษานี้ไม่ต้องประกาศชนิด ตัวตรวจจึงเดาชนิดเอาเอง (type inference)
เมื่อใดที่เดาไม่ได้ จะให้เป็น "ไม่ทราบ" แล้ว **เงียบ** ไม่ฟ้อง

การฟ้องผิด (false positive) ในภาษาสำหรับผู้เริ่มต้นเป็นอันตรายกว่าการปล่อยผ่าน
เพราะทำให้โปรแกรมที่ถูกต้องคอมไพล์ไม่ผ่าน  ตัวตรวจนี้จึงฟ้องเฉพาะกรณีที่
**ถ้าปล่อยไปก็พังตอนรันแน่นอน** เท่านั้น
"""

from ..diagnostics import Code
from ..lang.builtins import BUILTINS, SIGNATURES
from . import ast_nodes as A


# ====================================================== ชนิดข้อมูล
# ใช้ชื่อเดียวกับที่ผู้ใช้เห็นจากฟังก์ชัน ชนิด() เพื่อให้ข้อความสอดคล้องกัน
UNKNOWN = None                 # ไม่ทราบ — ห้ามฟ้องอะไรทั้งสิ้น
INT = "จำนวนเต็ม"
FLOAT = "ทศนิยม"
STR = "ข้อความ"
BOOL = "ค่าความจริง"
LIST = "รายการ"
DICT = "พจนานุกรม"
NONE = "ค่าว่าง"

NUMERIC = {INT, FLOAT, BOOL}   # ใน Python ค่าความจริงคำนวณได้เหมือนเลข
SEQUENCE = {STR, LIST, DICT}
INDEXABLE = {STR, LIST, DICT}

_CONST_TYPES = {"True": BOOL, "False": BOOL, "None": NONE}


def _article(kind):
    return kind if kind else "ไม่ทราบชนิด"


def _join(left, right):
    """ชนิดร่วมของสองกิ่ง — ต่างกันเมื่อไรก็ยอมแพ้เป็น "ไม่ทราบ" """
    if left == right:
        return left
    if left in NUMERIC and right in NUMERIC:
        return FLOAT if FLOAT in (left, right) else INT
    return UNKNOWN


# ====================================================== ตารางกฎของตัวดำเนินการ
_ARITH = {"MINUS", "DIV", "IDIV", "MOD", "POW"}
_ORDER = {"LT", "GT", "LE", "GE"}

_OP_WORD = {
    "PLUS": "บวก", "MINUS": "ลบ", "MUL": "คูณ", "DIV": "หาร",
    "IDIV": "หารลงตัว", "MOD": "หารเอาเศษ", "POW": "ยกกำลัง",
    "LT": "น้อยกว่า", "GT": "มากกว่า",
    "LE": "น้อยกว่าหรือเท่ากับ", "GE": "มากกว่าหรือเท่ากับ",
}


_VALUE_TYPES = {bool: BOOL, int: INT, float: FLOAT, str: STR,
                list: LIST, tuple: LIST, dict: DICT, type(None): NONE}


def type_of_value(value):
    """ชนิดของค่าจริงที่มีอยู่แล้ว — ใช้ในโหมดโต้ตอบที่รู้ค่าตัวแปรจริง ๆ"""
    return _VALUE_TYPES.get(type(value), UNKNOWN)


class TypeChecker:
    def __init__(self, bag, predefined=None):
        # กองซ้อนของขอบเขต — ชื่อ -> ชนิดที่เดาได้
        #
        # predefined รับได้สองแบบ
        #   เซ็ตของชื่อ   -> ไม่ทราบชนิด (ใช้ตอนคอมไพล์ทั้งไฟล์)
        #   dict ชื่อ->ชนิด -> รู้ชนิดแน่นอน (โหมดโต้ตอบ ซึ่งมีค่าจริงอยู่ในมือ)
        if isinstance(predefined, dict):
            base = dict(predefined)
        else:
            base = {name: UNKNOWN for name in (predefined or ())}
        self.scopes = [base]
        self.bag = bag
        self.returns = []          # ชนิดที่ฟังก์ชันปัจจุบันคืนออกมาบ้าง
        self.func_types = {}       # ชื่อฟังก์ชัน -> ชนิดที่คืน

    # -------------------------------------------------- ขอบเขต
    def get(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return UNKNOWN

    def declared(self, name):
        return any(name in scope for scope in self.scopes)

    def set(self, name, kind):
        self.scopes[-1][name] = kind

    def merge(self, name, kind):
        """กำหนดค่าซ้ำด้วยชนิดอื่น = ตัวแปรนี้เอาแน่ไม่ได้ ให้เป็นไม่ทราบ"""
        if self.declared(name):
            for scope in reversed(self.scopes):
                if name in scope:
                    scope[name] = _join(scope[name], kind)
                    return
        self.set(name, kind)

    # ====================================================== ทางเข้า
    def run(self, program):
        self._collect_returns(program.body)
        self.block(program.body)
        return self.bag

    def _collect_returns(self, body):
        """รอบแรก: เดาชนิดที่แต่ละฟังก์ชันคืน เพื่อให้เรียกก่อนประกาศได้"""
        for node in body:
            if isinstance(node, A.BindMethod):
                # กริยาที่ผูกจากเมธอดคืนชนิดอะไรก็ได้ ต้องรู้ตั้งแต่รอบแรก
                # เผื่อถูกเรียกก่อนบรรทัดที่ประกาศ
                self.func_types[node.alias] = UNKNOWN
            if isinstance(node, A.FuncDef):
                saved, self.returns = self.returns, []
                self.scopes.append({p: UNKNOWN for p in node.params})
                self.block(node.body, collecting=True)
                self.scopes.pop()
                kinds = self.returns
                self.returns = saved
                self.func_types[node.name] = (
                    kinds[0] if kinds and all(k == kinds[0] for k in kinds)
                    else UNKNOWN)
            for attr in ("body", "orelse"):
                child = getattr(node, attr, None)
                if isinstance(child, list) and not isinstance(node, A.FuncDef):
                    self._collect_returns(child)
            for _cond, branch in getattr(node, "branches", ()) or ():
                self._collect_returns(branch)

    # ====================================================== คำสั่ง
    def block(self, body, collecting=False):
        for node in body:
            self.stmt(node, collecting)

    def stmt(self, node, collecting=False):
        if isinstance(node, A.Print):
            for value in node.values:
                self.expr(value, collecting)

        elif isinstance(node, A.Assign):
            kind = self.expr(node.value, collecting)
            if node.op:                       # += / -= ต้องเป็นตัวเลขทั้งคู่
                kind = self.binop(node.op, self.target_type(node.target),
                                  kind, node, collecting)
            if isinstance(node.target, A.Name):
                self.merge(node.target.ident, kind)
            else:
                self.expr(node.target, collecting)

        elif isinstance(node, A.Ask):
            name = node.target if isinstance(node.target, str) \
                else getattr(node.target, "ident", None)
            cast = {"int": INT, "float": FLOAT, "str": STR}.get(node.cast, STR)
            if name:
                self.merge(name, cast)
            if node.prompt is not None:
                self.expr(node.prompt, collecting)

        elif isinstance(node, A.AppendTo):
            self.expr(node.value, collecting)
            self.expr(node.target, collecting)

        elif isinstance(node, A.If):
            for cond, branch in node.branches:
                if cond is not None:
                    self.expr(cond, collecting)
                self.block(branch, collecting)
            if node.orelse:
                self.block(node.orelse, collecting)

        elif isinstance(node, A.RepeatTimes):
            self.expr(node.count, collecting)
            self.block(node.body, collecting)

        elif isinstance(node, A.ForEach):
            self.expr(node.iterable, collecting)
            self.set(node.var, UNKNOWN)       # ไม่ตามชนิดสมาชิกในรายการ
            self.block(node.body, collecting)

        elif isinstance(node, A.CountLoop):
            for part in (node.start, node.end, node.step):
                if part is not None:
                    self.expr(part, collecting)
            self.set(node.var, INT)
            self.block(node.body, collecting)

        elif isinstance(node, A.While):
            self.expr(node.cond, collecting)
            self.block(node.body, collecting)

        elif isinstance(node, A.FuncDef):
            if not collecting:
                self.scopes.append({p: UNKNOWN for p in node.params})
                saved, self.returns = self.returns, []
                self.block(node.body)
                self.returns = saved
                self.scopes.pop()

        elif isinstance(node, A.Return):
            kind = self.expr(node.value, collecting) \
                if node.value is not None else NONE
            self.returns.append(kind)

        elif isinstance(node, A.ExprStmt):
            self.expr(node.expr, collecting)

        elif isinstance(node, A.Import):
            # ชนิดของสิ่งที่มาจากไลบรารี Python อยู่นอกความรู้ของคอมไพเลอร์
            # ประกาศเป็น "ไม่ทราบ" ไว้ ตัวตรวจจะได้เงียบแทนที่จะเดามั่ว
            for name in node.bound_names():
                self.set(name, UNKNOWN)

        elif isinstance(node, A.BindMethod):
            self.func_types[node.alias] = UNKNOWN

    def target_type(self, target):
        if isinstance(target, A.Name):
            return self.get(target.ident)
        return UNKNOWN

    # ====================================================== นิพจน์
    def expr(self, node, collecting=False):
        if node is None:
            return UNKNOWN

        if isinstance(node, A.Num):
            return FLOAT if isinstance(node.value, float) else INT
        if isinstance(node, A.Str):
            return STR
        if isinstance(node, A.Const):
            return _CONST_TYPES.get(node.value, UNKNOWN)
        if isinstance(node, A.ListLit):
            for item in node.items:
                self.expr(item, collecting)
            return LIST
        if isinstance(node, A.DictLit):
            for key, value in node.pairs:
                self.expr(key, collecting)
                self.expr(value, collecting)
            return DICT

        if isinstance(node, A.Name):
            return self.get(node.ident)

        if isinstance(node, A.BinOp):
            left = self.expr(node.left, collecting)
            right = self.expr(node.right, collecting)
            return self.binop(node.op, left, right, node, collecting)

        if isinstance(node, A.UnaryOp):
            inner = self.expr(node.operand, collecting)
            if node.op == "NOT":
                return BOOL
            if inner is not UNKNOWN and inner not in NUMERIC:
                self._error(node, collecting,
                            f"ใช้เครื่องหมายลบนำหน้า{_article(inner)}ไม่ได้",
                            hint="ตัวเลขเท่านั้นที่ติดลบได้")
            return inner

        if isinstance(node, A.Index):
            target = self.expr(node.target, collecting)
            self.expr(node.key, collecting)
            if target is not UNKNOWN and target not in INDEXABLE:
                self._error(node, collecting,
                            f"{_article(target)}ไม่มีสมาชิกให้อ้างถึงด้วย [ ]",
                            code=Code.NOT_INDEXABLE,
                            hint="ใช้ [ ] ได้กับ รายการ ข้อความ และพจนานุกรม")
            return UNKNOWN

        if isinstance(node, A.Attr):
            self.expr(node.target, collecting)
            return UNKNOWN

        if isinstance(node, A.Call):
            return self.call(node, collecting)

        return UNKNOWN

    # -------------------------------------------------- ตัวดำเนินการสองข้าง
    def binop(self, op, left, right, node, collecting=False):
        if op in ("AND", "OR"):
            return _join(left, right)
        if op in ("EQ", "NE"):
            return BOOL

        # ไม่ทราบข้างใดข้างหนึ่ง = เงียบไว้ก่อน
        if left is UNKNOWN or right is UNKNOWN:
            return UNKNOWN if op not in _ORDER else BOOL

        if op in _ORDER:
            if not self._comparable(left, right):
                self._error(node, collecting,
                            f"เทียบ{_article(left)}กับ{_article(right)}"
                            f"ด้วย “{_OP_WORD[op]}” ไม่ได้",
                            hint="เทียบได้เฉพาะค่าชนิดเดียวกัน "
                                 "เช่น ตัวเลขกับตัวเลข")
            return BOOL

        if op == "PLUS":
            if left in NUMERIC and right in NUMERIC:
                return _join(left, right)
            if left == right and left in (STR, LIST):
                return left
            return self._bad_operands(op, left, right, node, collecting)

        if op == "MUL":
            if left in NUMERIC and right in NUMERIC:
                return _join(left, right)
            # "ก" คูณ 3 = ทำซ้ำข้อความ — Python ทำได้จริง จึงต้องยอม
            if left in (STR, LIST) and right in NUMERIC:
                return left
            if right in (STR, LIST) and left in NUMERIC:
                return right
            return self._bad_operands(op, left, right, node, collecting)

        if op in _ARITH:
            if left in NUMERIC and right in NUMERIC:
                return FLOAT if op == "DIV" else _join(left, right)
            return self._bad_operands(op, left, right, node, collecting)

        return UNKNOWN

    @staticmethod
    def _comparable(left, right):
        if left in NUMERIC and right in NUMERIC:
            return True
        return left == right and left in (STR, LIST)

    def _bad_operands(self, op, left, right, node, collecting):
        word = _OP_WORD.get(op, op)
        self._error(node, collecting,
                    f"เอา{_article(left)}ไป{word}กับ{_article(right)}ไม่ได้",
                    hint=_repair_hint(op, left, right))
        return UNKNOWN

    # -------------------------------------------------- การเรียกฟังก์ชัน
    def call(self, node, collecting=False):
        kinds = [self.expr(arg, collecting) for arg in node.args]

        if not isinstance(node.func, A.Name):
            self.expr(node.func, collecting)
            return UNKNOWN

        name = node.func.ident
        # ตัวแปรของผู้ใช้บังชื่อฟังก์ชันสำเร็จรูปได้ ต้องเช็คก่อน
        if name in self.func_types:
            return self.func_types[name]
        if self.declared(name) or name not in BUILTINS:
            return UNKNOWN

        signature = SIGNATURES.get(name)
        if signature is None:
            return UNKNOWN

        params, result = signature
        for index, (want, got) in enumerate(zip(params, kinds), start=1):
            if want is None or got is UNKNOWN or got in want:
                continue
            self._error(node, collecting,
                        f"ฟังก์ชัน “{name}” ต้องการ{_or(want)}"
                        f"ในค่าที่ {index} แต่ได้{_article(got)}",
                        code=Code.BAD_ARGUMENT_TYPE,
                        length=len(name))
        return result

    # -------------------------------------------------- รายงาน
    def _error(self, node, collecting, message, hint=None,
               code=Code.BAD_OPERAND, length=0):
        # รอบเก็บชนิดที่ฟังก์ชันคืน เดินซ้ำโค้ดเดิม จึงต้องไม่รายงานซ้ำ
        if collecting:
            return
        col, width = _anchor(node)
        self.bag.error(code, message, phase="semantic",
                       line=getattr(node, "line", None),
                       col=col, length=length or width, hint=hint)


def _anchor(node):
    """หาตำแหน่งคอลัมน์ที่ควรขีดเส้นใต้ — คืน (คอลัมน์, ความยาว)

    โหนดอย่าง BinOp ไม่มีคอลัมน์ของตัวเอง จึงไล่ลงไปหาโหนดซ้ายสุดที่มี
    เพื่อให้ caret ชี้ตรงจุดที่ผู้ใช้อ่านแล้วเข้าใจ ไม่ใช่ชี้ทั้งบรรทัด
    """
    seen = set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        col = getattr(node, "col", None)
        if col is not None:
            width = len(node.ident) if isinstance(node, A.Name) else 1
            return col, width
        node = (getattr(node, "left", None) or getattr(node, "operand", None)
                or getattr(node, "target", None) or getattr(node, "func", None))
    return None, 0


def _repair_hint(op, left, right):
    """คำแนะนำที่ชี้ทางออกจริง ๆ ไม่ใช่บอกแค่ว่าผิด

    กรณีที่พบบ่อยที่สุดคือ "อยากตัดตัวอักษรออกจากข้อความ" แล้วเขียนเป็น ลบ
    ซึ่ง Python เองก็ทำไม่ได้ — ต้องใช้การตัดชิ้นส่วนแทน
    """
    if left in SEQUENCE and right in NUMERIC and op in ("MINUS", "DIV", "IDIV"):
        return ("ถ้าต้องการตัดตัวท้ายออก ใช้ ตัดท้าย(ค่า, จำนวน) "
                "· ตัดหัวใช้ ตัดหน้า(ค่า, จำนวน) · ตัดช่วงใช้ ตัดเอา(ค่า, เริ่ม, จบ)")
    if STR in (left, right) and op == "PLUS":
        return ("ถ้าต้องการต่อข้อความ ให้แปลงชนิดก่อนด้วย ข้อความ(ค่า) "
                "หรือใช้ ต่อข้อความ([...])")
    return "ลองใช้ ชนิด(ค่า) ดูว่าค่านั้นเป็นชนิดอะไร แล้วแปลงชนิดก่อน"


def _or(kinds):
    return " หรือ ".join(kinds)


def typecheck(program, bag, predefined=None):
    return TypeChecker(bag, predefined).run(program)
