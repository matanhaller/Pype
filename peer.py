"""Communication component of app.
"""

# Imports
import socket
import select
import json
import sys
from functools import partial

from kivy.app import App
from kivy.clock import Clock
from kivy.clock import mainthread
from kivy.uix.label import Label

from task import Task


class PypePeer(object):

    """App peer class.

    Attributes:
        conn_lst (list): Active connections.
        gui_event_conn (socket.socket): UDP connection with GUI component of app.
        logged_in (bool): Whether the peer has logged as a user.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once. (static)
        SERVER_ADDR (tuple): Server address info. (static)
        server_conn (socket.socket): Connection with server.
        task_lst (list): List of all pending tasks.

    Deleted Attributes:
        tasks (list): Data to be sent by peer.
    """

    SERVER_ADDR = ('10.0.0.7', 5050)
    MAX_RECV_SIZE = 65536

    def __init__(self):
        """Constructor method.
        """

        self.server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.gui_event_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.gui_event_conn.bind(('localhost', 0))
        self.conn_lst = [self.server_conn, self.gui_event_conn]
        self.task_lst = []
        self.logged_in = False

    def get_gui_event_port(self):
        """Get random allocated port number of GUI event listener.

        Returns:
            int: The port number.
        """

        return self.gui_event_conn.getsockname()[1]

    def run(self):
        """Peer mainloop method.
        """

        # Connecting to server
        try:
            self.server_conn.connect(PypePeer.SERVER_ADDR)
        except socket.error:
            pass  # (Change to something meaningful in the future)

        # Peer mainloop
        while True:
            read_lst, write_lst, err_lst = select.select(
                *((self.conn_lst,) * 3))

            # Handling readables
            self.handle_readables(read_lst)

            # Handling tasks
            self.handle_tasks(write_lst)

    def handle_readables(self, read_lst):
        """Handles all readable connections in mainloop.

        Args:
            read_lst (list): Readable connections list.
        """

        for conn in read_lst:
            if conn.type == socket.SOCK_STREAM:
                data = conn.recv(PypePeer.MAX_RECV_SIZE)
            else:
                data, addr = conn.recvfrom(PypePeer.MAX_RECV_SIZE)

            # Parsing JSON data
            data = json.loads(data)

            # GUI terminated
            if data['type'] == 'terminate':
                self.server_conn.close()
                self.gui_event_conn.close()
                sys.exit()

            # Join request/response
            if data['type'] == 'join':
                if data['subtype'] == 'request':
                    self.task_lst.append(Task(self.server_conn, {
                        'type': 'join',
                        'username': data['username']
                    }))
                elif data['subtype'] == 'response':
                    if data['status'] == 'ok':
                        self.logged_in = True
                        Clock.schedule_once(partial(App.get_running_app().switch_to_main_screen,
                                                    data['username'], data['user_lst']), 0)
                    else:
                        Clock.schedule_once(App.get_running_app().root_sm.get_screen(
                            'entry_screen').add_bottom_lbl, 0)

            # User join/leave
            if data['type'] == 'user':
                Clock.schedule_once(partial(App.get_running_app().root_sm.get_screen(
                    'main_screen').update_user_slots_layout,
                    data['subtype'], data['username']), 0)

    def handle_tasks(self, write_lst):
        """Iterates over tasks and sends messages if possible.

        Args:
            write_lst (list): Writable connections list.
        """
        for task in self.task_lst:
            if task.conn in write_lst:
                task.send_msg()
                self.task_lst.remove(task)
