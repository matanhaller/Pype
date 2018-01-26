"""Communication component of app.
"""

# Imports
import socket
import select
import json
import sys

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
                        pass  # (Change to something meaningful in the future)
                    else:
                        Clock.schedule_once(self.add_bottom_lbl_entry_screen, 0)

    def handle_tasks(self, write_lst):
        """Iterates over tasks and sends messages if possible.
        
        Args:
            write_lst (list): Writable connections list.
        """
        for task in self.task_lst:
            if task.conn in write_lst:
                task.send_msg()
                self.task_lst.remove(task)

    def add_bottom_lbl_entry_screen(self, dt):
        """Adds bottom label to entry screen (scheduled by Kivy clock).
        
        Args:
            dt (float): Time elapsed between scheduling
             and execution (passed autiomatically).
        """

        app = App.get_running_app()
        entry_screen = app.root_sm.get_screen('entry_screen')
        err_msg = 'Username already exists'

        # Checking if there already exists a bottom label
        if hasattr(entry_screen, 'bottom_lbl'):
            entry_screen.bottom_lbl.text = err_msg
        else:
            entry_screen.bottom_lbl = Label(text=err_msg)
            entry_screen.ids.main_layout.add_widget(entry_screen.bottom_lbl)
