# -*- coding: utf-8 -*-
"""
ขั้นที่ 1 : Tokenizer — ข้อความดิบ -> ชิ้นส่วน (chunk) ของแต่ละบรรทัด

หน้าที่
  * ตัดคอมเมนต์ (# ... หรือ หมายเหตุ ...)
  * นับระดับการเยื้อง เพื่อใช้แบ่งบล็อก
  * แยกสตริง ตัวเลข (รองรับเลขไทย ๐-๙) และเครื่องหมาย
  * แยก "ก้อนตัวอักษร" ตามระบบเขียน (ไทย / ละติน / ตัวเลข)

จุดสำคัญ
  ก้อนภาษาไทยจะยัง **ไม่ถูกตัดคำ** ในขั้นนี้ เพราะการตัดคำไทยกำกวม
  จึงส่งต่อให้ตัวตัดคำสร้าง "ตัวเลือกหลายแบบ" แล้วให้ parser เป็นคนตัดสิน
"""

from dataclasses import dataclass, field

from ..errors import LexError
from ..lang import lexicon
from . import wordseg

THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙"
QUOTE_PAIRS = {'"': '"', "'": "'", "“": "”", "‘": "’"}

TWO_CHAR_OPS = ("==", "!=", ">=", "<=", "//", "**")
ONE_CHAR_OPS = "+-*/%=<>()[]{},:;."

COMMENT_WORDS = ("หมายเหตุ", "คอมเมนต์", "อธิบาย")

MAX_LINE_CANDIDATES = 48
MIN_CHUNK_CANDIDATES = 8
MAX_CHUNK_CANDIDATES = 40


def _is_thai(ch):
    return "ก" <= ch <= "๛" and ch not in THAI_DIGITS


def _is_word_char(ch):
    return ch == "_" or ch.isalnum() or ("฀" <= ch <= "๿")


def _isdigit(ch):
    return ch.isdigit() or ch in THAI_DIGITS


def _script_of(ch):
    if _isdigit(ch) or ch == ".":
        return "digit"
    if _is_thai(ch):
        return "thai"
    return "latin"


# ======================================================================
@dataclass
class Token:
    kind: str                      # NUMBER | STRING | WORD | PUNCT
    text: str
    ids: set = field(default_factory=set)
    line: int = 0
    col: int = 0

    def has(self, canon):
        return canon in self.ids

    def __repr__(self):
        return f"<{self.kind}:{self.text}{sorted(self.ids) or ''}>"


@dataclass
class Chunk:
    """ชิ้นส่วนหนึ่งของบรรทัด — เป็นโทเคนสำเร็จรูป หรือก้อนไทยที่รอตัดคำ"""
    kind: str                      # "token" | "thai"
    token: Token = None
    text: str = ""
    line: int = 0
    col: int = 0


@dataclass
class Line:
    lineno: int
    indent: int
    chunks: list
    raw: str
    tokens: list = field(default_factory=list)   # ตัวเลือกที่ parser เลือกใช้


# ======================================================================
def tokenize(source, filename="<th>"):
    """แปลงซอร์สทั้งไฟล์เป็น list[Line] (ข้ามบรรทัดว่างและคอมเมนต์)"""
    lines = []
    for lineno, raw in enumerate(source.splitlines(), start=1):
        expanded = raw.replace("\t", "    ")
        stripped = expanded.strip()
        if not stripped:
            continue
        indent = len(expanded) - len(expanded.lstrip(" "))
        chunks = _scan(stripped, lineno, raw)
        if not chunks:
            continue
        # เลื่อนคอลัมน์ให้ตรงกับบรรทัดจริง เพื่อให้ขีดเส้นใต้ข้อผิดพลาดตรงตำแหน่ง
        for chunk in chunks:
            chunk.col += indent
            if chunk.token is not None:
                chunk.token.col += indent
        lines.append(Line(lineno, indent, chunks, raw))
    return lines


def _scan(text, lineno, raw):
    # ทั้งบรรทัดเป็นคอมเมนต์
    if any(text.startswith(word) for word in COMMENT_WORDS):
        return []

    chunks = []
    i, n = 0, len(text)

    def emit(token):
        chunks.append(Chunk("token", token=token, line=lineno, col=token.col))

    while i < n:
        ch = text[i]

        if ch.isspace():
            # คอมเมนต์ท้ายบรรทัดแบบไทย ๆ:  ให้กเป็น1    หมายเหตุ อธิบาย
            # บังคับว่าต้องมีช่องว่างนำหน้า จึงไม่มีทางไปตัดกลางชื่อตัวแปร
            # ที่บังเอิญมีคำว่า "หมายเหตุ" อยู่ข้างใน
            rest = text[i:].lstrip()
            if any(rest.startswith(word) for word in COMMENT_WORDS):
                break
            i += 1
            continue

        if ch == "#":
            break

        # ---- สตริง
        if ch in QUOTE_PAIRS:
            i = _read_string(text, i, lineno, raw, emit)
            continue

        # ---- ตัวเลขที่ขึ้นต้นด้วยตัวเลข (รองรับทศนิยม)
        if ch.isdigit() or ch in THAI_DIGITS:
            i = _read_number(text, i, lineno, emit)
            continue

        # ---- ก้อนตัวอักษร: แยกตามระบบเขียน
        if _is_word_char(ch):
            j = i
            while j < n:
                if _is_word_char(text[j]):
                    j += 1
                # จุดทศนิยมที่อยู่ระหว่างตัวเลข ถือเป็นส่วนหนึ่งของก้อนเดียวกัน
                # เช่น "เท่ากับ37.5แล้ว"
                elif (text[j] == "." and j + 1 < n
                        and _isdigit(text[j - 1]) and _isdigit(text[j + 1])):
                    j += 1
                else:
                    break
            _split_runs(text[i:j], i, lineno, raw, chunks, emit)
            i = j
            continue

        # ---- เครื่องหมาย
        two = text[i:i + 2]
        if two in TWO_CHAR_OPS:
            emit(Token("PUNCT", two, set(lexicon.ids_of(two)), lineno, i))
            i += 2
            continue
        if ch in ONE_CHAR_OPS:
            emit(Token("PUNCT", ch, set(lexicon.ids_of(ch)), lineno, i))
            i += 1
            continue

        raise LexError(f"ไม่รู้จักอักขระ {ch!r}", lineno, raw,
                       "ตรวจว่าพิมพ์ผิด หรือใช้สัญลักษณ์ที่ภาษายังไม่รองรับ",
                       col=i, length=1)

    return chunks


def _read_string(text, i, lineno, raw, emit):
    close = QUOTE_PAIRS[text[i]]
    j, buf, n = i + 1, [], len(text)
    while j < n and text[j] != close:
        if text[j] == "\\" and j + 1 < n:
            buf.append({"n": "\n", "t": "\t", "\\": "\\",
                        '"': '"', "'": "'"}.get(text[j + 1], "\\" + text[j + 1]))
            j += 2
            continue
        buf.append(text[j])
        j += 1
    if j >= n:
        raise LexError("ปิดเครื่องหมายคำพูดไม่ครบ", lineno, raw,
                       'ลองเติม " ปิดท้ายข้อความ')
    emit(Token("STRING", "".join(buf), set(), lineno, i))
    return j + 1


def _read_number(text, i, lineno, emit):
    j, n = i, len(text)
    while j < n and (text[j].isdigit() or text[j] in THAI_DIGITS):
        j += 1
    if j + 1 < n and text[j] == "." and \
            (text[j + 1].isdigit() or text[j + 1] in THAI_DIGITS):
        j += 1
        while j < n and (text[j].isdigit() or text[j] in THAI_DIGITS):
            j += 1
    emit(Token("NUMBER", _normalize_digits(text[i:j]), set(), lineno, i))
    return j


def _split_runs(run, col, lineno, raw, chunks, emit):
    """แยกก้อนตัวอักษรเป็นช่วงย่อยตามระบบเขียน แล้วสร้าง chunk ที่เหมาะสม"""
    start = 0
    while start < len(run):
        script = _script_of(run[start])
        # ตัวระบุแบบละตินมีตัวเลขปนได้ทุกตำแหน่งหลังตัวแรก
        #     log10 · sha256 · utf8 · COLOR_BGR2GRAY
        # ส่วนตัวเลขที่ตามหลังภาษาไทยไม่รวมเข้าด้วยกัน เพราะ "คะแนน80"
        # ต้องแยกเป็นชื่อตัวแปรกับตัวเลข
        allowed = {"latin", "digit"} if script == "latin" else {script}
        stop = start
        while stop < len(run) and _script_of(run[stop]) in allowed:
            stop += 1
        piece = run[start:stop]

        if script == "digit":
            emit(Token("NUMBER", _normalize_digits(piece), set(),
                       lineno, col + start))
        elif script == "thai":
            chunks.append(Chunk("thai", text=piece, line=lineno, col=col + start))
        else:
            emit(Token("WORD", piece, set(lexicon.ids_of(piece)),
                       lineno, col + start))
        start = stop


def _normalize_digits(text):
    for value, digit in enumerate(THAI_DIGITS):
        text = text.replace(digit, str(value))
    return text


# ======================================================================
def candidates(line, segmenter, limit=MAX_LINE_CANDIDATES):
    """สร้าง 'ลำดับโทเคนที่เป็นไปได้' ของบรรทัดนี้ เรียงจากน่าจะถูกที่สุด

    ก้อนภาษาไทยแต่ละก้อนถูกตัดคำได้หลายแบบ จึงต้องผสมข้ามก้อนแบบ best-first
    """
    groups, slots = [], []
    for pos, chunk in enumerate(line.chunks):
        if chunk.kind != "thai":
            continue
        # ยิ่งประโยคเขียนติดกันยาว ยิ่งกำกวม จึงต้องเสนอทางเลือกมากขึ้น
        depth = min(MAX_CHUNK_CANDIDATES,
                    max(MIN_CHUNK_CANDIDATES, 6 + 2 * len(chunk.text) // 3))
        options = segmenter.segment(chunk.text, depth)
        if not options:
            options = [(0.0, [chunk.text])]
        groups.append(options)
        slots.append(pos)

    if not groups:
        yield [c.token for c in line.chunks]
        return

    for choice in wordseg.combinations(groups, limit):
        picked = dict(zip(slots, choice))
        tokens = []
        for pos, chunk in enumerate(line.chunks):
            if chunk.kind != "thai":
                tokens.append(chunk.token)
                continue
            offset = chunk.col
            for word in picked[pos]:
                tokens.append(Token("WORD", word, set(lexicon.ids_of(word)),
                                    chunk.line, offset))
                offset += len(word)      # ให้แต่ละคำรู้คอลัมน์จริงของตัวเอง
        yield tokens
