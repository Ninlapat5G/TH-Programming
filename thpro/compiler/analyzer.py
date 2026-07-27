# -*- coding: utf-8 -*-
"""
ขั้นที่ 5 : ตัววิเคราะห์ความหมาย (Semantic Analyzer)
====================================================

ตรวจสิ่งที่ Python จะไม่บอกจนกว่าจะรันจริง เพื่อให้เจอปัญหาตั้งแต่ตอนคอมไพล์
  * ใช้ตัวแปรที่ไม่เคยกำหนดค่า (พร้อมเดาชื่อที่น่าจะตั้งใจ)
  * เรียกฟังก์ชันที่ไม่มีอยู่ หรือส่งจำนวนอาร์กิวเมนต์ไม่ตรง
  * ใช้ หยุด/ข้าม นอกลูป หรือ คืนค่า นอกฟังก์ชัน
  * ตัวแปรที่ประกาศแล้วไม่ได้ใช้ · โค้ดที่เข้าไม่ถึง

**ไม่หยุดที่ข้อผิดพลาดแรก** — บันทึกลง DiagnosticBag แล้ววิเคราะห์ต่อ
เพื่อรายงานทุกจุดในรอบเดียว
"""

from ..diagnostics import Code
from ..lang.builtins import BUILTINS
from . import ast_nodes as A
from .normalizer import suggest
from .symbols import SymbolTable, VARIABLE, FUNCTION, PARAMETER, LOOP_VAR


class Analyzer:
    def __init__(self, bag, predefined=None):
        self.bag = bag
        self.table = SymbolTable(predefined)
        self.functions = {}          # ชื่อ -> (จำนวนพารามิเตอร์, บรรทัดที่ประกาศ)
        self.assigned_anywhere = set(predefined or ())
        self.loop_depth = 0
        self.func_depth = 0

    # ================================================== ทางเข้า
    def run(self, program):
        self._collect(program.body)
        for name, (arity, line) in self.functions.items():
            self.table.declare_global(name, FUNCTION, line, arity)
        self.block(program.body)
        self._report_unused(self.table.root)
        return self.bag

    def _collect(self, body):
        """รอบแรก: เก็บชื่อทุกอย่างที่เคยถูกกำหนดค่าไว้ที่ใดที่หนึ่ง

        ทำให้เรียกฟังก์ชันที่ประกาศทีหลังได้ และแยกแยะ "ไม่เคยมีชื่อนี้เลย"
        ออกจาก "มีอยู่ แต่ยังไม่ถึงคิว"
        """
        for node in body:
            if isinstance(node, A.FuncDef):
                if node.name in self.functions:
                    self._warn(Code.DUPLICATE_FUNCTION, node,
                               f'ฟังก์ชัน "{node.name}" ถูกประกาศซ้ำ '
                               f"ตัวหลังจะทับตัวแรก")
                self.functions[node.name] = (len(node.params), node.line)
                self.assigned_anywhere.update(node.params)
                self.assigned_anywhere.add(node.name)
                self._collect(node.body)
            elif isinstance(node, A.Assign) and isinstance(node.target, A.Name):
                self.assigned_anywhere.add(node.target.ident)
            elif isinstance(node, A.Ask):
                self.assigned_anywhere.add(_name_of(node.target))
            elif isinstance(node, (A.ForEach, A.CountLoop)):
                self.assigned_anywhere.add(node.var)
                self._collect(node.body)
            elif isinstance(node, (A.While, A.RepeatTimes)):
                self._collect(node.body)
            elif isinstance(node, A.If):
                for _cond, branch in node.branches:
                    self._collect(branch)
                if node.orelse:
                    self._collect(node.orelse)

    # ================================================== คำสั่ง
    def block(self, body):
        for index, node in enumerate(body):
            self.stmt(node)
            if isinstance(node, (A.Return, A.Break, A.Continue)) and \
                    index + 1 < len(body):
                self._warn(Code.UNREACHABLE_CODE, body[index + 1],
                           "คำสั่งนี้ไม่มีทางถูกเรียกใช้ "
                           "เพราะบรรทัดก่อนหน้าออกจากบล็อกไปแล้ว",
                           hint="ลองย้ายขึ้นไปก่อนบรรทัดนั้น หรือลบทิ้ง")
                break

    def stmt(self, node):
        if isinstance(node, A.Print):
            for value in node.values:
                self.expr(value)

        elif isinstance(node, A.Assign):
            self.expr(node.value)
            if isinstance(node.target, A.Name):
                name = node.target.ident
                if node.op and self.table.lookup(name) is None:
                    self._undefined(node.target)
                elif name in self.functions:
                    self._warn(Code.ASSIGN_TO_FUNCTION, node.target,
                               f'"{name}" เป็นชื่อฟังก์ชัน การกำหนดค่าทับ '
                               f"จะทำให้เรียกฟังก์ชันนั้นไม่ได้อีก",
                               length=len(name))
                self.table.declare(name, VARIABLE, node.line)
            else:
                self.expr(node.target)

        elif isinstance(node, A.Ask):
            if node.prompt is not None:
                self.expr(node.prompt)
            self.table.declare(_name_of(node.target), VARIABLE, node.line)

        elif isinstance(node, A.AppendTo):
            self.expr(node.value)
            self.expr(node.target)

        elif isinstance(node, A.If):
            for cond, branch in node.branches:
                if cond is not None:
                    self.expr(cond)
                self.block(branch)
            if node.orelse:
                self.block(node.orelse)

        elif isinstance(node, A.RepeatTimes):
            self.expr(node.count)
            self._loop(node.body)

        elif isinstance(node, A.ForEach):
            self.expr(node.iterable)
            self.table.declare(node.var, LOOP_VAR, node.line)
            self._loop(node.body)

        elif isinstance(node, A.CountLoop):
            self.expr(node.start)
            self.expr(node.end)
            if node.step is not None:
                self.expr(node.step)
            self.table.declare(node.var, LOOP_VAR, node.line)
            self._loop(node.body)

        elif isinstance(node, A.While):
            self.expr(node.cond)
            self._loop(node.body)

        elif isinstance(node, (A.Break, A.Continue)):
            if self.loop_depth == 0:
                word = "หยุด" if isinstance(node, A.Break) else "ข้าม"
                self._error(Code.BREAK_OUTSIDE_LOOP, node,
                            f'คำสั่ง "{word}" ใช้ได้เฉพาะภายในลูป',
                            hint="ย้ายเข้าไปในบล็อก ทำซ้ำ / นับ / ตราบใดที่")

        elif isinstance(node, A.FuncDef):
            self.table.declare(node.name, FUNCTION, node.line, len(node.params))
            scope = self.table.enter(node.name)
            for param in node.params:
                self.table.declare(param, PARAMETER, node.line)
            self.func_depth += 1
            saved, self.loop_depth = self.loop_depth, 0
            self.block(node.body)
            self.loop_depth = saved
            self.func_depth -= 1
            self._report_unused(scope)
            self.table.leave()

        elif isinstance(node, A.Return):
            if self.func_depth == 0:
                self._error(Code.RETURN_OUTSIDE_FUNC, node,
                            'คำสั่ง "คืนค่า" ใช้ได้เฉพาะภายในฟังก์ชัน',
                            hint="ถ้าต้องการแสดงผล ให้ใช้คำสั่ง แสดง แทน")
            if node.value is not None:
                self.expr(node.value)

        elif isinstance(node, A.ExprStmt):
            self.expr(node.expr)

    def _loop(self, body):
        self.loop_depth += 1
        self.block(body)
        self.loop_depth -= 1

    # ================================================== นิพจน์
    def expr(self, node):
        if node is None or isinstance(node, (A.Num, A.Str, A.Const)):
            return

        if isinstance(node, A.Name):
            # ต้องดูตารางสัญลักษณ์ก่อนเสมอ ผู้ใช้มีสิทธิ์ตั้งชื่อตัวแปร
            # ซ้ำกับฟังก์ชันสำเร็จรูป เช่น "ยอดรวม" — ตัวแปรของผู้ใช้ต้องมาก่อน
            if self.table.mark_read(node.ident) is not None:
                return
            if node.ident in BUILTINS:
                return
            self._undefined(node)

        elif isinstance(node, A.BinOp):
            self.expr(node.left)
            self.expr(node.right)

        elif isinstance(node, A.UnaryOp):
            self.expr(node.operand)

        elif isinstance(node, A.Index):
            self.expr(node.target)
            self.expr(node.key)

        elif isinstance(node, A.ListLit):
            for item in node.items:
                self.expr(item)

        elif isinstance(node, A.DictLit):
            for key, value in node.pairs:
                self.expr(key)
                self.expr(value)

        elif isinstance(node, A.Call):
            self._call(node)

    def _call(self, node):
        for arg in node.args:
            self.expr(arg)

        if not isinstance(node.func, A.Name):
            self.expr(node.func)
            return

        name = node.func.ident
        if name in self.functions:
            self.table.mark_read(name)
            need, where = self.functions[name]
            if len(node.args) != need:
                self._error(Code.WRONG_ARITY, node.func,
                            f'ฟังก์ชัน "{name}" ต้องการ {need} ค่า '
                            f"แต่ได้รับ {len(node.args)} ค่า",
                            length=len(name),
                            hint=f"ประกาศไว้ที่บรรทัด {where}")
            return

        if name in BUILTINS or self.table.mark_read(name) is not None:
            return

        guess = suggest(name, set(self.functions) | set(BUILTINS), 0.6)
        self._error(Code.UNKNOWN_FUNCTION, node.func,
                    f'ไม่รู้จักฟังก์ชัน "{name}"', length=len(name),
                    hint=(f'หมายถึง "{guess}" หรือเปล่า?' if guess else
                          "ต้องประกาศด้วยคำสั่ง ฟังก์ชัน ก่อนเรียกใช้"))

    # ================================================== รายงาน
    def _undefined(self, node):
        name = node.ident
        if name in self.assigned_anywhere:
            self._warn(Code.USED_BEFORE_ASSIGN, node,
                       f'ตัวแปร "{name}" ถูกใช้ก่อนถูกกำหนดค่าในลำดับการอ่าน',
                       length=len(name))
        else:
            guess = suggest(name, self.assigned_anywhere | set(BUILTINS), 0.6)
            self._error(Code.UNDEFINED_NAME, node,
                        f'ยังไม่เคยกำหนดค่าให้ตัวแปร "{name}"',
                        length=len(name),
                        hint=(f'หมายถึง "{guess}" หรือเปล่า?' if guess else
                              f"ลองเขียน  ให้{name}เป็น <ค่า>  ก่อนใช้งาน"))
        # ประกาศทิ้งไว้ กันไม่ให้ฟ้องซ้ำทุกบรรทัดที่ใช้ชื่อเดิม
        symbol = self.table.declare(name, VARIABLE, node.line)
        symbol.reads += 1

    def _report_unused(self, scope):
        for symbol in scope.unused():
            if symbol.line:
                self.bag.warning(
                    Code.UNUSED_VARIABLE,
                    f'ตัวแปร "{symbol.name}" ถูกกำหนดค่า แต่ไม่เคยถูกนำไปใช้',
                    phase="semantic", line=symbol.line,
                    hint="ถ้าไม่ได้ใช้แล้ว ลบทิ้งได้เลย")

    def _error(self, code, node, message, hint=None, length=0):
        self.bag.error(code, message, phase="semantic",
                       line=getattr(node, "line", None),
                       col=getattr(node, "col", None),
                       length=length, hint=hint)

    def _warn(self, code, node, message, hint=None, length=0):
        self.bag.warning(code, message, phase="semantic",
                         line=getattr(node, "line", None),
                         col=getattr(node, "col", None),
                         length=length, hint=hint)


def _name_of(target):
    if isinstance(target, str):
        return target
    return target.ident if isinstance(target, A.Name) else str(target)


def analyze(program, bag, predefined=None):
    return Analyzer(bag, predefined).run(program)
