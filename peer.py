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
        call_block (bool): Blocks user from calling other users when true.
        conn_lst (list): Active connections.
        gui_evt_conn (socket.socket): UDP connection with GUI component of app.
        in_call (bool): Whether the user is in a call.
        logged_in (bool): Whether the peer has logged as a user.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once. (static)
        recv_buf (TYPE): Description
        SERVER_ADDR (tuple): Server address info. (static)
        server_conn (socket.socket): Connection with server.
        task_lst (list): List of all pending tasks.
    """

    SERVER_ADDR = ('10.0.0.8', 5050)
    MAX_RECV_SIZE = 65536

    def __init__(self):
        """Constructor method.
        """

        self.server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.gui_evt_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.gui_evt_conn.bind(('localhost', 0))
        self.conn_lst = [self.server_conn, self.gui_evt_conn]
        self.task_lst = []
        self.logged_in = False
        self.call_block = False
        self.in_call = False

    def get_gui_evt_port(self):
        """Get random allocated port number of GUI event listener.

        Returns:
            int: The port number.
        """

        return self.gui_evt_conn.getsockname()[1]

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
                raw_data = conn.recv(PypePeer.MAX_RECV_SIZE)
            else:
                raw_data, addr = conn.recvfrom(PypePeer.MAX_RECV_SIZE)

            # Getting current app references
            app = App.get_running_app()
            root = app.root_sm.current_screen

            # Parsing JSON data
            data_lst = self.get_jsons(raw_data)

            # Handling messages
            for data in data_lst:
                # GUI terminated
                if data['type'] == 'terminate':
                    self.server_conn.close()
                    self.gui_evt_conn.close()
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
                            app.switch_to_main_screen(data['username'], data[
                                                      'user_info_lst'], data['call_info_lst'])
                        else:
                            root.add_bottom_lbl('Username already exists')

                # User update
                elif data['type'] == 'user_update':
                    root.user_layout.update(data['subtype'], data['username'])

                # Call update
                elif data['type'] == 'call_update':
                    root.call_layout.update(
                        data['subtype'], data['master'], **data['info'])

                # Call request/response
                elif data['type'] == 'call':
                    if data['subtype'] == 'request':
                        if not self.call_block:
                            self.call_block = True
                            if root.user_layout.user_slot_dct[data['callee']].status == 'available':
                                type = 0
                                self.task_lst.append(Task(self.server_conn, {
                                    'type': 'call',
                                    'subtype': 'request',
                                    'callee': data['callee']
                                }))
                            else:
                                type = 1
                            root.add_footer_widget(type, data['callee'])

                    elif data['subtype'] == 'participate':
                        self.call_block = True
                        root.add_footer_widget(2, data['caller'])

                    elif data['subtype'] == 'response':
                        if data['status'] == 'reject':
                            self.call_block = False
                        self.task_lst.append(Task(self.server_conn, {
                            'type': 'call',
                            'subtype': 'callee_response',
                            'caller': data['caller'],
                            'status': data['status']
                        }))
                        root.remove_footer_widget()

                    elif data['subtype'] == 'callee_response':
                        if data['status'] == 'accept':
                            root.add_footer_widget(4)
                        else:
                            self.call_block = False
                            root.add_footer_widget(3, None)

    def handle_tasks(self, write_lst):
        """Iterates over tasks and sends messages if possible.

        Args:
            write_lst (list): Writable connections list.
        """

        for task in self.task_lst:
            if task.conn in write_lst:
                task.send_msg()
                self.task_lst.remove(task)

    def get_jsons(self, raw_data):
        """Retreives JSON objects string.
         and parses it.

        Args:
            raw_data (str): Data to parse.

        Returns:
            list: Parsed JSON objects list.
        """

        decoder = json.JSONDecoder()
        json_lst = []

        while True:
            try:
                json_obj, end_index = decoder.raw_decode(raw_data)
                json_lst.append(json_obj)
                raw_data = raw_data[end_index:]
            except ValueError:
                break

        return json_lst
