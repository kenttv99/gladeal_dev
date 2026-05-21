import json
from pathlib import Path

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LOCALE = "en"
TRANSLATIONS = {}


def translate(lang: str, key: str) -> str:
    lang = lang or DEFAULT_LOCALE
    if lang not in TRANSLATIONS:
        file_path = LOCALES_DIR / f"{lang}.json"
        if not file_path.exists():
            file_path = LOCALES_DIR / f"{DEFAULT_LOCALE}.json"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                TRANSLATIONS[lang] = json.load(f)
        except Exception:
            TRANSLATIONS[lang] = {}

    return TRANSLATIONS[lang].get(key, key)
