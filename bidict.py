"""Dictionary that enables bi-directional mapping.
"""


class BiDict(dict):

    """Bi-directional dictionary class.

    Note: This datas structure uses double memory compared to regular
     dictionary, so it should be used only when need.
    """

    def __init__(self):
        """Constructor method.
        """

        dict.__init__(self)

    def __setitem__(self, key, val):
        """Sets key and value such that they both map to each other.

        Args:
            key (T): Key.
            val (T): Value.
        """

        dict.__setitem__(self, key, val)
        dict.__setitem__(self, val, key)

    def __delitem__(self, key):
        """Summary

        Args:
            key (T): Key.
        """

        dict.__delitem__(self, self[key])
        dict.__delitem__(self, key)
