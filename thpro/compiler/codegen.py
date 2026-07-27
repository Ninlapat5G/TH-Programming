# -*- coding: utf-8 -*-
"""
ขั้นที่ 6 : ตัวสร้างโค้ด (Code Generator) — AST -> Python

จงใจสร้างโค้ดที่ "อ่านออก" เพื่อให้ผู้เรียนเปิดดูแล้วเข้าใจว่า
ประโยคภาษาไทยที่เขียนไป กลายเป็น Python หน้าตาแบบไหน
"""

import keyword

from . import ast_nodes as A
from ..lang.builtins import BUILTINS, HELPERS, IMPORT_LINES

PY_OP = {
    "PLUS": "+", "MINUS": "-", "MUL": "*", "DIV": "/", "IDIV": "//",
    "MOD": "%", "POW": "**",
    "EQ": "==", "NE": "!=", "LT": "<", "GT": ">", "LE": "<=", "GE": ">=",
    "AND": "and", "OR": "or",
}

# ระดับความสำคัญฝั่ง Python (ใช้ตัดสินว่าต้องใส่วงเล็บไหม)
PREC = {
    "OR": 1, "AND": 2,
    "EQ": 3, "NE": 3, "LT": 3, "GT": 3, "LE": 3, "GE": 3,
    "PLUS": 4, "MINUS": 4,
    "MUL": 5, "DIV": 5, "IDIV": 5, "MOD": 5,
    "POW": 7,
}
RIGHT_ASSOC = {"POW"}
ATOM_PREC = 99


def to_py_name(name):
    """แปลงชื่อไทยเป็นชื่อตัวแปร Python ที่ถูกต้อง (ไทยใช้ได้ตรง ๆ ใน Python 3)"""
    if name.isidentifier() and not keyword.iskeyword(name):
        return name
    safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)
    if not safe or safe[0].isdigit():
        safe = "_" + safe
    return safe + "_"


class CodeGen:
    def __init__(self, source_name="<th>"):
        self.user_funcs = set()
        self.lines = []
        self.map = []          # บรรทัด Python ที่ i มาจากบรรทัดไทยหมายเลขใด
        self.cur_line = 0
        self.linemap = {}
        self.indent = 0
        self.helpers = set()
        self.imports = set()
        self.loop_id = 0
        self.source_name = source_name

    # ------------------------------------------------ ตัวช่วยพิมพ์
    def emit(self, text=""):
        self.lines.append(("    " * self.indent + text) if text else "")
        self.map.append(self.cur_line)

    def use(self, helper):
        self.helpers.add(helper)
        self.imports.update(HELPERS[helper][1])
        return HELPERS[helper]

    # ------------------------------------------------ ทางเข้า
    def generate(self, program):
        # ฟังก์ชันที่ผู้ใช้ประกาศเอง ต้องไม่ถูกชื่อฟังก์ชันสำเร็จรูปทับ
        self.user_funcs = {n.name for n in _walk(program.body)
                           if isinstance(n, A.FuncDef)}
        body_start = len(self.lines)
        self.block(program.body)
        body = self.lines[body_start:]
        body_map = self.map[body_start:]

        head = [
            "# -*- coding: utf-8 -*-",
            f"# ไฟล์นี้ถูกสร้างอัตโนมัติจาก {self.source_name} โดยภาษาไทยโค้ด",
            "# แก้ไขที่ไฟล์ .th แล้วคอมไพล์ใหม่ อย่าแก้ไฟล์นี้โดยตรง",
            "",
            "# ให้พิมพ์ภาษาไทยได้ทุกคอนโซล แม้ codepage จะไม่ใช่ UTF-8",
            "import sys as _sys",
            "for _s in (_sys.stdin, _sys.stdout, _sys.stderr):",
            "    try:",
            "        _s.reconfigure(encoding='utf-8')",
            "    except Exception:",
            "        pass",
            "",
        ]
        for mod in sorted(self.imports):
            head.append(IMPORT_LINES[mod])
        if self.imports:
            head.append("")
        for key in sorted(self.helpers):
            head.append(HELPERS[key][0])
            head.append("")
        offset = sum(1 + h.count("\n") for h in head)
        self.linemap = {offset + i + 1: src
                        for i, src in enumerate(body_map) if src}
        return "\n".join(head + body) + "\n"

    # ------------------------------------------------ คำสั่ง
    def block(self, body):
        if not body:
            self.emit("pass")
            return
        for node in body:
            self.stmt(node)

    def stmt(self, node):
        self.cur_line = getattr(node, "line", 0)
        if isinstance(node, A.Print):
            args = ", ".join(self.expr(v) for v in node.values)
            self.emit(f"print({args})")

        elif isinstance(node, A.Assign):
            target = self.expr(node.target)
            value = self.expr(node.value)
            if node.op:
                self.emit(f"{target} {PY_OP[node.op]}= {value}")
            else:
                self.emit(f"{target} = {value}")

        elif isinstance(node, A.Ask):
            prompt = self.expr(node.prompt) if node.prompt is not None else '""'
            call = f"input({prompt})"
            if node.cast:
                call = f"{node.cast}({call})"
            self.emit(f"{to_py_name(node.target)} = {call}")

        elif isinstance(node, A.AppendTo):
            self.use("append")
            self.emit(f"_th_append({self.expr(node.target)}, "
                      f"{self.expr(node.value)})")

        elif isinstance(node, A.If):
            for i, (cond, body) in enumerate(node.branches):
                kw = "if" if i == 0 else "elif"
                self.emit(f"{kw} {self.expr(cond)}:")
                self.nested(body)
            if node.orelse is not None:
                self.emit("else:")
                self.nested(node.orelse)

        elif isinstance(node, A.RepeatTimes):
            var = f"_รอบที่{self.loop_id}"
            self.loop_id += 1
            self.emit(f"for {var} in range({self.expr(node.count)}):")
            self.nested(node.body)

        elif isinstance(node, A.ForEach):
            self.emit(f"for {to_py_name(node.var)} in {self.expr(node.iterable)}:")
            self.nested(node.body)

        elif isinstance(node, A.CountLoop):
            self.use("count")
            step = f", {self.expr(node.step)}" if node.step is not None else ""
            self.emit(f"for {to_py_name(node.var)} in _th_count("
                      f"{self.expr(node.start)}, {self.expr(node.end)}{step}):")
            self.nested(node.body)

        elif isinstance(node, A.While):
            self.emit(f"while {self.expr(node.cond)}:")
            self.nested(node.body)

        elif isinstance(node, A.Break):
            self.emit("break")

        elif isinstance(node, A.Continue):
            self.emit("continue")

        elif isinstance(node, A.FuncDef):
            params = ", ".join(to_py_name(p) for p in node.params)
            self.emit("")
            self.emit(f"def {to_py_name(node.name)}({params}):")
            self.nested(node.body)
            self.emit("")

        elif isinstance(node, A.Return):
            if node.value is None:
                self.emit("return")
            else:
                self.emit(f"return {self.expr(node.value)}")

        elif isinstance(node, A.ExprStmt):
            self.emit(self.expr(node.expr))

        else:
            raise AssertionError(f"ยังไม่รองรับโหนด {type(node).__name__}")

    def callee(self, func):
        """ชื่อฟังก์ชันสำเร็จรูปจะถูกแปลงเฉพาะตอนถูก 'เรียก' เท่านั้น
        เพื่อไม่ให้ชนกับชื่อตัวแปรที่ผู้ใช้ตั้งเอง"""
        if (isinstance(func, A.Name) and func.ident in BUILTINS
                and func.ident not in self.user_funcs):
            py, helper = BUILTINS[func.ident]
            if helper:
                self.use(helper)
            return py
        return self.expr(func, ATOM_PREC)

    def nested(self, body):
        self.indent += 1
        self.block(body)
        self.indent -= 1

    # ------------------------------------------------ นิพจน์
    def expr(self, node, parent_prec=0, right=False):
        if isinstance(node, A.Num):
            return repr(node.value)

        if isinstance(node, A.Str):
            return _py_string(node.value)

        if isinstance(node, A.Const):
            return node.value

        if isinstance(node, A.Name):
            return to_py_name(node.ident)

        if isinstance(node, A.BinOp):
            prec = PREC[node.op]
            # ตัวดำเนินการเชื่อมขวา (**) ต้องใส่วงเล็บฝั่งซ้ายแทนฝั่งขวา
            ra = node.op in RIGHT_ASSOC
            left = self.expr(node.left, prec, right=ra)
            rightside = self.expr(node.right, prec, right=not ra)
            text = f"{left} {PY_OP[node.op]} {rightside}"
            need = prec < parent_prec or (prec == parent_prec and right)
            return f"({text})" if need else text

        if isinstance(node, A.UnaryOp):
            if node.op == "NOT":
                inner = self.expr(node.operand, 3)
                return f"(not {inner})" if parent_prec > 2 else f"not {inner}"
            return f"-{self.expr(node.operand, 6)}"

        if isinstance(node, A.Call):
            args = ", ".join(self.expr(a) for a in node.args)
            return f"{self.callee(node.func)}({args})"

        if isinstance(node, A.Index):
            return f"{self.expr(node.target, ATOM_PREC)}[{self.expr(node.key)}]"

        if isinstance(node, A.ListLit):
            return "[" + ", ".join(self.expr(i) for i in node.items) + "]"

        if isinstance(node, A.DictLit):
            inner = ", ".join(f"{self.expr(k)}: {self.expr(v)}"
                              for k, v in node.pairs)
            return "{" + inner + "}"

        raise AssertionError(f"ยังไม่รองรับนิพจน์ {type(node).__name__}")


def _walk(body):
    """ไล่ดูทุกโหนดคำสั่งในต้นไม้ (ใช้หาชื่อฟังก์ชันที่ผู้ใช้ประกาศ)"""
    for node in body or ():
        yield node
        for attr in ("body", "orelse"):
            child = getattr(node, attr, None)
            if isinstance(child, list):
                yield from _walk(child)
        for _cond, branch in getattr(node, "branches", ()) or ():
            yield from _walk(branch)


def _py_string(value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\t", "\\t")
    return f'"{escaped}"'


def generate(program, source_name="<ไทยโค้ด>"):
    """คืน (โค้ด Python, ตารางเทียบบรรทัด Python -> บรรทัดไทย)"""
    gen = CodeGen(source_name)
    code = gen.generate(program)
    return code, gen.linemap
