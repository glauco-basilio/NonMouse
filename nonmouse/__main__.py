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
from pynput.mouse import Button, Controller

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
    cap_device, mode, kando, screenRes, ns = get_arg()
    dis = 0.7                           # Threshold distance for "touch" gestures.
    preX, preY = 0, 0
    nowCli, preCli = 0, 0               # Current and previous left-click state.
    norCli, prrCli = 0, 0               # Current and previous right-click state.
    douCli = 0                          # Double-click state.
    i, k, h = 0, 0, 0
    LiTx, LiTy, list0x, list0y, list1x, list1y, list4x, list4y, list6x, list6y, list8x, list8y, list12x, list12y = [
    ], [], [], [], [], [], [], [], [], [], [], [], [], []   # Moving average buffers.
    moving_average = [[0] * 3 for _ in range(3)]
    nowUgo = 1
    cap_width = 1280
    cap_height = 720
    start, c_start = float('inf'), float('inf')
    c_text = 0
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

        tk.Label(panel_root, text="Sensitivity").grid(row=row_offset + 2, column=0, sticky="w")
        tk.Scale(
            panel_root,
            orient="h",
            from_=1,
            to=100,
            variable=sens_var,
        ).grid(row=row_offset + 3, column=0, columnspan=3, sticky="we")

        panel_vars = {
            "cam_var": cam_var,
            "place_var": place_var,
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
                    nowCli, preCli = 0, 0
                    norCli, prrCli = 0, 0
                    douCli = 0
                    i, k, h = 0, 0, 0
                    LiTx, LiTy, list0x, list0y, list1x, list1y, list4x, list4y, list6x, list6y, list8x, list8y, list12x, list12y = [
                    ], [], [], [], [], [], [], [], [], [], [], [], [], []

                if desired_mode != mode:
                    mode = desired_mode
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
            # Draw hand landmarks.
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
            # When the global hotkey is pressed ###############################################
            if can == 1:
                # print(hand_landmarks.landmark[0])
                # Seed preX/preY once from the current finger position.
                if i == 0:
                    preX = hand_landmarks.landmark[8].x
                    preY = hand_landmarks.landmark[8].y
                    i += 1

                # Moving averages for landmarks used below.
                landmark0 = [calculate_moving_average(hand_landmarks.landmark[0].x, ran, list0x), calculate_moving_average(
                    hand_landmarks.landmark[0].y, ran, list0y)]
                landmark1 = [calculate_moving_average(hand_landmarks.landmark[1].x, ran, list1x), calculate_moving_average(
                    hand_landmarks.landmark[1].y, ran, list1y)]
                landmark4 = [calculate_moving_average(hand_landmarks.landmark[4].x, ran, list4x), calculate_moving_average(
                    hand_landmarks.landmark[4].y, ran, list4y)]
                landmark6 = [calculate_moving_average(hand_landmarks.landmark[6].x, ran, list6x), calculate_moving_average(
                    hand_landmarks.landmark[6].y, ran, list6y)]
                landmark8 = [calculate_moving_average(hand_landmarks.landmark[8].x, ran, list8x), calculate_moving_average(
                    hand_landmarks.landmark[8].y, ran, list8y)]
                landmark12 = [calculate_moving_average(hand_landmarks.landmark[12].x, ran, list12x), calculate_moving_average(
                    hand_landmarks.landmark[12].y, ran, list12y)]

                # Reference distance; all other distances are normalized by this.
                absKij = calculate_distance(landmark0, landmark1)
                # Distance between index fingertip and middle fingertip.
                absUgo = calculate_distance(landmark8, landmark12) / absKij
                # Distance between index PIP joint and thumb tip.
                absCli = calculate_distance(landmark4, landmark6) / absKij

                posx, posy = mouse.position

                # Use index fingertip to drive cursor movement.
                # Convert camera coordinates into mouse deltas.
                nowX = calculate_moving_average(
                    hand_landmarks.landmark[8].x, ran, LiTx)
                nowY = calculate_moving_average(
                    hand_landmarks.landmark[8].y, ran, LiTy)

                dx = kando * (nowX - preX) * image_width
                dy = kando * (nowY - preY) * image_height

                if pf == 'Windows' or pf == 'Linux':     # Add a small bias on Windows/Linux.
                    dx = dx+0.5
                    dy = dy+0.5
                preX = nowX
                preY = nowY
                # print(dx, dy)
                if posx+dx < 0:  # Prevent cursor from going off-screen permanently.
                    dx = -posx
                elif posx+dx > screenRes[0]:
                    dx = screenRes[0]-posx
                if posy+dy < 0:
                    dy = -posy
                elif posy+dy > screenRes[1]:
                    dy = screenRes[1]-posy

                # Flags ########################################################################
                # Click state.
                if absCli < dis:
                    nowCli = 1          # nowCli: left click state (1: click, 0: no click)
                    draw_circle(image, hand_landmarks.landmark[8].x * image_width,
                                hand_landmarks.landmark[8].y * image_height, 20, (0, 250, 250))
                elif absCli >= dis:
                    nowCli = 0
                if np.abs(dx) > 7 and np.abs(dy) > 7:
                    k = 0                           # k=0 when moving.
                # Right click: hold click for >1.5s without moving.
                # Only when the cursor is not moving.
                if nowCli == 1 and np.abs(dx) < 7 and np.abs(dy) < 7:
                    if k == 0:          # k: clicking and not moving.
                        start = time.perf_counter()
                        k += 1
                    end = time.perf_counter()
                    if end-start > 1.5:
                        norCli = 1
                        draw_circle(image, hand_landmarks.landmark[8].x * image_width,
                                    hand_landmarks.landmark[8].y * image_height, 20, (0, 0, 250))
                else:
                    norCli = 0

                # Actions ######################################################################
                # cursor
                if absUgo >= dis and nowUgo == 1:
                    mouse.move(dx, dy)
                    draw_circle(image, hand_landmarks.landmark[8].x * image_width,
                                hand_landmarks.landmark[8].y * image_height, 8, (250, 0, 0))
                # left click
                if nowCli == 1 and nowCli != preCli:
                    if h == 1:                                  # After right click: skip left click.
                        h = 0
                    elif h == 0:                                # Normal state.
                        mouse.press(Button.left)
                    # print('Click')
                # left click release
                if nowCli == 0 and nowCli != preCli:
                    mouse.release(Button.left)
                    k = 0
                    # print('Release')
                    if douCli == 0:                             # Start timing after first click.
                        c_start = time.perf_counter()
                        douCli += 1
                    c_end = time.perf_counter()
                    if 10*(c_end-c_start) > 5 and douCli == 1:  # Double click within 0.5s.
                        mouse.click(Button.left, 2)             # double click
                        douCli = 0
                # right click
                if norCli == 1 and norCli != prrCli:
                    # mouse.release(Button.left)                # Required in some cases.
                    mouse.press(Button.right)
                    mouse.release(Button.right)
                    h = 1                                       # Set "just right-clicked" state.
                    # print("right click")
                # scroll
                if hand_landmarks.landmark[8].y-hand_landmarks.landmark[5].y > -0.06:
                    mouse.scroll(0, -dy/50)                     # Reduce scroll sensitivity.
                    draw_circle(image, hand_landmarks.landmark[8].x * image_width,
                                hand_landmarks.landmark[8].y * image_height, 20, (0, 0, 0))
                    nowUgo = 0
                else:
                    nowUgo = 1

                preCli = nowCli
                prrCli = norCli

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
