"""Communication component of app.
"""

# Imports
import errno
import socket
import os
import select
import json
import sys
import struct
import pyaudio
import cv2
import base64

import ntplib

from kivy.app import App
from kivy.clock import Clock
from kivy.clock import mainthread
from kivy.uix.label import Label
from kivy.logger import Logger

from task import Task
from tracker import Tracker
from decorators import *
from webcamstream import WebcamStream


class PypePeer(object):

    """App peer class.

    Attributes:
        app_thread_running_flag (bool): Boolean indicating whether the app's Kivy thread is running.
        call_block (bool): Blocks user from calling other users when true.
        conn_lst (list): Active connections.
        gui_evt_conn (socket.socket): UDP connection with GUI component of app.
        logged_in (bool): Whether the peer has logged as a user.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once. (static)
        NTP_SERVER_ADDR (str): Description
        SERVER_ADDR (tuple): Server address info. (static)
        server_conn (socket.socket): Connection with server.
        session (Session): Session object of current call (defauls to None).
        session_buffer (list): Buffer of data yet to be updated in session.
        task_lst (list): List of all pending tasks.
        temp_audio_lst (list): Description
    """

    SERVER_ADDR = ('10.0.0.8', 5050)
    MAX_RECV_SIZE = 65536
    NTP_SERVER_ADDR = 'pool.ntp.org'

    def __init__(self):
        """Constructor method.
        """

        self.app_thread_running_flag = True
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

    @new_thread('peer_thread')
    def run(self):
        """Peer mainloop method.
        """

        # Syncing clock
        PypePeer.ntp_sync()

        # Connecting to server
        self.server_connect()

        # Peer mainloop
        while True:
            # Getting current app references
            app = App.get_running_app()
            root = app.root_sm.current_screen

            # Polling active connections
            read_lst, write_lst, err_lst = select.select(
                *((self.conn_lst,) * 3))

            # Handling readables
            self.handle_readables(read_lst)

            # Handling tasks
            self.handle_tasks(write_lst)

            # Handling call procedures
            if self.session and hasattr(root, 'session_layout'):

                # Updating statistics on screen
                self.session.update_stats()

    @staticmethod
    @new_thread('ntp_sync_thread')
    def ntp_sync():
        """Syncing the computer's clock with an external server via NTP protocol.
        """

        while True:
            try:
                # Connecting to NTP server
                ntp_client = ntplib.NTPClient()

                # Waiting for response from server
                ntp_response = ntp_client.request(PypePeer.NTP_SERVER_ADDR)
                time_obj = time.localtime(ntp_response.tx_time)

                # Updating local time
                os.system('date ' + time.strftime('%m-%d-%Y', time_obj))
                os.system('time ' + time.strftime('%H:%M:%S', time_obj))
                break
            except Exception as e:
                Logger.info('Time sync error: ' + str(e))
                continue

        Logger.info('Synced clock with network time.')

    @new_thread('server_connect_thread')
    def server_connect(self):
        """Tries connecting to server as long as it isn't connected
        """

        while self.app_thread_running_flag:
            try:
                self.server_conn.connect(PypePeer.SERVER_ADDR)
                break
            except socket.error:
                continue

        Logger.info('Connected to server.')

    @staticmethod
    def get_jsons(raw_data):
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

    def handle_readables(self, read_lst):
        """Handles all readable connections in mainloop.

        Args:
            read_lst (list): Readable connections list.
        """

        for conn in read_lst:
            try:
                if conn:
                    if conn.type == socket.SOCK_STREAM:
                        raw_data = conn.recv(PypePeer.MAX_RECV_SIZE)
                    else:
                        raw_data, addr = conn.recvfrom(PypePeer.MAX_RECV_SIZE)
            except socket.error as e:
                Logger.info('Unexpected error: ' + str(e))
                continue

            # Getting current app references
            app = App.get_running_app()
            root = app.root_sm.current_screen

            # Parsing JSON data
            data_lst = PypePeer.get_jsons(raw_data)

            # Handling messages
            for data in data_lst:
                # GUI terminated
                if data['type'] == 'terminate':
                    self.terminate()

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
                        if data['subtype'] == 'call_remove':
                            # Leaving call if necessary
                            self.leave_call()
                        elif data['subtype'] in ['user_join', 'user_leave'] and data['name'] != root.username:
                            # Updating session display
                            self.session.update(**data)
                            if hasattr(root, 'session_layout'):
                                root.session_layout.update(**data)
                            else:
                                self.session_buffer.append(data)

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
                                self.start_call(**data)
                        else:
                            root.add_footer_widget(mode='rejected_call')
                        self.call_block = False

                # Session messages
                elif data['type'] == 'session':
                    # Leaving call
                    if data['subtype'] == 'leave':
                        self.task_lst.append(Task(self.server_conn, data))
                        self.leave_call()

                    elif self.session:
                        # Sending chat message
                        if data['subtype'] == 'self_chat':
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

    def start_call(self, **kwargs):
        """Procedures to be done when starting call.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        root = App.get_running_app().root_sm.current_screen

        # Creating new session object
        self.session = Session(
            task_lst=self.task_lst, **kwargs)

        # Switching app interface to session layout
        root.switch_to_session_layout(**kwargs)

        # Adding chat multicast conn to connection list
        self.conn_lst.append(self.session.chat_conn)

        # Waiting for session layout switch to be complete
        while not hasattr(root, 'session_layout'):
            pass

        # Creating list for temporary storing of received audio packets.
        self.temp_audio_lst = []

        # Starting audio and video packets receiving threads
        self.session.audio_recv_loop()
        self.session.video_recv_loop()

        # Starting audio and video packet sending threads
        self.session.audio_send_loop()
        self.session.video_send_loop()

        Logger.info('Call started.')

    def leave_call(self):
        """Procedures to be done when leaving call.
        """

        root = App.get_running_app().root_sm.current_screen
        username = root.username

        # Plotting statistics graph
        for user in self.session.user_lst:
            if user != username:
                self.session.video_stat_dct[user].plot_stats()

        # Removing chat conn from connection list
        self.conn_lst.remove(self.session.chat_conn)

        # Closing session
        self.session.terminate()
        self.session = None

        # Switching to call layout
        root.switch_to_call_layout()

        Logger.info('Call ended.')

    def terminate(self):
        """A series of procedures to be done on GUI terminate.
        """

        # Signalling that GUI has terminated
        self.app_thread_running_flag = False

        # Leaving active call (if there is)
        if self.session and hasattr(self.session, 'video_capture'):
            self.leave_call()

        # Closing active connections
        self.server_conn.close()
        self.gui_evt_conn.close()

        # Exiting app
        sys.exit()


class Session(object):

    """Class used for management of current call.

    Attributes:
        audio_addr (str): Multicast address used for audio transmission.
        AUDIO_CHUNK_SIZE (int): The number of audio samples in a single read.
        audio_conn (socket.socket): UDP connection used for audio transmission.
        audio_input_stream (pyaudio.Stream): Audio input stream object.
        audio_interface (pyaudio.PyAudio): Interface for accessing audio methods.
        AUDIO_MULTICAST_PORT (int): Multicast port allocated for audio transmission.
        audio_output_stream (pyaudio.Stream): Audio output stream object.
        AUDIO_SAMPLING_RATE (int): Audio sampling rate.
        audio_seq (int): Audio sequence number.
        audio_stat_dct (dict): Audio statistics dictionary.
        chat_addr (str): Multicast address used for chat messaging.
        chat_conn (socket.socket): UDP connection used for chat messaging.
        CHAT_MULTICAST_PORT (int): Multicast port allocated for video transmission.
        INITIAL_SENDING_RATE (int): Initial sending rate.
        keep_sending_flag (bool): Flag indicating whether to keep sending audio and video packets.
        master (str): Currrent call master.
        MULTICAST_CONN_TIMEOUT (int): Timeout of audio and video multicast connections.
        task_lst (list): List of tasks to send (the same one that PypePeer has).
        user_lst (list): List of users in call.
        video_addr (str): Multicast address used for video transmission.
        VIDEO_COMPRESSION_QUALITY (int): Value indicating the quality of the resultant frame
         after JPEG compression.
        video_conn (socket.socket): UDP connection used for video transmission.
        VIDEO_MULTICAST_PORT (int): Multicast port allocated for chat messaging.
        video_seq (int): Video sequence number.
        video_stat_dct (dict): Video statistics dictionary.
        webcam_stream (WebcamStream): Live webcam stream object.
    """

    AUDIO_MULTICAST_PORT = 8192
    VIDEO_MULTICAST_PORT = 8193
    CHAT_MULTICAST_PORT = 8194
    MULTICAST_CONN_TIMEOUT = 1
    VIDEO_COMPRESSION_QUALITY = 20
    AUDIO_SAMPLING_RATE = 8000  # 8 KHz
    AUDIO_CHUNK_SIZE = 1024
    INITIAL_SENDING_RATE = 30  # 30 fps

    def __init__(self, **kwargs):
        """Constructor method.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.master = kwargs['master']
        self.user_lst = kwargs['user_lst']

        self.audio_addr = kwargs['addrs']['audio']
        self.video_addr = kwargs['addrs']['video']
        self.chat_addr = kwargs['addrs']['chat']

        # Creating connections for each multicast address
        self.audio_conn = self.create_multicast_conn(
            self.audio_addr, Session.AUDIO_MULTICAST_PORT)
        self.audio_conn.settimeout(Session.MULTICAST_CONN_TIMEOUT)
        self.video_conn = self.create_multicast_conn(
            self.video_addr, Session.VIDEO_MULTICAST_PORT)
        self.video_conn.settimeout(Session.MULTICAST_CONN_TIMEOUT)
        self.chat_conn = self.create_multicast_conn(
            self.chat_addr, Session.CHAT_MULTICAST_PORT)

        # Initializing audio and video sequence numbers
        self.audio_seq = 0
        self.video_seq = 0

        # Initializing audio and video statistics dictionaries
        self.audio_stat_dct = {user: Tracker() for user in self.user_lst}
        self.video_stat_dct = {user: Tracker() for user in self.user_lst}

        # Initializing audio stream
        self.audio_interface = pyaudio.PyAudio()
        self.audio_input_stream = self.audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=Session.AUDIO_SAMPLING_RATE,
            input=True)
        self.audio_output_stream = self.audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=Session.AUDIO_SAMPLING_RATE,
            output=True)

        # Creating webcam stream
        self.webcam_stream = WebcamStream()

        self.keep_sending_flag = True

        self.task_lst = kwargs['task_lst']

    def update(self, **kwargs):
        """Updates session when changes in call occur.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # User join
        if kwargs['subtype'] == 'user_join':
            self.user_lst.append(kwargs['name'])
            self.audio_stat_dct[kwargs['name']] = Tracker()
            self.video_stat_dct[kwargs['name']] = Tracker()

        # User leave
        elif kwargs['subtype'] == 'user_leave':
            self.user_lst.remove(kwargs['name'])
            if 'new_master' in kwargs:
                self.master = kwargs['new_master']
            del self.audio_stat_dct[kwargs['name']]
            del self.video_stat_dct[kwargs['name']]

    def create_multicast_conn(self, addr, port):
        """Creates UDP socket and adds it to multicast group.

        Args:
            addr (str): IP address of multicast group.
            port (int): Port number of multicast group.

        Returns:
            socket.socket: UDP socket connected to multicast group.
        """

        # Creating socket object and binding to designated port
        conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        conn.bind(('', port))

        # Joining multicast group
        byte_addr = socket.inet_aton(addr)
        group_info = struct.pack('4sL', byte_addr, socket.INADDR_ANY)
        conn.setsockopt(socket.IPPROTO_IP,
                        socket.IP_ADD_MEMBERSHIP, group_info)

        # Setting message TTL to 1 i.e. messages stay in local network
        ttl = struct.pack('b', 1)
        conn.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

        return conn

    @new_thread('audio_send_thread')
    def audio_send_loop(self):
        """Loop for sending audio packets in parallel.
        """

        while self.keep_sending_flag:
            self.send_audio()

    @new_thread('audio_recv_thread')
    def audio_recv_loop(self):
        """Receives and plays audio in parallel.
        """

        while self.keep_sending_flag:
            # Receiving and parsing new audio packets
            try:
                raw_data, addr = self.audio_conn.recvfrom(
                    PypePeer.MAX_RECV_SIZE)
            except socket.timeout:
                continue
            data_lst = PypePeer.get_jsons(raw_data)

            # Decoding and playing audio packets
            username = App.get_running_app().root_sm.current_screen.username
            for data in data_lst:
                if data['src'] != username and data['src'] != self.master:
                    audio_chunk = base64.b64decode(data['chunk'])
                    self.audio_output_stream.write(audio_chunk)

    def send_audio(self):
        """Sends audio packet to multicast group.
        """

        # Reading a chunk of audio samples from stream
        audio_chunk = self.audio_input_stream.read(Session.AUDIO_CHUNK_SIZE)

        # Composing audio packet
        username = App.get_running_app().root_sm.current_screen.username
        audio_msg = {
            'type': 'session',
            'subtype': 'audio',
            'mode': 'content',
            'timestamp': None,
            'src': username,
            'seq': self.audio_seq,
            'chunk': base64.b64encode(audio_chunk)
        }

        # Incrementing audio packet sequence number
        self.audio_seq += 1

        # Sending audio packet
        Task(self.audio_conn, audio_msg,
             (self.audio_addr, Session.AUDIO_MULTICAST_PORT)).send_msg()

    @new_thread('video_send_thread')
    def video_send_loop(self):
        """Loop for sending video packets in parallel.
        """

        while self.keep_sending_flag:
            self.send_video()

    @new_thread('video_recv_thread')
    def video_recv_loop(self):
        """Receives and displays video frames in parallel.
        """

        while self.keep_sending_flag:
            # Receiving and parsing new video packets
            try:
                raw_data, addr = self.video_conn.recvfrom(
                    PypePeer.MAX_RECV_SIZE)
            except socket.timeout:
                continue
            data_lst = PypePeer.get_jsons(raw_data)

            # Displaying new frames on screen
            for data in data_lst:
                root = App.get_running_app().root_sm.current_screen
                root.session_layout.video_layout.update_frame(
                    **data)

    @rate_limit(INITIAL_SENDING_RATE)
    def send_video(self):
        """Sends video packet to multicast group.
        """

        # Reading video frame from webcam
        frame = self.webcam_stream.read()

        # Compressing frame into JPEG format
        ret, encoded_frame = cv2.imencode(
            '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY,
                            Session.VIDEO_COMPRESSION_QUALITY])

        if ret:
            # Composing video packet
            username = App.get_running_app().root_sm.current_screen.username
            video_msg = {
                'type': 'session',
                'subtype': 'video',
                'mode': 'content',
                'timestamp': None,
                'src': username,
                'seq': self.video_seq,
                'frame': base64.b64encode(encoded_frame)
            }

            # Incrementing video packet sequence number
            self.video_seq += 1

            # Sending video packet
            Task(self.video_conn, video_msg,
                 (self.video_addr, Session.VIDEO_MULTICAST_PORT)).send_msg()

    def send_chat(self, **kwargs):
        """Sends chat message to call multicast chat group.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        kwargs['subtype'] = 'chat'
        kwargs['timestamp'] = None
        self.task_lst.append(
            Task(self.chat_conn, kwargs,
                 (self.chat_addr, Session.CHAT_MULTICAST_PORT)))

    @rate_limit(1)
    def update_stats(self):
        """Updates statistics on screen.
        """

        root = App.get_running_app().root_sm.current_screen
        username = root.username
        video_display_dct = root.session_layout.video_layout.video_display_dct
        for user in self.user_lst:
            if user != username:
                stats = self.video_stat_dct[user].stat_dct
                video_display_dct[user].stat_lbl.update(**stats)

    def terminate(self):
        """A series of operations to be done before session terminates.
        """

        # Signalling video and audio sending threads to terminate
        self.keep_sending_flag = False

        # Waiting for active threads to return
        for thread in threading.enumerate():
            if thread.name in ['audio_send_thread', 'audio_recv_thread',
                               'video_send_thread', 'video_recv_thread']:
                thread.join()

        # Stopping self camera capture
        root = App.get_running_app().root_sm.current_screen
        if hasattr(root, 'session_layout'):
            root.session_layout.video_layout.ids.self_cap.play = False

        # Closing active connections
        for conn in [self.audio_conn, self.video_conn, self.chat_conn]:
            conn.close()

        # Closing audio streams
        self.audio_input_stream.stop_stream()
        self.audio_input_stream.close()
        self.audio_output_stream.stop_stream()
        self.audio_output_stream.close()
        self.audio_interface.terminate()

        # Terminating webcam stream
        self.webcam_stream.terminate()
