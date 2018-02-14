"""User class file.
"""


class User(object):

    """App user class.

    Attributes:
        call (Call): The call in which the user is in (None if he's not).
        conn (socket.socket): Connection for communicating with user.
        name (str): Username.
        status (str): Whether the user is in call (available/in call).
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

    def join_call(self, call):
        """Adds user to call.

        Args:
            call (Call): Call to join.
        """

        self.call = call
        self.call.user_join(user.name)

    def leave_call(self):
        """Leaves current call.
        """

        self.call.user_leave(user_name)
        self.call = None
