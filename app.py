import tkinter as tk
from datetime import datetime, timedelta
import threading
import time
import math

# ── Schedule: (start_24h, end_24h, label, color) ─────────────────────────────
SCHEDULE = [
    ("07:00", "08:00", "Study AI",               "#00d4ff"),
    ("14:00", "15:00", "Study Physics",           "#ff6b35"),
    ("15:00", "16:00", "Physics Revision",        "#ff8c42"),
    ("16:00", "17:00", "Study Maths",             "#a8ff3e"),
    ("17:00", "18:00", "Study AI",                "#00d4ff"),
    ("21:30", "22:00", "Communication Practice",  "#ff3cac"),
    ("22:00", "22:30", "Podcast / Listening",     "#784ba0"),
    ("22:30", "00:00", "Study Maths",             "#a8ff3e"),
    ("00:00", "01:00", "Study English",           "#ffd700"),
]

DAILY_GOAL_HOURS = 8

COLORS = {
    "bg":      "#0a0a0f",
    "panel":   "#111118",
    "border":  "#1e1e2e",
    "text":    "#e2e2f0",
    "muted":   "#555570",
    "accent":  "#00d4ff",
    "success": "#a8ff3e",
    "warning": "#ffd700",
    "free":    "#444458",
}

# ── Time helpers ──────────────────────────────────────────────────────────────
def parse_hhmm(hhmm, ref):
    return datetime.strptime(hhmm, "%H:%M").replace(
        year=ref.year, month=ref.month, day=ref.day)

def get_slot(now):
    """Find which schedule slot 'now' falls in. Returns (task, color, start, end)."""
    # Check today's slots and also yesterday's (for midnight-crossing slots)
    for day_offset in [0, -1]:
        ref = now + timedelta(days=day_offset)
        for start_s, end_s, task, color in SCHEDULE:
            s = parse_hhmm(start_s, ref)
            e = parse_hhmm(end_s,   ref)
            if e <= s:          # crosses midnight
                e += timedelta(days=1)
            if s <= now < e:
                return task, color, s, e
    return "Free Time", COLORS["free"], now, now

def get_next_slot(now):
    """Find the next upcoming slot after 'now'."""
    candidates = []
    for day_offset in [0, 1]:
        ref = now + timedelta(days=day_offset)
        for start_s, end_s, task, color in SCHEDULE:
            s = parse_hhmm(start_s, ref)
            e = parse_hhmm(end_s,   ref)
            if e <= s:
                e += timedelta(days=1)
            if s > now:
                candidates.append((s, task, color))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        s, task, color = candidates[0]
        return task, color, s
    return "—", COLORS["muted"], now + timedelta(hours=1)

def fmt_12h(hhmm):
    """Convert 24h string to 12h AM/PM, no leading zero."""
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")

def fmt_countdown(secs):
    secs = int(max(secs, 0))
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"

def study_done_today(now):
    total = 0.0
    for start_s, end_s, _, _ in SCHEDULE:
        for day_offset in [0, -1]:
            ref = now + timedelta(days=day_offset)
            s = parse_hhmm(start_s, ref)
            e = parse_hhmm(end_s,   ref)
            if e <= s:
                e += timedelta(days=1)
            if e < now - timedelta(hours=20):
                continue
            actual_end = min(e, now)
            if actual_end > s:
                total += (actual_end - s).total_seconds() / 3600
    return min(total, DAILY_GOAL_HOURS)

def _greeting(now):
    h = now.hour
    if 5 <= h < 12:  return "🌅 Good Morning"
    if 12 <= h < 17: return "☀️ Good Afternoon"
    if 17 <= h < 21: return "🌆 Good Evening"
    return "🌙 Good Night"

def play_beep():
    try:
        import winsound
        for _ in range(2):
            winsound.Beep(880, 180)
            time.sleep(0.08)
        winsound.Beep(1100, 300)
    except Exception:
        pass

# ── Canvas helper ─────────────────────────────────────────────────────────────
def round_rect(canvas, x1, y1, x2, y2, r=12, **kw):
    pts = [
        x1+r, y1,   x2-r, y1,
        x2,   y1,   x2,   y1+r,
        x2,   y2-r, x2,   y2,
        x2-r, y2,   x1+r, y2,
        x1,   y2,   x1,   y2-r,
        x1,   y1+r, x1,   y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)

# ── Widget ────────────────────────────────────────────────────────────────────
class ProductivityWidget:
    W, H = 370, 570   # tall enough for all 9 tasks

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.97)
        self.root.configure(bg=COLORS["bg"])

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = sw - self.W - 20
        y  = sh - self.H - 55
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")

        self.last_task   = ""
        self._pulse_ang  = 0
        self._ox = self._oy = 0
        self._last_hour_reminded = -1

        self._build_ui()
        self.root.attributes("-alpha", 0)
        self._fade_in(0)
        self._update()
        # show welcome popup 2 seconds after launch
        self.root.after(2000, self._show_startup_popup)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        W, H = self.W, self.H
        c = tk.Canvas(self.root, width=W, height=H,
                      bg=COLORS["bg"], highlightthickness=0)
        c.pack(fill="both", expand=True)
        self.c = c

        round_rect(c, 2, 2, W-2, H-2, r=18,
                   fill=COLORS["panel"], outline=COLORS["border"], width=1)

        self._accent_line = c.create_line(
            30, 3, W-30, 3, fill=COLORS["accent"], width=2, capstyle="round")

        # header / drag bar
        drag = c.create_rectangle(0, 0, W, 36, fill=COLORS["panel"], outline="")
        c.tag_bind(drag, "<ButtonPress-1>", self._drag_start)
        c.tag_bind(drag, "<B1-Motion>",     self._drag_move)
        c.create_text(18, 18, text="⚡  PRODUCTIVITY", anchor="w",
                      fill=COLORS["accent"], font=("Consolas", 9, "bold"))

        close = c.create_text(W-14, 18, text="✕", anchor="e",
                               fill=COLORS["muted"], font=("Consolas", 11, "bold"))
        c.tag_bind(close, "<Button-1>", lambda e: self.root.destroy())
        c.tag_bind(close, "<Enter>",  lambda e: c.itemconfig(close, fill="#ff5f57"))
        c.tag_bind(close, "<Leave>",  lambda e: c.itemconfig(close, fill=COLORS["muted"]))

        mini = c.create_text(W-36, 18, text="—", anchor="e",
                              fill=COLORS["muted"], font=("Consolas", 11))
        c.tag_bind(mini, "<Button-1>", lambda e: self.root.iconify())
        c.tag_bind(mini, "<Enter>",  lambda e: c.itemconfig(mini, fill=COLORS["warning"]))
        c.tag_bind(mini, "<Leave>",  lambda e: c.itemconfig(mini, fill=COLORS["muted"]))

        c.create_line(14, 37, W-14, 37, fill=COLORS["border"], width=1)

        # clock
        self._clock_id = c.create_text(
            W//2, 70, text="12:00:00 AM",
            fill=COLORS["text"], font=("Consolas", 28, "bold"), anchor="center")
        self._date_id = c.create_text(
            W//2, 96, text="",
            fill=COLORS["muted"], font=("Consolas", 9), anchor="center")

        # current task card
        cy = 108
        round_rect(c, 14, cy, W-14, cy+78, r=12,
                   fill="#16161f", outline=COLORS["border"], width=1)
        c.create_text(26, cy+13, text="NOW", anchor="w",
                      fill=COLORS["muted"], font=("Consolas", 8, "bold"))
        self._pulse_id   = c.create_oval(W-30, cy+8, W-22, cy+16,
                                          fill=COLORS["accent"], outline="")
        self._task_id    = c.create_text(26, cy+40, text="Loading…",
                                          anchor="w", fill=COLORS["accent"],
                                          font=("Consolas", 15, "bold"))
        self._tasktime_id = c.create_text(26, cy+61, text="",
                                           anchor="w", fill=COLORS["muted"],
                                           font=("Consolas", 9))

        # next row
        ny = cy + 92
        c.create_text(26, ny, text="NEXT →", anchor="w",
                      fill=COLORS["muted"], font=("Consolas", 8, "bold"))
        self._next_id      = c.create_text(82, ny, text="", anchor="w",
                                            fill=COLORS["text"],
                                            font=("Consolas", 10, "bold"))
        self._countdown_id = c.create_text(W-20, ny, text="", anchor="e",
                                            fill=COLORS["warning"],
                                            font=("Consolas", 10, "bold"))

        # progress bar
        py = ny + 26
        c.create_text(26, py, text="DAILY PROGRESS", anchor="w",
                      fill=COLORS["muted"], font=("Consolas", 8, "bold"))
        self._prog_pct_id = c.create_text(W-20, py, text="0%", anchor="e",
                                           fill=COLORS["success"],
                                           font=("Consolas", 8, "bold"))
        by = py + 13
        bx1, bx2 = 26, W-26
        bw = bx2 - bx1
        round_rect(c, bx1, by, bx2, by+8, r=4, fill=COLORS["border"], outline="")
        self._prog_fill = round_rect(c, bx1, by, bx1, by+8, r=4,
                                     fill=COLORS["success"], outline="")
        self._bx1, self._bw, self._by = bx1, bw, by

        # schedule (all 9 rows)
        sy = by + 24
        c.create_text(26, sy, text="TODAY'S SCHEDULE", anchor="w",
                      fill=COLORS["muted"], font=("Consolas", 8, "bold"))
        sy += 16

        ROW = 26
        self._sched_rows = []
        for i, (start_s, end_s, task, color) in enumerate(SCHEDULE):
            label = f"{fmt_12h(start_s)}–{fmt_12h(end_s)}  {task}"
            dot = c.create_oval(26, sy+i*ROW+4, 33, sy+i*ROW+11,
                                fill=color, outline="")
            lbl = c.create_text(42, sy+i*ROW+8, text=label,
                                anchor="w", fill=COLORS["muted"],
                                font=("Consolas", 8))
            self._sched_rows.append((start_s, end_s, dot, lbl))

    # ── Drag ──────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._ox = e.x_root - self.root.winfo_x()
        self._oy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._ox}+{e.y_root - self._oy}")

    def _fade_in(self, a):
        a = min(a + 0.07, 0.97)
        self.root.attributes("-alpha", a)
        if a < 0.97:
            self.root.after(18, lambda: self._fade_in(a))

    # ── Update loop ───────────────────────────────────────────────────────────
    def _update(self):
        now  = datetime.now()
        c    = self.c
        W    = self.W

        task, color, slot_start, slot_end = get_slot(now)
        next_task, next_color, next_start  = get_next_slot(now)
        secs_to_next = (next_start - now).total_seconds()
        pct          = min(study_done_today(now) / DAILY_GOAL_HOURS, 1.0)

        # clock
        c.itemconfig(self._clock_id,
                     text=now.strftime("%I:%M:%S %p").lstrip("0"))
        c.itemconfig(self._date_id,
                     text=now.strftime("%A, %d %B %Y"))

        # current task
        c.itemconfig(self._task_id, text=task, fill=color)
        c.itemconfig(self._accent_line, fill=color)
        if task != "Free Time":
            end_12 = slot_end.strftime("%I:%M %p").lstrip("0")
            secs_rem = (slot_end - now).total_seconds()
            c.itemconfig(self._tasktime_id,
                         text=f"Until {end_12}  ·  {fmt_countdown(secs_rem)} remaining")
        else:
            c.itemconfig(self._tasktime_id, text="No task right now — enjoy the break!")

        # pulse
        self._pulse_ang = (self._pulse_ang + 12) % 360
        bright = math.sin(self._pulse_ang * math.pi / 180) > 0
        c.itemconfig(self._pulse_id, fill=color,
                     outline=color if bright else COLORS["bg"], width=2)

        # next
        c.itemconfig(self._next_id,      text=next_task, fill=next_color)
        c.itemconfig(self._countdown_id, text=fmt_countdown(secs_to_next))

        # progress bar
        fw = max(int(self._bw * pct), 4 if pct > 0 else 0)
        c.coords(self._prog_fill,
                 self._bx1, self._by, self._bx1 + fw, self._by + 8)
        c.itemconfig(self._prog_pct_id, text=f"{int(pct*100)}%")

        # highlight active schedule row
        for start_s, end_s, dot, lbl in self._sched_rows:
            active = False
            for day_offset in [0, -1]:
                ref = now + timedelta(days=day_offset)
                s = parse_hhmm(start_s, ref)
                e = parse_hhmm(end_s,   ref)
                if e <= s:
                    e += timedelta(days=1)
                if s <= now < e:
                    active = True
                    break
            c.itemconfig(lbl, fill=COLORS["text"] if active else COLORS["muted"])
            c.itemconfig(dot, outline="#ffffff" if active else "", width=1)

        # notification on task change
        if task != self.last_task:
            self.last_task = task
            if task != "Free Time":
                threading.Thread(target=play_beep, daemon=True).start()
                self._show_toast(task, color)

        # hourly reminder popup every full hour (e.g. 2:00, 3:00 ...)
        current_hour = now.hour
        if now.minute == 0 and now.second == 0 and current_hour != self._last_hour_reminded:
            self._last_hour_reminded = current_hour
            threading.Thread(target=play_beep, daemon=True).start()
            self._show_hourly_reminder(task, color, now)

        self.root.after(1000, self._update)

    # ── Toast ─────────────────────────────────────────────────────────────────
    def _show_toast(self, msg, color):
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.attributes("-alpha", 0)
        t.configure(bg=COLORS["panel"])
        sw = self.root.winfo_screenwidth()
        tw, th = 310, 62
        t.geometry(f"{tw}x{th}+{sw - tw - 20}+20")

        tk.Label(t, text="⚡  Task Starting",
                 bg=COLORS["panel"], fg=COLORS["muted"],
                 font=("Consolas", 8, "bold")).place(x=14, y=8)
        tk.Label(t, text=msg,
                 bg=COLORS["panel"], fg=color,
                 font=("Consolas", 13, "bold")).place(x=14, y=28)

        def fade_in(a=0):
            a = min(a + 0.1, 0.95)
            t.attributes("-alpha", a)
            if a < 0.95:
                t.after(22, lambda: fade_in(a))
            else:
                t.after(3200, lambda: fade_out(0.95))

        def fade_out(a):
            a = max(a - 0.06, 0)
            t.attributes("-alpha", a)
            if a > 0:
                t.after(28, lambda: fade_out(a))
            else:
                t.destroy()

        fade_in()

    def _show_startup_popup(self):
        now = datetime.now()
        task, color, _, slot_end = get_slot(now)
        next_task, next_color, next_start = get_next_slot(now)
        secs_to_next = int((next_start - now).total_seconds())

        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.attributes("-alpha", 0)
        t.configure(bg=COLORS["panel"])

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        tw, th = 360, 160
        # center of screen
        x = (sw - tw) // 2
        y = (sh - th) // 2
        t.geometry(f"{tw}x{th}+{x}+{y}")

        cv = tk.Canvas(t, width=tw, height=th,
                       bg=COLORS["panel"], highlightthickness=0)
        cv.place(x=0, y=0)
        cv.create_line(0, 0, tw, 0, fill=color, width=3)
        cv.create_line(0, th-1, tw, th-1, fill=COLORS["border"], width=1)

        greet = _greeting(now)
        tk.Label(t, text=f"{greet}  —  {now.strftime('%A, %d %B')}",
                 bg=COLORS["panel"], fg=COLORS["muted"],
                 font=("Consolas", 8, "bold")).place(x=16, y=12)

        tk.Label(t, text="RIGHT NOW:",
                 bg=COLORS["panel"], fg=COLORS["muted"],
                 font=("Consolas", 8)).place(x=16, y=34)
        tk.Label(t, text=task if task != "Free Time" else "Free Time 🌙",
                 bg=COLORS["panel"], fg=color,
                 font=("Consolas", 15, "bold")).place(x=16, y=52)

        if task != "Free Time":
            end_12 = slot_end.strftime("%I:%M %p").lstrip("0")
            sub = f"Until {end_12}  ·  {fmt_countdown((slot_end - now).total_seconds())} left"
        else:
            sub = f"Next: {next_task} in {fmt_countdown(secs_to_next)}"
        tk.Label(t, text=sub,
                 bg=COLORS["panel"], fg=COLORS["muted"],
                 font=("Consolas", 9)).place(x=16, y=80)

        tk.Label(t, text=f"Next up →  {next_task}  in {fmt_countdown(secs_to_next)}",
                 bg=COLORS["panel"], fg=next_color,
                 font=("Consolas", 9, "bold")).place(x=16, y=102)

        def close_it():
            fade_out(0.97)

        btn = tk.Label(t, text="  Let's Go! ⚡  ",
                       bg=color, fg=COLORS["bg"],
                       font=("Consolas", 9, "bold"), cursor="hand2")
        btn.place(x=tw//2 - 60, y=128)
        btn.bind("<Button-1>", lambda e: close_it())

        def fade_in(a=0):
            a = min(a + 0.08, 0.97)
            t.attributes("-alpha", a)
            if a < 0.97:
                t.after(18, lambda: fade_in(a))

        def fade_out(a):
            a = max(a - 0.07, 0)
            t.attributes("-alpha", a)
            if a > 0:
                t.after(22, lambda: fade_out(a))
            else:
                try: t.destroy()
                except: pass

        fade_in()

    def _show_hourly_reminder(self, task, color, now):
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.attributes("-alpha", 0)
        t.configure(bg=COLORS["panel"])

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        tw, th = 340, 110
        t.geometry(f"{tw}x{th}+{sw - tw - 20}+20")

        # border canvas
        cv = tk.Canvas(t, width=tw, height=th,
                       bg=COLORS["panel"], highlightthickness=0)
        cv.place(x=0, y=0)
        # accent top line
        cv.create_line(0, 0, tw, 0, fill=color, width=3)

        hour_str = now.strftime("%I:%M %p").lstrip("0")
        tk.Label(t, text=f"🕐  {hour_str} — Hourly Check-in",
                 bg=COLORS["panel"], fg=COLORS["muted"],
                 font=("Consolas", 8, "bold")).place(x=14, y=10)

        tk.Label(t, text=task if task != "Free Time" else "Free Time 🌙",
                 bg=COLORS["panel"], fg=color,
                 font=("Consolas", 14, "bold")).place(x=14, y=32)

        msg = "Stay focused — you're doing great! 💪" if task != "Free Time" else "Rest up, next task coming soon!"
        tk.Label(t, text=msg,
                 bg=COLORS["panel"], fg=COLORS["muted"],
                 font=("Consolas", 8)).place(x=14, y=60)

        # dismiss button
        def close_it():
            t.destroy()
        btn = tk.Label(t, text="  OK  ", bg=color, fg=COLORS["bg"],
                       font=("Consolas", 8, "bold"), cursor="hand2")
        btn.place(x=tw-60, y=78)
        btn.bind("<Button-1>", lambda e: close_it())

        def fade_in(a=0):
            a = min(a + 0.08, 0.97)
            t.attributes("-alpha", a)
            if a < 0.97:
                t.after(20, lambda: fade_in(a))
            else:
                t.after(6000, lambda: fade_out(0.97))  # auto-dismiss after 6s

        def fade_out(a):
            a = max(a - 0.06, 0)
            t.attributes("-alpha", a)
            if a > 0:
                t.after(28, lambda: fade_out(a))
            else:
                try: t.destroy()
                except: pass

        fade_in()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ProductivityWidget().run()
