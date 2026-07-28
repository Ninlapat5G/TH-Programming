# -*- coding: utf-8 -*-
"""
ขั้นที่ 7 : ตัวปรับให้เหมาะที่สุด (Optimizer)
=============================================

ทำงานบน AST ก่อนสร้างโค้ด ทำสามอย่างที่คอมไพเลอร์มาตรฐานควรมี

1. **Constant folding** — คำนวณค่าที่รู้ผลตั้งแต่ตอนคอมไพล์
       ให้วินาทีเป็น60คูณ60      ->  วินาที = 3600
2. **Algebraic simplification** — ตัดการคำนวณที่ไม่มีผล
       x บวก 0 · x คูณ 1 · ไม่(ไม่(x))
3. **Dead code elimination** — ตัดกิ่งที่ไม่มีทางถูกใช้
       ถ้า จริง ...            ->  เหลือเฉพาะบล็อกที่ทำงานจริง
       ทำซ้ำ 0 ครั้ง ...        ->  ตัดทิ้งทั้งบล็อก
       คำสั่งหลัง คืนค่า/หยุด    ->  ตัดทิ้ง

ทุกการแปลงต้อง "ปลอดภัยเสมอ" คือผลลัพธ์ของโปรแกรมต้องไม่เปลี่ยน
ถ้าไม่แน่ใจ จะไม่แตะ
"""

import operator

from . import ast_nodes as A

_ARITH = {
    "PLUS": operator.add, "MINUS": operator.sub, "MUL": operator.mul,
    "IDIV": operator.floordiv, "MOD": operator.mod, "POW": operator.pow,
}
_COMPARE = {
    "EQ": operator.eq, "NE": operator.ne, "LT": operator.lt,
    "GT": operator.gt, "LE": operator.le, "GE": operator.ge,
}


class Optimizer:
    def __init__(self):
        self.folded = 0        # จำนวนนิพจน์ที่คำนวณล่วงหน้าได้
        self.removed = 0       # จำนวนคำสั่งที่ตัดทิ้ง

    # ================================================== ทางเข้า
    def run(self, program):
        program.body = self.block(program.body)
        return program

    @property
    def changes(self):
        return self.folded + self.removed

    # ================================================== คำสั่ง
    def block(self, body):
        out = []
        for node in body:
            kept = self.stmt(node)
            if kept is None:
                self.removed += 1
                continue
            out.append(kept)
            if isinstance(kept, (A.Return, A.Break, A.Continue)):
                self.removed += len(body) - body.index(node) - 1
                break
        return out

    def stmt(self, node):
        if isinstance(node, A.Print):
            node.values = [self.expr(v) for v in node.values]

        elif isinstance(node, A.Assign):
            node.value = self.expr(node.value)

        elif isinstance(node, A.Ask):
            if node.prompt is not None:
                node.prompt = self.expr(node.prompt)

        elif isinstance(node, A.AppendTo):
            node.value = self.expr(node.value)
            node.target = self.expr(node.target)

        elif isinstance(node, A.ExprStmt):
            node.expr = self.expr(node.expr)

        elif isinstance(node, A.Return):
            if node.value is not None:
                node.value = self.expr(node.value)

        elif isinstance(node, A.If):
            return self._fold_if(node)

        elif isinstance(node, A.RepeatTimes):
            node.count = self.expr(node.count)
            node.body = self.block(node.body)
            if isinstance(node.count, A.Num) and node.count.value <= 0:
                return None            # ทำซ้ำ 0 ครั้ง = ไม่ต้องทำ
            if not node.body:
                return None

        elif isinstance(node, A.ForEach):
            node.iterable = self.expr(node.iterable)
            node.body = self.block(node.body)
            if isinstance(node.iterable, A.ListLit) and not node.iterable.items:
                return None            # วนรายการว่าง = ไม่ต้องทำ

        elif isinstance(node, A.CountLoop):
            node.start = self.expr(node.start)
            node.end = self.expr(node.end)
            if node.step is not None:
                node.step = self.expr(node.step)
            node.body = self.block(node.body)

        elif isinstance(node, A.While):
            node.cond = self.expr(node.cond)
            node.body = self.block(node.body)
            if _is_false(node.cond):
                return None            # เงื่อนไขเป็นเท็จเสมอ = ไม่เคยวน

        elif isinstance(node, A.FuncDef):
            node.body = self.block(node.body)

        return node

    def _fold_if(self, node):
        """ตัดกิ่งเงื่อนไขที่รู้ผลแน่นอนตั้งแต่ตอนคอมไพล์"""
        branches = []
        for cond, body in node.branches:
            cond = self.expr(cond) if cond is not None else None
            body = self.block(body)
            if _is_false(cond):
                self.removed += 1
                continue               # กิ่งนี้ไม่มีทางเข้า
            if _is_true(cond):
                # กิ่งนี้ทำงานแน่นอน — กิ่งที่เหลือหลังจากนี้ไม่มีความหมาย
                if not branches:
                    self.removed += 1
                    return _inline(body)
                branches.append((cond, body))
                node.branches, node.orelse = branches, None
                return node
            branches.append((cond, body))

        orelse = self.block(node.orelse) if node.orelse else None
        if not branches:
            self.removed += 1
            return _inline(orelse) if orelse else None

        node.branches, node.orelse = branches, orelse
        return node

    # ================================================== นิพจน์
    def expr(self, node):
        if node is None:
            return None

        if isinstance(node, A.BinOp):
            node.left = self.expr(node.left)
            node.right = self.expr(node.right)
            return self._fold_binop(node)

        if isinstance(node, A.UnaryOp):
            node.operand = self.expr(node.operand)
            return self._fold_unary(node)

        if isinstance(node, A.Call):
            node.args = [self.expr(a) for a in node.args]

        elif isinstance(node, A.Index):
            node.target = self.expr(node.target)
            node.key = self.expr(node.key)

        elif isinstance(node, A.ListLit):
            node.items = [self.expr(i) for i in node.items]

        elif isinstance(node, A.DictLit):
            node.pairs = [(self.expr(k), self.expr(v)) for k, v in node.pairs]

        return node

    def _fold_binop(self, node):
        left, right, op = node.left, node.right, node.op

        # ---- คำนวณล่วงหน้าเมื่อทั้งสองข้างเป็นค่าคงที่
        lit_l, lit_r = _literal(left), _literal(right)
        if lit_l is not _NOPE and lit_r is not _NOPE:
            value = self._apply(op, lit_l, lit_r)
            if value is not _NOPE:
                self.folded += 1
                return _to_node(value, node.line)

        # ---- กฎพีชคณิตที่ปลอดภัย
        if op == "PLUS":
            if _is_num(right, 0):
                self.folded += 1
                return left
            if _is_num(left, 0):
                self.folded += 1
                return right
        elif op == "MINUS" and _is_num(right, 0):
            self.folded += 1
            return left
        elif op == "MUL":
            if _is_num(right, 1):
                self.folded += 1
                return left
            if _is_num(left, 1):
                self.folded += 1
                return right
        elif op == "DIV" and _is_num(right, 1):
            self.folded += 1
            return left
        elif op == "POW" and _is_num(right, 1):
            self.folded += 1
            return left

        return node

    def _fold_unary(self, node):
        inner = node.operand
        if node.op == "MINUS" and isinstance(inner, A.Num):
            self.folded += 1
            return A.Num(-inner.value, node.line)
        if node.op == "NOT":
            if _is_true(inner):
                self.folded += 1
                return A.Const("False", node.line)
            if _is_false(inner):
                self.folded += 1
                return A.Const("True", node.line)
            # ไม่(ไม่(x)) = x  ก็ต่อเมื่อ x เป็นค่าความจริงอยู่แล้ว
            if isinstance(inner, A.UnaryOp) and inner.op == "NOT" and \
                    isinstance(inner.operand, (A.Const, A.BinOp)):
                self.folded += 1
                return inner.operand
        return node

    @staticmethod
    def _apply(op, left, right):
        try:
            if op in _ARITH:
                if op in ("IDIV", "MOD") and right == 0:
                    return _NOPE
                return _ARITH[op](left, right)
            if op == "DIV":
                return _NOPE if right == 0 else left / right
            if op in _COMPARE:
                return _COMPARE[op](left, right)
            if op == "AND":
                return left and right
            if op == "OR":
                return left or right
        except (TypeError, ValueError, OverflowError, ZeroDivisionError):
            return _NOPE
        return _NOPE


# ---------------------------------------------------------------- ตัวช่วย
class _Nope:
    """ตัวแทนของ 'คำนวณล่วงหน้าไม่ได้' (ต่างจาก None ซึ่งเป็นค่าจริงในภาษา)"""


_NOPE = _Nope()
_CONSTS = {"True": True, "False": False, "None": None}


def _literal(node):
    if isinstance(node, A.Num):
        return node.value
    if isinstance(node, A.Str):
        return node.value
    if isinstance(node, A.Const):
        return _CONSTS[node.value]
    return _NOPE


def _to_node(value, line):
    if isinstance(value, bool):
        return A.Const("True" if value else "False", line)
    if isinstance(value, (int, float)):
        return A.Num(value, line)
    if isinstance(value, str):
        return A.Str(value, line)
    return A.Const("None", line)


def _is_num(node, want):
    return isinstance(node, A.Num) and node.value == want


def _is_true(node):
    return _literal(node) is not _NOPE and bool(_literal(node)) is True


def _is_false(node):
    return _literal(node) is not _NOPE and bool(_literal(node)) is False


def _inline(body):
    """แทนที่คำสั่ง if ที่รู้ผลแล้ว ด้วยเนื้อในของมัน"""
    if not body:
        return None
    if len(body) == 1:
        return body[0]
    block = A.If([(A.Const("True", body[0].line), body)], None, body[0].line)
    return block


def optimize(program):
    opt = Optimizer()
    opt.run(program)
    return program, opt
