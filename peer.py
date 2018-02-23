"""Communication component of app.
"""

# Imports
import socket
import select
import json
import sys
import struct
import time

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
        logged_in (bool): Whether the peer has logged as a user.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once. (static)
        SERVER_ADDR (tuple): Server address info. (static)
        server_conn (socket.socket): Connection with server.
        session (Session): Session object of current call (defauls to None).
        session_buffer (list): Buffer of data yet to be updated in session.
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
        self.session = None
        self.session_buffer = []

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
                            'name': data['name']
                        }))

                    elif data['subtype'] == 'response':
                        if data['status'] == 'ok':
                            self.logged_in = True
                            app.switch_to_main_screen(**data)
                        else:
                            root.add_bottom_lbl('Username already exists')

                # User update
                elif data['type'] == 'user_update':
                    root.user_layout.update(**data)

                # Call update
                elif data['type'] == 'call_update':
                    root.call_layout.update(**data)
                    if self.session and data['master'] == self.session.master:
                        # Closing call if necessary
                        if data['subtype'] == 'call_remove':
                            # Removing multicast conns from connection list
                            for conn in [self.session.audio_conn, self.session.video_conn, self.session.chat_conn]:
                                self.conn_lst.remove(conn)
                            self.session = None
                            root.switch_to_call_layout()
                        else:
                            if hasattr(root, 'session_layout') and data['subtype'] != 'call_add':
                                self.session.update(**data)
                                root.session_layout.update(**data)
                            else:
                                self.session_buffer.append(data)
                            # Leaving call
                            if data['subtype'] == 'call_remove':
                                root.switch_to_call_layout()

                # Call request/response
                elif data['type'] == 'call':
                    if data['subtype'] == 'request':
                        if not self.call_block:
                            if not data['group'] and root.user_layout.user_slot_dct[data['callee']].status == 'in call':
                                self.call_block = False
                                mode = 'user_not_available'
                            else:
                                self.call_block = True
                                mode = 'pending_call'
                                self.task_lst.append(Task(self.server_conn, {
                                    'type': 'call',
                                    'subtype': 'request',
                                    'callee': data['callee']
                                }))
                            root.add_footer_widget(mode=mode, **data)

                    elif data['subtype'] == 'participate':
                        self.call_block = True
                        root.add_footer_widget(mode='call', **data)

                    elif data['subtype'] == 'response':
                        if data['status'] == 'reject':
                            self.call_block = False
                            root.remove_footer_widget()
                        self.task_lst.append(Task(self.server_conn, {
                            'type': 'call',
                            'subtype': 'callee_response',
                            'caller': data['caller'],
                            'status': data['status']
                        }))

                    elif data['subtype'] == 'callee_response':
                        if data['status'] == 'accept':
                            if hasattr(root, 'session_layout'):
                                if hasattr(root, 'footer_widget'):
                                    root.remove_footer_widget()
                            else:
                                self.session = Session(
                                    task_lst=self.task_lst, **data)
                                root.switch_to_session_layout(**data)

                                # Adding multicast conns to connection list
                                for conn in [self.session.audio_conn, self.session.video_conn, self.session.chat_conn]:
                                    self.conn_lst.append(conn)
                        else:
                            root.add_footer_widget(mode='rejected_call')
                        self.call_block = False

                # Session messages
                elif data['type'] == 'session':
                    # Leaving call
                    if data['subtype'] == 'leave':
                        self.task_lst.append(Task(self.server_conn, data))

                    # Sending chat message
                    elif data['subtype'] == 'self_chat':
                        self.session.send_chat(**data)

                    # Receiving chat message
                    elif data['subtype'] == 'chat':
                        if data['src'] == root.username:
                            data['src'] = 'You'
                        root.session_layout.chat_layout.add_msg(**data)

                # Updating session layout with data from buffer
                if hasattr(root, 'session_layout'):
                    while self.session_buffer:
                        kwargs = self.session_buffer.pop()
                        root.session_layout.update(**kwargs)

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
        """Retreives JSON objects string and parses it.

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


class Session(object):

    """Class used for management of current call.

    Attributes:
        audio_addr (str): Multicast address used for audio transmission.
        audio_conn (socket.socket): UDP connection used for audio transmission.
        audio_rate (int): Audio transmission rate (measured in packet/sec).
        chat_addr (str): Multicast address used for chat messaging.
        chat_conn (socket.socket): UDP connection used for chat messaging.
        master (str): Currrent call master.
        MULTICAST_PORT (int): Port for multicast communication.
        task_lst (list): List of tasks to send (the same one that PypePeer has).
        user_lst (list): List of users in call.
        video_addr (str): Multicast address used for video transmission.
        video_conn (socket.socket): UDP connection used for video transmission.
        video_rate (int): Video transmission rate (measured in packet/sec).
    """

    MULTICAST_PORT = 8192

    def __init__(self, **kwargs):
        """Constructor method.

        Args:
            **kwargs: Keyword arguments supplied by dictionary.
        """

        self.master = kwargs['master']
        self.user_lst = kwargs['user_lst']

        self.audio_addr = kwargs['addrs']['audio']
        self.video_addr = kwargs['addrs']['video']
        self.chat_addr = kwargs['addrs']['chat']

        # Creating connections for each multicast address
        self.audio_conn = self.create_multicast_conn(self.audio_addr)
        self.video_conn = self.create_multicast_conn(self.video_addr)
        self.chat_conn = self.create_multicast_conn(self.chat_addr)

        # Setting default audio and video  transmission rates
        self.audio_rate = 30
        self.video_rate = 30

        self.task_lst = kwargs['task_lst']

    def update(self, **kwargs):
        """Updates session when changes in call occur.

        Args:
            **kwargs: Keyword arguments supplied in dictioanry form.
        """

        # User join
        if kwargs['subtype'] == 'user_join':
            self.user_lst.append(kwargs['name'])

        # User leave
        elif kwargs['subtype'] == 'user_leave':
            self.user_lst.remove(kwargs['name'])
            if 'new_master' in kwargs:
                self.master = kwargs['new_master']

    def create_multicast_conn(self, addr):
        """Creates UDP socket and adds it to multicast group.

        Args:
            addr (str): IP address of multicast group.

        Returns:
            socket.socket: UDP socket connected to multicast group.
        """

        # Creating socket object and binding to designated port
        conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        conn.bind(('', Session.MULTICAST_PORT))

        # Joining multicast group
        byte_addr = socket.inet_aton(addr)
        group_info = struct.pack('4sL', byte_addr, socket.INADDR_ANY)
        conn.setsockopt(socket.IPPROTO_IP,
                        socket.IP_ADD_MEMBERSHIP, group_info)

        # Setting message TTL to 1 i.e. messages stay in local network
        ttl = struct.pack('b', 1)
        conn.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

        return conn

    def send_chat(self, **kwargs):
        """Sends chat message to call multicast chat group.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        kwargs['subtype'] = 'chat'
        kwargs['timestamp'] = None
        self.task_lst.append(Task(self.chat_conn, kwargs,
                                  (self.chat_addr, Session.MULTICAST_PORT)))
