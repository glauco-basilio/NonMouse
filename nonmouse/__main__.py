#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# NonMouse
# Author: Yuki Takeyama
# Date: 2023/04/09

import cv2
import time
import keyboard
import platform
import numpy as np
import mediapipe as mp
from pynput.mouse import Controller

from nonmouse.args import get_arg, list_camera_devices, TK_PANEL_GEOMETRY
from nonmouse.utils import *

mouse = Controller()
if not hasattr(mp, "solutions"):
    raise RuntimeError(
        "This project requires the legacy MediaPipe Solutions API (mp.solutions.*), "
        "but your installed 'mediapipe' package does not provide it.\n\n"
        "Fix:\n"
        "- Ather platforms: install a MediaPipe build that includes `mp.solutions`.\n"
    )

mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands

pf = platform.system()
if pf == 'Windows':
    hotkey = 'Alt'
elif pf == 'Darwin':
    hotkey = 'Command'
elif pf == 'Linux':
    hotkey = 'XXX'              # Hotkey is disabled on Linux.

def _get_display_bounds():
    if pf != "Darwin":
        return []
    try:
        import Quartz  # type: ignore
    except Exception:
        Quartz = None
    if Quartz is not None:
        try:
            max_displays = 32
            err, display_ids, display_count = Quartz.CGGetActiveDisplayList(
                max_displays, None, None
            )
            if err != 0:
                raise RuntimeError("CGGetActiveDisplayList failed")
            bounds = []
            for display_id in display_ids[:display_count]:
                rect = Quartz.CGDisplayBounds(display_id)
                min_x = int(rect.origin.x)
                min_y = int(rect.origin.y)
                max_x = int(rect.origin.x + rect.size.width)
                max_y = int(rect.origin.y + rect.size.height)
                bounds.append((min_x, min_y, max_x, max_y))
            return bounds
        except Exception:
            pass
    try:
        import AppKit  # type: ignore
    except Exception:
        return []
    bounds = []
    for screen in AppKit.NSScreen.screens():
        frame = screen.frame()
        min_x = int(frame.origin.x)
        min_y = int(frame.origin.y)
        max_x = int(frame.origin.x + frame.size.width)
        max_y = int(frame.origin.y + frame.size.height)
        bounds.append((min_x, min_y, max_x, max_y))
    return bounds


def _find_display_bounds(x, y, bounds):
    for idx, (min_x, min_y, max_x, max_y) in enumerate(bounds):
        if min_x <= x < max_x and min_y <= y < max_y:
            return idx, (min_x, min_y, max_x, max_y)
    return None, None


def main():
    cap_device, mode, kando, dead_zone, debug_overlay, screenRes, screen_bounds, hand, ns = get_arg()
    preX, preY = 0, 0
    i = 0
    LiTx, LiTy = [], []   # Moving average buffers.
    cap_width = 1280
    cap_height = 720
    c_text = 0
    prev_can = 0
    # Webcam input and configuration.
    window_name = 'NonMouse'
    cv2.namedWindow(window_name)
    def open_capture(device_index):
        cap_local = cv2.VideoCapture(device_index)
        cap_local.set(cv2.CAP_PROP_FPS, 60)
        cfps_local = int(cap_local.get(cv2.CAP_PROP_FPS))
        if cfps_local < 30:
            cap_local.set(cv2.CAP_PROP_FRAME_WIDTH, cap_width)
            cap_local.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_height)
            cfps_local = int(cap_local.get(cv2.CAP_PROP_FPS))
        return cap_local, cfps_local

    cap, cfps = open_capture(cap_device)
    # Smoothing window (smaller = jittery cursor, larger = more latency).
    ran = max(int(cfps/10), 1)
    display_bounds = _get_display_bounds()
    display_crop = None
    prev_hand_count = 0
    panel_root = None
    panel_vars = None
    if ns.panel:
        import tkinter as tk

        panel_root = tk.Tk()
        panel_root.title("NonMouse Control Panel")
        panel_root.geometry(TK_PANEL_GEOMETRY)

        devices = list_camera_devices()
        if not devices:
            devices = [(0, "Device 0")]

        cam_var = tk.IntVar(value=cap_device)
        place_var = tk.IntVar(value=mode)
        hand_var = tk.IntVar(value=0 if hand == "right" else 1)
        sens_var = tk.IntVar(value=int(kando * 10))
        dead_zone_var = tk.IntVar(value=int(dead_zone))
        debug_overlay_var = tk.IntVar(value=1 if debug_overlay else 0)

        tk.Label(panel_root, text="Camera").grid(row=0, column=0, sticky="w")
        for row_idx, (idx, name) in enumerate(devices, start=1):
            tk.Radiobutton(
                panel_root,
                value=idx,
                variable=cam_var,
                text=f"{idx}: {name}",
            ).grid(row=row_idx, column=0, columnspan=4, sticky="w")

        row_offset = 1 + len(devices)
        tk.Label(panel_root, text="How to place").grid(row=row_offset, column=0, sticky="w")
        place_labels = ["Normal", "Above", "Behind"]
        for i, label in enumerate(place_labels):
            tk.Radiobutton(
                panel_root,
                value=i,
                variable=place_var,
                text=label,
            ).grid(row=row_offset + 1, column=i, sticky="w")

        tk.Label(panel_root, text="Mouse move hand").grid(row=row_offset + 2, column=0, sticky="w")
        tk.Radiobutton(
            panel_root,
            value=1,
            variable=hand_var,
            text="Left",
        ).grid(row=row_offset + 3, column=0, sticky="w")
        tk.Radiobutton(
            panel_root,
            value=0,
            variable=hand_var,
            text="Right",
        ).grid(row=row_offset + 3, column=1, sticky="w")

        tk.Label(panel_root, text="Sensitivity").grid(row=row_offset + 4, column=0, sticky="w")
        tk.Scale(
            panel_root,
            orient="h",
            from_=1,
            to=100,
            variable=sens_var,
        ).grid(row=row_offset + 5, column=0, columnspan=3, sticky="we")

        tk.Label(panel_root, text="Dead zone (px)").grid(row=row_offset + 6, column=0, sticky="w")
        tk.Scale(
            panel_root,
            orient="h",
            from_=0,
            to=100,
            variable=dead_zone_var,
        ).grid(row=row_offset + 7, column=0, columnspan=3, sticky="we")

        tk.Label(panel_root, text="Debug overlay").grid(row=row_offset + 8, column=0, sticky="w")
        tk.Checkbutton(
            panel_root,
            variable=debug_overlay_var,
            text="On",
        ).grid(row=row_offset + 8, column=1, sticky="w")

        panel_vars = {
            "cam_var": cam_var,
            "place_var": place_var,
            "hand_var": hand_var,
            "sens_var": sens_var,
            "dead_zone_var": dead_zone_var,
            "debug_overlay_var": debug_overlay_var,
        }
    hands = mp_hands.Hands(
        min_detection_confidence=0.8,   # Detection confidence.
        min_tracking_confidence=0.8,    # Tracking confidence.
        max_num_hands=2                 # Max number of hands.
    )
    # Main loop ########################################################################
    while cap.isOpened():
        if panel_root is not None:
            try:
                panel_root.update()
            except Exception:
                panel_root = None
                panel_vars = None

            if panel_vars is not None:
                desired_device = int(panel_vars["cam_var"].get())
                desired_mode = int(panel_vars["place_var"].get())
                desired_hand = "right" if int(panel_vars["hand_var"].get()) == 0 else "left"
                desired_kando = float(panel_vars["sens_var"].get()) / 10.0
                desired_dead_zone = float(panel_vars["dead_zone_var"].get())
                desired_debug_overlay = bool(panel_vars["debug_overlay_var"].get())

                if desired_device != cap_device:
                    previous_device = cap_device
                    cap.release()
                    cap, cfps = open_capture(desired_device)
                    if not cap.isOpened():
                        cap.release()
                        cap, cfps = open_capture(previous_device)
                        panel_vars["cam_var"].set(previous_device)
                    else:
                        cap_device = desired_device
                    ran = max(int(cfps/10), 1)
                    preX, preY = 0, 0
                    i = 0
                    LiTx, LiTy = [], []

                if desired_mode != mode:
                    mode = desired_mode
                if desired_hand != hand:
                    hand = desired_hand
                if desired_kando != kando:
                    kando = desired_kando
                if desired_dead_zone != dead_zone:
                    dead_zone = desired_dead_zone
                if desired_debug_overlay != debug_overlay:
                    debug_overlay = desired_debug_overlay
        p_s = time.perf_counter()
        success, image = cap.read()
        if not success:
            continue
        debug_target_pos = None
        # if mode == 1:                   # Mouse
        #     image = cv2.flip(image, 0)  # Flip vertically.
        # elif mode == 2:                 # Touch
        #     image = cv2.flip(image, 1)  # Flip horizontally.

        # Flip horizontally and convert BGR to RGB.
        image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
        image.flags.writeable = False   # Mark read-only for pass-by-reference.
        results = hands.process(image)  # MediaPipe processing.
        image.flags.writeable = True    # Draw annotations on the image.
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        frame_height, frame_width, _ = image.shape

        hand_count = len(results.multi_hand_landmarks or [])
        if hand_count != prev_hand_count:
            if hand_count > 0:
                min_x, min_y = 1.0, 1.0
                max_x, max_y = 0.0, 0.0
                for hand_landmarks in results.multi_hand_landmarks:
                    for lm in hand_landmarks.landmark:
                        min_x = min(min_x, lm.x)
                        min_y = min(min_y, lm.y)
                        max_x = max(max_x, lm.x)
                        max_y = max(max_y, lm.y)
                min_x = max(min_x, 0.0)
                min_y = max(min_y, 0.0)
                max_x = min(max_x, 1.0)
                max_y = min(max_y, 1.0)
                if max_x > min_x and max_y > min_y:
                    pad_ratio = 0.2
                    box_w = (max_x - min_x) * frame_width
                    box_h = (max_y - min_y) * frame_height
                    pad_x = int(box_w * pad_ratio)
                    pad_y = int(box_h * pad_ratio)
                    min_x_px = max(int(min_x * frame_width) - pad_x, 0)
                    min_y_px = max(int(min_y * frame_height) - pad_y, 0)
                    max_x_px = min(int(max_x * frame_width) + pad_x, frame_width)
                    max_y_px = min(int(max_y * frame_height) + pad_y, frame_height)
                    if max_x_px - min_x_px > 0 and max_y_px - min_y_px > 0:
                        display_crop = (min_x_px, min_y_px, max_x_px, max_y_px)
                    else:
                        display_crop = None
                else:
                    display_crop = None
            else:
                display_crop = None
            prev_hand_count = hand_count

        if results.multi_hand_landmarks:
            selected_index = None
            if results.multi_handedness:
                for idx, handedness in enumerate(results.multi_handedness):
                    label = handedness.classification[0].label.lower()
                    print(label,hand)
                    if label == hand:
                        selected_index = idx
                        break
                    # if mode == 1:
                    #     if label == "left":
                    #         label = "right"
                    #     elif label == "right":
                    #         label = "left"
                    #     break
            mouse_move_landmarks = None
            if selected_index is not None:
                mouse_move_landmarks = results.multi_hand_landmarks[selected_index]
            # Draw all detected hands for feedback.
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    image, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            if pf == 'Linux':           # Always allow motion on Linux.
                can = 1
                c_text = 0
            else:                       # Use the global hotkey on non-Linux.
                if keyboard.is_pressed(hotkey):  # Avoid this branch on Linux.
                    can = 1
                    c_text = 0          # Hotkey pressed.
                else:                   # No input, do not move.
                    can = 0
                    c_text = 1          # Prompt to press hotkey.
                    # i = 0
            if can == 0 and mouse_move_landmarks is not None:
                # Keep a live baseline while inactive to avoid jumps on activation.
                baseline_x = calculate_moving_average(mouse_move_landmarks.landmark[8].x, ran, LiTx)
                baseline_y = calculate_moving_average(mouse_move_landmarks.landmark[8].y, ran, LiTy)
                preX, preY = baseline_x, baseline_y
                i = 0
            # When the global hotkey is pressed ###############################################
            if can == 1 and mouse_move_landmarks is not None:
                # print(hand_landmarks.landmark[0])
                # Seed preX/preY when we first activate the hotkey.
                if prev_can == 0 or i == 0:
                    i += 1

                posx, posy = mouse.position

                # Use index fingertip to drive cursor movement.
                # Convert camera coordinates into mouse deltas.
                nowX = calculate_moving_average(
                    mouse_move_landmarks.landmark[8].x, ran, LiTx)
                nowY = calculate_moving_average(
                    mouse_move_landmarks.landmark[8].y, ran, LiTy)
                if prev_can == 0:
                    preX, preY = nowX, nowY

                dx = kando * (nowX - preX) * frame_width
                dy = kando * (nowY - preY) * frame_height

                if dead_zone > 0:
                    if abs(dx) < dead_zone:
                        dx = 0.0
                    if abs(dy) < dead_zone:
                        dy = 0.0

                if pf == 'Windows' or pf == 'Linux':     # Add a small bias on Windows/Linux.
                    if dx != 0:
                        dx = dx + 0.5
                    if dy != 0:
                        dy = dy + 0.5
                preX = nowX
                preY = nowY
                print(dx, dy)
                target_x = posx + dx
                target_y = posy + dy
                if display_bounds:
                    _, target_bounds = _find_display_bounds(target_x, target_y, display_bounds)
                    if target_bounds is None:
                        _current_idx, current_bounds = _find_display_bounds(posx, posy, display_bounds)
                        if current_bounds is not None:
                            min_x, min_y, max_x, max_y = current_bounds
                            if target_x < min_x:
                                dx = min_x - posx
                            elif target_x >= max_x:
                                dx = max_x - posx
                            if target_y < min_y:
                                dy = min_y - posy
                            elif target_y >= max_y:
                                dy = max_y - posy
                        else:
                            min_x, min_y, max_x, max_y = screen_bounds
                            if target_x < min_x:  # Prevent cursor from going off-screen permanently.
                                dx = min_x - posx
                            elif target_x > max_x:
                                dx = max_x - posx
                            if target_y < min_y:
                                dy = min_y - posy
                            elif target_y > max_y:
                                dy = max_y - posy
                else:
                    min_x, min_y, max_x, max_y = screen_bounds
                    if target_x < min_x:  # Prevent cursor from going off-screen permanently.
                        dx = min_x - posx
                    elif target_x > max_x:
                        dx = max_x - posx
                    if target_y < min_y:
                        dy = min_y - posy
                    elif target_y > max_y:
                        dy = max_y - posy

                if mode == 1:
                    dy = -dy
                debug_target_pos = (posx + dx, posy + dy)
                # Cursor movement only while the hotkey is pressed.
                if prev_can == 1:
                    mouse.move(dx, dy)
                draw_circle(image, mouse_move_landmarks.landmark[8].x * frame_width,
                            mouse_move_landmarks.landmark[8].y * frame_height, 8, (250, 0, 0))
            prev_can = can

        # Display ########################################################################
        display_image = image
        if display_crop is not None:
            min_x_px, min_y_px, max_x_px, max_y_px = display_crop
            display_image = image[min_y_px:max_y_px, min_x_px:max_x_px]



        display_scale = 0.4
        target_width = max(int(frame_width * display_scale), 1)
        target_height = max(int(frame_height * display_scale), 1)
        dst = cv2.resize(display_image, (target_width, target_height))

        if c_text == 1:
            cv2.putText(dst, f"Push {hotkey}", (20, 250),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
        cv2.putText(dst, "cameraFPS:"+str(cfps), (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
        p_e = time.perf_counter()
        fps = str(int(1/(float(p_e)-float(p_s))))
        cv2.putText(dst, "FPS:"+fps, (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
        if debug_overlay:
            debug_mouse_pos = mouse.position
            debug_text_y = 120
            cv2.putText(
                dst,
                f"Mouse: {debug_mouse_pos[0]:.0f},{debug_mouse_pos[1]:.0f}",
                (20, debug_text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )
            if debug_target_pos is None:
                target_text = "Target: -"
            else:
                target_text = f"Target: {debug_target_pos[0]:.0f},{debug_target_pos[1]:.0f}"
            cv2.putText(
                dst,
                target_text,
                (20, debug_text_y + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )
            if display_bounds:
                display_idx, active_bounds = _find_display_bounds(
                    debug_mouse_pos[0], debug_mouse_pos[1], display_bounds
                )
                if active_bounds is not None:
                    min_x, min_y, max_x, max_y = active_bounds
                    display_text = (
                        f"Display {display_idx + 1}/{len(display_bounds)}: "
                        f"{min_x},{min_y}-{max_x},{max_y}"
                    )
                else:
                    display_text = f"Display: gap ({len(display_bounds)} total)"
            else:
                display_text = "Display: unknown"
            cv2.putText(
                dst,
                display_text,
                (20, debug_text_y + 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )
        
        cv2.imshow(window_name, dst)
        if (cv2.waitKey(1) & 0xFF == 27) or (cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) == 0):
            break
    cap.release()


if __name__ == "__main__":
    main()
