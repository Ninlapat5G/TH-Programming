# -*- coding: utf-8 -*-
"""
คำสั่ง thpro — ตัวสั่งงานภาษา TH-Programming

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
SUBCOMMANDS = {"run", "show", "build", "check", "fmt", "new", "demo",
               "repl", "doctor", "version", "help"}

TEMPLATE = """หมายเหตุ {ชื่อ} — สร้างโดย thpro new

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


def _report(program, color):
    """แสดงคำเตือนทั้งหมด (ข้อผิดพลาดถูกโยนเป็น CompileError ไปแล้ว)"""
    if not program.diagnostics:
        return
    for item in program.diagnostics.warnings:
        print(item.render(color), file=sys.stderr)


# ---------------------------------------------------------------- คำสั่งย่อย
def cmd_run(args):
    program = compile_source(_read(args.file), args.file,
                             optimize_level=0 if args.no_optimize else 1)
    if not args.quiet:
        _report(program, args.color)
    run(program, show_warnings=False)
    return 0


def cmd_show(args):
    program = compile_source(_read(args.file), args.file,
                             optimize_level=0 if args.no_optimize else 1)
    _report(program, args.color)
    print(program.python)
    return 0


def cmd_build(args):
    program = compile_source(_read(args.file), args.file,
                             optimize_level=0 if args.no_optimize else 1)
    _report(program, args.color)
    target = Path(args.output) if args.output else Path(args.file).with_suffix(".py")
    target.write_text(program.python, encoding="utf-8")
    print(f"สร้างไฟล์ {target} เรียบร้อย")
    print("รันได้ด้วย:  python", target)
    return 0


def cmd_check(args):
    """ตรวจอย่างเดียว ไม่รัน — รองรับผลลัพธ์แบบเครื่องอ่านได้ด้วย

    โหมด --json ต้องไม่โยน CompileError ออกไป เพราะเครื่องมือภายนอก
    ต้องได้ JSON ที่ parse ได้เสมอ ไม่ว่าคอมไพล์จะผ่านหรือไม่
    """
    if args.json:
        bag = check_source(_read(args.file), args.file)
        print(bag.to_json())
        return 1 if bag.has_errors() else 0

    program = compile_source(_read(args.file), args.file)
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
    print(f"ลองรันด้วย:  thpro {path}")
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
    print(f"  ลองแก้ไฟล์ {path.name} แล้วสั่ง  thpro {path.name}  ได้เลย")
    print(f"  พิมพ์  thpro help  เพื่อดูคำสั่งทั้งหมด")
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


def cmd_help(args):
    build_parser().print_help()
    print()
    print("ตัวอย่างการใช้งาน")
    print("  thpro โปรแกรม.th              รันโปรแกรม")
    print("  thpro new โปรแกรมแรก          สร้างไฟล์เริ่มต้น")
    print("  thpro show โปรแกรม.th         ดูโค้ด Python ที่แปลได้")
    print("  thpro build โปรแกรม.th        สร้างไฟล์ .py ที่รันเองได้")
    print("  thpro check โปรแกรม.th        ตรวจอย่างเดียว ไม่รัน")
    print("  thpro fmt โปรแกรม.th          จัดระเบียบการเยื้อง")
    print("  thpro repl                    โหมดโต้ตอบ")
    print("  thpro doctor                  ตรวจความพร้อมของเครื่อง")
    return 0


def cmd_repl(args):
    print(BANNER)
    print('พิมพ์คำสั่งภาษาไทยทีละบรรทัด  (พิมพ์ "ออก" เพื่อจบ)')
    env = {"__name__": "__main__"}
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
            program = compile_source(source, "<repl>", known, segmenter)
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
        prog="thpro", description=BANNER,
        epilog="เขียนไฟล์นามสกุล .th แล้วสั่ง  thpro ชื่อไฟล์.th")
    sub = ap.add_subparsers(dest="cmd", metavar="คำสั่ง")

    def add_file_cmd(name, help_text, func, optimize=True):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("file", metavar="ไฟล์.th")
        if optimize:
            p.add_argument("-O0", "--no-optimize", action="store_true",
                           help="ปิดการปรับให้เหมาะที่สุด")
        p.set_defaults(func=func)
        return p

    p = add_file_cmd("run", "แปลแล้วรันทันที", cmd_run)
    p.add_argument("-q", "--quiet", action="store_true", help="ซ่อนคำเตือน")

    add_file_cmd("show", "แสดงโค้ด Python ที่แปลได้", cmd_show)

    p = add_file_cmd("build", "แปลเป็นไฟล์ .py", cmd_build)
    p.add_argument("-o", "--output", metavar="ไฟล์ผลลัพธ์")

    p = sub.add_parser("check", help="ตรวจอย่างเดียว ไม่รัน")
    p.add_argument("file", metavar="ไฟล์.th")
    p.add_argument("--stats", action="store_true", help="แสดงสถิติการคอมไพล์")
    p.add_argument("--json", action="store_true",
                   help="แสดงผลเป็น JSON สำหรับ editor หรือ CI")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("fmt", help="จัดระเบียบการเยื้องและช่องว่าง")
    p.add_argument("file", metavar="ไฟล์.th")
    p.add_argument("-n", "--dry-run", action="store_true",
                   help="แสดงผลลัพธ์โดยไม่เขียนทับไฟล์")
    p.set_defaults(func=cmd_fmt)

    p = sub.add_parser("new", help="สร้างไฟล์โปรแกรมเริ่มต้น")
    p.add_argument("name", metavar="ชื่อโปรแกรม")
    p.add_argument("-f", "--force", action="store_true", help="เขียนทับได้")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("demo", help="สาธิตภาษาแบบครบวงจร")
    p.add_argument("file", nargs="?", metavar="ไฟล์.th")
    p.set_defaults(func=cmd_demo)

    sub.add_parser("repl", help="โหมดโต้ตอบ").set_defaults(func=cmd_repl)
    sub.add_parser("doctor", help="ตรวจความพร้อมของเครื่อง").set_defaults(
        func=cmd_doctor)
    sub.add_parser("version", help="แสดงเวอร์ชัน").set_defaults(func=cmd_version)
    sub.add_parser("help", help="แสดงวิธีใช้").set_defaults(func=cmd_help)
    return ap


def main(argv=None):
    _utf8_console()
    argv = list(sys.argv[1:] if argv is None else argv)

    # ทางลัด:  thpro โปรแกรม.th  ให้ถือว่าเป็น  thpro run โปรแกรม.th
    if argv and argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
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
