from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from fluent.runtime import FluentBundle, FluentResource

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "uk", "ru")
LOCALE_NAMES = {"en": "English", "uk": "Українська", "ru": "Русский"}
LOCALES_DIR = Path(__file__).parent / "locales"

_current_locale: ContextVar[str] = ContextVar("locale", default=DEFAULT_LOCALE)


def _load_bundle(locale: str) -> FluentBundle:
    bundle = FluentBundle([locale], use_isolating=False)
    bundle.add_resource(FluentResource((LOCALES_DIR / f"{locale}.ftl").read_text(encoding="utf-8")))
    return bundle


_BUNDLES = {locale: _load_bundle(locale) for locale in SUPPORTED_LOCALES}


def translate(locale: str, key: str, /, **args: object) -> str:
    bundle = _BUNDLES.get(locale, _BUNDLES[DEFAULT_LOCALE])
    if not bundle.has_message(key):
        bundle = _BUNDLES[DEFAULT_LOCALE]
    text, errors = bundle.format_pattern(bundle.get_message(key).value, args)
    if errors:
        logger.warning("Translation failed; locale=%s key=%s errors=%s", locale, key, errors)
    return text


def t(key: str, /, **args: object) -> str:
    return translate(_current_locale.get(), key, **args)


def current_locale() -> str:
    return _current_locale.get()


def resolve_locale(*candidates: str | None) -> str:
    for candidate in candidates:
        code = (candidate or "").split("-")[0].lower()
        if code in SUPPORTED_LOCALES:
            return code
    return DEFAULT_LOCALE


@contextmanager
def use_locale(locale: str) -> Iterator[None]:
    token = _current_locale.set(resolve_locale(locale))
    try:
        yield
    finally:
        _current_locale.reset(token)


class LocalizedError(ValueError):
    def __init__(self, key: str, /, **params: object) -> None:
        super().__init__(key)
        self.key = key
        self.params = params

    def __str__(self) -> str:
        return t(self.key, **self.params)
