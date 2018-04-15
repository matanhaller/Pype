"""Communication component of app.
"""

# Imports
import ConfigParser
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
import random
from collections import deque

import ntplib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA

from kivy.app import App
from kivy.clock import Clock
from kivy.clock import mainthread
from kivy.uix.label import Label
from kivy.logger import Logger

from configparser import get_option
from task import Task
from tracker import Tracker
from decorators import *
from webcamstream import WebcamStream


class PypePeer(object):

    """App peer class.

    Attributes:
        app_thread_running_flag (bool): Flag indicating whether the app's Kivy thread is running.
        call_block (bool): Blocks user from calling other users when true.
        conn_lst (list): Active connections.
        gui_evt_conn (socket.socket): UDP connection with GUI component of app.
        logged_in (bool): Whether the peer has logged as a user.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once. (static)
        NTP_SERVER_ADDR (str): Address of an Israeli NTP server.
        plot_stats_flag (bool): Flag used for signalling that statistics are ready to be plotted.
        reset_frame_evt (ClockEvent): Frame resetting event called when a user stops transmitting video.
        SERVER_ADDR (tuple): Server address info. (static)
        server_conn (socket.socket): Connection with server.
        session (Session): Session object of current call (defauls to None).
        session_buffer (list): Buffer of data yet to be updated in session.
        task_lst (list): List of all pending tasks.
    """

    SERVER_ADDR = (get_option('server_ip_addr'), 5050)
    MAX_RECV_SIZE = 65536  # Bytes
    NTP_SERVER_ADDR = 'il.pool.ntp.org'

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
        self.plot_stats_flag = False
        if get_option('plot_stats'):
            self.stat_plot_loop()

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
                if get_option('feedback'):
                    # Sending rate feedback to all active peers in call
                    self.session.send_optimal_rates()

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
                # Decoding first JSON object from raw data
                json_obj, end_index = decoder.raw_decode(raw_data)

                # Decrypting JSON if necessary
                if 'payload' in json_obj:
                    if self.session and hasattr(self.session, 'aes_key'):
                        json_obj = self.session.decrypt_msg(json_obj)

                        # Checking session nonce identity (to ensure integrity)
                        session_nonce = base64.b64decode(
                            json_obj['session_nonce'])
                        if session_nonce != self.session.session_nonce:
                            continue
                    else:
                        raw_data = raw_data[end_index:]
                        continue

                # Appending JSON to list
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
            # Getting current app references
            app = App.get_running_app()
            root = app.root_sm.current_screen

            try:
                # Accepting connection for AES symmetric key exchange
                if self.session and hasattr(self.session, 'crypto_conn') \
                        and conn is self.session.crypto_conn and  hasattr(root, 'username') \
                        and self.session.master == root.username:
                    new_crypto_conn, addr = conn.accept()
                    self.conn_lst.append(new_crypto_conn)
                    continue
                else:
                    if conn.type == socket.SOCK_STREAM:
                        raw_data = conn.recv(PypePeer.MAX_RECV_SIZE)
                    else:
                        raw_data, addr = conn.recvfrom(PypePeer.MAX_RECV_SIZE)

                # Closing connection if necessary
                if not raw_data:
                    self.conn_lst.remove(conn)
                    conn.close()
            except socket.error as e:
                Logger.info('Unexpected error: ' + str(e))
                break

            # Parsing JSON data
            data_lst = self.get_jsons(raw_data)

            # Handling messages
            for data in data_lst:
                # GUI terminated
                if data['type'] == 'terminate':
                    self.terminate()

                # Join request/response
                if data['type'] == 'join':
                    if data['subtype'] == 'request':
                        del data['subtype']
                        self.task_lst.append(Task(self.server_conn, data))

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
                            Logger.info('Call ended.')
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

                    # Call request
                    elif data['subtype'] == 'participate':
                        self.call_block = True
                        root.add_footer_widget(mode='call', **data)

                    # Self call response
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

                    # Callee response
                    elif data['subtype'] == 'callee_response':
                        if data['status'] == 'accept':
                            if hasattr(root, 'session_layout'):
                                if hasattr(root, 'footer_widget'):
                                    root.remove_footer_widget()
                            else:
                                self.start_call(**data)
                                Logger.info('Call started.')
                        else:
                            root.add_footer_widget(mode='rejected_call')
                        self.call_block = False

                # Session messages
                elif data['type'] == 'session':
                    # Leaving call
                    if data['subtype'] == 'leave':
                        self.task_lst.append(Task(self.server_conn, data))
                        self.leave_call()
                        Logger.info('Call ended.')

                    elif self.session:
                        # Sending chat message
                        if data['subtype'] == 'self_chat':
                            self.session.send_chat(**data)

                        # Content packets
                        elif data['subtype'] == 'content':
                            # Receiving chat message
                            if data['medium'] == 'chat':
                                if data['src'] != root.username:
                                    root.session_layout.chat_layout.add_msg(
                                        **data)

                        # Control packets
                        elif data['subtype'] == 'control':
                            # Receiving RSA public key
                            if data['mode'] == 'rsa_public_key':
                                self.session.send_crypto_info(
                                    data['key'], conn)

                            # Receiving cryptographic info from call master
                            elif data['mode'] == 'crypto_info':
                                self.session.set_crypto_info(**data)
                                Logger.info('Cryptographic info set.')

                            # Starting/stopping transmission
                            elif data['mode'] == 'self_state':
                                self.session.send_flag_dct[data['medium']] = \
                                    not self.session.send_flag_dct[
                                        data['medium']]
                                if data['medium'] == 'video':
                                    data['mode'] = 'state'
                                    self.task_lst.append(Task(self.session.control_conn_dct['video'], data, dst=(
                                        self.session.multicast_addr_dct['video'], Session.MULTICAST_CONTROL_PORT)))

                            # Other peer video transmission stop
                            elif data['mode'] == 'state':
                                if data['src'] != root.username:
                                    if data['state'] == 'down':
                                        self.reset_frame_evt = Clock.schedule_interval(
                                            lambda dt: root.session_layout.video_layout.reset_frame(
                                                data['src']), 0.1)
                                    else:
                                        self.reset_frame_evt.cancel()

                            # Sending rate feedback
                            elif data['mode'] == 'feedback':
                                if data['src'] != root.username and data['rate']:
                                    self.session.set_optimal_rate(**data)
                                    Logger.info(
                                        'New sending rate: {} fps'.format(
                                            self.session.send_video.rate))

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

        # Adding session connections to connection list
        self.conn_lst.append(self.session.content_conn_dct['chat'])
        for conn in self.session.control_conn_dct.values():
            self.conn_lst.append(conn)
        self.conn_lst.append(self.session.unicast_control_conn)
        self.conn_lst.append(self.session.crypto_conn)

        # Sending RSA public key if user isn't call master
        if root.username != kwargs['master']:
            self.session.send_rsa_public_key()
            Logger.info('Sending RSA public key.')

        # Starting audio and video packets receiving threads
        self.session.audio_recv_loop()
        for user in self.session.user_lst:
            self.session.play_audio_packets(user)
        self.session.video_recv_loop()

        # Starting audio and video packet sending threads
        self.session.audio_send_loop()
        self.session.video_send_loop()

    @new_thread('plot_thread')
    def stat_plot_loop(self):
        """Plots user audio and video statistics on a separate thread.
        """

        while self.app_thread_running_flag:
            if self.session and self.plot_stats_flag:
                self.session.plot_users_stats()
                self.plot_stats_flag = False

    def leave_call(self):
        """Procedures to be done when leaving call.
        """

        # Signalling statistics plot thread to plot call statistics
        peer = App.get_running_app().peer
        peer.plot_stats_flag = True

        # Removing active conns from connection list
        self.conn_lst.remove(self.session.content_conn_dct['chat'])
        for conn in self.session.control_conn_dct.values():
            self.conn_lst.remove(conn)
        self.conn_lst.remove(self.session.unicast_control_conn)

        # Closing session
        self.session.terminate()
        self.session = None

        # Switching to call layout
        root = App.get_running_app().root_sm.current_screen
        root.switch_to_call_layout()

    def terminate(self):
        """A series of procedures to be done on GUI terminate.
        """

        # Signalling that GUI has terminated
        self.app_thread_running_flag = False

        # Leaving active call (if there is)
        if self.session:
            self.leave_call()
            Logger.info('Call ended.')

        # Closing active connections
        self.server_conn.close()
        self.gui_evt_conn.close()

        # Exiting app
        sys.exit()


class Session(object):

    """Class used for management of current call.

    Attributes:
        aes_iv (str): Initialization vector for AES encryption and decryption.
        AES_IV_SIZE (int): Size of AES initialization vector.
        aes_key (str): Symmetric key for AES encryption and decryption.
        AES_KEY_SIZE (int): Size of AES symmetric key.
        AUDIO_CHUNK_SIZE (int): The number of audio samples in a single read.
        audio_deque_dct (dict): Dictionary of thread-safe queues for transfering audio packets.
        audio_input_stream (pyaudio.Stream): Audio input stream object.
        audio_interface (pyaudio.PyAudio): Interface for accessing audio methods.
        audio_output_stream_dct (dict): Dictionary containing audio streams for each user in call.
        AUDIO_SAMPLING_RATE (int): Audio sampling rate.
        audio_stat_dct (dict): Audio statistics dictionary.
        clr (list): Username + optimal sending rate of CLR (current limiting receiver).
        content_conn_dct (dict): Dictionary of connections used for content transmission.
        control_conn_dct (dict): Dictionary of connections used for control transmission.
        crypto_conn (socket.socket): TCP connection used for exchanging cyptographic info.
        INITIAL_SENDING_RATE (int): Initial sending rate.
        INTIAL_SEQ_RANGE (int): Range of possible randomly generated initial sequence numbers.
        keep_sending_flag (bool): Flag indicating whether to keep sending audio and video packets.
        master (str): Currrent call master.
        multicast_addr_dct (dict): Dictionary of multicast addresses allocated by server.
        MULTICAST_CONN_TIMEOUT (int): Timeout of audio and video multicast connections.
        MULTICAST_CONTENT_PORT (int): Port allocated for content transmission (audio, video and chat).
        MULTICAST_CONTROL_PORT (int): Port allocated for control transmission (feedback, cryptographic info etc.).
        rsa_keypair (RSAobj): RSA keypair object used for assymetric encryption and decryption.
        RSA_KEYS_SIZE (int): Size of RSA public and private keys.
        send_flag_dct (dict): Dictionary with boolean values indicating whether to transmit audio and video packets.
        seq_dct (dict): Dictionary of audio and video sequence numbers.
        session_nonce (str): Nonce generated at the beginning of call and keeps data integrity.
        SESSION_NONCE_SIZE (int): Size of session nonce.
        task_lst (list): List of tasks to send (the same one that PypePeer has).
        unicast_control_conn (socket.socket): Unicast connection used for control transmission.
        user_addr_dct (dict): Dictioanry mapping each user to its IP address.
        user_lst (list): List of users in call.
        VIDEO_COMPRESSION_QUALITY (int): Value indicating the quality of the resultant frame
         after JPEG compression.
        video_stat_dct (dict): Video statistics dictionary.
        webcam_stream (WebcamStream): Live webcam stream object.

    Deleted Attributes:
        plot_stats_flag (bool): Description
        audio_output_stream (pyaudio.Stream): Audio output stream object.
    """

    MULTICAST_CONTROL_PORT = 8192
    MULTICAST_CONTENT_PORT = 8193
    MULTICAST_CONN_TIMEOUT = 1
    INTIAL_SEQ_RANGE = 65536
    VIDEO_COMPRESSION_QUALITY = 50
    AUDIO_SAMPLING_RATE = 16000  # Hz
    AUDIO_CHUNK_SIZE = 1024  # Samples
    INITIAL_SENDING_RATE = 30  # Fps
    AES_KEY_SIZE = 32  # Bytes
    AES_IV_SIZE = 16  # Bytes
    RSA_KEYS_SIZE = 1024  # Bits
    SESSION_NONCE_SIZE = 8  # Bytes

    def __init__(self, **kwargs):
        """Constructor method.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.task_lst = kwargs['task_lst']

        self.master = kwargs['master']
        self.user_lst = kwargs['user_lst']
        self.user_addr_dct = kwargs['peer_addrs']

        # Creating connection for cryptographic info sharing
        self.crypto_conn = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.crypto_conn.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        username = App.get_running_app().root_sm.current_screen.username
        if username == kwargs['master']:
            # Initializing AES symmetric key and initialization vector
            self.aes_key = os.urandom(Session.AES_KEY_SIZE)
            self.aes_iv = os.urandom(Session.AES_IV_SIZE)
            Logger.info('Cryptographic info set.')

            # Creating session nonce
            self.session_nonce = os.urandom(Session.SESSION_NONCE_SIZE)

            self.crypto_conn.bind(('', Session.MULTICAST_CONTROL_PORT))
            self.crypto_conn.listen(1)
        else:
            # If user isn't the call master, create RSA keypair for receiving
            # cryptographic info
            Logger.info('Creating RSA keypair.')
            self.rsa_keypair = RSA.generate(Session.RSA_KEYS_SIZE)
            Logger.info('RSA keypair generation complete.')

            self.crypto_conn.connect(
                (self.user_addr_dct[self.master], Session.MULTICAST_CONTROL_PORT))

        # Storing multicast addresses allocated by server
        self.multicast_addr_dct = kwargs['addrs']

        # Creating content connections for each multicast address
        self.content_conn_dct = {medium: self.create_multicast_conn(self.multicast_addr_dct[medium],
                                                                    Session.MULTICAST_CONTENT_PORT)
                                 for medium in self.multicast_addr_dct}
        for medium in ['audio', 'video']:
            self.content_conn_dct[medium].settimeout(
                Session.MULTICAST_CONN_TIMEOUT)

        # Creating control connections for each multicast address
        self.control_conn_dct = {medium: self.create_multicast_conn(self.multicast_addr_dct[medium],
                                                                    Session.MULTICAST_CONTROL_PORT)
                                 for medium in self.multicast_addr_dct}

        # Creating unicast control conn for sending and receiving feedback
        self.unicast_control_conn = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM)
        self.unicast_control_conn.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.unicast_control_conn.bind(('', Session.MULTICAST_CONTROL_PORT))

        # Initializing audio, video and feedback sequence numbers with random
        # values
        self.seq_dct = {
            'audio': random.randint(0, Session.INTIAL_SEQ_RANGE),
            'video': random.randint(0, Session.INTIAL_SEQ_RANGE),
            'feedback': random.randint(0, Session.INTIAL_SEQ_RANGE)
        }

        # Initializing audio and video statistics dictionaries
        self.audio_stat_dct = {user: Tracker() for user in self.user_lst}
        self.video_stat_dct = {user: Tracker() for user in self.user_lst}

        # Initializing audio streams
        self.audio_interface = pyaudio.PyAudio()
        self.audio_input_stream = self.audio_interface.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=Session.AUDIO_SAMPLING_RATE,
            input=True)
        self.audio_output_stream_dct = {user: self.audio_interface.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=Session.AUDIO_SAMPLING_RATE,
            output=True) for user in self.user_lst}

        # Initializing audio deques
        self.audio_deque_dct = {user: deque() for user in self.user_lst}

        # Creating webcam stream
        self.webcam_stream = WebcamStream()

        self.keep_sending_flag = True
        self.send_flag_dct = {
            'audio': True,
            'video': True
        }

        # Initializing CLR (current limit receiver) value
        self.clr = [None, None]

    def update(self, **kwargs):
        """Updates session when changes in call occur.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # User join
        if kwargs['subtype'] == 'user_join':
            user = kwargs['name']
            self.user_lst.append(user)
            self.user_addr_dct[user] = kwargs['addr']
            self.audio_stat_dct[user] = Tracker()
            self.video_stat_dct[user] = Tracker()
            self.audio_deque_dct[user] = deque()
            self.audio_output_stream_dct[user] = self.audio_interface.open(
                format=pyaudio.paInt16,
                channels=2,
                rate=Session.AUDIO_SAMPLING_RATE,
                output=True)
            self.play_audio_packets(user)

        # User leave
        elif kwargs['subtype'] == 'user_leave':
            user = kwargs['name']
            self.user_lst.remove(user)
            del self.user_addr_dct[user]
            if 'new_master' in kwargs:
                prev_master = self.master
                self.master = kwargs['new_master']

                # Creating TCP connection for cryptographic info exchange is
                # user is the new call master
                username = App.get_running_app().root_sm.current_screen.username
                if prev_master != username and self.master == username:
                    self.crypto_conn = socket.socket(
                        socket.AF_INET, socket.SOCK_STREAM)
                    self.crypto_conn.setsockopt(
                        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.crypto_conn.bind(('', Session.MULTICAST_CONTROL_PORT))
                    self.crypto_conn.listen(1)
                    peer = App.get_running_app().peer
                    peer.conn_lst.append(self.crypto_conn)

            del self.audio_stat_dct[user]
            del self.video_stat_dct[user]
            self.audio_output_stream_dct[user].stop_stream()
            self.audio_output_stream_dct[user].close()
            del self.audio_deque_dct[user]
            del self.audio_output_stream_dct[user]

    def send_rsa_public_key(self):
        """Sends RSA public key to call master for receiving
        cryptographic info.
        """

        # Retreiving PEM-encoded RSA public key
        rsa_public_key = self.rsa_keypair.publickey().exportKey()

        # Sending public key to call master
        crypto_msg = {
            'type': 'session',
            'subtype': 'control',
            'mode': 'rsa_public_key',
            'key': rsa_public_key
        }
        self.task_lst.append(Task(self.crypto_conn, crypto_msg))

    def send_crypto_info(self, public_key, conn):
        """Sends cryptographic info (AES symmetric key and initialization vector
            and session nonce) to a new user in call who isn't the call master.

        Args:
            public_key (str): RSA public key received from user.
            conn (socket.socket): TCP connection for sending the info.
        """

        # Encrypting AES key and session nonce with RSA public key
        rsa_cipher = RSA.importKey(public_key)
        encrypted_key, encrypted_nonce = rsa_cipher.encrypt(
            self.aes_key, 0)[0], rsa_cipher.encrypt(self.session_nonce, 0)[0]

        # Sending cryptographic info to user
        crypto_msg = {
            'type': 'session',
            'subtype': 'control',
            'mode': 'crypto_info',
            'key': base64.b64encode(encrypted_key),
            'iv': base64.b64encode(self.aes_iv),
            'nonce': base64.b64encode(encrypted_nonce)
        }
        self.task_lst.append(Task(conn, crypto_msg))

    def set_crypto_info(self, **kwargs):
        """Decrypts and sets cryptographic info received from call master.

        Args:
            **kwargs: Keyword arguments supplied in dictioanry form.
        """

        # Decrypting AES key and session nonce with RSA private key
        encrypted_key, encrypted_nonce = base64.b64decode(
            kwargs['key']), base64.b64decode(kwargs['nonce'])
        decrypted_key, decrypted_nonce = self.rsa_keypair.decrypt(
            encrypted_key), self.rsa_keypair.decrypt(encrypted_nonce)

        # Storing decrypted cryptographic info
        self.aes_key = decrypted_key
        self.aes_iv = base64.b64decode(kwargs['iv'])
        self.session_nonce = decrypted_nonce

        # Closing TCP cryptographic info exchange connection
        peer = App.get_running_app().peer
        peer.conn_lst.remove(self.crypto_conn)
        self.crypto_conn.close()
        self.crypto_conn = None

    def encrypt_msg(self, msg):
        """Encrypts message with AES symmetric encryption.

        Args:
            msg (dict): JSON-formatted message.

        Returns:
            dict: The encrypted message wrapped in another JSON.
        """

        # Creating AES cipher object
        aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)

        # Preparing message for encryption
        msg = json.dumps(msg, separators=(',', ':'))
        if len(msg) % 16 != 0:
            msg += (16 - len(msg) % 16) * '\x00'

        payload = aes_cipher.encrypt(msg)
        encrypted_msg = {
            'payload': base64.b64encode(payload)
        }
        if 'timestamp' in msg:
            encrypted_msg['timestamp'] = None

        return encrypted_msg

    def decrypt_msg(self, msg):
        """Decrypts message with AES symmetric encryption.

        Args:
            msg (dict): Encrypted data wrapped in JSON.

        Returns:
            dict: Decrypted JSON-formatted message.
        """

        # Creating AES cipher object
        aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)

        # Decrypting data
        encrypted_data = base64.b64decode(msg['payload'])
        decrypted_data = aes_cipher.decrypt(encrypted_data)

        # Unpadding decrypted data
        decrypted_data = decrypted_data.rstrip('\x00')

        # Converting encrypted data to JSON format
        decrypted_msg = json.loads(decrypted_data)

        # Moving timestamp to original message if necessary:
        if 'timestamp' in msg:
            decrypted_msg['timestamp'] = msg['timestamp']

        return decrypted_msg

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

        # Waiting for cryptographic info exchange to complete
        while not hasattr(self, 'aes_key'):
            pass

        # Sending audio in a loop
        while self.keep_sending_flag:
            if self.send_flag_dct['audio']:
                self.send_audio()

    @new_thread('audio_recv_thread')
    def audio_recv_loop(self):
        """Receives audio packets in parallel.
        """

        while self.keep_sending_flag:
            # Receiving and parsing new audio packets
            try:
                raw_data, addr = self.content_conn_dct['audio'].recvfrom(
                    PypePeer.MAX_RECV_SIZE)
            except socket.timeout:
                continue
            peer = App.get_running_app().peer
            data_lst = peer.get_jsons(raw_data)

            # Tranferring audio packets to parallel threads for playing
            root = App.get_running_app().root_sm.current_screen
            for data in data_lst:
                if data['src'] != root.username:
                    self.audio_deque_dct[data['src']].append(data)

                    # Updating audio statistics
                    if peer.session and data['src'] in self.user_lst:
                        tracker = self.audio_stat_dct[data['src']]
                        tracker.update(**data)

    @new_thread()
    def play_audio_packets(self, user):
        """Plays audio of a certain user in parallel.

        Args:
            user (str): User whose audio is to be processed.
        """

        while self.keep_sending_flag:
            # Checking deque for audio packets
            try:
                if self.audio_deque_dct[user]:
                    data = self.audio_deque_dct[user].pop()

                    # Decoding and playing audio packet
                    username = App.get_running_app().root_sm.current_screen.username
                    if user in self.audio_stat_dct:
                        if user != username and self.audio_stat_dct[user].check_packet_integrity(**data):
                            audio_chunk = base64.b64decode(data['chunk'])
                            self.audio_output_stream_dct[
                                user].write(audio_chunk)
            except KeyError:
                break

    def send_audio(self):
        """Sends encrypted audio packet to multicast group.
        """

        # Reading a chunk of audio samples from stream
        audio_chunk = self.audio_input_stream.read(Session.AUDIO_CHUNK_SIZE)

        # Composing audio packet
        username = App.get_running_app().root_sm.current_screen.username
        audio_msg = {
            'type': 'session',
            'subtype': 'content',
            'medium': 'audio',
            'timestamp': None,
            'src': username,
            'seq': self.seq_dct['audio'],
            'session_nonce': base64.b64encode(self.session_nonce),
            'packet_nonce': base64.b64encode(os.urandom(Session.SESSION_NONCE_SIZE)),
            'chunk': base64.b64encode(audio_chunk)
        }

        # Encrypting audio packet
        encrypted_audio_msg = self.encrypt_msg(audio_msg)

        # Incrementing audio packet sequence number
        self.seq_dct['audio'] += 1

        # Sending audio packet
        Task(self.content_conn_dct['audio'], encrypted_audio_msg,
             dst=(self.multicast_addr_dct['audio'], Session.MULTICAST_CONTENT_PORT)).send_msg()

    @new_thread('video_send_thread')
    def video_send_loop(self):
        """Loop for sending video packets in parallel.
        """

        # Waiting for cryptographic info exchange to complete
        while not hasattr(self, 'aes_key'):
            pass

        # Sending video in a loop
        while self.keep_sending_flag:
            if self.send_flag_dct['video']:
                self.send_video()

    @new_thread('video_recv_thread')
    def video_recv_loop(self):
        """Receives and displays video frames in parallel.
        """

        while self.keep_sending_flag:
            # Receiving and parsing new video packets
            try:
                raw_data, addr = self.content_conn_dct['video'].recvfrom(
                    PypePeer.MAX_RECV_SIZE)
            except socket.timeout:
                continue
            peer = App.get_running_app().peer
            data_lst = peer.get_jsons(raw_data)

            # Displaying new frames on screen
            for data in data_lst:
                if data['src'] in self.video_stat_dct:
                    if self.video_stat_dct[data['src']].check_packet_integrity(**data):
                        root = App.get_running_app().root_sm.current_screen
                        if hasattr(root, 'session_layout') and data['src'] != root.username:
                            root.session_layout.video_layout.update_frame(
                                **data)

    @rate_limit(INITIAL_SENDING_RATE)
    def send_video(self):
        """Sends encrypted video packet to multicast group.
        """

        # Reading a new video frame from webcam
        frame = None
        while frame is None:
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
                'subtype': 'content',
                'medium': 'video',
                'timestamp': None,
                'src': username,
                'seq': self.seq_dct['video'],
                'session_nonce': base64.b64encode(self.session_nonce),
                'packet_nonce': base64.b64encode(os.urandom(Session.SESSION_NONCE_SIZE)),
                'frame': base64.b64encode(encoded_frame)
            }

            # Encrypting audio packet
            encrypted_video_msg = self.encrypt_msg(video_msg)

            # Incrementing video packet sequence number
            self.seq_dct['video'] += 1

            # Sending video packet
            Task(self.content_conn_dct['video'], encrypted_video_msg,
                 dst=(self.multicast_addr_dct['video'], Session.MULTICAST_CONTENT_PORT)).send_msg()

    def send_chat(self, **kwargs):
        """Sends chat message to call multicast chat group.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        kwargs['subtype'] = 'content'
        kwargs['medium'] = 'chat'
        kwargs['timestamp'] = None
        self.task_lst.append(
            Task(self.content_conn_dct['chat'], kwargs,
                 dst=(self.multicast_addr_dct['chat'], Session.MULTICAST_CONTENT_PORT)))

    @rate_limit(1)
    def send_optimal_rates(self):
        """Sends the calculated optimal sending rate to all users in call
        """

        root = App.get_running_app().root_sm.current_screen
        username = root.username

        for user in self.user_lst:
            if user != username:
                optimal_rate = self.video_stat_dct[user].optimal_sending_rate()
                if optimal_rate:
                    feedback_msg = {
                        'type': 'session',
                        'subtype': 'control',
                        'mode': 'feedback',
                        'src': username,
                        'seq': self.seq_dct['feedback'],
                        'session_nonce': base64.b64encode(self.session_nonce),
                        'packet_nonce': base64.b64encode(os.urandom(Session.SESSION_NONCE_SIZE)),
                        'rate': optimal_rate
                    }

                    # Incrementing feedback packet sequence number
                    self.seq_dct['feedback'] += 1

                    self.task_lst.append(Task(self.unicast_control_conn, feedback_msg, dst=(
                        self.user_addr_dct[self.master], Session.MULTICAST_CONTROL_PORT)))

    def set_optimal_rate(self, **kwargs):
        """
        Sets the new sending rate unsing the following logic:
            1. If CLR hasn't been determined or a user offered a sending rate
             lower and current CLR, make the user the new CLR.
            2. IF the user is CLR, update the rate according to him.
            3. Else, don't change a thing.

            The rate is updated with 40% weight to avoid abruptness in rate change.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        clr_user, clr_rate = self.clr

        # Determining new rate
        if not clr_user or clr_user != kwargs['src'] \
                and kwargs['rate'] < clr_rate:
            self.clr = [kwargs['src'], kwargs['rate']]
            new_rate = kwargs['rate']
        elif clr_user == kwargs['src']:
            new_rate = kwargs['rate']
        else:
            return

        # Setting new rate
        current_rate = self.send_video.rate
        self.send_video.__func__.rate = int(
            0.6 * current_rate + 0.4 * new_rate)

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

    def plot_stats(self, user):
        """Plots audio and video statistics of user.

        Args:
            user (str): User whose statistics are to be plotted.
        """

        # Audio and video tracker objects
        audio_tracker = self.audio_stat_dct[user]
        video_tracker = self.video_stat_dct[user]

        # Setting plot title
        plt.suptitle('Call statistics: ' + user,
                     fontsize=24)

        # Getting statistics to plot from configuration file
        if get_option('stats_to_plot') == 'all':
            stats_to_plot = audio_tracker.stat_dct.keys()
        else:
            stats_to_plot = get_option('stats_to_plot')

        # Ploting statistics
        rows, cols = len(stats_to_plot), 1
        row_index = 1
        for stat in stats_to_plot:
            plt.subplot(rows, cols, row_index)
            plt.plot(audio_tracker.x_val_dct[
                     stat], audio_tracker.y_val_dct[stat],
                     color='red', label='audio')
            plt.plot(video_tracker.x_val_dct[
                     stat], video_tracker.y_val_dct[stat],
                     color='blue', label='video')
            if row_index == 1:
                plt.legend()
            plt.ylabel('{} ({})'.format(stat, audio_tracker.unit_dct[
                       stat]))
            row_index += 1

        plt.xlabel('time (s)')

        # Displaying plot
        plt.show()

        # Resetting plot
        plt.cla()
        plt.clf()
        plt.close()

    def plot_users_stats(self):
        """Plots audio and video statistics of all users in call.
        """

        root = App.get_running_app().root_sm.current_screen
        username = root.username

        for user in self.user_lst:
            if user != username:
                self.plot_stats(user)

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
        for conn in self.content_conn_dct.values() + self.control_conn_dct.values():
            conn.close()
        self.unicast_control_conn.close()
        if self.crypto_conn:
            peer = App.get_running_app().peer
            peer.conn_lst.remove(self.crypto_conn)
            self.crypto_conn.close()

        # Closing audio streams
        self.audio_input_stream.stop_stream()
        self.audio_input_stream.close()
        for audio_output_stream in self.audio_output_stream_dct.values():
            audio_output_stream.stop_stream()
            audio_output_stream.close()
        self.audio_interface.terminate()

        # Terminating webcam stream
        self.webcam_stream.terminate()
