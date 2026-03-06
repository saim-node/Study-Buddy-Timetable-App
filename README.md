# ⚡ Study Buddy

**Study Buddy** is a lightweight desktop widget built with Python and Tkinter.  
It helps you track your schedule, current and next tasks, and daily study progress.

## Screenshots

![Screenshot](https://i.imgur.com/abcd1234.png)  
*(This is Study Buddy in action)*

---

## Features

- Shows **current task** and **next task** with countdown.  
- **Daily progress bar** for study goals.  
- **Hourly reminders** with gentle beep notifications.  
- Customizable **schedule and colors**.

---

## Installation

```bash
git clone https://github.com/yourusername/study-buddy.git
cd study-buddy
python -m venv venv
# Activate:
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install tk
```
---
## Usage
```bash
python study_buddy.py
```
---
## Customization

* Edit the SCHEDULE variable in study_buddy.py:

``` bash
SCHEDULE = [
    ("07:00", "08:00", "Study AI", "#00d4ff"),
    ("14:00", "15:00", "Study Physics", "#ff6b35"),
]
DAILY_GOAL_HOURS = 8

Format: ("start_time", "end_time", "Task Name", "HEX Color").
```
---

## Converting to .exe (Windows)
``` bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=myicon.ico study_buddy.py
```

* Output .exe is in the dist folder
* Copy it to shell:startup for auto-launch on login

## License

MIT License © Saim Raza
