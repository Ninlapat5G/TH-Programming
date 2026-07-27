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
