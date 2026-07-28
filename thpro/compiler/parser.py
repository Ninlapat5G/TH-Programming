# -*- coding: utf-8 -*-
"""
ขั้นที่ 5 : ตัวแยกวิเคราะห์ประโยค — หัวใจของการตีความภาษาไทย

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
    1. ตัวเลือกการตัดคำทั้งหมด (เรียงตามต้นทุน)      -> หนึ่งบรรทัด = หนึ่งคำสั่ง
    2. ตัดประโยค                                    -> หนึ่งบรรทัด = หลายคำสั่ง
    3. ตัดคำเสริมแบบเข้มข้น
    4. เดาคำที่พิมพ์ผิด

ข้อ 2 อยู่ *หลัง* ข้อ 1 เสมอ — ถ้าทั้งบรรทัดแปลเป็นคำสั่งเดียวได้ จะใช้แบบนั้น
โปรแกรมที่เคยคอมไพล์ผ่านจึงไม่มีทางเปลี่ยนความหมายเพราะฟีเจอร์ตัดประโยค
"""

from dataclasses import dataclass, field
from typing import List

from ..diagnostics import Code, DiagnosticBag
from ..errors import ParseError
from ..lang import lexicon
from ..lang.builtins import CAST_TYPES
from ..lang.grammar import PATTERNS, INLINE_PATTERNS, Kw, Opt, Pattern, Slot
from . import ast_nodes as A
from . import normalizer, sentence, tokenizer
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


@dataclass
class Match:
    """รูปประโยคหนึ่งอันที่จับคู่สำเร็จ พร้อมค่าที่เติมลงช่องต่าง ๆ"""
    pattern: Pattern
    slots: dict


@dataclass
class Reading:
    """การตีความบรรทัดหนึ่งบรรทัด — หนึ่งคำสั่ง หรือหลายคำสั่งที่ตัดประโยคแล้ว"""
    matches: List[Match] = field(default_factory=list)
    note: str = None

    @property
    def opens_block(self):
        """มีเฉพาะกรณีคำสั่งเดียวเท่านั้นที่เปิดบล็อกย่อยได้"""
        return len(self.matches) == 1 and self.matches[0].pattern.block


class Parser:
    # ตำแหน่งที่ต้องตามด้วย "ชื่อ" เสมอ — ใช้ตรวจว่าตั้งชื่อชนคำสงวนหรือไม่
    _NAME_SLOTS = {"FUNC", "CALL", "COUNT", "FOREACH", "STORE_IN", "TAKES",
                   "HAVE"}

    # เมื่อเจอการตีความที่ใช้ได้แล้ว ยังมองต่ออีกกี่ตัวเลือกเพื่อหาที่ดีกว่า
    LOOKAHEAD = 12

    # จำนวนลำดับโทเคนที่เก็บไว้ให้ขั้นตัดประโยคลองต่อ ถ้าแปลทั้งบรรทัดไม่ได้
    SPLIT_CANDIDATES = 6

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
                for node, role in self.parse_statement(indent):
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
        """อ่านหนึ่งบรรทัด — คืน list ของ (โหนด, บทบาท)

        ปกติได้หนึ่งรายการ แต่บรรทัดที่ถูก "ตัดประโยค" จะได้หลายรายการ
        """
        line = self.lines[self.pos]
        reading = self.resolve(line)

        if reading is None:
            first = line.tokens[0] if line.tokens else None
            raise ParseError(
                "ไม่เข้าใจคำสั่งนี้", line.lineno, line.raw, self._hint(line),
                col=first.col if first else line.indent,
                length=len(first.text) if first else 1,
                code=self._error_code(line))
        if reading.note:
            self.bag.warning(Code.TYPO_GUESS, reading.note, phase="syntax",
                             line=line.lineno)
        self._check_swallowed_keyword(line)

        # ต้องจำชื่อ *ก่อน* อ่านบล็อกย่อย มิฉะนั้นตัวแปรลูปและพารามิเตอร์
        # จะยังไม่อยู่ในพจนานุกรมตอนตัดคำบรรทัดข้างใน
        for match in reading.matches:
            self._learn(match.slots)

        self.pos += 1
        body = []
        if reading.opens_block:
            body = self._child_block(line, indent)

        out = []
        for match in reading.matches:
            node = match.pattern.build(match.slots, line.lineno, body)
            node.line = line.lineno
            out.append((node, match.pattern.role))
        return out

    def _child_block(self, line, indent):
        if self.pos >= len(self.lines) or self.lines[self.pos].indent <= indent:
            raise ParseError("บล็อกว่างเปล่า", line.lineno, line.raw,
                             "ต้องมีคำสั่งอย่างน้อยหนึ่งบรรทัดและเยื้องเข้าไป "
                             "(แนะนำ 4 ช่องว่าง) หรือเขียนจบในบรรทัดเดียว",
                             col=line.indent, code=Code.EMPTY_BLOCK)
        return self.parse_block(self.lines[self.pos].indent)

    # ============================================ คำสงวนถูกกลืนเข้าไปในชื่อ
    def _check_swallowed_keyword(self, line):
        """จับกรณีที่ชื่อตัวแปร "กลืน" คำสั่งที่ขึ้นต้นบรรทัดเข้าไป

        ปัญหา
            ให้บวกเป็น 3

        ผู้ใช้ตั้งใจตั้งชื่อตัวแปรว่า "บวก" ซึ่งเป็นตัวดำเนินการ ทำไม่ได้
        การตีความที่ถูกต้องจึงพังทั้งหมด แล้วตัวตัดคำไปเสนอ "ให้บวก"
        เป็นชื่อเดียวแทน — ซึ่ง *แปลผ่าน* เป็น ให้บวก = 3

        ผลคือคอมไพเลอร์เงียบ แล้วสร้างตัวแปรที่ผู้ใช้ไม่ได้ตั้งใจ
        อันตรายกว่าการฟ้อง เพราะผู้ใช้ไม่มีทางรู้เลยว่าเกิดอะไรขึ้น

        เงื่อนไขที่ฟ้อง (แคบมากโดยตั้งใจ เพื่อไม่ให้ฟ้องผิด)
            1. โทเคนแรกของบรรทัดเป็นชื่อที่ผู้ใช้ตั้ง (ไม่มี id)
            2. ชื่อนั้นขึ้นต้นด้วยคำที่ใช้ขึ้นต้นคำสั่งได้
            3. ส่วนที่เหลือหลังตัดคำนั้นออก เป็น "คำสงวนแข็ง" พอดีเป๊ะ

        ข้อ 3 คือสิ่งที่กันการฟ้องผิด — ชื่ออย่าง "นับถอยหลัง" เหลือ "ถอยหลัง"
        ซึ่งไม่ใช่คำสงวน จึงไม่ถูกแตะ
        """
        if not line.tokens:
            return
        head = line.tokens[0]
        if head.kind != "WORD" or head.ids:
            return

        for starter in lexicon.COMMAND_STARTERS:
            if not head.text.startswith(starter) or len(head.text) == len(starter):
                continue
            rest = head.text[len(starter):]
            if not (lexicon.ids_of(rest) & RESERVED_IN_EXPR):
                continue
            self.bag.error(
                Code.RESERVED_AS_NAME,
                f'"{rest}" เป็นคำสงวนของภาษา จึงตั้งเป็นชื่อไม่ได้',
                phase="syntax", line=line.lineno, col=head.col,
                length=len(head.text),
                hint=f'คอมไพเลอร์เลยอ่าน "{head.text}" รวมเป็นชื่อเดียว '
                     f'ซึ่งน่าจะไม่ใช่สิ่งที่ตั้งใจ — ลองเปลี่ยนเป็น '
                     f'"{rest}เลข" หรือ "ค่า{rest}"')
            return

    @staticmethod
    def _error_code(line):
        for tok in line.tokens:
            if tok.kind == "WORD" and (tok.ids & RESERVED_IN_EXPR):
                return Code.RESERVED_AS_NAME
        return Code.UNKNOWN_STATEMENT

    # ================================================== เลือกการตัดคำที่แปลได้
    def resolve(self, line):
        """ลองตัดคำหลายแบบ แล้วเลือก "การตีความที่ดีที่สุด" — คืน Reading

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
        tried = []

        for index, tokens in enumerate(tokenizer.candidates(line, self.seg)):
            if first is None:
                first = tokens
            if seen_at is not None and index - seen_at > self.LOOKAHEAD:
                break

            line.tokens = normalizer.normalize(tokens)
            if len(tried) < self.SPLIT_CANDIDATES:
                tried.append(line.tokens)
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
            return Reading([Match(best[1], best[2])])

        if first is None:
            return None

        # ทางเลือกสำรอง 1: ตัดประโยค — หนึ่งบรรทัดอาจมีหลายคำสั่ง
        reading = self._resolve_split(line, tried)
        if reading is not None:
            return reading

        # ทางเลือกสำรอง 2: ตัดคำเสริมแบบเข้มข้น
        line.tokens = normalizer.normalize(first, aggressive=True)
        pattern, slots = self.match(line)
        if pattern is not None:
            return Reading([Match(pattern, slots)])

        # ทางเลือกสำรอง 3: เดาคำที่พิมพ์ผิด
        line.tokens = normalizer.normalize(first)
        fixed, note = normalizer.repair(line.tokens)
        if fixed is not None:
            saved, line.tokens = line.tokens, fixed
            pattern, slots = self.match(line)
            if pattern is not None:
                return Reading([Match(pattern, slots)], note)
            line.tokens = saved

        return None

    # -------------------------------------------------- ตัดประโยค
    def _resolve_split(self, line, token_lists):
        """ลองมองบรรทัดนี้เป็น "หลายคำสั่งเรียงกัน"

        ทุกท่อนต้องแปลเป็นคำสั่งได้ครบถ้วน ถ้ามีท่อนใดแปลไม่ได้ถือว่าการตัด
        แบบนั้นผิด แล้วไปลองแบบถัดไป — เกณฑ์เดียวกับที่ใช้ตัดสินการตัดคำ

        ทำสองรอบ เพราะประโยคแรกของบรรทัดมักเป็นตัวประกาศชื่อที่ประโยคหลัง
        จะใช้ต่อ

            มีรายการโปรดเป็น[] แล้ว เพิ่ม"ลาเต้"เข้าไปในรายการโปรด

        รอบแรกยังไม่รู้จัก "รายการโปรด" จึงตัดท่อนหลังผิดเป็น ในรายการ|โปรด
        แต่ระหว่างค้นได้เรียนรู้ชื่อจากท่อนแรกไปแล้ว รอบสองจึงตัดถูก
        (หลักการเดียวกับการเรียนรู้ข้ามบรรทัด เพียงแต่ทำภายในบรรทัดเดียว)
        """
        known = len(self.seg.words)
        reading = self._try_split(line, token_lists)
        if reading is not None or len(self.seg.words) == known:
            return reading
        return self._try_split(line, self._candidates(line))

    def _try_split(self, line, token_lists):
        for rank, tokens in enumerate(token_lists):
            # ยอมให้ "เดา" ชื่อจากประโยคแรกเฉพาะการตัดคำที่ถูกที่สุดเท่านั้น
            # การตัดคำที่แพงกว่าเป็นเพียงข้อสันนิษฐาน ถ้าปล่อยให้จำชื่อด้วย
            # พจนานุกรมจะเปื้อนชื่อผิด ๆ แล้วทำให้รอบถัดไปตัดเพี้ยนหนักกว่าเดิม
            matches = self._split_search(tokens, line, learn=(rank == 0))
            if matches is not None and len(matches) > 1:
                line.tokens = tokens
                return Reading(matches)
        return None

    def _candidates(self, line):
        """ลำดับโทเคนที่เป็นไปได้ของบรรทัดนี้ เท่าที่ขั้นตัดประโยคจะลองไหว"""
        out = []
        for tokens in tokenizer.candidates(line, self.seg):
            out.append(normalizer.normalize(tokens))
            if len(out) >= self.SPLIT_CANDIDATES:
                break
        return out

    def _split_search(self, tokens, line, learn=False):
        """หาการตัดประโยคที่ทุกท่อนแปลได้ ด้วยการค้นแบบจำผลลัพธ์ (memoized)

        solve(i) = "ตั้งแต่โทเคนที่ i ถึงจบ ตัดเป็นคำสั่งครบได้ไหม"
        ลองเอาทั้งช่วงที่เหลือเป็นคำสั่งเดียวก่อนเสมอ จึงได้จำนวนรอยตัดน้อยที่สุด
        โดยธรรมชาติ แล้วค่อยไล่จุดตัดตามอันดับที่ sentence เสนอมา

        จำผลของแต่ละจุดเริ่ม ทำให้ทำงานเป็น O(จุดตัด^2) ไม่ระเบิดแบบลองทุกชุด
        """
        points = sentence.cut_points(tokens)
        if not points:
            return None

        memo = {}

        def solve(start):
            if start in memo:
                return memo[start]
            memo[start] = None                  # กันการวนซ้ำระหว่างค้น
            whole = self._match_part(tokens[start:], line)
            if whole is not None:
                memo[start] = [whole]
                return memo[start]
            for index, drop in points:
                if index <= start:
                    continue
                head = self._match_part(tokens[start:index], line)
                if head is None:
                    continue
                # จำชื่อที่ประโยคแรกประกาศ เพื่อให้ตัดคำประโยคถัดไปถูก
                if learn and start == 0:
                    self._learn(head.slots)
                rest = solve(index + drop)
                if rest is not None:
                    memo[start] = [head] + rest
                    return memo[start]
            return None

        return solve(0)

    def _match_part(self, part, line):
        """จับคู่โทเคนหนึ่งท่อนกับรูปประโยคแบบบรรทัดเดียว — None ถ้าไม่เข้ารูปไหน"""
        if not part:
            return None
        pattern, slots = self.match(line, INLINE_PATTERNS, tokens=part)
        return None if pattern is None else Match(pattern, slots)

    def match(self, line, patterns=PATTERNS, tokens=None):
        toks = line.tokens if tokens is None else tokens
        self._cache = {}
        for pattern in patterns:
            slots = self._match(pattern.elems, 0, toks, 0, {}, line)
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
        saved_cache = self._cache
        try:
            pattern, slots = self.match(line, INLINE_PATTERNS, tokens=sub)
            if pattern is None:
                return None
            self._learn(slots)
            node = pattern.build(slots, line.lineno, [])
            node.line = line.lineno
            return node
        finally:
            self._cache = saved_cache

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
