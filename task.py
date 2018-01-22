"""Task class file.
"""

# Imports
import json
import socket


class Task(object):

    """Task that communication component should handle.

    Attributes:
        conn (socket.socket): The connection to which the message
         should be sent.
        dst (tuple): Destination address (for UDP sockets only).
        msg (dict): Message to be sent (in JSON format).
    """

    def __init__(self, conn, msg, dst=None):
        """Constructor method.

        Args:
            conn (socket.socket): The connection to which the message
             should be sent.
            msg (dict): Message to be sent (in JSON format).
            dst (tuple, optional): Destination address (for UDP sockets only).
        """
        self.conn = conn
        self.msg = msg
        if dst:
            self.dst = dst

    def send_msg(self):
        """Sends message to connection.
        """

        str_msg = json.dumps(self.msg)
        # For TCP sockets
        if self.conn.type == socket.SOCK_STREAM:
            self.conn.sendall(str_msg)
        # For UDP sockets
        else:
            self.conn.sendto(str_msg, self.dst)
