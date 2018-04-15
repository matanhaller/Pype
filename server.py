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

        # Configuring logger
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
                        self.report_user_update(
                            subtype='leave', name=user.name)

                        # Removing user from call if participated
                        if user.call:
                            self.handle_call_user_leave(user)

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
                            if data['name'] in self.user_dct:
                                self.task_lst.append(Task(conn, {
                                    'type': 'join',
                                    'subtype': 'response',
                                    'status': 'no'
                                }))

                            else:
                                # Creating new user
                                self.user_dct[data['name']] = User(
                                    conn=conn, **data)

                                # Sending relevant info to new user
                                user_info_lst, call_info_lst = [], []
                                for username in self.user_dct:
                                    if username != data['name']:
                                        user_info_lst.append({
                                            'name': username,
                                            'status': self.user_dct[username].status,
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
                                    'name': data['name'],
                                    'user_info_lst': user_info_lst,
                                    'call_info_lst': call_info_lst
                                }))
                                self.logger.info(
                                    '{} joined.'.format(data['name']))

                                # Reporting user join to other users
                                self.report_user_update(subtype='join', **data)

                        # Call request/response
                        elif data['type'] == 'call':
                            if data['subtype'] == 'request':
                                caller = self.get_user_from_conn(conn)
                                for username in [caller.name, data['callee']]:
                                    if self.user_dct[username].status == 'available':
                                        self.user_dct[username].switch_status()
                                        self.report_user_update(
                                            subtype='status', name=username)
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
                                    if self.user_dct[caller].call or callee.call:
                                        if self.user_dct[caller].call:
                                            call = self.user_dct[caller].call
                                            callee.join_call(call)
                                            self.report_call_update(
                                                subtype='user_join', master=call.master,
                                                name=callee.name, addr=self.conn_dct[callee.conn][0])
                                            self.logger.info(
                                                '{} joined a call.'.format(callee.name))
                                        else:
                                            call = callee.call
                                            self.user_dct[
                                                caller].join_call(call)
                                            self.report_call_update(
                                                subtype='user_join', master=call.master,
                                                name=caller, addr=self.conn_dct[self.user_dct[caller].conn][0])
                                            self.logger.info(
                                                '{} joined a call.'.format(self.user_dct[caller].name))
                                    else:
                                        # Creating new call
                                        call = Call({
                                            'audio': self.get_multicast_addr(),
                                            'video': self.get_multicast_addr(),
                                            'chat': self.get_multicast_addr()
                                        })
                                        for user in [self.user_dct[caller], callee]:
                                            user.join_call(call)
                                        self.call_dct[caller] = call
                                        self.report_call_update(
                                            subtype='call_add', master=caller, user_lst=call.user_lst)
                                        self.logger.info('Call started, participants: {}.'.format(
                                            ', '.join(call.user_lst)))

                                    self.user_dct[caller].call = call
                                    response_msg['master'] = call.master
                                    response_msg['user_lst'] = call.user_lst
                                    response_msg['peer_addrs'] = {user: self.conn_dct[
                                        self.user_dct[user].conn][0] for user in call.user_lst}

                                    # Adding addresses to response message
                                    response_msg['addrs'] = call.addr_dct
                                    self.task_lst.append(
                                        Task(conn, response_msg))
                                else:
                                    callee = self.get_user_from_conn(conn)
                                    for username in [callee.name, data['caller']]:
                                        self.user_dct[username].switch_status()
                                        self.report_user_update(
                                            subtype='status', name=username)
                                self.task_lst.append(
                                    Task(self.user_dct[caller].conn, response_msg))

                        # Session messages
                        elif data['type'] == 'session':
                            user = self.get_user_from_conn(conn)
                            self.handle_call_user_leave(user)

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

    def report_user_update(self, **kwargs):
        """Reports user join/leave/status change to other users.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # Tweaking kwargs before message update
        if 'type' in kwargs:
            del kwargs['type']
        if 'status' not in kwargs:
            kwargs['status'] = 'available'

        for active_user in self.user_dct:
            if kwargs['subtype'] in ['join', 'status']:
                if active_user == kwargs['name']:
                    continue

            user_update_msg = {
                'type': 'user_update',
                'timestamp': None
            }

            user_update_msg.update(kwargs)

            self.task_lst.append(
                Task(self.user_dct[active_user].conn, user_update_msg))

    def report_call_update(self, **kwargs):
        """Notifies users of changes in active calls.

        Args:
            **kwargs: Keyword arguments passed in dictionary form.
        """

        # Tweaking kwargs before message update
        if 'type' in kwargs:
            del kwargs['type']

        for active_user in self.user_dct:
            call_update_msg = {
                'type': 'call_update',
                'timestamp': None
            }
            call_update_msg.update(kwargs)
            self.task_lst.append(
                Task(self.user_dct[active_user].conn, call_update_msg))

    def handle_call_user_leave(self, user):
        """Removes user from call and reports other users.

        Args:
            user (User): User that left the call.
        """

        call = user.call
        prev_master = call.master
        user.leave_call()
        del self.call_dct[prev_master]
        self.call_dct[call.master] = call

        self.logger.info('{} left a call.'.format(user.name))

        # Removing call if user number reduced to 1
        if len(call.user_lst) == 1:
            # Returning allocated addresses to list
            self.multicast_addr_lst += call.addr_dct.values()

            self.report_call_update(
                subtype='call_remove', master=prev_master)
            del self.call_dct[call.master]
            for participant in call.user_lst:
                if participant in self.user_dct:
                    self.user_dct[participant].switch_status()
                    self.user_dct[participant].leave_call()
                    self.report_user_update(
                        subtype='status', name=participant)

            self.logger.info('A call ended.')
        else:
            self.report_call_update(
                subtype='user_leave', master=prev_master,
                new_master=call.master, name=user.name)

        if user.name in self.user_dct:
            user.switch_status()
            self.report_user_update(
                subtype='status', name=user.name)

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
