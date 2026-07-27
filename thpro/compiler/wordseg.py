# -*- coding: utf-8 -*-
"""
ตัวตัดคำภาษาไทย (Word Segmenter)
================================

ปัญหา
-----
คนไทยเขียนติดกันโดยไม่เว้นวรรค

    ให้ราคาสินค้าเป็น250          ← ต้องตัดเป็น  ให้ | ราคาสินค้า | เป็น | 250
    ถ้าคะแนนมากกว่า80แล้วแสดง"ผ่าน"

วิธีที่ใช้ (อ้างอิงแนวทาง newmm ของ PyThaiNLP)
--------------------------------------------
1. **TCC** จำกัดตำแหน่งที่ตัดได้ ไม่ให้ตัดกลางกลุ่มอักขระ
2. **Dictionary-based maximal matching** ด้วย dynamic programming
   หาเส้นทางการตัดที่ "ต้นทุนต่ำสุด"
3. **จัดการคำที่ไม่รู้จัก** ช่วงที่ไม่มีในพจนานุกรมคือ "ชื่อที่ผู้ใช้ตั้งเอง"
   ยิ่งยาวยิ่งเสียค่าใช้จ่าย จึงถูกยุบรวมเป็นก้อนเดียวโดยอัตโนมัติ
4. **k-best** คืนผลลัพธ์หลายแบบเรียงตามต้นทุน ไม่ใช่แบบเดียว
   เพราะตัวแยกวิเคราะห์จะเป็นคนตัดสินว่าแบบไหน "แปลเป็นโปรแกรมได้จริง"
5. **พจนานุกรมที่เรียนรู้ได้** ชื่อตัวแปร/ฟังก์ชันที่ผู้ใช้ประกาศ
   จะถูกเพิ่มเข้าพจนานุกรมทันที บรรทัดถัดไปจึงตัดถูกตั้งแต่ครั้งแรก

ต้นทุน
------
    คำที่รู้จัก    = 1.0                       (ยิ่งใช้คำที่รู้จักน้อยชิ้น ยิ่งดี)
    คำที่ไม่รู้จัก = 1.0 + 0.7 x จำนวนกลุ่ม TCC  (ยาวขึ้น แพงขึ้น จึงไม่กลืนทั้งบรรทัด)
"""

import heapq

from . import tcc

# ค่าคงที่ของฟังก์ชันต้นทุน — ปรับสามค่านี้คือการปรับ "สัญชาตญาณ" ของตัวตัดคำ
#
#   KNOWN_COST < UNKNOWN_PER_UNIT   กันไม่ให้คำที่รู้จักถูกกลืนเข้าไปในชื่อยาว ๆ
#                                   (มิฉะนั้น "ให้ชื่อ" จะกลายเป็นชื่อตัวแปรเดียว)
#   SHORT_UNKNOWN_PENALTY           กันการซอยชื่อเป็นเศษเล็กเศษน้อยไร้ความหมาย
#                                   (มิฉะนั้น "ผลบวก" จะถูกซอยเป็น ผ|ลบ|วก
#                                    เพราะ "ลบ" บังเอิญเป็นคำของภาษา)
#                                   คิดจาก "จำนวนตัวอักษร" ไม่ใช่จำนวนกลุ่ม TCC
#                                   เพราะชื่อสั้นจริง ๆ อย่าง "ค่า" มีแค่กลุ่มเดียว
KNOWN_COST = 0.25
UNKNOWN_BASE = 0.3
UNKNOWN_PER_UNIT = 0.7
SHORT_UNKNOWN_PENALTY = 1.0
SHORT_UNKNOWN_CHARS = 2
MAX_UNKNOWN_CHARS = 60


class Segmenter:
    """ตัดคำไทยด้วยพจนานุกรมที่เพิ่มคำใหม่ระหว่างคอมไพล์ได้"""

    def __init__(self, words=()):
        self.words = set(words)
        self._cache = {}

    def learn(self, name):
        """เพิ่มชื่อที่ผู้ใช้ประกาศเข้าพจนานุกรม เพื่อให้บรรทัดถัดไปตัดถูก"""
        if name and name not in self.words:
            self.words.add(name)
            self._cache.clear()

    # ------------------------------------------------------------------
    def segment(self, text, k=6):
        """คืนผลการตัดคำ k แบบที่ต้นทุนต่ำสุด เรียงจากดีที่สุดไปหาแย่ที่สุด

        คืนค่าเป็น list ของ (ต้นทุน, [คำ, คำ, ...])
        """
        key = (text, k)
        if key not in self._cache:
            self._cache[key] = self._segment(text, k)
        return self._cache[key]

    def _segment(self, text, k):
        marks = tcc.boundaries(text)
        index = {pos: i for i, pos in enumerate(marks)}
        end = marks[-1]

        # paths[i] = k เส้นทางที่ดีที่สุดมาถึงตำแหน่ง marks[i]
        # แต่ละรายการ = (ต้นทุนสะสม, ตำแหน่งก่อนหน้า, ลำดับเส้นทางก่อนหน้า,
        #                คำสุดท้ายเป็นคำที่ไม่รู้จักหรือไม่)
        paths = [[] for _ in marks]
        paths[0] = [(0.0, None, None, False)]

        for j, stop in enumerate(marks):
            if j == 0:
                continue
            candidates = []
            for i in range(j - 1, -1, -1):
                start = marks[i]
                if not paths[i]:
                    continue
                token = text[start:stop]
                known = token in self.words
                if known:
                    cost = KNOWN_COST
                elif len(token) <= MAX_UNKNOWN_CHARS:
                    cost = UNKNOWN_BASE + UNKNOWN_PER_UNIT * (j - i)
                    if len(token) <= SHORT_UNKNOWN_CHARS:
                        cost += SHORT_UNKNOWN_PENALTY
                else:
                    continue
                for rank, (acc, _, _, prev_unknown) in enumerate(paths[i]):
                    # ห้ามมีคำที่ไม่รู้จักสองก้อนติดกัน — ชื่อสองชื่อวางชิดกัน
                    # ไม่มีความหมายในภาษานี้ กฎนี้ตัดตัวเลือกขยะทิ้งได้มหาศาล
                    if not known and prev_unknown:
                        continue
                    candidates.append((acc + cost, i, rank, not known))
            candidates.sort(key=lambda item: item[0])
            paths[j] = candidates[:k]

        return self._rebuild(text, marks, index, paths, k)

    @staticmethod
    def _rebuild(text, marks, index, paths, k):
        results, seen = [], set()
        last = len(marks) - 1
        for cost, prev_i, prev_rank, _unknown in paths[last]:
            words, i = [], last
            cur_prev, cur_rank = prev_i, prev_rank
            while cur_prev is not None:
                words.append(text[marks[cur_prev]:marks[i]])
                i = cur_prev
                cur_prev, cur_rank = paths[i][cur_rank][1], paths[i][cur_rank][2]
            words.reverse()
            key = tuple(words)
            if key not in seen:
                seen.add(key)
                results.append((cost, words))
            if len(results) >= k:
                break
        return results


# ----------------------------------------------------------------------
def combinations(option_groups, limit=24):
    """ผสมตัวเลือกจากหลายก้อนให้ออกมาเรียงตามต้นทุนรวม (best-first)

    option_groups : list ของ list[(ต้นทุน, ค่า)] — แต่ละก้อนเรียงจากถูกไปแพงแล้ว
    คืน generator ของ list[ค่า]
    """
    if not option_groups:
        yield []
        return

    start = tuple(0 for _ in option_groups)
    total = sum(group[0][0] for group in option_groups)
    heap = [(total, start)]
    visited = {start}
    produced = 0

    while heap and produced < limit:
        cost, picks = heapq.heappop(heap)
        yield [option_groups[g][p][1] for g, p in enumerate(picks)]
        produced += 1

        for g, p in enumerate(picks):
            if p + 1 >= len(option_groups[g]):
                continue
            nxt = picks[:g] + (p + 1,) + picks[g + 1:]
            if nxt in visited:
                continue
            visited.add(nxt)
            delta = option_groups[g][p + 1][0] - option_groups[g][p][0]
            heapq.heappush(heap, (cost + delta, nxt))
