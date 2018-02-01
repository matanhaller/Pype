"""User class file.
"""


class User(object):

    """App user class.

    Attributes:
        conn (socket.socket): Connection for communicating with user.
        status (str): Whether the user is in call (available/occupied).
        username (str): Username.
    """

    def __init__(self, username, conn):
        """Constructor method.

        Args:
            username (str): Username.
            conn (socket.socket): Connection for communicating with user.
        """

        self.username = username
        self.conn = conn
        self.status = 'available'

    def switch_status(self):
        """Switching user status.
        """

        if self.status == 'available':
            self.status = 'occupied'
        else:
            self.status = 'available'
