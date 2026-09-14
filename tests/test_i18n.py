import pytest
from fluent.syntax import ast, parse
from fluent.syntax.visitor import Visitor

from app.i18n import DEFAULT_LOCALE, LOCALES_DIR, SUPPORTED_LOCALES, LocalizedError, resolve_locale, translate, use_locale


class _VariableCollector(Visitor):
    def __init__(self) -> None:
        super().__init__()
        self.names: set[str] = set()

    def visit_VariableReference(self, node) -> None:
        self.names.add(node.id.name)
        self.generic_visit(node)


def _message_variables(locale: str) -> dict[str, set[str]]:
    resource = parse((LOCALES_DIR / f"{locale}.ftl").read_text(encoding="utf-8"))
    assert not [entry for entry in resource.body if isinstance(entry, ast.Junk)]
    messages = {}
    for entry in resource.body:
        if isinstance(entry, ast.Message):
            collector = _VariableCollector()
            collector.visit(entry)
            messages[entry.id.name] = collector.names
    return messages


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_locale_has_same_messages_and_variables_as_default(locale: str) -> None:
    assert _message_variables(locale) == _message_variables(DEFAULT_LOCALE)


@pytest.mark.parametrize(
    ("candidates", "expected"),
    [
        ((None, "uk"), "uk"),
        (("ru", "en"), "ru"),
        ((None, "uk-UA"), "uk"),
        ((None, "pt-br"), "en"),
        ((None, None), "en"),
    ],
)
def test_resolve_locale_prefers_first_supported_language(candidates, expected) -> None:
    assert resolve_locale(*candidates) == expected


def test_localized_error_renders_in_current_locale() -> None:
    error = LocalizedError("error-duration-too-long", max="1d")

    assert str(error) == "Use at most 1d."
    with use_locale("uk"):
        assert str(error) == translate("uk", "error-duration-too-long", max="1d")
