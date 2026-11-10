#!/usr/bin/env python3
"""Record a continuous, unedited raw run of `python -m demo run-all`.

Windows-only: uses a borderless Tk terminal window and ffmpeg gdigrab.
The command itself is real; the pauses only make the log readable on video.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, H = 1440, 900
X, Y = 240, 90

BG = "#1F1B16"
BAR = "#2A241D"
TEXT = "#F4EEE5"
DIM = "#B6AA9A"
LINE = "#3A332A"
RED = "#D77A6B"
GREEN = "#8FB59B"
AMBER = "#C9A46A"

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FONT = "JetBrains Mono"


def load_font() -> None:
    path = ROOT / "assets" / "fonts" / "JetBrainsMono.ttf"
    if path.exists() and sys.platform == "win32":
        ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)


def strip_ansi(value: str) -> str:
    return ANSI.sub("", value).replace("\r", "")


def line_color(line: str) -> str:
    if "WARN" in line:
        return RED
    if "Report:" in line or "Hotovo:" in line:
        return GREEN
    if line.startswith("$"):
        return TEXT
    if line.startswith("─") or line.startswith("┌") or line.startswith("│") or line.startswith("├") or line.startswith("└"):
        return DIM
    return TEXT


class Terminal:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.lines: list[tuple[str, str]] = []
        self.events: queue.Queue[tuple] = queue.Queue()
        self.done = False

        root.overrideredirect(True)
        root.title("demo raw")
        root.geometry(f"{W}x{H}+{X}+{Y}")
        root.configure(bg=BG)
        root.attributes("-topmost", True)
        root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=W, height=H, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.log_font = tkfont.Font(family=FONT, size=18)
        self.canvas.create_rectangle(0, 0, W, 5, fill=RED, outline="")
        self.canvas.create_rectangle(0, 5, W, 64, fill=BAR, outline="")
        for index, color in enumerate((RED, GREEN, TEXT)):
            self.canvas.create_oval(28 + index * 22, 28, 40 + index * 22, 40, fill=color, outline="")
        self.canvas.create_text(108, 36, anchor="w", text="demo — python -m demo run-all", fill=DIM, font=(FONT, 14))
        self.canvas.create_rectangle(W - 126, 22, W - 30, 52, outline=RED, width=1)
        self.canvas.create_text(W - 78, 37, text="DEMO", fill=RED, font=(FONT, 11, "bold"))
        self.canvas.create_text(72, 88, anchor="w", text="RAW / BEZ STRIHU / BEZ ZVUKU", fill=RED, font=(FONT, 11, "bold"))
        self.canvas.create_text(72, 116, anchor="w", text="Reálny beh. Žiadny strih, žiadna hudba.", fill=TEXT, font=(FONT, 22, "bold"))
        self.canvas.create_line(72, 148, W - 72, 148, fill=LINE)
        self.canvas.create_rectangle(72, 842, W - 72, 844, fill=LINE, outline="")
        self.canvas.create_text(72, 862, anchor="w", text="Syntetické dáta · všetky firmy a doklady sú vymyslené · bez reálneho IČO/DIČ", fill=DIM, font=(FONT, 12))
        self.canvas.create_text(W - 72, 862, anchor="e", text="perepolkin.sk / DEMO", fill=RED, font=(FONT, 11, "bold"))

        self.log_y = 174
        self.log_step = 25
        self.max_lines = 25
        self.render()
        root.after(40, self.poll)

    def add(self, value: str = "", color: str = TEXT) -> None:
        self.lines.append((value, color))
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines :]
        self.render()

    def append_char(self, char: str) -> None:
        if not self.lines:
            self.lines.append(("", TEXT))
        value, color = self.lines[-1]
        self.lines[-1] = (value + char, color)
        self.render()

    def _chunks(self, value: str) -> list[str]:
        if not value:
            return [""]
        chunks: list[str] = []
        current = ""
        for char in value:
            if self.log_font.measure(current + char) <= W - 144:
                current += char
            else:
                chunks.append(current)
                current = char
        chunks.append(current)
        return chunks

    def render(self) -> None:
        self.canvas.delete("log")
        y = self.log_y
        for value, color in self.lines:
            for chunk in self._chunks(value):
                self.canvas.create_text(72, y, anchor="nw", text=chunk, fill=color, font=(FONT, 18), tags="log")
                y += self.log_step

    def poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                try:
                    if event[0] == "line":
                        self.add(event[1], event[2])
                    elif event[0] == "char":
                        self.append_char(event[1])
                    elif event[0] == "done":
                        self.done = True
                finally:
                    self.events.task_done()
        except queue.Empty:
            pass
        if not self.done:
            self.root.after(40, self.poll)

    def type_command(self, command: str) -> None:
        self.events.put(("line", "$ ", GREEN))
        for char in command:
            self.events.put(("char", char))
            time.sleep(0.016)
        self.events.put(("line", "", TEXT))
        self.events.join()

    def run_stream(self, command: list[str], show: str | None = None, delay: float = 0.22) -> int:
        if show:
            self.type_command(show)
            self.events.join()
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = strip_ansi(raw.rstrip("\n"))
            self.events.put(("line", line, line_color(line)))
            time.sleep(delay)
        code = proc.wait()
        if code != 0:
            self.events.put(("line", f"[exit {code}]", RED))
        self.events.join()
        return code


def record(out_path: Path, duration: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg nie je v PATH")
    load_font()
    root = tk.Tk()
    terminal = Terminal(root)

    ffmpeg_proc: subprocess.Popen | None = None

    def start_capture() -> None:
        nonlocal ffmpeg_proc
        command = [
            ffmpeg, "-y", "-loglevel", "error",
            "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "0",
            "-i", "title=demo raw", "-t", str(duration),
            "-vf", f"scale={W}:{H}",
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
            str(out_path),
        ]
        ffmpeg_proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    def worker() -> None:
        time.sleep(0.8)
        terminal.run_stream([sys.executable, "-m", "demo", "run-all"], show="python -m demo run-all", delay=0.20)
        time.sleep(0.8)
        terminal.run_stream(
            [
                "powershell.exe", "-NoProfile", "-Command",
                "dir data\\output -Name",
            ],
            show="dir data\\output -Name",
            delay=0.20,
        )
        time.sleep(0.5)
        terminal.run_stream(
            ["powershell.exe", "-NoProfile", "-Command", "(dir data\\output\\shoptet\\invoices -Filter *.xml).Count"],
            show="(dir data\\output\\shoptet\\invoices -Filter *.xml).Count",
            delay=0.20,
        )
        terminal.run_stream(
            ["powershell.exe", "-NoProfile", "-Command", "(dir data\\output\\invoices\\invoices -Filter *.xml).Count"],
            show="(dir data\\output\\invoices\\invoices -Filter *.xml).Count",
            delay=0.20,
        )
        terminal.run_stream(
            ["powershell.exe", "-NoProfile", "-Command", "(dir data\\output\\mergado\\master_feed.*).Name"],
            show="(dir data\\output\\mergado\\master_feed.*).Name",
            delay=0.20,
        )
        time.sleep(0.5)
        terminal.run_stream(
            ["powershell.exe", "-NoProfile", "-Command", "(dir data\\output -Recurse -File).Count"],
            show="(dir data\\output -Recurse -File).Count",
            delay=0.20,
        )
        terminal.events.put(("line", "", TEXT))
        terminal.events.put(("line", "Hotovo. Súbory sú v data/output/.", GREEN))
        terminal.events.put(("done",))

    root.after(400, start_capture)
    root.after(1100, lambda: threading.Thread(target=worker, daemon=True).start())
    root.after(duration * 1000, root.destroy)
    root.mainloop()
    if ffmpeg_proc is not None:
        try:
            _, err = ffmpeg_proc.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            ffmpeg_proc.terminate()
            _, err = ffmpeg_proc.communicate(timeout=10)
        if ffmpeg_proc.returncode != 0:
            raise RuntimeError(f"ffmpeg zlyhal:\n{err[-3000:]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "handoff" / "raw" / "run-all.mp4"))
    parser.add_argument("--duration", type=int, default=60)
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    record(out, args.duration)
    poster = out.with_name("poster.png")
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-ss", "11", "-i", str(out), "-frames:v", "1", "-update", "1", str(poster)],
        check=True,
    )
    print(f"raw: {out}")
    print(f"poster: {poster}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
