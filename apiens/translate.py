""" Translation support for Apiens """

import gettext
from typing import Union

translation: Union[gettext.NullTranslations, gettext.GNUTranslations]

# Init translations
# TODO: will this work with lazy translations? will it allow applications to override it?
try:
    translation = gettext.translation('apiens')  # type: ignore[assignment]
except FileNotFoundError:
    translation = gettext.NullTranslations()  # type: ignore[assignment]

_ = translation.gettext
