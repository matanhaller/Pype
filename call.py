"""Call class file.
"""


class Call(object):

    """App call class.

    Attributes:
        master (str): Call master.
        user_lst (lst): List of all users in call.
    """

    def __init__(self, user_lst, master):
        """Constructor method.

        Args:
            user_lst (lst): List of all users in call.
            master (str): Call master.
        """

        self.user_lst = user_lst
        self.master = master

    def user_join(username):
        """Adding user to call.

        Args:
            username (str): Username of joining user.
        """

        self.user_lst.append(username)

    def user_leave(username):
        """Removing user from call.

        Args:
            username (str): Username of leaving user.
        """

        self.user_lst.remove(username)

        # Switching call master if the leaving user is the master
        if username == self.master:
            self.master = self.user_lst[0]
