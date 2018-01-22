"""Communication component of app.
"""

# Imports
import socket
import select
import json
from sets import Set

from kivy.app import App

from task import Task


class PypePeer(object):

    """App peer class.

    Attributes:
        connections (list): Active connections.
        gui_event_conn (socket.socket): UDP connection with GUI component of app.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once.
        SERVER_ADDR (tuple): Server address info.
        server_conn (socket.socket): Connection with server.
        task_lst (list): Description

    Deleted Attributes:
        tasks (list): Data to be sent by peer.
    """

    SERVER_ADDR = ('10.0.0.17', 5050)
    MAX_RECV_SIZE = 65536

    def __init__(self):
        """Constructor method.
        """

        self.server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.gui_event_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.gui_event_conn.bind(('localhost', 0))
        self.connections = [self.server_conn, self.gui_event_conn]
        self.task_lst = []

    def get_gui_event_port(self):
        """Get random allocated port number of GUI event listener.

        Returns:
            int: The port number.
        """

        return self.gui_event_conn.getsockname()[1]

    def run(self):
        """Peer mainloop method.
        """

        app = App.get_running_app()

        # Connecting to server
        try:
            self.server_conn.connect(Peer.SERVER_ADDR)
        except socket.error:
            pass  # (Change to something meaningful in the future)

        # Peer mainloop
        while True:
            read_set, write_set, err_set = select.select(
                *((self.connections,) * 3))
            read_set, write_set, err_set = set(
                read_set), set(write_set), set(err_set)

            # Handling readables
            self.handle_readables(read_set)

            # Handling tasks
            self.handle_tasks(write_set)

    def handle_readables(self, read_set):
        """Handles all readable connections in mainloop.

        Args:
            read_set (Set): Readable connections set.
        """

        for conn in read_set:
            data, addr = conn.recvfrom(Peer.MAX_RECV_SIZE)

            # Parsing JSON data
            data = json.loads(data)

            # Join request/response
            if data['type'] == 'login':
                if data['subtype'] == 'request':
                    self.task_lst.add(Task(self.server_conn, {
                        'type': 'join'
                        'username': data['username']
                    }))
                elif data['subtype'] == 'response':
                    pass

    def handle_tasks(self, write_set):
        """Iterates over tasks and sends messages if possible.

        Args:
            write_set (Set): Writable connections set.
        """
        for task in self.task_lst:
            if task.conn in write_set:
                task.send_msg()
                write_set.remove(task)
