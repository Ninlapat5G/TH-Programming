# -*- coding: utf-8 -*-
"""
ขั้นที่ 3 : Normalizer — ชั้น NLP เชิงสัญลักษณ์

  1) รวมวลีหลายคำเป็นโทเคนเดียว (longest-match)
         "มากกว่า หรือ เท่ากับ"  ->  GE
         "ไม่ งั้น"              ->  ELSE
  2) ตัดคำเสริมที่ไม่มีผลต่อความหมาย  ("ว่า" "นะ" "ครับ" ...)
  3) ตัดหน่วยและลักษณนามที่ตามหลังตัวเลข  ("0 บาท" -> 0)
  4) เดาคำที่พิมพ์ผิดด้วยการวัดความคล้าย (ใช้เมื่อจับรูปประโยคไม่ได้)
"""

import difflib

from ..lang import lexicon
from ..lang.builtins import BUILTINS
from .tokenizer import Token


def collapse_phrases(tokens):
    """รวมโทเคนที่อยู่ติดกันให้เป็นวลีเดียว โดยจับคู่แบบยาวที่สุดก่อน"""
    out, i, n = [], 0, len(tokens)
    while i < n:
        matched = False
        for size in range(min(lexicon.MAX_PHRASE, n - i), 1, -1):
            key = tuple(t.text for t in tokens[i:i + size])
            if key in lexicon.PHRASE_IDS:
                head = tokens[i]
                out.append(Token("WORD", "".join(key),
                                 set(lexicon.PHRASE_IDS[key]),
                                 head.line, head.col))
                i += size
                matched = True
                break
        if not matched:
            out.append(tokens[i])
            i += 1
    return out


def _is_polite(tok):
    return (tok.kind == "WORD" and not tok.ids
            and tok.text in lexicon.POLITE)


def drop_fillers(tokens, aggressive=False):
    """ตัดคำเสริมออก

    ปกติจะตัดเฉพาะคำที่ไม่ได้ทำหน้าที่เป็นคีย์เวิร์ด เพื่อไม่ให้คำอย่าง "ด้วย"
    (ซึ่งใช้ส่งอาร์กิวเมนต์) หายไป  แต่เมื่อจับรูปประโยคไม่ได้เลย
    จะลองตัดแบบเข้มข้นอีกรอบ

    ส่วนคำลงท้ายประโยค (ครับ ค่ะ นะ) ตัดจาก **ท้ายประโยคเข้ามา** เท่านั้น
    ถ้าตัดได้ทุกตำแหน่งจะกินพยางค์แรกของชื่อตัวแปร ("คะแนน" -> "แนน")
    """
    keep = []
    for tok in tokens:
        if tok.kind == "WORD" and tok.text in lexicon.FILLERS:
            if aggressive or not tok.ids:
                continue
        keep.append(tok)
    while keep and _is_polite(keep[-1]):
        keep.pop()
    return keep


def drop_units(tokens):
    """ตัดหน่วย/ลักษณนามที่ "ตามหลังตัวเลขโดยตรง" ออก

        มีเงิน 0 บาท      ->  มี เงิน 0
        ให้ราคาเป็น50บาท   ->  ให้ ราคา เป็น 50

    เงื่อนไขว่าต้องตามหลังตัวเลขคือสิ่งที่ทำให้กฎนี้ปลอดภัย เพราะคำอย่าง
    "คน" "ชิ้น" "วัน" คนไทยเอาไปตั้งเป็นชื่อตัวแปรกันทั้งนั้น
    ตัวที่ทำหน้าที่เป็นคีย์เวิร์ดอยู่แล้ว (มี ids) จะไม่ถูกแตะ
    """
    keep = []
    for tok in tokens:
        if (tok.kind == "WORD" and not tok.ids and tok.text in lexicon.UNITS
                and keep and keep[-1].kind == "NUMBER"):
            continue
        keep.append(tok)
    return keep


def normalize(tokens, aggressive=False):
    return drop_units(drop_fillers(collapse_phrases(tokens), aggressive))


# ---------------------------------------------------------------- เดาคำผิด
def suggest(word, pool=None, cutoff=0.72):
    """คืนคำที่ใกล้เคียงที่สุดในคลังคำ หรือ None"""
    pool = pool if pool is not None else set(lexicon.WORD_IDS) | set(BUILTINS)
    hits = difflib.get_close_matches(word, list(pool), n=1, cutoff=cutoff)
    return hits[0] if hits else None


def repair(tokens):
    """ซ่อมบรรทัดที่อ่านไม่ออก โดยแก้คำแรกที่ไม่รู้จักให้ใกล้เคียงที่สุด

    คืน (tokens ใหม่, ข้อความอธิบาย) หรือ (None, None) ถ้าซ่อมไม่ได้
    """
    for idx, tok in enumerate(tokens):
        if tok.kind != "WORD" or tok.ids or tok.text in BUILTINS:
            continue
        pool = lexicon.COMMAND_STARTERS if idx == 0 else set(lexicon.WORD_IDS)
        guess = suggest(tok.text, pool, cutoff=0.75)
        if not guess:
            continue
        fixed = list(tokens)
        fixed[idx] = Token("WORD", guess, set(lexicon.ids_of(guess)),
                           tok.line, tok.col)
        return normalize(fixed), f'เดาว่า "{tok.text}" น่าจะหมายถึง "{guess}"'
    return None, None
