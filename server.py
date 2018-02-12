"""Central server of app.
"""

# Imports
import logging
import socket
import select
import json
import logging

from task import Task
from user import User
from call import Call


class PypeServer(object):

    """App server class.

    Attributes:
        ADDR (tuple): Address to which the server is bound.
        call_dct (dict): Dictionary mapping call master to call object.
        conn_dct (dict): Dictionary mapping all active connections
         to their addresses.
        LISTEN_QUEUE_SIZE (int): Number of connections that server can queue
         before accepting (5 is typically enough). (static)
        logger (logging.Logger): Logging object.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once.
        multicast_addr_counter (int): Counter of the number of used multicast addresses.
        multicast_addr_lst (list): List of already used multicast addresses.
        server_listener (socket.socket): Server socket. (static)
        task_lst (list): List of all pending tasks.
        user_dct (dict): Dictionary mapping username to user object.
    """

    ADDR = ('', 5050)
    LISTEN_QUEUE_SIZE = 5
    MAX_RECV_SIZE = 65536

    def __init__(self):
        """Constructor method.
        """

        # Cofiguring logger
        logging.basicConfig(
            format='[%(asctime)s]%(levelname)s: %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S')
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.server_listener = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.server_listener.bind(PypeServer.ADDR)
        self.server_listener.listen(PypeServer.LISTEN_QUEUE_SIZE)
        self.conn_dct = {}
        self.task_lst = []
        self.user_dct = {}
        self.call_dct = {}
        self.multicast_addr_lst = []
        self.multicast_addr_counter = 0

    def run(self):
        """Server mainloop method.
        """

        while True:
            read_lst, write_lst, err_lst = select.select(
                self.conn_dct.keys() + [self.server_listener],
                *((self.conn_dct.keys(),) * 2))

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
            # Handling new connections
            if conn is self.server_listener:
                new_conn, addr = self.server_listener.accept()
                self.conn_dct[new_conn] = addr
                self.logger.info('{} connected.'.format(addr))
            else:
                if conn.type == socket.SOCK_STREAM:
                    raw_data = conn.recv(PypeServer.MAX_RECV_SIZE)
                else:
                    raw_data, addr = conn.recvfrom(PypeServer.MAX_RECV_SIZE)

                # Closing socket if disconnected
                if not raw_data:
                    user = self.get_user_from_conn(conn)
                    if user:
                        self.logger.info('{} left.'.format(user.name))
                        del self.user_dct[user.name]

                        # Notifying other users that user has left
                        self.report_user_update('leave', user.name)

                    self.logger.info(
                        '{} disconnected.'.format(self.conn_dct[conn]))
                    del self.conn_dct[conn]
                    conn.close()
                else:
                    # Parsing JSON data
                    data_lst = self.get_jsons(raw_data)

                    # Handling messages
                    for data in data_lst:
                        # Join request/response
                        if data['type'] == 'join':
                            # Checking if username already exists
                            if data['username'] in self.user_dct:
                                self.task_lst.append(Task(conn, {
                                    'type': 'join',
                                    'subtype': 'response',
                                    'status': 'no'
                                }))

                            else:
                                self.user_dct[data['username']] = User(
                                    data['username'], conn)
                                user_info_lst, call_info_lst = [], []
                                for username in self.user_dct:
                                    if username != data['username']:
                                        user_info_lst.append({
                                            'name': username,
                                            'status': self.user_dct[username].status
                                        })
                                for master in self.call_dct:
                                    call_info_lst.append({
                                        'master': master,
                                        'user_lst': self.call_dct[master].user_lst
                                    })
                                self.task_lst.append(Task(conn, {
                                    'type': 'join',
                                    'subtype': 'response',
                                    'status': 'ok',
                                    'username': data['username'],
                                    'user_info_lst': user_info_lst,
                                    'call_info_lst': call_info_lst
                                }))
                                self.logger.info(
                                    '{} joined.'.format(data['username']))
                                self.report_user_update(
                                    'join', data['username'])

                        # Call request/response
                        elif data['type'] == 'call':
                            if data['subtype'] == 'request':
                                caller = self.get_user_from_conn(conn)
                                for username in [caller.name, data['callee']]:
                                    self.report_user_update('status', username)
                                self.task_lst.append(Task(self.user_dct[
                                    data['callee']].conn, {
                                    'type': 'call',
                                    'subtype': 'participate',
                                    'caller': caller.name
                                }))

                            elif data['subtype'] == 'callee_response':
                                caller = data['caller']
                                callee = self.get_user_from_conn(conn)
                                response_msg = {
                                    'type': 'call',
                                    'subtype': 'callee_response',
                                    'status': data['status']
                                }
                                if data['status'] == 'accept':
                                    if self.user_dct[caller].call:
                                        call = self.user_dct[caller].call
                                        call.user_join(callee)
                                    else:
                                        # Creating new call
                                        call = Call([caller, callee.name], caller,
                                                    self.get_multicast_addr(),
                                                    self.get_multicast_addr(),
                                                    self.get_multicast_addr())
                                        self.user_dct[caller].call = call
                                        self.call_dct[caller] = call
                                        self.report_call_update(
                                            caller, 'call_add', user_lst=call.user_lst)
                                    self.user_dct[caller].call = call
                                    # Adding addresses to response message
                                    response_msg['addrs'] = {
                                        'audio': call.audio_addr,
                                        'video': call.video_addr,
                                        'chat': call.chat_addr
                                    }
                                    self.logger.info('Call started, participants: {}'.format(
                                        ', '.join(call.user_lst)))
                                    self.task_lst.append(
                                        Task(conn, response_msg))
                                else:
                                    callee = self.get_user_from_conn(conn)
                                    for username in [callee.name, data['caller']]:
                                        self.report_user_update(
                                            'status', username)
                                self.task_lst.append(
                                    Task(self.user_dct[caller].conn, response_msg))

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

    def get_user_from_conn(self, conn):
        """Retreives user corresponding to connection (if exists).

        Args:
            conn (socket.socket): The connection to check.

        Returns:
            User: The user object corresponding to the connection
             (None if doesn't exist).
        """

        for username in self.user_dct:
            if self.user_dct[username].conn is conn:
                return self.user_dct[username]
        return None

    def report_user_update(self, mode, username):
        """Reports user join/leave/status change to other users.

        Args:
            mode (str): join/leave/status.
            username (str): Username.
        """

        for active_user in self.user_dct:
            if mode == 'join' or mode == 'status':
                if active_user == username:
                    continue
            self.task_lst.append(Task(self.user_dct[active_user].conn, {
                'type': 'user_update',
                'subtype': mode,
                'username': username
            }))

    def report_call_update(self, master, mode, **kwargs):
        """Notifies users of changes in active calls.

        Args:
            master (str): Call master.
            mode (str): call_add/call_remove/user_join/user_leave.
            **kwargs: Additional necessary keyword arguments.
        """

        for active_user in self.user_dct:
            self.task_lst.append(Task(self.user_dct[active_user].conn, {
                'type': 'call_update',
                'subtype': mode,
                'master': master,
                'info': kwargs
            }))

    def get_multicast_addr(self):
        """Retreives a vacant multicast IP address.

        Returns:
            str: The given IP address.
        """

        # If address list isn't empty, take address from there
        if self.multicast_addr_lst:
            return self.multicast_addr_lst.pop()

        # Else, take the next address in range
        self.multicast_addr_counter += 1
        return '239.{}.{}.{}'.format(self.multicast_addr_counter / 65536,
                                     self.multicast_addr_counter / 256,
                                     self.multicast_addr_counter % 256)

# Running server
if __name__ == '__main__':
    PypeServer().run()
