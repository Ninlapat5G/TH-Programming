# -*- coding: utf-8 -*-
"""
ฟังก์ชันสำเร็จรูปของภาษา TH-Programming

สองส่วน
  BUILTINS : ชื่อภาษาไทย -> (โค้ด Python ที่จะเรียก, ชื่อ helper ที่ต้องแนบ)
  HELPERS  : โค้ด helper ที่จะถูก "ฝัง" ลงไฟล์ผลลัพธ์เฉพาะตัวที่ถูกใช้จริง
             ทำให้ไฟล์ .py ที่ได้เป็นไฟล์เดี่ยว รันได้เองโดยไม่ต้องติดตั้งอะไร
"""

BUILTINS = {
    # ----- ขนาดและการนับ -----
    "ความยาว": ("len", None),
    "ขนาด": ("len", None),
    "จำนวนสมาชิก": ("len", None),
    "จำนวนตัว": ("len", None),

    # ----- แปลงชนิดข้อมูล -----
    "ตัวเลข": ("int", None),
    "จำนวนเต็ม": ("int", None),
    "แปลงเป็นตัวเลข": ("int", None),
    "ทศนิยม": ("float", None),
    "แปลงเป็นทศนิยม": ("float", None),
    "ข้อความ": ("str", None),
    "สตริง": ("str", None),
    "แปลงเป็นข้อความ": ("str", None),

    # ----- คณิตศาสตร์และสถิติ -----
    "ผลรวม": ("sum", None),
    "รวมทั้งหมด": ("sum", None),
    "ยอดรวม": ("sum", None),
    "ค่ามากสุด": ("max", None),
    "มากสุด": ("max", None),
    "ค่าสูงสุด": ("max", None),
    "ค่าน้อยสุด": ("min", None),
    "น้อยสุด": ("min", None),
    "ค่าต่ำสุด": ("min", None),
    "ปัดเศษ": ("round", None),
    "ปัดทศนิยม": ("round", None),
    "ค่าสัมบูรณ์": ("abs", None),
    "ค่าเฉลี่ย": ("_th_mean", "mean"),
    "รากที่สอง": ("_th_sqrt", "sqrt"),
    "สแควร์รูท": ("_th_sqrt", "sqrt"),

    # ----- สุ่ม -----
    "สุ่ม": ("_th_rand", "rand"),
    "สุ่มเลข": ("_th_rand", "rand"),
    "สุ่มเลือก": ("_th_choice", "choice"),
    "สุ่มหยิบ": ("_th_choice", "choice"),

    # ----- รายการ -----
    "ช่วง": ("range", None),
    "ช่วงตัวเลข": ("range", None),
    "เรียงลำดับ": ("sorted", None),
    "จัดเรียง": ("sorted", None),
    "กลับลำดับ": ("_th_reverse", "reverse"),
    "ย้อนลำดับ": ("_th_reverse", "reverse"),
    "รายการว่าง": ("_th_newlist", "newlist"),
    "ลบสมาชิก": ("_th_remove", "remove"),
    "เอาออก": ("_th_remove", "remove"),
    "มีอยู่": ("_th_contains", "contains"),
    "ประกอบด้วย": ("_th_contains", "contains"),
    "หาตำแหน่ง": ("_th_indexof", "indexof"),

    # ----- ตัด / หยิบ ชิ้นส่วน (ใช้ได้ทั้งข้อความและรายการ) -----
    # ภาษาไทยเรียก "ตัดตัวท้ายออก" ตรง ๆ ไม่ต้องรู้จักไวยากรณ์สไลซ์ของ Python
    "ตัดท้าย": ("_th_drop_last", "droplast"),
    "ตัดตัวท้าย": ("_th_drop_last", "droplast"),
    "ตัดท้ายออก": ("_th_drop_last", "droplast"),
    "ตัดหน้า": ("_th_drop_first", "dropfirst"),
    "ตัดตัวแรก": ("_th_drop_first", "dropfirst"),
    "ตัดหน้าออก": ("_th_drop_first", "dropfirst"),
    "ตัวแรก": ("_th_first", "first"),
    "อันแรก": ("_th_first", "first"),
    "ตัวสุดท้าย": ("_th_last", "last"),
    "อันสุดท้าย": ("_th_last", "last"),
    "ตัดเอา": ("_th_slice", "slice"),
    "ตัดช่วง": ("_th_slice", "slice"),
    "เอาช่วง": ("_th_slice", "slice"),
    "ลบตัวอักษร": ("_th_delete", "delete"),
    "เอาตัวอักษรออก": ("_th_delete", "delete"),
    "ลบทุกตัวที่เป็น": ("_th_delete", "delete"),
    "นับจำนวน": ("_th_count_of", "countof"),
    "นับตัวที่เป็น": ("_th_count_of", "countof"),

    # ----- ข้อความ -----
    "ตัวพิมพ์ใหญ่": ("_th_upper", "upper"),
    "พิมพ์ใหญ่": ("_th_upper", "upper"),
    "ตัวพิมพ์เล็ก": ("_th_lower", "lower"),
    "พิมพ์เล็ก": ("_th_lower", "lower"),
    "แยกคำ": ("_th_split", "split"),
    "แบ่งข้อความ": ("_th_split", "split"),
    "ต่อข้อความ": ("_th_join", "join"),
    "เชื่อมข้อความ": ("_th_join", "join"),
    "ตัดช่องว่าง": ("_th_strip", "strip"),
    "แทนที่": ("_th_replace", "replace"),

    # ----- อื่น ๆ -----
    "ชนิด": ("_th_typename", "typename"),
    "ชนิดข้อมูล": ("_th_typename", "typename"),
    "ประเภท": ("_th_typename", "typename"),
}


# ชนิดข้อมูลที่ใช้กับ "ถาม ... เก็บใน ... เป็น <ชนิด>"
CAST_TYPES = {
    "ตัวเลข": "int", "จำนวนเต็ม": "int", "เลขจำนวนเต็ม": "int",
    "ทศนิยม": "float", "เลขทศนิยม": "float",
    "ข้อความ": "str", "สตริง": "str", "ตัวหนังสือ": "str",
}


# key -> (โค้ด, โมดูลที่ต้อง import)
HELPERS = {
    "append": ("def _th_append(lst, value):\n"
               "    lst.append(value)\n"
               "    return lst", ()),
    "remove": ("def _th_remove(lst, value):\n"
               "    if value in lst:\n"
               "        lst.remove(value)\n"
               "    return lst", ()),
    "contains": ("def _th_contains(container, value):\n"
                 "    return value in container", ()),
    "indexof": ("def _th_indexof(container, value):\n"
                "    try:\n"
                "        return container.index(value)\n"
                "    except ValueError:\n"
                "        return -1", ()),
    "newlist": ("def _th_newlist():\n"
                "    return []", ()),
    "reverse": ("def _th_reverse(seq):\n"
                "    return list(reversed(seq))", ()),
    "upper": ("def _th_upper(text):\n"
              "    return str(text).upper()", ()),
    "lower": ("def _th_lower(text):\n"
              "    return str(text).lower()", ()),
    "strip": ("def _th_strip(text):\n"
              "    return str(text).strip()", ()),
    "replace": ("def _th_replace(text, old, new):\n"
                "    return str(text).replace(str(old), str(new))", ()),
    "split": ("def _th_split(text, sep=None):\n"
              "    return str(text).split(sep)", ()),
    "join": ("def _th_join(parts, sep=''):\n"
             "    return str(sep).join(str(p) for p in parts)", ()),
    "mean": ("def _th_mean(values):\n"
             "    values = list(values)\n"
             "    return sum(values) / len(values) if values else 0", ()),
    "typename": ("def _th_typename(value):\n"
                 "    return {int: 'จำนวนเต็ม', float: 'ทศนิยม', str: 'ข้อความ',\n"
                 "            bool: 'ค่าความจริง', list: 'รายการ',\n"
                 "            dict: 'พจนานุกรม', type(None): 'ค่าว่าง'\n"
                 "            }.get(type(value), type(value).__name__)", ()),
    "sqrt": ("def _th_sqrt(x):\n"
             "    return _math.sqrt(x)", ("math",)),
    "rand": ("def _th_rand(a, b):\n"
             "    return _random.randint(a, b)", ("random",)),
    "choice": ("def _th_choice(seq):\n"
               "    return _random.choice(seq)", ("random",)),
    # ---- ตัด/หยิบชิ้นส่วน — เขียนให้รับได้ทั้งข้อความและรายการ
    # เหมือน Python ที่ใช้สไลซ์ตัวเดียวกันกับทั้งสองชนิด
    "droplast": ("def _th_drop_last(seq, n=1):\n"
                 "    n = int(n)\n"
                 "    return seq if n <= 0 else seq[:-n]", ()),
    "dropfirst": ("def _th_drop_first(seq, n=1):\n"
                  "    n = int(n)\n"
                  "    return seq if n <= 0 else seq[n:]", ()),
    "first": ("def _th_first(seq, n=None):\n"
              "    return seq[0] if n is None else seq[:int(n)]", ()),
    "last": ("def _th_last(seq, n=None):\n"
             "    if n is None:\n"
             "        return seq[-1]\n"
             "    n = int(n)\n"
             "    return seq[0:0] if n <= 0 else seq[-n:]", ()),
    "slice": ("def _th_slice(seq, start, end=None):\n"
              "    start = int(start)\n"
              "    return seq[start:] if end is None else seq[start:int(end)]",
              ()),
    "delete": ("def _th_delete(seq, value):\n"
               "    if isinstance(seq, str):\n"
               "        return seq.replace(str(value), '')\n"
               "    return [x for x in seq if x != value]", ()),
    "countof": ("def _th_count_of(seq, value):\n"
                "    if isinstance(seq, str):\n"
                "        return seq.count(str(value))\n"
                "    return list(seq).count(value)", ()),

    # แสดงค่าของนิพจน์เดี่ยวในโหมดโต้ตอบ — เงียบเมื่อค่าเป็นค่าว่าง
    # เพื่อให้การเรียกคำสั่งที่ไม่คืนค่า ไม่พ่นคำว่า None ออกมารกจอ
    "show": ("def _th_show(value):\n"
             "    if value is not None:\n"
             "        print(value)", ()),
    "count": ("def _th_count(start, end, step=1):\n"
              "    if step == 0:\n"
              "        raise ValueError('ทีละ 0 ทำให้วนไม่รู้จบ')\n"
              "    if step > 0:\n"
              "        return range(start, end + 1, step)\n"
              "    return range(start, end - 1, step)", ()),
}

IMPORT_LINES = {
    "math": "import math as _math",
    "random": "import random as _random",
}


# ======================================================================
#  เมธอดของ Python ที่มีคำไทยให้ใช้อยู่แล้ว
# ======================================================================
# ใช้เตือน (TW106) เมื่อผู้ใช้เขียน  ค่า.strip()  ทั้งที่พิมพ์ ตัดช่องว่างของค่า ได้
# จุดยังใช้ได้เสมอ — เป็นทางออกฉุกเฉินสำหรับของที่ยังไม่มีคำไทย
#
# ใส่เฉพาะตัวที่ "มีคำไทยมาตรฐานอยู่แล้วจริง ๆ" เพื่อไม่ให้เตือนพร่ำเพรื่อ
THAI_FOR_METHOD = {
    "strip": "ตัดช่องว่าง(ค่า)",
    "upper": "ตัวพิมพ์ใหญ่(ค่า)",
    "lower": "ตัวพิมพ์เล็ก(ค่า)",
    "split": "แยกคำ(ค่า)",
    "join": "ต่อข้อความ(รายการ, ตัวคั่น)",
    "replace": "แทนที่(ค่า, ของเดิม, ของใหม่)",
    "append": "เพิ่ม <ค่า> เข้าไปใน <รายการ>",
    "remove": "เอาออก(รายการ, ค่า)",
    "sort": "เรียงลำดับ(รายการ)",
    "sorted": "เรียงลำดับ(รายการ)",
    "reverse": "กลับลำดับ(รายการ)",
}


# ======================================================================
#  ลายเซ็นชนิดข้อมูลของฟังก์ชันสำเร็จรูป — ใช้โดยตัวตรวจชนิด (typecheck.py)
# ======================================================================
#     ชื่อไทย : ([ชนิดที่รับได้ของแต่ละพารามิเตอร์], ชนิดที่คืน)
#
# `None` ในตำแหน่งพารามิเตอร์ = รับอะไรก็ได้ (ไม่ต้องตรวจ)
# ชื่อที่ไม่อยู่ในตารางนี้ = ไม่ตรวจชนิด (ปลอดภัยไว้ก่อน)
#
# ชื่อชนิดตรงกับที่ผู้ใช้เห็นจากฟังก์ชัน ชนิด() เพื่อให้ข้อความผิดพลาดสอดคล้องกัน
_NUM = ("จำนวนเต็ม", "ทศนิยม")
_SIZED = ("ข้อความ", "รายการ", "พจนานุกรม")

SIGNATURES = {
    # ----- ขนาดและการนับ -----
    "ความยาว": ([_SIZED], "จำนวนเต็ม"),
    "ขนาด": ([_SIZED], "จำนวนเต็ม"),
    "จำนวนสมาชิก": ([_SIZED], "จำนวนเต็ม"),
    "จำนวนตัว": ([_SIZED], "จำนวนเต็ม"),

    # ----- แปลงชนิดข้อมูล (รับอะไรก็ได้) -----
    "ตัวเลข": ([None], "จำนวนเต็ม"),
    "จำนวนเต็ม": ([None], "จำนวนเต็ม"),
    "แปลงเป็นตัวเลข": ([None], "จำนวนเต็ม"),
    "ทศนิยม": ([None], "ทศนิยม"),
    "แปลงเป็นทศนิยม": ([None], "ทศนิยม"),
    "ข้อความ": ([None], "ข้อความ"),
    "สตริง": ([None], "ข้อความ"),
    "แปลงเป็นข้อความ": ([None], "ข้อความ"),

    # ----- คณิตศาสตร์ -----
    "ผลรวม": ([("รายการ",)], None),
    "รวมทั้งหมด": ([("รายการ",)], None),
    "ยอดรวม": ([("รายการ",)], None),
    "ค่าเฉลี่ย": ([("รายการ",)], "ทศนิยม"),
    "ปัดเศษ": ([_NUM, _NUM], None),
    "ปัดทศนิยม": ([_NUM, _NUM], None),
    "ค่าสัมบูรณ์": ([_NUM], None),
    "รากที่สอง": ([_NUM], "ทศนิยม"),
    "สแควร์รูท": ([_NUM], "ทศนิยม"),

    # ----- สุ่ม -----
    "สุ่ม": ([_NUM, _NUM], "จำนวนเต็ม"),
    "สุ่มเลข": ([_NUM, _NUM], "จำนวนเต็ม"),
    "สุ่มเลือก": ([_SIZED], None),
    "สุ่มหยิบ": ([_SIZED], None),

    # ----- รายการ -----
    "ช่วง": ([_NUM, _NUM, _NUM], "รายการ"),
    "ช่วงตัวเลข": ([_NUM, _NUM, _NUM], "รายการ"),
    "เรียงลำดับ": ([_SIZED], "รายการ"),
    "จัดเรียง": ([_SIZED], "รายการ"),
    "กลับลำดับ": ([_SIZED], "รายการ"),
    "ย้อนลำดับ": ([_SIZED], "รายการ"),
    "รายการว่าง": ([], "รายการ"),
    "ลบสมาชิก": ([("รายการ",), None], "รายการ"),
    "เอาออก": ([("รายการ",), None], "รายการ"),
    "มีอยู่": ([_SIZED, None], "ค่าความจริง"),
    "ประกอบด้วย": ([_SIZED, None], "ค่าความจริง"),
    "หาตำแหน่ง": ([_SIZED, None], "จำนวนเต็ม"),

    # ----- ตัด / หยิบ ชิ้นส่วน -----
    # คืนชนิดเดียวกับที่รับเข้ามา จึงบอกชนิดล่วงหน้าไม่ได้ -> None (ไม่ทราบ)
    "ตัดท้าย": ([_SIZED, _NUM], None),
    "ตัดตัวท้าย": ([_SIZED, _NUM], None),
    "ตัดท้ายออก": ([_SIZED, _NUM], None),
    "ตัดหน้า": ([_SIZED, _NUM], None),
    "ตัดตัวแรก": ([_SIZED, _NUM], None),
    "ตัดหน้าออก": ([_SIZED, _NUM], None),
    "ตัวแรก": ([_SIZED, _NUM], None),
    "อันแรก": ([_SIZED, _NUM], None),
    "ตัวสุดท้าย": ([_SIZED, _NUM], None),
    "อันสุดท้าย": ([_SIZED, _NUM], None),
    "ตัดเอา": ([_SIZED, _NUM, _NUM], None),
    "ตัดช่วง": ([_SIZED, _NUM, _NUM], None),
    "เอาช่วง": ([_SIZED, _NUM, _NUM], None),
    "ลบตัวอักษร": ([_SIZED, None], None),
    "เอาตัวอักษรออก": ([_SIZED, None], None),
    "ลบทุกตัวที่เป็น": ([_SIZED, None], None),
    "นับจำนวน": ([_SIZED, None], "จำนวนเต็ม"),
    "นับตัวที่เป็น": ([_SIZED, None], "จำนวนเต็ม"),

    # ----- ข้อความ -----
    "ตัวพิมพ์ใหญ่": ([None], "ข้อความ"),
    "พิมพ์ใหญ่": ([None], "ข้อความ"),
    "ตัวพิมพ์เล็ก": ([None], "ข้อความ"),
    "พิมพ์เล็ก": ([None], "ข้อความ"),
    "แยกคำ": ([None, None], "รายการ"),
    "แบ่งข้อความ": ([None, None], "รายการ"),
    "ต่อข้อความ": ([("รายการ",), None], "ข้อความ"),
    "เชื่อมข้อความ": ([("รายการ",), None], "ข้อความ"),
    "ตัดช่องว่าง": ([None], "ข้อความ"),
    "แทนที่": ([None, None, None], "ข้อความ"),

    # ----- อื่น ๆ -----
    "ชนิด": ([None], "ข้อความ"),
    "ชนิดข้อมูล": ([None], "ข้อความ"),
    "ประเภท": ([None], "ข้อความ"),
}
