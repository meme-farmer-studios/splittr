import tkinter as tk
from tkinter import filedialog, ttk
import subprocess
import threading
import os
import math
import re

FORMATS = ["source", "mp3", "flac", "ogg", "wav", "m4a"]

FORMAT_CODECS = {
    "source": None,
    "mp3":    ["-c:a", "libmp3lame", "-q:a", "2"],
    "flac":   ["-c:a", "flac"],
    "ogg":    ["-c:a", "libvorbis", "-q:a", "4"],
    "wav":    ["-c:a", "pcm_s16le"],
    "m4a":    ["-c:a", "aac", "-b:a", "192k"],
}

class Splittr:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("splittr")
        self.window.geometry("640x480")
        self.window.minsize(560, 420)

        self.input_file = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.output_name = tk.StringVar(value="output - part ")
        self.split_mode = tk.StringVar(value="duration")

        self.segment_time_h = tk.StringVar(value="00")
        self.segment_time_m = tk.StringVar(value="02")
        self.segment_time_s = tk.StringVar(value="01")

        self.equal_parts = tk.StringVar(value="5")
        self.parts_preview = tk.StringVar(value="")
        self.name_preview = tk.StringVar(value="")

        self.output_format = tk.StringVar(value="source")

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_label = tk.StringVar(value="")
        self.open_when_done = tk.BooleanVar(value=True)
        self.running = False

        self._preview_timer = None

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self.window, padding="12")
        main.pack(fill="both", expand=True)

        # input file
        ttk.Label(main, text="input audio file").pack(anchor="w")
        row1 = ttk.Frame(main)
        row1.pack(fill="x", pady=(0, 8))
        ttk.Entry(row1, textvariable=self.input_file).pack(side="left", fill="x", expand=True)
        ttk.Button(row1, text="browse", command=self._browse_input).pack(side="right", padx=(6, 0))

        # output folder
        ttk.Label(main, text="output folder").pack(anchor="w")
        row2 = ttk.Frame(main)
        row2.pack(fill="x", pady=(0, 8))
        ttk.Entry(row2, textvariable=self.output_folder).pack(side="left", fill="x", expand=True)
        ttk.Button(row2, text="browse", command=self._browse_output).pack(side="right", padx=(6, 0))

        # naming
        ttk.Label(main, text="output name").pack(anchor="w")
        ttk.Entry(main, textvariable=self.output_name).pack(fill="x", pady=(0, 4))
        self.name_preview_label = ttk.Label(main, textvariable=self.name_preview, font=("", 9))
        self.name_preview_label.pack(anchor="w", pady=(0, 4))

        # format
        fmt_frame = ttk.Frame(main)
        fmt_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(fmt_frame, text="output format").pack(side="left", padx=(0, 8))
        fmt_combo = ttk.Combobox(fmt_frame, textvariable=self.output_format,
                                 values=FORMATS, state="readonly", width=12)
        fmt_combo.pack(side="left")

        # separator
        ttk.Separator(main).pack(fill="x", pady=(0, 8))

        # split mode
        mode_frame = ttk.Frame(main)
        mode_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(mode_frame, text="split by duration", variable=self.split_mode,
                        value="duration", command=self._on_mode_change).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(mode_frame, text="split into equal parts", variable=self.split_mode,
                        value="equal", command=self._on_mode_change).pack(side="left")

        # duration mode
        self.duration_frame = ttk.Frame(main)
        self.duration_frame.pack(fill="x", pady=(0, 4))
        ttk.Label(self.duration_frame, text="segment duration (hh:mm:ss)").pack(anchor="w")
        dur_row = ttk.Frame(self.duration_frame)
        dur_row.pack(fill="x", pady=(2, 0))
        self._make_time_entry(dur_row, self.segment_time_h, 4)
        ttk.Label(dur_row, text=":").pack(side="left")
        self._make_time_entry(dur_row, self.segment_time_m, 4)
        ttk.Label(dur_row, text=":").pack(side="left")
        self._make_time_entry(dur_row, self.segment_time_s, 4)

        # equal parts mode
        self.equal_frame = ttk.Frame(main)
        ttk.Label(self.equal_frame, text="number of equal parts").pack(anchor="w")
        eq_row = ttk.Frame(self.equal_frame)
        eq_row.pack(fill="x", pady=(2, 0))
        ttk.Entry(eq_row, textvariable=self.equal_parts, width=8).pack(side="left")

        # preview label
        self.preview_label = ttk.Label(main, textvariable=self.parts_preview, font=("", 9))
        self.preview_label.pack(anchor="w", pady=(0, 8))

        # separator
        ttk.Separator(main).pack(fill="x", pady=(0, 8))

        # progress
        self.progress_bar = ttk.Progressbar(main, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=(0, 4))
        ttk.Label(main, textvariable=self.progress_label).pack(anchor="w", pady=(0, 8))

        # open folder option
        ttk.Checkbutton(main, text="open output folder when done",
                        variable=self.open_when_done).pack(anchor="w", pady=(0, 6))

        # start button
        self.start_btn = ttk.Button(main, text="start split", command=self._start_split)
        self.start_btn.pack()

        # auto-preview triggers
        self.input_file.trace_add("write", lambda *_: self._schedule_preview())
        self.segment_time_h.trace_add("write", lambda *_: self._schedule_preview())
        self.segment_time_m.trace_add("write", lambda *_: self._schedule_preview())
        self.segment_time_s.trace_add("write", lambda *_: self._schedule_preview())
        self.equal_parts.trace_add("write", lambda *_: self._schedule_preview())
        self.output_name.trace_add("write", lambda *_: self._update_name_preview())
        self.output_format.trace_add("write", lambda *_: self._update_name_preview())

    def _make_time_entry(self, parent, var, width):
        e = ttk.Entry(parent, textvariable=var, width=width)
        e.pack(side="left")
        e.bind("<FocusOut>", lambda ev: self._pad_time(var))
        return e

    def _pad_time(self, var):
        val = var.get().strip()
        if val.isdigit():
            var.set(f"{int(val):02d}")

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="select input audio file",
            filetypes=[("audio files", "*.wav *.mp3 *.flac *.ogg *.m4a *.aac *.wma *.aiff"), ("all files", "*.*")]
        )
        if path:
            self.input_file.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="select output folder")
        if path:
            self.output_folder.set(path)

    def _on_mode_change(self):
        if self.split_mode.get() == "duration":
            self.equal_frame.pack_forget()
            self.duration_frame.pack(fill="x", pady=(0, 4))
        else:
            self.duration_frame.pack_forget()
            self.equal_frame.pack(fill="x", pady=(0, 4))
        self._schedule_preview()

    def _get_output_ext(self):
        fmt = self.output_format.get()
        if fmt != "source":
            return f".{fmt}"
        path = self.input_file.get()
        if not path:
            return ".mp3"
        _, ext = os.path.splitext(path)
        return ext if ext else ".mp3"

    def _update_name_preview(self):
        name = self.output_name.get()
        ext = self._get_output_ext()
        if not name.strip():
            self.name_preview.set("")
            return
        self.name_preview.set(f"e.g. {name}1{ext}, {name}2{ext}, {name}3{ext}")

    def _schedule_preview(self):
        if self._preview_timer:
            self.window.after_cancel(self._preview_timer)
        self._preview_timer = self.window.after(400, self._update_preview)

    def _update_preview(self):
        self._preview_timer = None
        self._update_name_preview()
        if self.split_mode.get() == "duration":
            self._preview_duration()
        else:
            self._preview_equal()

    def _get_duration_seconds(self, path):
        if not path or not os.path.isfile(path):
            return None
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        return None

    def _preview_duration(self):
        path = self.input_file.get()
        total = self._get_duration_seconds(path)
        if total is None:
            self.parts_preview.set("")
            return
        h = int(self.segment_time_h.get() or 0)
        m = int(self.segment_time_m.get() or 0)
        s = int(self.segment_time_s.get() or 0)
        seg_secs = h * 3600 + m * 60 + s
        if seg_secs <= 0:
            self.parts_preview.set("")
            return
        n_parts = math.ceil(total / seg_secs)
        total_str = self._format_time(total)
        seg_str = self._format_time(seg_secs)
        self.parts_preview.set(f"{n_parts} parts of {seg_str} each (total {total_str})")

    def _preview_equal(self):
        path = self.input_file.get()
        total = self._get_duration_seconds(path)
        if total is None:
            self.parts_preview.set("")
            return
        try:
            n = int(self.equal_parts.get())
        except ValueError:
            self.parts_preview.set("")
            return
        if n <= 0:
            self.parts_preview.set("")
            return
        seg_secs = total / n
        total_str = self._format_time(total)
        seg_str = self._format_time(seg_secs)
        self.parts_preview.set(f"{n} parts of {seg_str} each (total {total_str})")

    def _format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        if h > 0:
            return f"{h}h {m:02d}m {s:05.2f}s"
        elif m > 0:
            return f"{m}m {s:05.2f}s"
        else:
            return f"{s:.2f}s"

    def _make_ffmpeg_template(self):
        name = self.output_name.get()
        ext = self._get_output_ext()
        if not name.strip():
            return f"output_%01d{ext}"
        return f"{name}%01d{ext}"

    def _get_output_codec_args(self):
        fmt = self.output_format.get()
        codec = FORMAT_CODECS.get(fmt)
        if codec is None:
            return ["-c", "copy"]
        return codec

    def _start_split(self):
        if self.running:
            return
        input_path = self.input_file.get()
        output_dir = self.output_folder.get()
        pattern = self.output_name.get().strip()

        if not input_path or not os.path.isfile(input_path):
            self.parts_preview.set("please select a valid input file")
            return
        if not output_dir:
            self.parts_preview.set("please select an output folder")
            return
        if not pattern:
            self.parts_preview.set("please enter an output name")
            return

        os.makedirs(output_dir, exist_ok=True)
        self.running = True
        self.start_btn.config(state="disabled")
        self.progress_var.set(0)
        self.progress_label.set("")

        ffmpeg_template = self._make_ffmpeg_template()

        if self.split_mode.get() == "duration":
            thread = threading.Thread(target=self._run_duration_split, args=(input_path, output_dir, ffmpeg_template))
        else:
            thread = threading.Thread(target=self._run_equal_split, args=(input_path, output_dir, ffmpeg_template))
        thread.daemon = True
        thread.start()

    def _get_total_parts_ffmpeg(self, input_path, seg_secs):
        total = self._get_duration_seconds(input_path)
        if total is None:
            return 0
        return math.ceil(total / seg_secs)

    def _run_duration_split(self, input_path, output_dir, ffmpeg_template):
        try:
            h = int(self.segment_time_h.get() or 0)
            m = int(self.segment_time_m.get() or 0)
            s = int(self.segment_time_s.get() or 0)
            seg_secs = h * 3600 + m * 60 + s
            if seg_secs <= 0:
                self.window.after(0, lambda: self.parts_preview.set("segment duration must be greater than 0"))
                self._reset()
                return

            seg_str = f"{h:02d}:{m:02d}:{s:02d}"
            total_parts = self._get_total_parts_ffmpeg(input_path, seg_secs)
            if total_parts == 0:
                self.window.after(0, lambda: self.parts_preview.set("could not determine file duration"))
                self._reset()
                return

            out_template = os.path.join(output_dir, ffmpeg_template)
            codec_args = self._get_output_codec_args()
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-f", "segment",
                "-segment_time", seg_str,
                "-segment_start_number", "1",
            ] + codec_args + [out_template]

            self._run_ffmpeg_with_progress(cmd, total_parts, input_path, seg_secs, output_dir)
        except Exception as e:
            self.window.after(0, lambda: self.parts_preview.set(f"error: {str(e)}"))
        finally:
            self._reset()

    def _run_equal_split(self, input_path, output_dir, ffmpeg_template):
        try:
            n = int(self.equal_parts.get())
            if n <= 0:
                self.window.after(0, lambda: self.parts_preview.set("number of parts must be greater than 0"))
                self._reset()
                return

            total = self._get_duration_seconds(input_path)
            if total is None:
                self.window.after(0, lambda: self.parts_preview.set("could not determine file duration"))
                self._reset()
                return

            seg_secs = total / n
            h = int(seg_secs // 3600)
            m = int((seg_secs % 3600) // 60)
            s = seg_secs % 60
            seg_str = f"{h:02d}:{m:02d}:{int(s):02d}"

            out_template = os.path.join(output_dir, ffmpeg_template)
            codec_args = self._get_output_codec_args()
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-f", "segment",
                "-segment_time", seg_str,
                "-segment_start_number", "1",
            ] + codec_args + [out_template]

            self._run_ffmpeg_with_progress(cmd, n, input_path, seg_secs, output_dir)
        except Exception as e:
            self.window.after(0, lambda: self.parts_preview.set(f"error: {str(e)}"))
        finally:
            self._reset()

    def _run_ffmpeg_with_progress(self, cmd, total_parts, input_path, seg_secs, output_dir):
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        pattern = r"time=(\d+):(\d+):(\d+)\.\d+"
        total_duration = self._get_duration_seconds(input_path)
        last_pct = -1

        for line in process.stderr:
            match = re.search(pattern, line)
            if match and total_duration and total_duration > 0:
                h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
                current_time = h * 3600 + m * 60 + s
                pct = min(int((current_time / total_duration) * 100), 100)

                if pct != last_pct:
                    last_pct = pct
                    current_part = min(int(current_time / seg_secs) + 1, total_parts)
                    self.window.after(0, lambda p=pct, cp=current_part, tp=total_parts: self._update_progress(p, cp, tp))

        process.wait()

        if process.returncode == 0:
            self.window.after(0, lambda: self._update_progress(100, total_parts, total_parts))
            self.window.after(0, lambda: self.parts_preview.set("split complete"))
            if self.open_when_done.get():
                self.window.after(200, lambda: os.startfile(output_dir))
        else:
            self.window.after(0, lambda: self.parts_preview.set("split failed - check ffmpeg output"))

    def _update_progress(self, pct, current_part, total_parts):
        self.progress_var.set(pct)
        self.progress_label.set(f"{current_part}/{total_parts} parts  {pct}%")

    def _reset(self):
        self.running = False
        self.window.after(0, lambda: self.start_btn.config(state="normal"))

    def run(self):
        self.window.mainloop()


if __name__ == "__main__":
    Splittr().run()
