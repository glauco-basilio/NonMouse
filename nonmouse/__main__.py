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

from nonmouse.args import get_arg, list_camera_devices
from nonmouse.utils import *

mouse = Controller()
if not hasattr(mp, "solutions"):
    raise RuntimeError(
        "This project requires the legacy MediaPipe Solutions API (mp.solutions.*), "
        "but your installed 'mediapipe' package does not provide it.\n\n"
        "Fix:\n"
        "- Apple Silicon (macOS/arm64): `pip install mediapipe-silicon numpy<2 opencv-contrib-python<4.12`\n"
        "- Other platforms: install a MediaPipe build that includes `mp.solutions`.\n"
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


def main():
    cap_device, mode, kando, screenRes, screen_bounds, hand, ns = get_arg()
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
    panel_root = None
    panel_vars = None
    if ns.panel:
        import tkinter as tk

        panel_root = tk.Tk()
        panel_root.title("NonMouse Control Panel")
        panel_root.geometry("360x420")

        devices = list_camera_devices()
        if not devices:
            devices = [(0, "Device 0")]

        cam_var = tk.IntVar(value=cap_device)
        place_var = tk.IntVar(value=mode)
        hand_var = tk.IntVar(value=0 if hand == "right" else 1)
        sens_var = tk.IntVar(value=int(kando * 10))

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
            value=0,
            variable=hand_var,
            text="Right",
        ).grid(row=row_offset + 3, column=0, sticky="w")
        tk.Radiobutton(
            panel_root,
            value=1,
            variable=hand_var,
            text="Left",
        ).grid(row=row_offset + 3, column=1, sticky="w")

        tk.Label(panel_root, text="Sensitivity").grid(row=row_offset + 4, column=0, sticky="w")
        tk.Scale(
            panel_root,
            orient="h",
            from_=1,
            to=100,
            variable=sens_var,
        ).grid(row=row_offset + 5, column=0, columnspan=3, sticky="we")

        panel_vars = {
            "cam_var": cam_var,
            "place_var": place_var,
            "hand_var": hand_var,
            "sens_var": sens_var,
        }
    hands = mp_hands.Hands(
        min_detection_confidence=0.8,   # Detection confidence.
        min_tracking_confidence=0.8,    # Tracking confidence.
        max_num_hands=1                 # Max number of hands.
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
        p_s = time.perf_counter()
        success, image = cap.read()
        if not success:
            continue
        if mode == 1:                   # Mouse
            image = cv2.flip(image, 0)  # Flip vertically.
        elif mode == 2:                 # Touch
            image = cv2.flip(image, 1)  # Flip horizontally.

        # Flip horizontally and convert BGR to RGB.
        image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
        image.flags.writeable = False   # Mark read-only for pass-by-reference.
        results = hands.process(image)  # MediaPipe processing.
        image.flags.writeable = True    # Draw annotations on the image.
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        image_height, image_width, _ = image.shape

        if results.multi_hand_landmarks:
            selected_index = None
            if results.multi_handedness:
                for idx, handedness in enumerate(results.multi_handedness):
                    label = handedness.classification[0].label.lower()
                    if mode == 1:
                        if label == "left":
                            label = "right"
                        elif label == "right":
                            label = "left"
                    if label == hand:
                        selected_index = idx
                        break
            selected_landmarks = None
            if selected_index is not None:
                selected_landmarks = results.multi_hand_landmarks[selected_index]
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
            if can == 0 and selected_landmarks is not None:
                # Keep a live baseline while inactive to avoid jumps on activation.
                baseline_x = calculate_moving_average(selected_landmarks.landmark[8].x, ran, LiTx)
                baseline_y = calculate_moving_average(selected_landmarks.landmark[8].y, ran, LiTy)
                preX, preY = baseline_x, baseline_y
                i = 0
            # When the global hotkey is pressed ###############################################
            if can == 1:
                if selected_landmarks is None:
                    continue
                # print(hand_landmarks.landmark[0])
                # Seed preX/preY when we first activate the hotkey.
                if prev_can == 0 or i == 0:
                    i += 1

                posx, posy = mouse.position

                # Use index fingertip to drive cursor movement.
                # Convert camera coordinates into mouse deltas.
                nowX = calculate_moving_average(
                    hand_landmarks.landmark[8].x, ran, LiTx)
                nowY = calculate_moving_average(
                    hand_landmarks.landmark[8].y, ran, LiTy)
                if prev_can == 0:
                    preX, preY = nowX, nowY

                dx = kando * (nowX - preX) * image_width
                dy = kando * (nowY - preY) * image_height

                if pf == 'Windows' or pf == 'Linux':     # Add a small bias on Windows/Linux.
                    dx = dx+0.5
                    dy = dy+0.5
                preX = nowX
                preY = nowY
                # print(dx, dy)
                min_x, min_y, max_x, max_y = screen_bounds
                if posx + dx < min_x:  # Prevent cursor from going off-screen permanently.
                    dx = min_x - posx
                elif posx + dx > max_x:
                    dx = max_x - posx
                if posy + dy < min_y:
                    dy = min_y - posy
                elif posy + dy > max_y:
                    dy = max_y - posy

                # Cursor movement only while the hotkey is pressed.
                if prev_can == 1:
                    mouse.move(dx, dy)
                draw_circle(image, selected_landmarks.landmark[8].x * image_width,
                            selected_landmarks.landmark[8].y * image_height, 8, (250, 0, 0))
            prev_can = can

        # Display ########################################################################
        if c_text == 1:
            cv2.putText(image, f"Push {hotkey}", (20, 450),
                        cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
        cv2.putText(image, "cameraFPS:"+str(cfps), (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
        p_e = time.perf_counter()
        fps = str(int(1/(float(p_e)-float(p_s))))
        cv2.putText(image, "FPS:"+fps, (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
        dst = cv2.resize(image, dsize=None, fx=0.4,
                         fy=0.4)         # Display at 0.4x scale.
        cv2.imshow(window_name, dst)
        if (cv2.waitKey(1) & 0xFF == 27) or (cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) == 0):
            break
    cap.release()


if __name__ == "__main__":
    main()
