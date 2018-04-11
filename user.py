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

    def __init__(self, **kwargs):
        """Constructor method.
        
        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.name = kwargs['name']
        self.conn = kwargs['conn']
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
        call.user_join(self.name)

    def leave_call(self):
        """Leaves current call.
        """

        call = self.call
        call.user_leave(self.name)
        self.call = None
