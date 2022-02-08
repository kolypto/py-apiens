class DictMatch(dict):
    """ Partial match of a dictionary to another one, with nice diffs

    Example:
        assert DictMatch({'praenomen': 'Gaius'}) == {'praenomen': 'Gaius', 'nomen': 'Julius', 'cognomen': 'Caesar'}
    """
    def __eq__(self, other):
        # Only equal if have the same type
        if not isinstance(other, dict):
            return False

        # Copy the missing values from another dict (in order to have nice diffs)
        self.update({k: v for k, v in other.items() if k not in self})

        # Compare
        return all(other[name] == value for name, value in self.items())
