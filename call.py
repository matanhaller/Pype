"""Call class file.
"""


class Call(object):

    """App call class.

    Attributes:
        addr_dct (dict): Dictionary of audio, video and chat multicast
         addresses allocated for call.
        master (str): Call master.
        user_lst (lst): List of all users in call.
    """

    def __init__(self, addr_dct):
        """Constructor method.

        Args:
            addr_dct (dct): Dictionary of audio, video and chat multicast addresses.
        """

        self.master = None
        self.addr_dct = addr_dct
        self.user_lst = []

    def user_join(self, username):
        """Adding user to call.

        Args:
            username (str): Username of joining user.
        """

        # Making user master if he's first in call
        if not self.user_lst:
            self.master = username

        self.user_lst.append(username)

    def user_leave(self, username):
        """Removing user from call.

        Args:
            username (str): Username of leaving user.
        """

        self.user_lst.remove(username)

        # Switching call master if the leaving user is the master
        if username == self.master:
            if self.user_lst:
                self.master = self.user_lst[0]
