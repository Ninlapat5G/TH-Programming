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
