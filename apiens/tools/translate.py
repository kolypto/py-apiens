""" Translation support for Apiens """

import gettext

# Init translations
# TODO: will this work with lazy translations? will it allow applications to override it?
try:
    translation = gettext.translation('apiens')
except FileNotFoundError:
    translation = gettext.NullTranslations()
_ = translation.gettext
