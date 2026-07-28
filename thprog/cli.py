# -*- coding: utf-8 -*-
"""
คำสั่ง thprog — ตัวสั่งงานภาษา TH-Programming

ออกแบบให้ผู้ใช้ไม่ต้องยุ่งกับ Python เลย ทุกอย่างจบในคำสั่งเดียว
"""

import argparse
import io
import os
import sys
from pathlib import Path

from . import __version__
from .diagnostics import Code
from .errors import CompileError, ThaiError
from .compiler.typecheck import type_of_value
from .pipeline import check_source, compile_source, run, new_segmenter

BANNER = f"TH-Programming v{__version__} — เขียนโปรแกรมด้วยภาษาไทย"

# ทุกคำสั่งย่อยเรียกเป็นภาษาไทยได้ — ทั้งโปรเจกต์ตั้งใจให้ใช้ภาษาไทยล้วน
THAI_NAMES = {
    "run": ["รัน"],
    "show": ["ดูโค้ด"],
    "build": ["แปลง"],
    "check": ["ตรวจ"],
    "fmt": ["จัดรูป"],
    "new": ["ใหม่"],
    "mklib": ["สร้างคลัง"],
    "demo": ["สาธิต"],
    "repl": ["โต้ตอบ"],
    "doctor": ["ตรวจเครื่อง"],
    "version": ["รุ่น"],
    "help": ["ช่วยเหลือ"],
}
SUBCOMMANDS = set(THAI_NAMES) | {n for names in THAI_NAMES.values()
                                 for n in names}

TEMPLATE = """หมายเหตุ {ชื่อ} — สร้างโดย thprog new

แสดง"สวัสดี {ชื่อ}!"

ให้จำนวนรอบเป็น3
ทำซ้ำจำนวนรอบครั้ง
    แสดง"กำลังทำงาน..."

ฟังก์ชันบวกเลขรับตัวแรกและตัวหลัง
    คืนค่าตัวแรกบวกตัวหลัง

แสดง"2 + 3 =",บวกเลข(2,3)
"""


# ---------------------------------------------------------------- สภาพแวดล้อม
def _utf8_console():
    """บังคับให้อ่าน/เขียน UTF-8 เสมอ ไม่ว่าคอนโซลจะตั้ง codepage ใดไว้"""
    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, name, None)
        if isinstance(stream, io.TextIOWrapper) and \
                (stream.encoding or "").lower().replace("-", "") != "utf8":
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _use_color():
    if os.environ.get("NO_COLOR") or os.environ.get("THPRO_NO_COLOR"):
        return False
    if not sys.stderr.isatty():
        return False
    if os.name == "nt":
        try:                       # เปิดโหมดสี ANSI ของ Windows Terminal / cmd
            import ctypes
            handle = ctypes.windll.kernel32.GetStdHandle(-12)
            ctypes.windll.kernel32.SetConsoleMode(handle, 7)
        except Exception:
            return False
    return True


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _source(args):
    """ซอร์สที่จะคอมไพล์ — คืน (โค้ด, ชื่ออ้างอิง, แสดงค่าอัตโนมัติหรือไม่)

    รับได้สามทาง เหมือนที่ python เองรองรับ
        thprog โปรแกรม.th          จากไฟล์
        thprog 'แสดง 1'             จากบรรทัดคำสั่งโดยตรง (ไม่ต้องใส่ -c ก็ได้)
        ... | thprog -             จาก stdin

    สองทางหลังถือเป็น "โหมดพิมพ์สด" จึงแสดงค่าของนิพจน์เดี่ยวให้อัตโนมัติ
    ไฟล์ .th ไม่เปิดโหมดนี้ โปรแกรมที่เขียนไว้แล้วจึงทำงานเหมือนเดิมทุกประการ
    """
    if getattr(args, "command", None) is not None:
        return args.command, "<คำสั่ง>", True
    path = getattr(args, "file", None)
    if path in (None, "-"):
        return sys.stdin.read(), "<stdin>", True
    return _read(path), path, False


def _need_source(args):
    """ตรวจว่ามีอะไรให้คอมไพล์จริง ๆ ก่อนไปนั่งรอ stdin ค้างอยู่เฉย ๆ"""
    if getattr(args, "command", None) is not None:
        return True
    if getattr(args, "file", None) is not None:
        return True
    if not sys.stdin.isatty():
        return True
    print("ต้องระบุไฟล์.th หรือใช้ -c \"โค้ด\" หรือส่งโค้ดทาง stdin",
          file=sys.stderr)
    return False


def _report(program, color):
    """แสดงคำเตือนทั้งหมด (ข้อผิดพลาดถูกโยนเป็น CompileError ไปแล้ว)"""
    if not program.diagnostics:
        return
    for item in program.diagnostics.warnings:
        print(item.render(color), file=sys.stderr)


# ---------------------------------------------------------------- คำสั่งย่อย
def cmd_run(args):
    if not _need_source(args):
        return 1
    source, name, live = _source(args)
    program = compile_source(source, name, auto_show=live,
                             optimize_level=0 if args.no_optimize else 1)
    if not args.quiet:
        _report(program, args.color)
    env = run(program, show_warnings=False)
    if getattr(args, "interactive", False):
        # -i : รันจบแล้วอยู่ต่อในโหมดโต้ตอบ พร้อมตัวแปรทั้งหมดที่โปรแกรมสร้างไว้
        return cmd_repl(args, env)
    return 0


def cmd_show(args):
    if not _need_source(args):
        return 1
    source, name, live = _source(args)
    program = compile_source(source, name, auto_show=live,
                             optimize_level=0 if args.no_optimize else 1)
    _report(program, args.color)
    print(program.python)
    return 0


def cmd_build(args):
    if not _need_source(args):
        return 1
    source, name, _live = _source(args)
    program = compile_source(source, name,
                             optimize_level=0 if args.no_optimize else 1)
    _report(program, args.color)
    if args.output:
        target = Path(args.output)
    elif args.file and args.file != "-":
        target = Path(args.file).with_suffix(".py")
    else:
        print("ต้องระบุไฟล์ผลลัพธ์ด้วย -o เมื่อซอร์สไม่ได้มาจากไฟล์",
              file=sys.stderr)
        return 1
    target.write_text(program.python, encoding="utf-8")
    print(f"สร้างไฟล์ {target} เรียบร้อย")
    print("รันได้ด้วย:  python", target)
    return 0


def cmd_check(args):
    """ตรวจอย่างเดียว ไม่รัน — รองรับผลลัพธ์แบบเครื่องอ่านได้ด้วย

    โหมด --json ต้องไม่โยน CompileError ออกไป เพราะเครื่องมือภายนอก
    ต้องได้ JSON ที่ parse ได้เสมอ ไม่ว่าคอมไพล์จะผ่านหรือไม่
    """
    if not _need_source(args):
        return 1
    source, name, _live = _source(args)
    if args.json:
        bag = check_source(source, name)
        print(bag.to_json())
        return 1 if bag.has_errors() else 0

    program = compile_source(source, name)
    _report(program, args.color)
    bag = program.diagnostics
    print(f"ตรวจสอบผ่าน — {bag.summary()}")
    if args.stats:
        print("สถิติการคอมไพล์:")
        for key, value in program.stats.items():
            print(f"   {key}: {value}")
    return 0


def cmd_fmt(args):
    """จัดระเบียบการเยื้องและช่องว่าง โดยรักษาคอมเมนต์ไว้ครบ"""
    path = Path(args.file)
    source = _read(path)
    compile_source(source, str(path))          # ต้องคอมไพล์ผ่านก่อนจึงจะจัดรูปแบบ
    formatted = _format(source)
    if formatted == source:
        print("จัดรูปแบบอยู่แล้ว ไม่มีอะไรต้องแก้")
        return 0
    if args.dry_run:
        print(formatted, end="")
        return 0
    path.write_text(formatted, encoding="utf-8")
    print(f"จัดรูปแบบ {path} เรียบร้อย")
    return 0


def _format(source, width=4):
    """แปลงระดับการเยื้องให้เป็นทวีคูณของ 4 ช่องว่าง และตัดช่องว่างท้ายบรรทัด"""
    levels = []          # สแต็กของค่า indent เดิมในแต่ละระดับ
    out = []
    for raw in source.splitlines():
        line = raw.replace("\t", " " * width).rstrip()
        if not line.strip():
            out.append("")
            continue
        indent = len(line) - len(line.lstrip(" "))
        while levels and indent < levels[-1]:
            levels.pop()
        if not levels or indent > levels[-1]:
            if indent > 0:
                levels.append(indent)
        out.append(" " * (width * len(levels)) + line.strip())
    return "\n".join(out).rstrip("\n") + "\n"


def cmd_new(args):
    name = args.name
    path = Path(name if name.endswith(".th") else name + ".th")
    if path.exists() and not args.force:
        print(f"มีไฟล์ {path} อยู่แล้ว — ใช้ --force เพื่อเขียนทับ",
              file=sys.stderr)
        return 1
    path.write_text(TEMPLATE.format(ชื่อ=path.stem), encoding="utf-8")
    print(f"สร้าง {path} เรียบร้อย")
    print(f"ลองรันด้วย:  thprog {path}")
    return 0


def cmd_version(args):
    print(BANNER)
    return 0


def cmd_demo(args):
    """สาธิตภาษาแบบครบวงจร — ใช้โดย run_demo.bat

    ตั้งใจให้ข้อความภาษาไทยทั้งหมดออกจาก Python ไม่ใช่จากไฟล์ .bat
    เพราะ cmd.exe อ่านไฟล์ .bat ด้วย codepage เดิมของระบบ ทำให้ภาษาไทยเพี้ยน
    """
    path = Path(args.file) if args.file else \
        Path(__file__).resolve().parent.parent / "examples" / "demo.th"
    if not path.exists():
        print(f"ไม่พบไฟล์ตัวอย่าง: {path}", file=sys.stderr)
        return 1

    rule = "=" * 60
    print(rule)
    print(f"  {BANNER}")
    print(rule)

    print(f"\n[1/3] โปรแกรมตัวอย่าง — {path}")
    print("-" * 60)
    print(path.read_text(encoding="utf-8"))

    program = compile_source(path.read_text(encoding="utf-8"), str(path))

    print("-" * 60)
    print("[2/3] ผลการรัน")
    print("-" * 60)
    run(program, show_warnings=False)

    print("\n" + "-" * 60)
    print("[3/3] โค้ด Python ที่คอมไพเลอร์แปลออกมา")
    print("-" * 60)
    print(program.python)

    print(rule)
    print(f"  ลองแก้ไฟล์ {path.name} แล้วสั่ง  thprog {path.name}  ได้เลย")
    print("  พิมพ์  thprog ช่วยเหลือ  เพื่อดูคำสั่งทั้งหมด")
    print(rule)
    return 0


def cmd_doctor(args):
    """ตรวจว่าเครื่องพร้อมใช้งานหรือไม่"""
    print(BANNER)
    print()
    ok = True

    version = ".".join(str(v) for v in sys.version_info[:3])
    enough = sys.version_info >= (3, 8)
    ok &= enough
    print(f"{'[ผ่าน]' if enough else '[ไม่ผ่าน]'} Python {version} "
          f"(ต้องการ 3.8 ขึ้นไป)")

    encoding = (sys.stdout.encoding or "?").lower()
    print(f"[ผ่าน] การเข้ารหัสหน้าจอ: {encoding}")

    print(f"[ผ่าน] ตำแหน่งตัวภาษา: {Path(__file__).resolve().parent}")

    try:
        program = compile_source('แสดง"ทดสอบ"', "<doctor>")
        assert 'print("ทดสอบ")' in program.python
        print("[ผ่าน] ทดสอบคอมไพล์: สำเร็จ")
    except Exception as err:                     # noqa: BLE001
        ok = False
        print(f"[ไม่ผ่าน] ทดสอบคอมไพล์: {err}")

    print()
    print("พร้อมใช้งาน" if ok else "ยังมีปัญหา — ดูรายการด้านบน")
    return 0 if ok else 1


def cmd_make_library(args):
    """สร้างโครงคลังคำจากโมดูล Python — ชั้นที่ทำให้คลังคำ "ผลิตได้เร็ว"

    งานที่เหลือของคนคือ *แปลศัพท์* ไม่ใช่ *เขียน wrapper*
    ซึ่งเป็นงานที่กระจายให้คนอื่นช่วยได้ ต่างจากการเขียนโค้ด
    """
    import importlib
    import inspect

    target = args.module
    out = ['หมายเหตุ ==========================================',
           f'หมายเหตุ  โครงคลังคำที่สร้างจาก {target}',
           'หมายเหตุ  เติมชื่อไทยแทน ______ แล้วลบบรรทัดที่ไม่ต้องการทิ้ง',
           'หมายเหตุ  จากนั้นบันทึกไว้ที่  คลัง/<ชื่อคลัง>.th',
           'หมายเหตุ ==========================================',
           'หมายเหตุ',
           'หมายเหตุ  กติกาการตั้งชื่อไทย',
           'หมายเหตุ    * ห้ามขึ้นต้นด้วยคำที่ใช้ขึ้นต้นคำสั่ง '
           '(แสดง ให้ เพิ่ม เติม นับ ทำ ใช้)',
           'หมายเหตุ    * ห้ามลงท้ายด้วย "ของ" เพราะ "ของ" มาจากจุดที่เรียกใช้',
           'หมายเหตุ    * ตั้งให้อ่านเป็น กริยา+กรรม เช่น  ตัดช่องว่างของประโยค',
           ""]

    obj = _BASIC_TYPES.get(target)
    if obj is not None:
        out.append(f"หมายเหตุ --- เมธอดของ {obj.__name__} ---")
        for member in sorted(n for n in dir(obj) if not n.startswith("_")):
            out.append(f"นำเข้าวิธี {member} เป็น______"
                       f"      {_describe(getattr(obj, member), member)}")
    else:
        try:
            module = importlib.import_module(target)
        except Exception as err:                      # noqa: BLE001
            print(f'นำเข้าโมดูล "{target}" ไม่สำเร็จ: {err}', file=sys.stderr)
            print(f"ชนิดพื้นฐานที่รองรับ: {' · '.join(sorted(_BASIC_TYPES))}",
                  file=sys.stderr)
            return 1
        # ใช้ __all__ ถ้ามี มิฉะนั้นกรองของที่โมดูลอื่นนำเข้ามาทิ้ง
        # (เช่น statistics นำ math.acos เข้ามา ซึ่งไม่ใช่ของตัวเอง)
        names = getattr(module, "__all__", None)
        if names is None:
            names = [n for n in dir(module) if not n.startswith("_")
                     and getattr(getattr(module, n), "__module__", target)
                     == target]
        out.append(f"หมายเหตุ --- ของใน {target} ---")
        for member in sorted(names):
            value = getattr(module, member, None)
            if value is None or inspect.ismodule(value):
                continue
            out.append(f"นำเข้า {member} จาก {target} เป็น______"
                       f"      {_describe(value, member)}")

    text = "\n".join(out) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"สร้างโครงคลังคำที่ {args.output} เรียบร้อย "
              f"({len(out)} บรรทัด)")
    else:
        print(text, end="")
    return 0


_BASIC_TYPES = {
    "str": str, "ข้อความ": str,
    "list": list, "รายการ": list,
    "dict": dict, "พจนานุกรม": dict,
    "set": set, "เซต": set,
}


def _describe(value, name):
    """คำอธิบายสั้น ๆ ของสมาชิกหนึ่งตัว ใช้เป็นคอมเมนต์ช่วยคนแปล"""
    import inspect
    try:
        signature = str(inspect.signature(value))
    except (TypeError, ValueError):
        signature = ""
    doc = (inspect.getdoc(value) or "").strip().splitlines()
    summary = doc[0][:60] if doc else type(value).__name__
    return f"หมายเหตุ {name}{signature} — {summary}"


def cmd_help(args):
    build_parser().print_help()
    print()
    print("ตัวอย่างการใช้งาน")
    print("  thprog โปรแกรม.th              รันโปรแกรม")
    print("  thprog '2 บวก 3'               รันโค้ดสั้น ๆ แล้วแสดงผลให้เลย")
    print("  thprog 'แสดง \"สวัสดี\"'          ไม่ต้องใส่ -c ก็ได้")
    print("  cat โปรแกรม.th | thprog -      รับโค้ดทาง stdin")
    print("  thprog -i โปรแกรม.th           รันจบแล้วคุยต่อในโหมดโต้ตอบ")
    print("  thprog ใหม่ โปรแกรมแรก          สร้างไฟล์เริ่มต้น")
    print("  thprog ดูโค้ด โปรแกรม.th        ดูโค้ด Python ที่แปลได้")
    print("  thprog แปลง โปรแกรม.th          สร้างไฟล์ .py ที่รันเองได้")
    print("  thprog ตรวจ โปรแกรม.th          ตรวจอย่างเดียว ไม่รัน")
    print("  thprog จัดรูป โปรแกรม.th         จัดระเบียบการเยื้อง")
    print("  thprog สร้างคลัง str            สร้างโครงคลังคำไทยจากโมดูล Python")
    print("  thprog โต้ตอบ                   โหมดโต้ตอบ")
    print("  thprog ตรวจเครื่อง               ตรวจความพร้อมของเครื่อง")
    print()
    print("ทุกคำสั่งย่อยเรียกเป็นภาษาอังกฤษก็ได้: run show build check fmt new")
    return 0


def cmd_repl(args, env=None):
    """โหมดโต้ตอบ — รับ env มาต่อได้ เพื่อให้ `thprog -i` รันโปรแกรมก่อนแล้วคุยต่อ"""
    if env is None:
        print(BANNER)
        env = {"__name__": "__main__"}
    else:
        print(f"\n--- {BANNER} : โหมดโต้ตอบ ---")
    print('พิมพ์คำสั่งภาษาไทยทีละบรรทัด  (พิมพ์ "ออก" เพื่อจบ)')
    segmenter = new_segmenter()
    buffer = []

    while True:
        try:
            line = input("..... " if buffer else "ไทย> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not buffer and line.strip() in ("ออก", "จบ", "exit", "quit"):
            break
        if not buffer and not line.strip():
            continue

        forced = bool(buffer) and not line.strip()
        buffer.append(line)
        source = "\n".join(buffer)

        try:
            # โหมดโต้ตอบรู้ "ค่าจริง" ของตัวแปรที่ประกาศไปแล้ว จึงบอกชนิดที่
            # แน่นอนให้ตัวตรวจชนิดได้ ทำให้ตรวจได้เข้มเท่ากับตอนคอมไพล์ทั้งไฟล์
            known = {k: type_of_value(v) for k, v in env.items()
                     if not k.startswith("_")}
            program = compile_source(source, "<repl>", known, segmenter,
                                     auto_show=True)
        except CompileError as err:
            # บล็อกยังไม่จบ -> รอบรรทัดถัดไป (เว้นแต่ผู้ใช้เคาะบรรทัดว่าง)
            if not forced and any(d.code == Code.EMPTY_BLOCK
                                  for d in err.bag.errors):
                continue
            print(err.render(args.color))
            buffer = []
            continue
        except ThaiError as err:
            print(err.render(args.color))
            buffer = []
            continue

        buffer = []
        _report(program, args.color)
        try:
            exec(compile(program.python, "<repl-py>", "exec"), env)
        except Exception as err:                  # noqa: BLE001
            print(f"[TH401] ข้อผิดพลาดขณะทำงาน — {err}")
    return 0


# ---------------------------------------------------------------- ตัวแจงอาร์กิวเมนต์
def build_parser():
    ap = argparse.ArgumentParser(
        prog="thprog", description=BANNER,
        epilog='เขียนไฟล์นามสกุล .th แล้วสั่ง  thprog ชื่อไฟล์.th'
               '  ·  หรือสั่งสั้น ๆ ด้วย  thprog -c \'แสดง "สวัสดี"\'')
    sub = ap.add_subparsers(dest="cmd", metavar="คำสั่ง")

    def add_source_arg(p):
        """ทุกคำสั่งที่ต้องใช้ซอร์ส รับได้ทั้งไฟล์ · -c · stdin"""
        p.add_argument("file", nargs="?", metavar="ไฟล์.th",
                       help='ไฟล์ .th  (ใส่ - เพื่ออ่านจาก stdin)')
        p.add_argument("-c", "--command", metavar="โค้ด",
                       help='เขียนโค้ดตรงนี้เลย เช่น  -c \'แสดง "สวัสดี"\'')

    def add_file_cmd(name, help_text, func, optimize=True):
        p = sub.add_parser(name, help=help_text, aliases=THAI_NAMES[name])
        add_source_arg(p)
        if optimize:
            p.add_argument("-O0", "--no-optimize", action="store_true",
                           help="ปิดการปรับให้เหมาะที่สุด")
        p.set_defaults(func=func)
        return p

    p = add_file_cmd("run", "แปลแล้วรันทันที", cmd_run)
    p.add_argument("-q", "--quiet", action="store_true", help="ซ่อนคำเตือน")
    p.add_argument("-i", "--interactive", action="store_true",
                   help="รันจบแล้วอยู่ต่อในโหมดโต้ตอบ พร้อมตัวแปรเดิม")

    add_file_cmd("show", "แสดงโค้ด Python ที่แปลได้", cmd_show)

    p = add_file_cmd("build", "แปลเป็นไฟล์ .py", cmd_build)
    p.add_argument("-o", "--output", metavar="ไฟล์ผลลัพธ์")

    p = sub.add_parser("check", help="ตรวจอย่างเดียว ไม่รัน",
                       aliases=THAI_NAMES["check"])
    add_source_arg(p)
    p.add_argument("--stats", action="store_true", help="แสดงสถิติการคอมไพล์")
    p.add_argument("--json", action="store_true",
                   help="แสดงผลเป็น JSON สำหรับ editor หรือ CI")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("fmt", help="จัดระเบียบการเยื้องและช่องว่าง",
                       aliases=THAI_NAMES["fmt"])
    p.add_argument("file", metavar="ไฟล์.th")
    p.add_argument("-n", "--dry-run", action="store_true",
                   help="แสดงผลลัพธ์โดยไม่เขียนทับไฟล์")
    p.set_defaults(func=cmd_fmt)

    p = sub.add_parser("new", help="สร้างไฟล์โปรแกรมเริ่มต้น",
                       aliases=THAI_NAMES["new"])
    p.add_argument("name", metavar="ชื่อโปรแกรม")
    p.add_argument("-f", "--force", action="store_true", help="เขียนทับได้")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("mklib", help="สร้างโครงคลังคำไทยจากโมดูล Python",
                       aliases=THAI_NAMES["mklib"])
    p.add_argument("module", metavar="โมดูล",
                   help="ชื่อโมดูล Python หรือชนิดพื้นฐาน (str/list/dict/set)")
    p.add_argument("-o", "--output", metavar="ไฟล์ผลลัพธ์")
    p.set_defaults(func=cmd_make_library)

    p = sub.add_parser("demo", help="สาธิตภาษาแบบครบวงจร",
                       aliases=THAI_NAMES["demo"])
    p.add_argument("file", nargs="?", metavar="ไฟล์.th")
    p.set_defaults(func=cmd_demo)

    for name, help_text, func in (
            ("repl", "โหมดโต้ตอบ", cmd_repl),
            ("doctor", "ตรวจความพร้อมของเครื่อง", cmd_doctor),
            ("version", "แสดงเวอร์ชัน", cmd_version),
            ("help", "แสดงวิธีใช้", cmd_help)):
        sub.add_parser(name, help=help_text,
                       aliases=THAI_NAMES[name]).set_defaults(func=func)
    return ap


def _looks_like_code(arg):
    """อาร์กิวเมนต์แรกเป็น "โค้ด" หรือ "ชื่อไฟล์"

    ตัดสินง่าย ๆ และเดาได้: เป็นไฟล์ที่มีอยู่จริง หรือลงท้าย .th = ไฟล์
    นอกนั้นถือเป็นโค้ด  ทำให้พิมพ์  thprog '2 บวก 3'  ได้เลยโดยไม่ต้องมี -c
    ส่วนการพิมพ์ชื่อไฟล์ผิดยังฟ้อง "ไม่พบไฟล์" ตามเดิม เพราะลงท้าย .th
    """
    if arg.startswith("-") or arg.endswith(".th"):
        return False
    return not Path(arg).exists()


def main(argv=None):
    _utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)

    # ทางลัด — ทุกแบบนี้ให้ถือว่าเป็นคำสั่ง run
    #     thprog โปรแกรม.th          จากไฟล์
    #     thprog 'แสดง 1'             จากบรรทัดคำสั่งโดยตรง (ไม่ต้องใส่ -c)
    #     thprog -c 'แสดง 1'          รูปแบบยาว ยังใช้ได้เหมือน python -c
    #     thprog -                   จาก stdin
    if argv and argv[0] not in SUBCOMMANDS and argv[0] not in ("-h", "--help"):
        if _looks_like_code(argv[0]):
            argv[:1] = ["run", "-c", argv[0]]
        else:
            argv.insert(0, "run")

    ap = build_parser()
    args = ap.parse_args(argv)
    args.color = _use_color()
    if not getattr(args, "func", None):
        cmd_help(args)
        return 1

    try:
        return args.func(args)
    except CompileError as err:
        print(err.render(args.color), file=sys.stderr)
        return 1
    except ThaiError as err:
        print(err.render(args.color), file=sys.stderr)
        return 1
    except FileNotFoundError as err:
        print(f"ไม่พบไฟล์: {err.filename}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nหยุดการทำงานแล้ว", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
