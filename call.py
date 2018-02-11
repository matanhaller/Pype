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

    def __init__(self, user_lst, master, audio_addr, video_addr, chat_addr):
        """Constructor method.
        
        Args:
            user_lst (lst): List of all users in call.
            master (str): Call master.
            audio_addr (str): Multicast IP address of audio transmission.
            video_addr (str): Multicast IP address of video transmission.
            chat_addr (str): Multicast IP address of chat.
        """

        self.user_lst = user_lst
        self.master = master
        self.audio_addr = audio_addr
        self.video_addr = video_addr
        self.chat_addr = chat_addr

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
