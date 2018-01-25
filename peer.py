"""Communication component of app.
"""

# Imports
import socket
import select
import json
import sys
from sets import Set
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
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once. (static)
        SERVER_ADDR (tuple): Server address info. (static)
        server_conn (socket.socket): Connection with server.
        task_lst (list): List of all pending tasks.

    Deleted Attributes:
        tasks (list): Data to be sent by peer.
    """

    SERVER_ADDR = ('192.168.101.122', 5050)
    MAX_RECV_SIZE = 65536

    def __init__(self):
        """Constructor method.
        """

        self.server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.gui_event_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.gui_event_conn.bind(('localhost', 0))
        self.conn_lst = [self.server_conn, self.gui_event_conn]
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

        # Connecting to server
        try:
            self.server_conn.connect(PypePeer.SERVER_ADDR)
        except socket.error:
            pass  # (Change to something meaningful in the future)

        # Peer mainloop
        while True:
            read_set, write_set, err_set = select.select(
                *((self.conn_lst,) * 3))
            read_set, write_set, err_set = Set(
                read_set), Set(write_set), Set(err_set)

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
                        pass  # (Change to something meaningful in the future)
                    else:
                        msg = 'Username already exists'
                        Clock.schedule_once(
                            partial(self.add_bottom_label_entry_screen, msg), 0)

    def handle_tasks(self, write_set):
        """Iterates over tasks and sends messages if possible.

        Args:
            write_set (Set): Writable connections set.
        """
        for task in self.task_lst:
            if task.conn in write_set:
                task.send_msg()
                self.task_lst.remove(task)

    def add_bottom_label_entry_screen(self, msg, dt):
        """Adds bottom label to entry screen (scheduled by Kivy clock).

        Args:
            msg (str): Label message.
            dt (float): Time elapsed between scheduling
             and execution (passed autiomatically).
        """

        app = App.get_running_app()
        entry_screen = app.root_sm.get_screen('entry_screen')

        if len(entry_screen.ids.main_layout.children) > 3:
            entry_screen.ids.main_layout.children[0].text = msg
        else:
            entry_screen.ids.main_layout.add_widget(Label(text=msg))
