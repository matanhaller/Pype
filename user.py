"""User class file.
"""


class User(object):

    """App user class.

    Attributes:
        conn (socket.socket): Connection for communicating with user.
        status (str): Whether the user is in call (available/in call).
        name (str): Username.
        call (Call): The call in which the user is in (None if he's not).
    """

    def __init__(self, name, conn):
        """Constructor method.

        Args:
            name (str): Username.
            conn (socket.socket): Connection for communicating with user.
        """

        self.name = name
        self.conn = conn
        self.status = 'available'
        self.call = None

    def switch_status(self):
        """Switching user status.
        """

        if self.status == 'available':
            self.status = 'in call'
        else:
            self.status = 'available'
