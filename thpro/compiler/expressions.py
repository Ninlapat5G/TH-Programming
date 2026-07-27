# -*- coding: utf-8 -*-
"""
ขั้นที่ 4 : ตัวแยกวิเคราะห์นิพจน์ (Pratt parser)

รองรับตัวดำเนินการทั้งแบบคำไทยและสัญลักษณ์ปนกันได้ เช่น
    ราคา คูณ 2 บวก ภาษี
    (a + b) มากกว่าหรือเท่ากับ 10 และ ไม่ ปิดร้าน
    ความยาว ของ รายชื่อ
"""

from ..errors import ParseError
from . import ast_nodes as A

# ระดับความสำคัญของตัวดำเนินการ (มากกว่า = ผูกแน่นกว่า)
BINARY_PREC = {
    "OR": 1,
    "AND": 2,
    "EQ": 3, "NE": 3, "LT": 3, "GT": 3, "LE": 3, "GE": 3,
    "PLUS": 4, "MINUS": 4,
    "MUL": 5, "DIV": 5, "IDIV": 5, "MOD": 5,
    "POW": 7,
}
RIGHT_ASSOC = {"POW"}


class ExprParser:
    def __init__(self, tokens, raw=None):
        self.toks = tokens
        self.i = 0
        self.raw = raw

    # -------------------------------------------------- เครื่องมือช่วย
    def peek(self, offset=0):
        j = self.i + offset
        return self.toks[j] if j < len(self.toks) else None

    def next(self):
        tok = self.peek()
        self.i += 1
        return tok

    def at(self, canon):
        tok = self.peek()
        return tok is not None and canon in tok.ids

    def eat(self, canon, what):
        if not self.at(canon):
            self.fail(f"ต้องการ {what} ตรงนี้")
        return self.next()

    def fail(self, msg):
        tok = self.peek()
        line = tok.line if tok else (self.toks[-1].line if self.toks else 0)
        near = f' ใกล้ ๆ "{tok.text}"' if tok else " (จบบรรทัดก่อนกำหนด)"
        raise ParseError(msg + near, line, self.raw)

    # -------------------------------------------------- ตัวหลัก
    def parse(self, min_prec=0):
        left = self.parse_unary()
        while True:
            tok = self.peek()
            if tok is None:
                break
            op = next((i for i in tok.ids if i in BINARY_PREC), None)
            if op is None:
                break
            prec = BINARY_PREC[op]
            if prec < min_prec:
                break
            self.next()
            nxt = prec if op in RIGHT_ASSOC else prec + 1
            right = self.parse(nxt)
            left = A.BinOp(op, left, right, tok.line)
        return left

    def parse_unary(self):
        tok = self.peek()
        if tok is None:
            self.fail("ต้องการค่าหรือนิพจน์")
        if "NOT" in tok.ids:
            self.next()
            return A.UnaryOp("NOT", self.parse(3), tok.line)
        if "MINUS" in tok.ids:
            self.next()
            return A.UnaryOp("MINUS", self.parse(6), tok.line)
        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_atom()
        while True:
            tok = self.peek()
            if tok is None:
                break
            if "LPAREN" in tok.ids:
                self.next()
                args = self.parse_arglist("RPAREN")
                node = A.Call(node, args, tok.line)
            elif "LBRACK" in tok.ids:
                self.next()
                key = self.parse()
                self.eat("RBRACK", "เครื่องหมาย ]")
                node = A.Index(node, key, tok.line)
            elif "OF" in tok.ids and isinstance(node, A.Name):
                # รูปแบบภาษาพูด:  ความยาว ของ รายชื่อ
                self.next()
                node = A.Call(node, [self.parse(4)], tok.line)
            else:
                break
        return node

    def parse_arglist(self, closer):
        args = []
        if self.at(closer):
            self.next()
            return args
        while True:
            args.append(self.parse())
            if self.at("COMMA"):
                self.next()
                continue
            self.eat(closer, "เครื่องหมายปิด")
            break
        return args

    def parse_atom(self):
        tok = self.next()
        if tok is None:
            self.fail("ต้องการค่าหรือนิพจน์")

        if tok.kind == "NUMBER":
            val = float(tok.text) if "." in tok.text else int(tok.text)
            return A.Num(val, tok.line)

        if tok.kind == "STRING":
            return A.Str(tok.text, tok.line)

        if "LPAREN" in tok.ids:
            node = self.parse()
            self.eat("RPAREN", "เครื่องหมาย )")
            return node

        if "LBRACK" in tok.ids:
            items = self.parse_arglist("RBRACK")
            return A.ListLit(items, tok.line)

        if "LBRACE" in tok.ids:
            pairs = []
            if self.at("RBRACE"):
                self.next()
                return A.DictLit(pairs, tok.line)
            while True:
                key = self.parse()
                self.eat("COLON", "เครื่องหมาย :")
                pairs.append((key, self.parse()))
                if self.at("COMMA"):
                    self.next()
                    continue
                self.eat("RBRACE", "เครื่องหมาย }")
                break
            return A.DictLit(pairs, tok.line)

        if tok.kind == "WORD":
            if "TRUE" in tok.ids:
                return A.Const("True", tok.line)
            if "FALSE" in tok.ids:
                return A.Const("False", tok.line)
            if "NONE" in tok.ids:
                return A.Const("None", tok.line)
            # คำที่เป็นตัวดำเนินการ ห้ามยืนอยู่ตำแหน่งของค่า
            if tok.ids & RESERVED_IN_EXPR:
                raise ParseError(f'คำว่า "{tok.text}" เป็นตัวดำเนินการ '
                                 f"ใช้เป็นค่าไม่ได้", tok.line, self.raw,
                                 "ถ้าตั้งใจใช้เป็นชื่อตัวแปร ให้เปลี่ยนชื่อใหม่")
            return A.Name(tok.text, tok.line, tok.col)

        raise ParseError(f'ไม่เข้าใจ "{tok.text}" ในนิพจน์', tok.line, self.raw)


# คำสั่งที่ใช้ขึ้นต้นประโยค — ห้ามถูกตีความเป็นชื่อตัวแปรกลางนิพจน์
# มิฉะนั้น "ฟังก์ชันบวกเลข..." จะถูกอ่านเป็น  ฟังก์ชัน + เลข...  ซึ่งไร้ความหมาย
COMMAND_IDS = {
    "PRINT", "LET", "ASK", "INC", "DEC", "IF", "ELIF", "ELSE", "REPEAT",
    "FOREACH", "WHILE", "UNTIL", "COUNT", "BREAK", "CONTINUE", "FUNC",
    "RETURN", "CALL",
}

# id ที่ห้ามปรากฏในตำแหน่ง "ค่า"
# หมายเหตุ: คำเชื่อมอ่อน ๆ อย่าง ครั้ง/ใน/ถึง/ด้วย ไม่อยู่ในชุดนี้
# เพราะคนไทยนิยมเอาไปตั้งเป็นชื่อตัวแปร เช่น "รอบ"
RESERVED_IN_EXPR = set(BINARY_PREC) | COMMAND_IDS | {
    "NOT", "COMMA", "COLON", "ASSIGN_OP", "RPAREN", "RBRACK", "RBRACE",
}


def parse_expression(tokens, raw=None):
    """แยกวิเคราะห์นิพจน์ และบังคับว่าต้องใช้โทเคนหมดพอดี"""
    if not tokens:
        raise ParseError("ต้องการนิพจน์ แต่ไม่มีข้อมูล", None, raw)
    p = ExprParser(tokens, raw)
    node = p.parse()
    if p.i != len(tokens):
        p.fail("มีคำเกินมาในนิพจน์")
    return node


def try_parse_expression(tokens, raw=None):
    """เหมือน parse_expression แต่คืน None แทนการโยนข้อผิดพลาด"""
    try:
        return parse_expression(tokens, raw)
    except ParseError:
        return None
