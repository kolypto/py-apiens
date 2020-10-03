from typing import Mapping, Any


# Values for an SqlAlchemy instance, in the form of a dictionary. Possibly, partial.
InstanceDict = Mapping[str, Any]

# User-supplied values for filtering objects
UserFilterValue = Any


# Sugar. Marks a field that will be automatically initialized.
AUTOMATIC = None
