#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import platform
import sys
from typing import Optional, Tuple

TK_PANEL_GEOMETRY = "370x460"


def _get_screen_resolution() -> Tuple[int, int]:
    pf = platform.system()
    if pf == "Darwin":
        try:
            import AppKit  # type: ignore

            screens = AppKit.NSScreen.screens()
            if screens:
                min_x = min(screen.frame().origin.x for screen in screens)
                min_y = min(screen.frame().origin.y for screen in screens)
                max_x = max(screen.frame().origin.x + screen.frame().size.width for screen in screens)
                max_y = max(screen.frame().origin.y + screen.frame().size.height for screen in screens)
                return int(max_x - min_x), int(max_y - min_y)
        except Exception:
            pass
    elif pf == "Windows":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            return int(user32.GetSystemMetrics(78)), int(user32.GetSystemMetrics(79))
        except Exception:
            pass

    return (1920, 1080)


def _get_screen_bounds() -> Tuple[int, int, int, int]:
    pf = platform.system()
    if pf == "Darwin":
        try:
            import AppKit  # type: ignore

            screens = AppKit.NSScreen.screens()
            if screens:
                min_x = min(screen.frame().origin.x for screen in screens)
                min_y = min(screen.frame().origin.y for screen in screens)
                max_x = max(screen.frame().origin.x + screen.frame().size.width for screen in screens)
                max_y = max(screen.frame().origin.y + screen.frame().size.height for screen in screens)
                return int(min_x), int(min_y), int(max_x), int(max_y)
        except Exception:
            pass
    elif pf == "Windows":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            min_x = int(user32.GetSystemMetrics(76))
            min_y = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
            return min_x, min_y, min_x + width, min_y + height
        except Exception:
            pass

    width, height = _get_screen_resolution()
    return 0, 0, width, height


def _list_camera_devices(max_devices: int = 6) -> list:
    pf = platform.system()
    if pf == "Darwin":
        try:
            from AVFoundation import AVCaptureDevice, AVMediaTypeVideo  # type: ignore

            devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeVideo)
            return [(idx, dev.localizedName()) for idx, dev in enumerate(devices)]
        except Exception:
            pass

    try:
        import cv2  # type: ignore

        devices = []
        for idx in range(max_devices):
            cap = cv2.VideoCapture(idx)
            if cap is not None and cap.isOpened():
                devices.append((idx, f"Device {idx}"))
                cap.release()
        return devices
    except Exception:
        return [(idx, f"Device {idx}") for idx in range(4)]


def list_camera_devices(max_devices: int = 6) -> list:
    return _list_camera_devices(max_devices)


def cli_arg(argv: Optional[list] = None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--camera", type=int, default=0, help="Camera device index (default: 0)")
    parser.add_argument(
        "--place",
        choices=["normal", "above", "behind"],
        default="above",
        help="Camera placement / orientation (default: above)",
    )
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=10.0,
        help="Mouse sensitivity multiplier (default: 10.0)",
    )
    parser.add_argument(
        "--dead-zone",
        type=float,
        default=0.0,
        help="Cursor dead zone in pixels (default: 0)",
    )
    parser.add_argument(
        "--hand",
        choices=["right", "left"],
        default="right",
        help="Hand to track for mouse movement (default: right)",
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
    parser.add_argument(
        "--panel",
        action="store_true",
        help="Show a Tk side panel for live camera/settings changes (default).",
    )
    parser.add_argument(
        "--no-panel",
        action="store_true",
        help="Disable the Tk side panel.",
    )

    ns, _unknown = parser.parse_known_args(argv)
    place_to_mode = {"normal": 0, "above": 1, "behind": 2}
    screen_w = ns.screen_width
    screen_h = ns.screen_height
    if screen_w is None or screen_h is None:
        auto_w, auto_h = _get_screen_resolution()
        screen_w = screen_w or auto_w
        screen_h = screen_h or auto_h
    bounds = _get_screen_bounds()
    return (
        ns.camera,
        place_to_mode[ns.place],
        float(ns.sensitivity),
        float(ns.dead_zone),
        (int(screen_w), int(screen_h)),
        bounds,
        ns.hand,
        ns,
    )


def tk_arg():
    import tkinter as tk

    root = tk.Tk()
    root.title("First Setup")
    root.geometry(TK_PANEL_GEOMETRY)
    screenRes = (root.winfo_screenwidth(),
                 root.winfo_screenheight())  # Display resolution
    Val1 = tk.IntVar()
    Val2 = tk.IntVar()
    Val3 = tk.IntVar()
    Val4 = tk.IntVar()
    Val5 = tk.IntVar()
    Val2.set(1)                         # Default placement: Above
    Val3.set(0)                         # Default hand: Right
    Val4.set(100)                       # Default mouse sensitivity
    Val5.set(0)                         # Default dead zone (pixels)
    place = ['Normal', 'Above', 'Behind']
    hands = ['Right', 'Left']
    # Camera #########################################################################
    tk.Label(text='Camera').grid(row=1, column=0, sticky="w")
    devices = _list_camera_devices()
    if not devices:
        devices = [(0, "Device 0")]
    for offset, (idx, name) in enumerate(devices):
        tk.Radiobutton(
            root,
            value=idx,
            variable=Val1,
            text=f"{idx}: {name}",
        ).grid(row=2 + offset, column=0, columnspan=4, sticky="w")
    next_row = 2 + len(devices)
    tk.Label(text='     ').grid(row=next_row, column=0)
    # Place #########################################################################
    tk.Label(text='How to place').grid(row=next_row + 1, column=0, sticky="w")
    for i in range(3):
        tk.Radiobutton(root,
                       value=i,
                       variable=Val2,
                       text=f'{place[i]}'
                       ).grid(row=next_row + 2, column=i*2)
    tk.Label(text='     ').grid(row=next_row + 3)
    # Mouse move hand ##############################################################
    tk.Label(text='Mouse move hand').grid(row=next_row + 4, column=0, sticky="w")
    for i in range(2):
        tk.Radiobutton(root,
                       value=i,
                       variable=Val3,
                       text=f'{hands[i]}'
                       ).grid(row=next_row + 5, column=i*2)
    tk.Label(text='     ').grid(row=next_row + 6)
    # Sensitivity ###################################################################
    tk.Label(text='Sensitivity').grid(row=next_row + 7, column=0, sticky="w")
    s1 = tk.Scale(root, orient='h',
                  from_=1, to=100, variable=Val4
                  ).grid(row=next_row + 8, column=2)
    tk.Label(text='     ').grid(row=next_row + 9)
    # Dead zone ######################################################################
    tk.Label(text='Dead zone (px)').grid(row=next_row + 10, column=0, sticky="w")
    tk.Scale(root, orient='h',
             from_=0, to=100, variable=Val5
             ).grid(row=next_row + 11, column=2)
    tk.Label(text='     ').grid(row=next_row + 12)
    # continue
    Button = tk.Button(text="continue", command=root.destroy).grid(
        row=next_row + 13, column=2)
    # Wait
    root.mainloop()
    # Output
    cap_device = Val1.get()             # 0,1,2
    mode = Val2.get()                     # 0:youself 1:
    kando = Val4.get()/10               # 1~10
    hand = "right" if Val3.get() == 0 else "left"
    dead_zone = float(Val5.get())
    bounds = _get_screen_bounds()
    return cap_device, mode, kando, dead_zone, screenRes, bounds, hand


def get_arg():
    cap_device, mode, kando, dead_zone, screenRes, bounds, hand, ns = cli_arg()
    has_cli_overrides = (
        ns.no_gui
        or ns.gui
        or ns.panel
        or ns.no_panel
        or "--camera" in os.sys.argv
        or "--place" in os.sys.argv
        or "--sensitivity" in os.sys.argv
        or "--dead-zone" in os.sys.argv
        or "--hand" in os.sys.argv
        or "--screen-width" in os.sys.argv
        or "--screen-height" in os.sys.argv
    )

    if ns.gui and os.getenv("NONMOUSE_NO_GUI") not in {"1", "true", "yes"}:
        cap_device, mode, kando, dead_zone, screenRes, bounds, hand = tk_arg()
        return cap_device, mode, kando, dead_zone, screenRes, bounds, hand, ns

    # Apple's Command Line Tools Python is frequently missing a usable Tk build; calling tk.Tk()
    # can abort the process. Prefer the CLI config unless the user explicitly forces --gui.
    using_clt_python = sys.executable.startswith("/Library/Developer/CommandLineTools/")

    if (
        os.getenv("NONMOUSE_NO_GUI") in {"1", "true", "yes"}
        or has_cli_overrides
        or using_clt_python
    ):
        ns.panel = ns.panel or not ns.no_panel
        return cap_device, mode, kando, dead_zone, screenRes, bounds, hand, ns

    ns.panel = ns.panel or not ns.no_panel
    cap_device, mode, kando, dead_zone, screenRes, bounds, hand = tk_arg()
    return cap_device, mode, kando, dead_zone, screenRes, bounds, hand, ns
