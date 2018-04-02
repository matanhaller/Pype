"""Call class file.
"""


class Call(object):

    """App call class.

    Attributes:
        audio_addr (str): Multicast IP address of audio transmission.
        chat_addr (str): Multicast IP address of chat.
        master (str): Call master.
        user_lst (lst): List of all users in call.
        video_addr (str): Multicast IP address of video transmission.
    """

    def __init__(self, **kwargs):
        """Constructor method.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.master = None
        self.audio_addr = kwargs['audio_addr']
        self.video_addr = kwargs['video_addr']
        self.chat_addr = kwargs['chat_addr']
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
