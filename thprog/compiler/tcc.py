# -*- coding: utf-8 -*-
"""
TCC — Thai Character Cluster
============================

"กลุ่มอักขระไทยที่แยกจากกันไม่ได้" ตามหลักการเขียนภาษาไทย
เช่น "เก" ต้องอยู่ด้วยกัน (สระหน้าลอยเดี่ยวไม่ได้) หรือ "ตั" ที่มีไม้หันอากาศ

ทำไมต้องมี
----------
ภาษาไทยเขียนติดกันโดยไม่เว้นวรรค การตัดคำจึงกำกวมมาก
TCC ลดจุดที่ "ตัดได้" ให้เหลือเฉพาะจุดที่ถูกต้องตามหลักการเขียน
ตัวตัดคำจึงไม่มีทางสร้างคำที่เป็นไปไม่ได้ เช่น "ต" + "ัว"

เทคนิคนี้เป็นหัวใจของ engine `newmm` ใน PyThaiNLP
(dictionary-based maximal matching ที่ถูกจำกัดด้วยขอบเขต TCC)
ชุดกฎด้านล่างอ้างอิงจากกฎ TCC ที่ PyThaiNLP ใช้
"""

import re

# ตัวแทนในกฎ: c = พยัญชนะ, t = วรรณยุกต์ (มีหรือไม่ก็ได้), k = ตัวสะกด/การันต์
_C = "[ก-ฮ]"
_T = "[่-๋]?"
_K = "(cc?[ุูิ]?[์])?"

# เรียงจากกฎเฉพาะเจาะจงไปหากฎทั่วไป เพราะ regex เลือกทางเลือกแรกที่แมตช์
_RULES = [
    "เcctาะk",
    "เccีtยะk",
    "เccีtย(?=[เ-ไก-ฮ]|$)k",
    "เc[ิีุู]tย(?=[เ-ไก-ฮ]|$)k",
    "เcc็ck",
    "เcิc์ck",
    "เcิtck",
    "เcีtยะ?k",
    "เcืtอะk",
    "เc็ck",
    "เcื",
    "เctา?ะ?k",
    "แc็ck",
    "แcc์k",
    "แctะk",
    "แcc็ck",
    "โctะk",
    "c[ั]([่-๋]c)?k",
    "c[ั]([่-๋]c)?",
    "c[ึื]tck",
    "c[ิุู]์",
    "cรรc์",
    "cรร",
    "c[ะ-ู]tk",
    "c็",
    "ct[ะาำ]?k",
    "[เ-ไ]ctk",
    "ก็",
    "อึ",
    "หึ",
]


def _expand(rule):
    return rule.replace("k", _K).replace("c", _C).replace("t", _T)


_PATTERN = re.compile("|".join(f"(?:{_expand(r)})" for r in _RULES))


def clusters(text):
    """แบ่งข้อความไทยเป็นกลุ่มอักขระที่แยกจากกันไม่ได้"""
    out = []
    pos, size = 0, len(text)
    while pos < size:
        match = _PATTERN.match(text, pos)
        step = match.end() - pos if match and match.end() > pos else 1
        out.append(text[pos:pos + step])
        pos += step
    return out


def boundaries(text):
    """คืนรายการตำแหน่งที่ตัดคำได้ (รวมตำแหน่ง 0 และตำแหน่งสุดท้าย)"""
    marks, pos = [0], 0
    for unit in clusters(text):
        pos += len(unit)
        marks.append(pos)
    return marks
