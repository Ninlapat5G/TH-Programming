# -*- coding: utf-8 -*-
"""
ระบบรายงานข้อผิดพลาด (Diagnostics)
==================================

คอมไพเลอร์ที่ดีต้องบอกได้ว่า *ผิดตรงไหน* และ *ควรแก้อย่างไร* ไม่ใช่แค่ว่าผิด
โมดูลนี้เป็นศูนย์กลางของข้อความทุกชนิดที่คอมไพเลอร์พูดกับผู้ใช้

    [TH301] ข้อผิดพลาดความหมาย — บรรทัด 4 คอลัมน์ 12
       4 | แสดงราค
         |     ^^^
       ↳ ยังไม่เคยกำหนดค่าให้ตัวแปร "ราค"
       ↳ คำแนะนำ: หมายถึง "ราคา" หรือเปล่า?

หลักการ
  * ทุกข้อความมี "รหัส" เพื่อค้นหาและอ้างอิงได้
  * ทุกข้อความมีบรรทัด/คอลัมน์ และขีดเส้นใต้ตำแหน่งที่ผิดจริง
  * คอมไพเลอร์ **ไม่หยุดที่ข้อผิดพลาดแรก** แต่กู้คืนแล้วเดินต่อ
    เพื่อรายงานทุกจุดในรอบเดียว
"""

from dataclasses import dataclass
from typing import List, Optional

ERROR = "error"
WARNING = "warning"
NOTE = "note"

_LABEL = {
    ERROR: "ข้อผิดพลาด",
    WARNING: "คำเตือน",
    NOTE: "หมายเหตุ",
}

_PHASE_LABEL = {
    "lex": "การอ่านคำ",
    "syntax": "ไวยากรณ์",
    "semantic": "ความหมาย",
    "runtime": "ขณะทำงาน",
    "internal": "ภายในคอมไพเลอร์",
}


# ======================================================================
#  รหัสข้อผิดพลาด
#     TH1xx  ระดับตัวอักษร      TH2xx  ระดับไวยากรณ์
#     TH3xx  ระดับความหมาย      TH4xx  ขณะทำงาน
#     TH5xx  ภายในคอมไพเลอร์    TW1xx  คำเตือน
# ======================================================================
class Code:
    # --- lexical ---
    UNKNOWN_CHAR = "TH101"
    UNTERMINATED_STRING = "TH102"

    # --- syntax ---
    UNKNOWN_STATEMENT = "TH201"
    BAD_INDENT = "TH202"
    EMPTY_BLOCK = "TH203"
    DANGLING_ELSE = "TH204"
    DUPLICATE_ELSE = "TH205"
    BAD_EXPRESSION = "TH206"
    RESERVED_AS_NAME = "TH207"
    LIBRARY_ERROR = "TH208"

    # --- semantic ---
    UNDEFINED_NAME = "TH301"
    UNKNOWN_FUNCTION = "TH302"
    WRONG_ARITY = "TH303"
    BREAK_OUTSIDE_LOOP = "TH304"
    RETURN_OUTSIDE_FUNC = "TH305"
    DUPLICATE_FUNCTION = "TH306"
    ASSIGN_TO_FUNCTION = "TH307"

    # --- ชนิดข้อมูล ---
    BAD_OPERAND = "TH311"
    NOT_INDEXABLE = "TH312"
    BAD_ARGUMENT_TYPE = "TH313"

    # --- runtime ---
    RUNTIME = "TH401"

    # --- warnings ---
    TYPO_GUESS = "TW101"
    USED_BEFORE_ASSIGN = "TW102"
    UNUSED_VARIABLE = "TW103"
    UNREACHABLE_CODE = "TW104"
    MODULE_NOT_FOUND = "TW105"
    PREFER_THAI_WORD = "TW106"


@dataclass
class Diagnostic:
    code: str
    severity: str
    message: str
    phase: str = "semantic"
    line: Optional[int] = None
    col: Optional[int] = None
    length: int = 0
    source: Optional[str] = None
    hint: Optional[str] = None

    # ------------------------------------------------------------------
    def render(self, color=False):
        head = f"[{self.code}] {_LABEL[self.severity]}"
        phase = _PHASE_LABEL.get(self.phase)
        if phase:
            head += f"{phase}"
        if self.line is not None:
            head += f" — บรรทัด {self.line}"
            if self.col is not None:
                head += f" คอลัมน์ {self.col + 1}"

        out = [_paint(head, self.severity, color)]

        if self.source is not None and self.line is not None:
            gutter = f"{self.line:>4} | "
            out.append(gutter + self.source.rstrip())
            if self.col is not None:
                pad = " " * len(f"{self.line:>4}") + " | "
                caret = " " * self.col + "^" * max(1, self.length)
                out.append(_paint(pad + caret, self.severity, color))

        out.append(f"     ↳ {self.message}")
        if self.hint:
            out.append(f"     ↳ คำแนะนำ: {self.hint}")
        return "\n".join(out)

    def to_dict(self):
        """รูปแบบที่เครื่องอ่านได้ — ใช้กับ editor, CI และเครื่องมือภายนอก

        คอลัมน์ในนี้เริ่มที่ 1 ตามธรรมเนียมของเครื่องมือทั่วไป
        (ภายในคอมไพเลอร์เก็บแบบเริ่มที่ 0)
        """
        return {
            "code": self.code,
            "severity": self.severity,
            "phase": self.phase,
            "message": self.message,
            "hint": self.hint,
            "line": self.line,
            "column": None if self.col is None else self.col + 1,
            "length": self.length or None,
            "source": self.source,
        }

    def __str__(self):
        return self.render()


_COLORS = {ERROR: "\033[91m", WARNING: "\033[93m", NOTE: "\033[96m"}


def _paint(text, severity, color):
    if not color:
        return text
    return f"{_COLORS.get(severity, '')}{text}\033[0m"


# ======================================================================
class DiagnosticBag:
    """ที่รวบรวมข้อความทั้งหมดของการคอมไพล์หนึ่งครั้ง"""

    def __init__(self, source="", name="<th>"):
        self.items: List[Diagnostic] = []
        self.name = name
        self.lines = source.splitlines()

    # ------------------------------------------------------------------
    def _source_of(self, line):
        if line and 0 < line <= len(self.lines):
            return self.lines[line - 1]
        return None

    def add(self, code, severity, message, phase="semantic",
            line=None, col=None, length=0, hint=None, source=None):
        self.items.append(Diagnostic(
            code, severity, message, phase, line, col, length,
            source if source is not None else self._source_of(line), hint))
        return self.items[-1]

    def error(self, code, message, **kw):
        return self.add(code, ERROR, message, **kw)

    def record(self, err):
        """บันทึกข้อผิดพลาดที่เฟสหนึ่งโยนออกมา ให้กลายเป็นรายการในถุงนี้"""
        item = err.to_diagnostic()
        if item.source is None:
            item.source = self._source_of(item.line)
        self.items.append(item)
        return item

    def warning(self, code, message, **kw):
        kw.setdefault("phase", "semantic")
        return self.add(code, WARNING, message, **kw)

    # ------------------------------------------------------------------
    @property
    def errors(self):
        return [d for d in self.items if d.severity == ERROR]

    @property
    def warnings(self):
        return [d for d in self.items if d.severity == WARNING]

    def has_errors(self):
        return any(d.severity == ERROR for d in self.items)

    def sorted_items(self):
        return sorted(self.items, key=lambda d: (d.line or 0, d.col or 0))

    def render(self, color=False, only=None):
        chosen = [d for d in self.sorted_items()
                  if only is None or d.severity == only]
        return "\n\n".join(d.render(color) for d in chosen)

    def to_dict(self, ok=None):
        """สรุปผลการคอมไพล์ทั้งไฟล์ในรูปที่เครื่องอ่านได้"""
        return {
            "file": self.name,
            "ok": (not self.has_errors()) if ok is None else ok,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "diagnostics": [d.to_dict() for d in self.sorted_items()],
        }

    def to_json(self, ok=None, indent=2):
        import json
        return json.dumps(self.to_dict(ok), ensure_ascii=False, indent=indent)

    def summary(self):
        errors, warnings = len(self.errors), len(self.warnings)
        parts = []
        if errors:
            parts.append(f"{errors} ข้อผิดพลาด")
        if warnings:
            parts.append(f"{warnings} คำเตือน")
        return " · ".join(parts) if parts else "ไม่พบปัญหา"

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.sorted_items())
