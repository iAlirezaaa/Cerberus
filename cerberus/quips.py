"""Cerberus's little lines, in English and Persian. Qt-free and deterministic under a seeded RNG."""
from __future__ import annotations

import random
from datetime import datetime

LANGUAGES = ("en", "fa")

LINES: dict[str, dict[str, tuple[str, ...]]] = {
    "greet_morning": {
        "en": ("Morning! All three heads are awake.", "Good morning, keeper of tabs!"),
        "fa": ("صبح بخیر! هر سه تا کله‌م بیدارن.", "صبح بخیر رفیق! نگهبانی شروع شد."),
    },
    "greet_afternoon": {
        "en": ("Afternoon! The vault is safe.", "Hi again! Anything to fetch?"),
        "fa": ("ظهر بخیر! گنجینه امن و امانه.", "سلام دوباره! چیزی هست بیارم؟"),
    },
    "greet_evening": {
        "en": ("Good evening, friend!", "Evening patrol has begun."),
        "fa": ("عصر بخیر رفیق!", "گشت عصرگاهی شروع شد."),
    },
    "greet_night": {
        "en": ("It's late… I'll guard, you sleep!", "Night shift: three heads, no naps. Mostly."),
        "fa": ("دیروقته‌ها… من نگهبانی می‌دم، تو بخواب!", "شیفت شب: سه تا کله، بدون چرت. تقریباً!"),
    },
    "idle": {
        "en": (
            "Guarding your memories. Very serious job.",
            "Three heads, zero bad ideas.",
            "Got anything for me? Text, links, files…",
            "Underworld rule #1: never lose a file.",
            "Head two says hi. Head three is shy.",
            "No cloud. Just me. Very loyal.",
            "Is it snack o'clock yet?",
            "Drag something onto me, I dare you.",
        ),
        "fa": (
            "دارم از خاطره‌هات نگهبانی می‌کنم. کار خیلی جدیه.",
            "سه تا کله، صفر ایده‌ی بد.",
            "چیزی داری بهم بدی؟ متن، لینک، فایل…",
            "قانون اول دنیای زیرین: هیچ فایلی گم نمی‌شه.",
            "کله‌ی دوم سلام می‌رسونه. سومی خجالتیه.",
            "ابری در کار نیست. فقط من، خیلی وفادار.",
            "وقت خوراکی نشده هنوز؟",
            "یه چیزی بنداز روم، جرئت داری!",
        ),
    },
    "think": {
        "en": (
            "Hmm… where did I bury that PDF?",
            "Three heads… one brain cell?",
            "Is a link just a very long stick?",
            "Does Hades have Wi-Fi?",
            "Counting memories… one, two, many!",
            "If I guard a guard, who guards me?",
        ),
        "fa": (
            "هوم… اون PDF رو کجا چال کردم؟",
            "سه تا کله… یه دونه مغز؟",
            "لینک هم یه جور چوب درازه، نه؟",
            "یعنی هادس وای‌فای داره؟",
            "دارم خاطره‌ها رو می‌شمرم… یک، دو، خیلی!",
            "اگه من نگهبان باشم، کی نگهبان منه؟",
        ),
    },
    "pet": {
        "en": ("Good human!", "Again! Again!", "All three heads approve.", "Ear scratches accepted."),
        "fa": ("آدم خوب!", "بازم! بازم!", "هر سه تا کله تأیید می‌کنن.", "نازم کن، نازم کن!"),
    },
    "drag_over": {
        "en": ("Ooh! Is that for me?", "Drop it! Drop it!", "I smell a fresh memory!"),
        "fa": ("اوه! اینو برای من آوردی؟", "ولش کن! ولش کن!", "بوی یه خاطره‌ی تازه میاد!"),
    },
    "capture_text": {
        "en": ("Note guarded!", "Words? Delicious.", "Saved. I won't forget."),
        "fa": ("یادداشت محافظت شد!", "کلمه‌ها؟ خوشمزه‌ن.", "ذخیره شد. یادم نمی‌ره."),
    },
    "capture_url": {
        "en": ("Link fetched!", "Got the link, like a stick!"),
        "fa": ("لینک رو آوردم!", "لینک رو گرفتم، مثل چوب!"),
    },
    "capture_image": {
        "en": ("Pretty picture, saved!", "Into the vault it goes!"),
        "fa": ("عکس قشنگیه، نگهش داشتم!", "رفت توی گنجینه!"),
    },
    "capture_file": {
        "en": ("{name} is safe with me!", "Guarded: {name}"),
        "fa": ("{name} پیش من امنه!", "محافظت شد: {name}"),
    },
    "capture_files": {
        "en": ("Guarded {count} files!", "{count} files, three heads. Easy."),
        "fa": ("{count} تا فایل رو نگه داشتم!", "{count} تا فایل، سه تا کله. کاری نداره!"),
    },
    "sleep": {
        "en": ("Zzz… guarding in my dreams…", "Just resting my six eyes."),
        "fa": ("خررر… توی خوابم هم نگهبانی می‌دم…", "فقط شش تا چشمم رو یه کم استراحت می‌دم."),
    },
    "wake": {
        "en": ("I'm up! I'm up!", "Did I miss anything?"),
        "fa": ("بیدارم! بیدارم!", "چیزی رو از دست دادم؟"),
    },
    "leave": {
        "en": ("Off to patrol the underworld!", "Bored… going for a walk!", "Brb, a soul escaped!"),
        "fa": ("می‌رم یه سر به دنیای زیرین بزنم!", "حوصله‌م سر رفت… می‌رم قدم بزنم!", "زود برمی‌گردم، یه روح فرار کرده!"),
    },
    "dismiss": {
        "en": ("Okay, okay, I'm going!", "Call me if you need me!"),
        "fa": ("باشه باشه، رفتم!", "کارم داشتی صدام کن!"),
    },
    "arrive": {
        "en": ("You called? I'm back!", "Cerberus, reporting for duty!"),
        "fa": ("صدام کردی؟ برگشتم!", "سربروس، آماده‌ی خدمت!"),
    },
    "walk": {
        "en": ("Patrol time.", "Stretching my legs."),
        "fa": ("وقت گشت‌زنیه.", "یه کم پاهام رو کش بدم."),
    },
    "dragged": {
        "en": ("Wheee!", "Where are we going?"),
        "fa": ("ووووی!", "کجا داریم می‌ریم؟"),
    },
    "error": {
        "en": ("Grr… I couldn't catch that.",),
        "fa": ("غررر… نتونستم بگیرمش.",),
    },
    "milestone": {
        "en": ("That's {total} memories guarded!",),
        "fa": ("{total} تا خاطره رو نگه داشتم!",),
    },
}


def resolve_language(setting: str, system_language: str = "") -> str:
    """'auto' follows the system language (Persian → fa), otherwise English."""
    if setting in LANGUAGES:
        return setting
    return "fa" if system_language.lower().startswith(("fa", "persian")) else "en"


def greeting_event(hour: int) -> str:
    if 5 <= hour < 12:
        return "greet_morning"
    if 12 <= hour < 17:
        return "greet_afternoon"
    if 17 <= hour < 22:
        return "greet_evening"
    return "greet_night"


class QuipBook:
    """Picks lines without repeating the previous one for the same event."""

    def __init__(self, language: str = "en", rng: random.Random | None = None) -> None:
        self.language = language if language in LANGUAGES else "en"
        self.rng = rng or random.Random()
        self._last: dict[str, str] = {}

    def pick(self, event: str, **values: object) -> str:
        options = LINES.get(event, {}).get(self.language) or LINES.get(event, {}).get("en")
        if not options:
            return ""
        pool = [line for line in options if line != self._last.get(event)] or list(options)
        line = self.rng.choice(pool)
        self._last[event] = line
        safe = {key: str(value)[:28] for key, value in values.items()}
        try:
            return line.format(**safe)
        except (KeyError, IndexError):
            return line

    def greeting(self, now: datetime | None = None) -> str:
        return self.pick(greeting_event((now or datetime.now()).hour))
