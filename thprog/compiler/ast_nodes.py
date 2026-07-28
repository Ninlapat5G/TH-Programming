# -*- coding: utf-8 -*-
"""โครงสร้างต้นไม้ไวยากรณ์ (AST) — เป็นกลาง ไม่ผูกกับทั้งภาษาไทยและ Python"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


class Node:
    line: int = 0


# ------------------------------------------------------------------ นิพจน์
@dataclass
class Num(Node):
    value: Any
    line: int = 0


@dataclass
class Str(Node):
    value: str
    line: int = 0


@dataclass
class Const(Node):
    value: str          # "True" | "False" | "None"
    line: int = 0


@dataclass
class Name(Node):
    ident: str
    line: int = 0
    col: int = 0


@dataclass
class BinOp(Node):
    op: str             # canonical id เช่น PLUS, GT, AND
    left: Node = None
    right: Node = None
    line: int = 0


@dataclass
class UnaryOp(Node):
    op: str             # MINUS | NOT
    operand: Node = None
    line: int = 0


@dataclass
class Call(Node):
    func: Node = None
    args: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class Index(Node):
    target: Node = None
    key: Node = None
    line: int = 0


@dataclass
class Attr(Node):
    """เข้าถึงสมาชิกของอ็อบเจ็กต์ Python —  math.sqrt  ·  ข้อความ.upper"""
    target: Node = None
    name: str = ""
    line: int = 0


@dataclass
class ListLit(Node):
    items: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class DictLit(Node):
    pairs: List[Tuple[Node, Node]] = field(default_factory=list)
    line: int = 0


# ------------------------------------------------------------------ คำสั่ง
@dataclass
class Program(Node):
    body: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class Print(Node):
    values: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class Assign(Node):
    target: Node = None
    value: Node = None
    op: Optional[str] = None      # None = '=' , 'PLUS'/'MINUS' = += / -=
    line: int = 0


@dataclass
class Ask(Node):
    prompt: Optional[Node] = None
    target: Node = None
    cast: Optional[str] = None    # 'int' | 'float' | 'str' | None
    line: int = 0


@dataclass
class AppendTo(Node):
    target: Node = None
    value: Node = None
    line: int = 0


@dataclass
class If(Node):
    branches: List[Tuple[Node, List[Node]]] = field(default_factory=list)
    orelse: Optional[List[Node]] = None
    line: int = 0


@dataclass
class RepeatTimes(Node):
    count: Node = None
    body: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class ForEach(Node):
    var: str = ""
    iterable: Node = None
    body: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class CountLoop(Node):
    var: str = ""
    start: Node = None
    end: Node = None
    step: Optional[Node] = None
    body: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class While(Node):
    cond: Node = None
    body: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class Break(Node):
    line: int = 0


@dataclass
class Continue(Node):
    line: int = 0


@dataclass
class FuncDef(Node):
    name: str = ""
    params: List[str] = field(default_factory=list)
    body: List[Node] = field(default_factory=list)
    line: int = 0


@dataclass
class Return(Node):
    value: Optional[Node] = None
    line: int = 0


@dataclass
class ExprStmt(Node):
    expr: Node = None
    line: int = 0
    # โหมดโต้ตอบ/บรรทัดคำสั่ง: แสดงค่าที่ได้ออกมาเลย (ข้ามถ้าเป็นค่าว่าง)
    # ไฟล์ .th ไม่เปิดโหมดนี้ พฤติกรรมของโปรแกรมที่เขียนไว้แล้วจึงไม่เปลี่ยน
    show: bool = False


@dataclass
class Import(Node):
    """นำเข้าโมดูลของ Python

        module="math"                        ->  import math
        module="math", alias="คณิต"           ->  import math as คณิต
        module="math", names=["sqrt","pi"]   ->  from math import sqrt, pi
        module="math", names=["sqrt"],
                       alias="ราก"            ->  from math import sqrt as ราก
    """
    module: str = ""
    names: Optional[List[str]] = None
    alias: Optional[str] = None
    line: int = 0

    def bound_names(self):
        """ชื่อที่คำสั่งนี้ทำให้ใช้งานได้ในโปรแกรม"""
        if self.names:
            return [self.alias] if self.alias else list(self.names)
        if self.alias:
            return [self.alias]
        return [self.module.split(".")[0]]


@dataclass
class BindMethod(Node):
    """ผูกเมธอดของ Python ให้เป็นกริยาไทย (UFCS)

        นำเข้าวิธี strip เป็นตัดช่องว่าง

    กลายเป็นฟังก์ชันอิสระที่รับตัวมันเป็นอาร์กิวเมนต์แรก จึงเขียนแบบไทยได้

        ตัดช่องว่างของประโยค          แทน   ประโยค.strip()
    """
    method: str = ""
    alias: str = ""
    line: int = 0


@dataclass
class UseLibrary(Node):
    """ใช้คลังคำไทย —  ใช้คลัง ข้อความ

    ตัวแยกวิเคราะห์จะแทนที่โหนดนี้ด้วยเนื้อในของไฟล์คลังทันทีที่อ่านเจอ
    จึงไม่มีโหนดชนิดนี้หลงเหลือถึงขั้นสร้างโค้ด
    """
    name: str = ""
    line: int = 0
