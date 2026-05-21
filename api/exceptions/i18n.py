import json
from pathlib import Path
from typing import Optional

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LOCALE = "en"
TRANSLATIONS = {}


def translate(lang: Optional[str], key: str) -> str:
    lang_code = lang or DEFAULT_LOCALE
    if lang_code not in TRANSLATIONS:
        file_path = LOCALES_DIR / f"{lang_code}.json"
        if not file_path.exists():
            file_path = LOCALES_DIR / f"{DEFAULT_LOCALE}.json"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                TRANSLATIONS[lang_code] = json.load(f)
        except Exception:
            TRANSLATIONS[lang_code] = {}

    return TRANSLATIONS[lang_code].get(key, key)
