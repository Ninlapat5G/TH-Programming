# -*- coding: utf-8 -*-
"""
ตารางสัญลักษณ์ (Symbol Table)
=============================

โครงสร้างมาตรฐานของคอมไพเลอร์ ใช้ตอบคำถามว่า
    ชื่อนี้ประกาศไว้หรือยัง · ประกาศที่บรรทัดไหน · เป็นอะไร · ถูกใช้หรือเปล่า

ขอบเขต (scope) ซ้อนกันเป็นลูกโซ่
    ระดับบนสุด (โมดูล)  →  ฟังก์ชัน  →  ฟังก์ชันซ้อน ...
การค้นหาจะไล่จากขอบเขตในสุดออกไปข้างนอก
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

VARIABLE = "ตัวแปร"
FUNCTION = "ฟังก์ชัน"
PARAMETER = "พารามิเตอร์"
LOOP_VAR = "ตัวแปรลูป"
BUILTIN = "ฟังก์ชันสำเร็จรูป"
MODULE = "ไลบรารี"


@dataclass
class Symbol:
    name: str
    kind: str = VARIABLE
    line: int = 0
    arity: Optional[int] = None     # เฉพาะฟังก์ชัน
    reads: int = 0
    writes: int = 0

    @property
    def used(self):
        return self.reads > 0


@dataclass
class Scope:
    name: str = "โมดูล"
    parent: Optional["Scope"] = None
    symbols: Dict[str, Symbol] = field(default_factory=dict)
    children: List["Scope"] = field(default_factory=list)

    # ------------------------------------------------------------------
    def declare(self, name, kind=VARIABLE, line=0, arity=None):
        existing = self.symbols.get(name)
        if existing is not None:
            existing.writes += 1
            if arity is not None:
                existing.arity = arity
            return existing
        symbol = Symbol(name, kind, line, arity, writes=1)
        self.symbols[name] = symbol
        return symbol

    def lookup_local(self, name):
        return self.symbols.get(name)

    def lookup(self, name):
        scope = self
        while scope is not None:
            found = scope.symbols.get(name)
            if found is not None:
                return found
            scope = scope.parent
        return None

    def push(self, name):
        child = Scope(name, self)
        self.children.append(child)
        return child

    # ------------------------------------------------------------------
    def all_names(self):
        names = set()
        scope = self
        while scope is not None:
            names |= set(scope.symbols)
            scope = scope.parent
        return names

    def unused(self):
        """ชื่อที่ประกาศแล้วไม่เคยถูกอ่าน (ไม่นับพารามิเตอร์และตัวแปรลูป)"""
        return [s for s in self.symbols.values()
                if not s.used and s.kind in (VARIABLE, MODULE)]


class SymbolTable:
    """ตัวจัดการขอบเขตทั้งหมดของโปรแกรมหนึ่งไฟล์"""

    def __init__(self, predefined=()):
        self.root = Scope("โมดูล")
        self.current = self.root
        for name in predefined or ():
            self.root.declare(name, VARIABLE, 0)

    # ------------------------------------------------------------------
    def enter(self, name):
        self.current = self.current.push(name)
        return self.current

    def leave(self):
        finished = self.current
        if self.current.parent is not None:
            self.current = self.current.parent
        return finished

    def declare(self, name, kind=VARIABLE, line=0, arity=None):
        return self.current.declare(name, kind, line, arity)

    def declare_global(self, name, kind=FUNCTION, line=0, arity=None):
        return self.root.declare(name, kind, line, arity)

    def lookup(self, name):
        return self.current.lookup(name)

    def visible_names(self):
        return self.current.all_names()

    def mark_read(self, name):
        symbol = self.lookup(name)
        if symbol is not None:
            symbol.reads += 1
        return symbol
