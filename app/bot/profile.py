from app.i18n import translate

BOT_NAME = "Price Bird"


def bot_description(locale: str) -> str:
    return translate(locale, "profile-description")


def bot_short_description(locale: str) -> str:
    return translate(locale, "profile-short-description")
