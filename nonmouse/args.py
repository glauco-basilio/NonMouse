#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import platform
import sys
from typing import Optional, Tuple


def _get_screen_resolution() -> Tuple[int, int]:
    pf = platform.system()
    if pf == "Darwin":
        try:
            import AppKit  # type: ignore

            screen = AppKit.NSScreen.mainScreen()
            if screen is not None:
                frame = screen.frame()
                return int(frame.size.width), int(frame.size.height)
        except Exception:
            pass
    elif pf == "Windows":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
        except Exception:
            pass

    return (1920, 1080)


def cli_arg(argv: Optional[list] = None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--camera", type=int, default=0, help="Camera device index (default: 0)")
    parser.add_argument(
        "--place",
        choices=["normal", "above", "behind"],
        default="normal",
        help="Camera placement / orientation (default: normal)",
    )
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=3.0,
        help="Mouse sensitivity multiplier (default: 3.0)",
    )
    parser.add_argument("--screen-width", type=int, default=None)
    parser.add_argument("--screen-height", type=int, default=None)
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Force the Tk first-setup window (may crash if Tk is broken).",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Skip the Tk first-setup window and use CLI defaults/flags.",
    )

    ns, _unknown = parser.parse_known_args(argv)
    place_to_mode = {"normal": 0, "above": 1, "behind": 2}
    screen_w = ns.screen_width
    screen_h = ns.screen_height
    if screen_w is None or screen_h is None:
        auto_w, auto_h = _get_screen_resolution()
        screen_w = screen_w or auto_w
        screen_h = screen_h or auto_h
    return ns.camera, place_to_mode[ns.place], float(ns.sensitivity), (int(screen_w), int(screen_h)), ns


def tk_arg():
    import tkinter as tk

    root = tk.Tk()
    root.title("First Setup")
    root.geometry("370x320")
    screenRes = (root.winfo_screenwidth(),
                 root.winfo_screenheight())  # ディスプレイ解像度取得
    Val1 = tk.IntVar()
    Val2 = tk.IntVar()
    Val4 = tk.IntVar()
    Val4.set(30)                        # デフォルトマウス感度
    place = ['Normal', 'Above', 'Behind']
    # Camera #########################################################################
    Static1 = tk.Label(text='Camera').grid(row=1)
    for i in range(4):
        tk.Radiobutton(root,
                       value=i,
                       variable=Val1,
                       text=f'Device{i}'
                       ).grid(row=2, column=i*2)
    St1 = tk.Label(text='     ').grid(row=3)
    # Place #########################################################################
    Static1 = tk.Label(text='How to place').grid(row=4)
    for i in range(3):
        tk.Radiobutton(root,
                       value=i,
                       variable=Val2,
                       text=f'{place[i]}'
                       ).grid(row=5, column=i*2)
    St1 = tk.Label(text='     ').grid(row=6)
    # Sensitivity ###################################################################
    Static4 = tk.Label(text='Sensitivity').grid(row=7)
    s1 = tk.Scale(root, orient='h',
                  from_=1, to=100, variable=Val4
                  ).grid(row=8, column=2)
    St4 = tk.Label(text='     ').grid(row=9)
    # continue
    Button = tk.Button(text="continue", command=root.destroy).grid(
        row=10, column=2)
    # 待機
    root.mainloop()
    # 出力
    cap_device = Val1.get()             # 0,1,2
    mode = Val2.get()                     # 0:youself 1:
    kando = Val4.get()/10               # 1~10
    return cap_device, mode, kando, screenRes


def get_arg():
    cap_device, mode, kando, screenRes, ns = cli_arg()
    has_cli_overrides = (
        ns.no_gui
        or ns.gui
        or "--camera" in os.sys.argv
        or "--place" in os.sys.argv
        or "--sensitivity" in os.sys.argv
        or "--screen-width" in os.sys.argv
        or "--screen-height" in os.sys.argv
    )

    if ns.gui and os.getenv("NONMOUSE_NO_GUI") not in {"1", "true", "yes"}:
        return tk_arg()

    # Apple's Command Line Tools Python is frequently missing a usable Tk build; calling tk.Tk()
    # can abort the process. Prefer the CLI config unless the user explicitly forces --gui.
    using_clt_python = sys.executable.startswith("/Library/Developer/CommandLineTools/")

    if (
        os.getenv("NONMOUSE_NO_GUI") in {"1", "true", "yes"}
        or has_cli_overrides
        or using_clt_python
    ):
        return cap_device, mode, kando, screenRes

    return tk_arg()
