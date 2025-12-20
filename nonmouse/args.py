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
    return ns.camera, place_to_mode[ns.place], float(ns.sensitivity), (int(screen_w), int(screen_h)), ns


def tk_arg():
    import tkinter as tk

    root = tk.Tk()
    root.title("First Setup")
    root.geometry("370x320")
    screenRes = (root.winfo_screenwidth(),
                 root.winfo_screenheight())  # Display resolution
    Val1 = tk.IntVar()
    Val2 = tk.IntVar()
    Val4 = tk.IntVar()
    Val4.set(30)                        # Default mouse sensitivity
    place = ['Normal', 'Above', 'Behind']
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
    # Sensitivity ###################################################################
    tk.Label(text='Sensitivity').grid(row=next_row + 4, column=0, sticky="w")
    s1 = tk.Scale(root, orient='h',
                  from_=1, to=100, variable=Val4
                  ).grid(row=next_row + 5, column=2)
    tk.Label(text='     ').grid(row=next_row + 6)
    # continue
    Button = tk.Button(text="continue", command=root.destroy).grid(
        row=next_row + 7, column=2)
    # Wait
    root.mainloop()
    # Output
    cap_device = Val1.get()             # 0,1,2
    mode = Val2.get()                     # 0:youself 1:
    kando = Val4.get()/10               # 1~10
    return cap_device, mode, kando, screenRes


def get_arg():
    cap_device, mode, kando, screenRes, ns = cli_arg()
    has_cli_overrides = (
        ns.no_gui
        or ns.gui
        or ns.panel
        or ns.no_panel
        or "--camera" in os.sys.argv
        or "--place" in os.sys.argv
        or "--sensitivity" in os.sys.argv
        or "--screen-width" in os.sys.argv
        or "--screen-height" in os.sys.argv
    )

    if ns.gui and os.getenv("NONMOUSE_NO_GUI") not in {"1", "true", "yes"}:
        return (*tk_arg(), ns)

    # Apple's Command Line Tools Python is frequently missing a usable Tk build; calling tk.Tk()
    # can abort the process. Prefer the CLI config unless the user explicitly forces --gui.
    using_clt_python = sys.executable.startswith("/Library/Developer/CommandLineTools/")

    if (
        os.getenv("NONMOUSE_NO_GUI") in {"1", "true", "yes"}
        or has_cli_overrides
        or using_clt_python
    ):
        ns.panel = ns.panel or not ns.no_panel
        return cap_device, mode, kando, screenRes, ns

    ns.panel = ns.panel or not ns.no_panel
    return (*tk_arg(), ns)
