# -*- coding: utf-8 -*-
"""
ข้อผิดพลาดของ TH-Programming — ข้อความเป็นภาษาไทยทั้งหมด

แบ่งเป็นสองระดับ
  * ข้อผิดพลาด "รายจุด" (LexError / ParseError / SemanticError)
    แต่ละเฟสโยนออกมา แล้วถูกแปลงเป็น Diagnostic เก็บสะสมไว้
  * ข้อผิดพลาด "รวม" (CompileError)
    โยนออกจากคอมไพเลอร์ครั้งเดียวตอนจบ พร้อมรายการปัญหาทั้งหมด
"""

from .diagnostics import Code, Diagnostic, DiagnosticBag, ERROR


class ThaiError(Exception):
    """ข้อผิดพลาดฐานของทั้งคอมไพเลอร์"""

    phase = "internal"
    code = Code.RUNTIME

    def __init__(self, message, line=None, source=None, hint=None,
                 col=None, length=0, code=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.source = source
        self.hint = hint
        self.col = col
        self.length = length
        if code:
            self.code = code

    def to_diagnostic(self):
        return Diagnostic(self.code, ERROR, self.message, self.phase,
                          self.line, self.col, self.length,
                          self.source, self.hint)

    def render(self, color=False):
        return self.to_diagnostic().render(color)

    def __str__(self):
        return self.render()


class LexError(ThaiError):
    phase = "lex"
    code = Code.UNKNOWN_CHAR


class ParseError(ThaiError):
    phase = "syntax"
    code = Code.UNKNOWN_STATEMENT


class SemanticError(ThaiError):
    phase = "semantic"
    code = Code.UNDEFINED_NAME


class RuntimeThaiError(ThaiError):
    phase = "runtime"
    code = Code.RUNTIME


class CompileError(ThaiError):
    """รวมทุกปัญหาที่พบในการคอมไพล์หนึ่งครั้ง"""

    phase = "internal"

    def __init__(self, bag: DiagnosticBag, name="<th>"):
        self.bag = bag
        self.name = name
        super().__init__(f"คอมไพล์ไม่สำเร็จ — พบ {len(bag.errors)} ข้อผิดพลาด")

    def render(self, color=False):
        body = self.bag.render(color)
        tail = f"สรุป: {self.bag.summary()} ในไฟล์ {self.name}"
        return f"{body}\n\n{tail}" if body else tail
