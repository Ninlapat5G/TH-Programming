# -*- coding: utf-8 -*-
"""
ขั้นที่ 3 : ตัวแยกวิเคราะห์ประโยค — หัวใจของการตีความภาษาไทย

แนวคิดหลัก: **ให้ไวยากรณ์เป็นคนตัดสินการตัดคำ**
-----------------------------------------------
การตัดคำไทยกำกวมโดยธรรมชาติ ตัวตัดคำจึงไม่ฟันธงแบบเดียว แต่เสนอ
"ตัวเลือกหลายแบบเรียงตามความน่าจะเป็น" แล้ว parser ลองทีละแบบ
แบบแรกที่ **แปลเป็นโปรแกรมได้จริง** คือคำตอบ

ตัวอย่าง  ให้จำนวนนับเป็น0
    แบบที่ 1  ให้ | จำนวน | นับ | เป็น | 0     ← ถูกกว่าตามพจนานุกรม แต่ผิดไวยากรณ์
    แบบที่ 2  ให้ | จำนวนนับ | เป็น | 0        ← แปลได้  ✔ เลือกอันนี้

เมื่อแปลผ่านแล้ว ชื่อ "จำนวนนับ" จะถูกจำเข้าพจนานุกรม
บรรทัดถัดไปที่ใช้ชื่อนี้จึงตัดถูกตั้งแต่ครั้งแรก

ลำดับการพยายาม
    1. ตัวเลือกการตัดคำทั้งหมด (เรียงตามต้นทุน)
    2. ตัดคำเสริมแบบเข้มข้น
    3. เดาคำที่พิมพ์ผิด
"""

from ..diagnostics import Code, DiagnosticBag
from ..errors import ParseError
from ..lang import lexicon
from ..lang.builtins import CAST_TYPES
from ..lang.grammar import PATTERNS, INLINE_PATTERNS, Kw, Opt, Slot
from . import ast_nodes as A
from . import normalizer, tokenizer
from .expressions import try_parse_expression, RESERVED_IN_EXPR
from .wordseg import Segmenter


def _is_name_token(tok):
    return tok.kind == "WORD" and not (tok.ids & RESERVED_IN_EXPR)


_RANK = {id(p): i for i, p in enumerate(PATTERNS)}
_KEYWORDS = {id(p): sum(1 for e in p.elems if isinstance(e, Kw)) for p in PATTERNS}


def _pattern_rank(pattern):
    return _RANK.get(id(pattern), len(PATTERNS))


def _keyword_count(pattern):
    return _KEYWORDS.get(id(pattern), 0)


class Parser:
    # ตำแหน่งที่ต้องตามด้วย "ชื่อ" เสมอ — ใช้ตรวจว่าตั้งชื่อชนคำสงวนหรือไม่
    _NAME_SLOTS = {"FUNC", "CALL", "COUNT", "FOREACH", "STORE_IN", "TAKES"}

    # เมื่อเจอการตีความที่ใช้ได้แล้ว ยังมองต่ออีกกี่ตัวเลือกเพื่อหาที่ดีกว่า
    LOOKAHEAD = 12

    # จำนวนข้อผิดพลาดไวยากรณ์สูงสุดที่จะรายงาน ก่อนจะยอมแพ้
    MAX_ERRORS = 20

    def __init__(self, lines, segmenter=None, bag=None):
        self.lines = lines
        self.pos = 0
        self.bag = bag if bag is not None else DiagnosticBag()
        self.seg = segmenter or Segmenter(lexicon.WORD_IDS)
        self._cache = {}

    # ================================================== ระดับโปรแกรม
    def parse(self):
        body = self.parse_block(self.lines[0].indent if self.lines else 0)
        return A.Program(body, 1)

    def parse_block(self, indent):
        """อ่านคำสั่งทีละบรรทัดในระดับการเยื้องเดียวกัน

        ถ้าบรรทัดใดอ่านไม่ออก จะ **กู้คืนแล้วอ่านต่อ** (panic-mode recovery
        ระดับคำสั่ง) เพื่อรายงานข้อผิดพลาดให้ครบในการคอมไพล์รอบเดียว
        """
        body = []
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            if line.indent < indent:
                break

            start = self.pos
            try:
                if line.indent > indent:
                    raise ParseError(
                        "เยื้องเข้ามาโดยไม่มีคำสั่งเปิดบล็อก",
                        line.lineno, line.raw,
                        "บล็อกย่อยเกิดหลังคำสั่ง ถ้า / ทำซ้ำ / ตราบใดที่ / "
                        "ฟังก์ชัน เท่านั้น",
                        col=0, length=line.indent, code=Code.BAD_INDENT)
                node, role = self.parse_statement(indent)
                self._attach(body, node, role, line)
            except ParseError as err:
                self._recover(err, start)
        return body

    # -------------------------------------------------- การกู้คืน
    def _recover(self, err, start):
        """บันทึกข้อผิดพลาด แล้วข้ามคำสั่งที่พังทั้งก้อน (รวมบล็อกย่อยของมัน)"""
        if len(self.bag.errors) < self.MAX_ERRORS:
            self.bag.record(err)
        elif len(self.bag.errors) == self.MAX_ERRORS:
            self.bag.error(Code.UNKNOWN_STATEMENT,
                           "ข้อผิดพลาดเยอะเกินไป — หยุดรายงานเพียงเท่านี้",
                           phase="syntax")

        self.pos = max(self.pos, start + 1)
        base = self.lines[start].indent
        while self.pos < len(self.lines) and self.lines[self.pos].indent > base:
            self.pos += 1

    @staticmethod
    def _attach(body, node, role, line):
        if role not in ("elif", "else"):
            body.append(node)
            return
        if not body or not isinstance(body[-1], A.If):
            raise ParseError("คำสั่งนี้ต้องอยู่ต่อจากบล็อก ถ้า",
                             line.lineno, line.raw,
                             "บล็อก ไม่งั้น / ไม่งั้นถ้า ต้องตามหลังบล็อก ถ้า "
                             "ที่อยู่ระดับการเยื้องเดียวกัน",
                             col=line.indent, code=Code.DANGLING_ELSE)
        head = body[-1]
        if head.orelse is not None:
            raise ParseError("มีบล็อก ไม่งั้น ซ้ำซ้อน", line.lineno, line.raw,
                             "หนึ่งบล็อก ถ้า มี ไม่งั้น ได้แค่ครั้งเดียว",
                             col=line.indent, code=Code.DUPLICATE_ELSE)
        if role == "elif":
            head.branches.extend(node.branches)
        else:
            head.orelse = node.branches[0][1]

    # ================================================== ระดับประโยค
    def parse_statement(self, indent):
        line = self.lines[self.pos]
        pattern, slots, note = self.resolve(line)

        if pattern is None:
            first = line.tokens[0] if line.tokens else None
            raise ParseError(
                "ไม่เข้าใจคำสั่งนี้", line.lineno, line.raw, self._hint(line),
                col=first.col if first else line.indent,
                length=len(first.text) if first else 1,
                code=self._error_code(line))
        if note:
            self.bag.warning(Code.TYPO_GUESS, note, phase="syntax",
                             line=line.lineno)

        # ต้องจำชื่อ *ก่อน* อ่านบล็อกย่อย มิฉะนั้นตัวแปรลูปและพารามิเตอร์
        # จะยังไม่อยู่ในพจนานุกรมตอนตัดคำบรรทัดข้างใน
        self._learn(slots)

        self.pos += 1
        body = []
        if pattern.block:
            body = self._child_block(line, indent)

        node = pattern.build(slots, line.lineno, body)
        node.line = line.lineno
        return node, pattern.role

    def _child_block(self, line, indent):
        if self.pos >= len(self.lines) or self.lines[self.pos].indent <= indent:
            raise ParseError("บล็อกว่างเปล่า", line.lineno, line.raw,
                             "ต้องมีคำสั่งอย่างน้อยหนึ่งบรรทัดและเยื้องเข้าไป "
                             "(แนะนำ 4 ช่องว่าง) หรือเขียนจบในบรรทัดเดียว",
                             col=line.indent, code=Code.EMPTY_BLOCK)
        return self.parse_block(self.lines[self.pos].indent)

    @staticmethod
    def _error_code(line):
        for tok in line.tokens:
            if tok.kind == "WORD" and (tok.ids & RESERVED_IN_EXPR):
                return Code.RESERVED_AS_NAME
        return Code.UNKNOWN_STATEMENT

    # ================================================== เลือกการตัดคำที่แปลได้
    def resolve(self, line):
        """ลองตัดคำหลายแบบ แล้วเลือก "การตีความที่ดีที่สุด"

        เกณฑ์การเลือก (น้อยกว่า = ดีกว่า)
            1. รูปประโยคที่ต้องใช้คีย์เวิร์ดมากกว่า  (ตีความได้ละเอียดกว่า)
            2. ลำดับของรูปประโยคในตาราง              (เฉพาะเจาะจงมาก่อน)
            3. ลำดับของตัวเลือกการตัดคำ              (ต้นทุนตัดคำต่ำกว่า)

        ข้อ 1 กันกรณีอย่าง "ฟังก์ชันบวกเลขรับตัวแรกและตัวหลัง" ที่ตัดได้ทั้งแบบ
        กลืน "รับ" เข้าไปในชื่อฟังก์ชัน (ฟังก์ชันไม่มีพารามิเตอร์) และแบบที่
        เห็น "รับ" เป็นตัวคั่น — แบบหลังใช้คีย์เวิร์ดมากกว่า จึงถูกต้องกว่า
        """
        first, best = None, None
        seen_at = None

        for index, tokens in enumerate(tokenizer.candidates(line, self.seg)):
            if first is None:
                first = tokens
            if seen_at is not None and index - seen_at > self.LOOKAHEAD:
                break

            line.tokens = normalizer.normalize(tokens)
            pattern, slots = self.match(line)
            if pattern is None:
                continue

            key = (-_keyword_count(pattern), _pattern_rank(pattern), index)
            if best is None or key < best[0]:
                best = (key, pattern, slots, line.tokens)
            if seen_at is None:
                seen_at = index

        if best is not None:
            line.tokens = best[3]
            return best[1], best[2], None

        if first is None:
            return None, None, None

        # ทางเลือกสำรอง 1: ตัดคำเสริมแบบเข้มข้น
        line.tokens = normalizer.normalize(first, aggressive=True)
        pattern, slots = self.match(line)
        if pattern is not None:
            return pattern, slots, None

        # ทางเลือกสำรอง 2: เดาคำที่พิมพ์ผิด
        line.tokens = normalizer.normalize(first)
        fixed, note = normalizer.repair(line.tokens)
        if fixed is not None:
            saved, line.tokens = line.tokens, fixed
            pattern, slots = self.match(line)
            if pattern is not None:
                return pattern, slots, note
            line.tokens = saved

        return None, None, None

    def match(self, line, patterns=PATTERNS):
        self._cache = {}
        for pattern in patterns:
            slots = self._match(pattern.elems, 0, line.tokens, 0, {}, line)
            if slots is not None:
                return pattern, slots
        return None, None

    # ================================================== ตัวจับคู่ (backtracking)
    def _match(self, elems, ei, toks, ti, slots, line):
        if ei == len(elems):
            return dict(slots) if ti == len(toks) else None

        el = elems[ei]

        if isinstance(el, Kw):
            if ti < len(toks) and (toks[ti].ids & el.ids):
                return self._match(elems, ei + 1, toks, ti + 1, slots, line)
            return None

        if isinstance(el, Opt):
            if ti < len(toks) and (toks[ti].ids & el.ids):
                got = self._match(elems, ei + 1, toks, ti + 1, slots, line)
                if got is not None:
                    return got
            return self._match(elems, ei + 1, toks, ti, slots, line)

        assert isinstance(el, Slot)
        return self._match_slot(el, elems, ei, toks, ti, slots, line)

    def _match_slot(self, el, elems, ei, toks, ti, slots, line):
        def attempt(value, nxt):
            slots[el.name] = value
            got = self._match(elems, ei + 1, toks, nxt, slots, line)
            if got is None:
                del slots[el.name]
            return got

        kind = el.kind

        if kind in ("expr", "target"):
            for end in range(len(toks), ti, -1):
                node = self._expr(toks, ti, end, line)
                if node is None:
                    continue
                if kind == "target" and not isinstance(node, (A.Name, A.Index)):
                    continue
                got = attempt(node, end)
                if got is not None:
                    return got
            return None

        if kind == "exprlist":
            for end in range(len(toks), ti, -1):
                items = self._exprlist(toks, ti, end, line)
                if items is None:
                    continue
                got = attempt(items, end)
                if got is not None:
                    return got
            return None

        if kind == "stmt":
            node = self._substatement(toks[ti:], line)
            return attempt(node, len(toks)) if node is not None else None

        if kind == "name":
            if ti < len(toks) and _is_name_token(toks[ti]):
                return attempt(toks[ti].text, ti + 1)
            return None

        if kind == "type":
            if ti < len(toks) and toks[ti].text in CAST_TYPES:
                return attempt(CAST_TYPES[toks[ti].text], ti + 1)
            return None

        if kind == "namelist":
            names, pos = [], ti
            while pos < len(toks) and _is_name_token(toks[pos]):
                names.append(toks[pos].text)
                pos += 1
                got = attempt(list(names), pos)
                if got is not None:
                    return got
                if pos < len(toks) and (toks[pos].ids & {"COMMA", "AND"}):
                    pos += 1
                    continue
                break
            return None

        raise AssertionError(f"ไม่รู้จักชนิดช่อง {kind}")

    # -------------------------------------------------- ตัวช่วย
    def _expr(self, toks, start, end, line):
        key = (start, end)
        if key not in self._cache:
            self._cache[key] = try_parse_expression(toks[start:end], line.raw)
        return self._cache[key]

    def _exprlist(self, toks, start, end, line):
        parts, depth, cur = [], 0, start
        for i in range(start, end):
            ids = toks[i].ids
            if ids & {"LPAREN", "LBRACK", "LBRACE"}:
                depth += 1
            elif ids & {"RPAREN", "RBRACK", "RBRACE"}:
                depth -= 1
            elif "COMMA" in ids and depth == 0:
                parts.append((cur, i))
                cur = i + 1
        parts.append((cur, end))
        out = []
        for a, b in parts:
            node = self._expr(toks, a, b, line)
            if node is None:
                return None
            out.append(node)
        return out

    def _substatement(self, sub, line):
        """แปลชุดโทเคนย่อยให้เป็นคำสั่งหนึ่งคำสั่ง (ใช้กับรูปแบบบรรทัดเดียว)"""
        if not sub:
            return None
        saved_tokens, saved_cache = line.tokens, self._cache
        try:
            line.tokens = sub
            pattern, slots = self.match(line, INLINE_PATTERNS)
            if pattern is None:
                return None
            self._learn(slots)
            node = pattern.build(slots, line.lineno, [])
            node.line = line.lineno
            return node
        finally:
            line.tokens, self._cache = saved_tokens, saved_cache

    # ================================================== พจนานุกรมที่เรียนรู้ได้
    _NAME_KEYS = ("var", "name", "target")

    def _learn(self, slots):
        """จำชื่อที่ผู้ใช้เพิ่งประกาศ เพื่อให้บรรทัดถัดไปตัดคำถูกตั้งแต่แรก

        นี่คือสิ่งที่ทำให้เขียนติดกันยาว ๆ ได้จริง: ยิ่งอ่านโปรแกรมไปเรื่อย ๆ
        พจนานุกรมยิ่งรู้จักศัพท์ของผู้ใช้มากขึ้น การตัดคำจึงแม่นขึ้นเรื่อย ๆ
        """
        for key in self._NAME_KEYS:
            value = slots.get(key)
            if isinstance(value, str):
                self.seg.learn(value)
            elif isinstance(value, A.Name):
                self.seg.learn(value.ident)
        for param in slots.get("params") or ():
            self.seg.learn(param)

    # ================================================== ข้อความช่วยเหลือ
    def _hint(self, line):
        toks = line.tokens
        first = toks[0] if toks else None

        if first is not None and first.kind == "WORD" and not first.ids:
            guess = normalizer.suggest(first.text, lexicon.COMMAND_STARTERS, 0.6)
            if guess:
                return f'คำขึ้นต้นคล้ายกับ "{guess}" — ตรวจการสะกดอีกครั้ง'

        for i in range(1, len(toks)):
            tok = toks[i]
            if (tok.kind == "WORD" and (tok.ids & RESERVED_IN_EXPR)
                    and (toks[i - 1].ids & self._NAME_SLOTS)):
                return (f'"{tok.text}" เป็นคำสงวนของภาษา (ใช้เป็นตัวดำเนินการ) '
                        f'จึงตั้งเป็นชื่อไม่ได้ — ลองใช้ "{tok.text}เลข" แทน')

        return ("ตรวจรูปประโยค เช่น  แสดง <ค่า> / ให้ <ตัวแปร> เป็น <ค่า> / "
                "ถ้า <เงื่อนไข> / ทำซ้ำ <จำนวน> ครั้ง")


def parse(lines, segmenter=None, bag=None):
    """คืน (AST, ถุงข้อความ) — ไม่โยนข้อผิดพลาดออกมา แต่สะสมไว้ในถุง"""
    parser = Parser(lines, segmenter, bag)
    return parser.parse(), parser.bag
