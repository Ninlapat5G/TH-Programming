# -*- coding: utf-8 -*-
"""
TH-Programming — ภาษาโปรแกรมที่เขียนด้วยประโยคภาษาไทย
คอมไพล์เป็น Python ก่อนสั่งทำงาน

    from thprog import compile_source, run_source
    run_source('แสดง "สวัสดี"')
"""

from .pipeline import (compile_source, check_source, run_source, run,
                       new_segmenter, Program)
from .errors import ThaiError, CompileError
from .diagnostics import DiagnosticBag, Diagnostic

__version__ = "1.0.1"
__all__ = [
    "compile_source", "check_source", "run_source", "run", "new_segmenter",
    "Program", "ThaiError", "CompileError", "DiagnosticBag", "Diagnostic",
]
