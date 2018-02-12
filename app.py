"""Main app file (GUI component).
"""

# Imports
import json
import threading
import socket
import re

from kivy.app import App
from kivy.config import Config
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget

from peer import PypePeer


class EntryScreen(Screen):

    """Entry screen class (see .kv file for structure).

    Attributes:
        bottom_lbl (Label): Bottom label to be added
         (when username is invalid or taken).
        USERNAME_REGEX (str): Regex of valid username format: Non-empty, doesn't
         start with spaces and is no longer than 14 characters.
    """

    USERNAME_REGEX = r'[^\s].{0,13}$'

    def __init__(self):
        """Constructor method,
        """

        Screen.__init__(self, name='entry_screen')

    def on_join_btn_press(self):
        """Sends join request to server.
        """

        app = App.get_running_app()
        username = self.ids.username_input.text

        # Checking if username is valid
        if not re.match(EntryScreen.USERNAME_REGEX, username):
            err_msg = 'Invalid username'
            self.add_bottom_lbl(err_msg)
        else:
            # Notifying communication component
            app.send_gui_evt({
                'type': 'join',
                'subtype': 'request',
                'username': username
            })

    @mainthread
    def add_bottom_lbl(self, msg):
        """Adds bottom label to entry screen.

        Args:
            msg (str): The message to be shown in the label.
        """

        # Checking if there already exists a bottom label
        if hasattr(self, 'bottom_lbl'):
            self.bottom_lbl.text = msg
        else:
            self.bottom_lbl = Label(text=msg, size_hint_y=0.4)
            self.ids.main_layout.add_widget(self.bottom_lbl)


class MainScreen(Screen):

    """Main screen class (see .kv file for structure).

    Attributes:
        call_layout (CallLayout): Layout of all active calls.
        footer_widget (Widget): Widget that's added to the bottom of the screen
         when necessary.
        remove_widget_evt (TYPE): Description
        user_layout (UserLayout): Layout of all online users.
        username (str): Username.
    """

    def __init__(self, username, user_info_lst, call_info_lst):
        """Constructor method

        Args:
            username (str): Username of current user.
            user_info_lst (list): List of online users and their status.
            call_info_lst (list): List of users in each call and their masters.
        """

        self.username = username
        self.user_layout = UserLayout(user_info_lst)
        self.call_layout = CallLayout(call_info_lst)
        Screen.__init__(self, name='main_screen')
        for layout in [self.user_layout, self.call_layout]:
            self.ids.interface_layout.add_widget(layout)

    @mainthread
    def add_footer_widget(self, type, username=None):
        """Adds footer widget to main screen.

        Args:
            type (int): Widget type:
                0: Pending call
                1: User not available
                2: Call
                3: Rejected call
                4: Active call
            username (str, optional): Username to be used for widget construction.
        """

        # Checking if there already exists a footer widget
        if hasattr(self, 'footer_widget'):
            self.ids.main_layout.remove_widget(self.footer_widget)
        if hasattr(self, 'remove_widget_evt'):
            self.remove_widget_evt.cancel()
            del self.remove_widget_evt

        # Pending call
        if type == 0:
            self.footer_widget = PendingCallFooter(username)
        # User not available
        elif type == 1:
            self.footer_widget = Label(text='User is in call', size_hint_y=0.1)
            Clock.schedule_once(lambda dt: self.remove_footer_widget(), 3)
        # Call
        elif type == 2:
            self.footer_widget = CallFooter(username)
        # Rejected call
        elif type == 3:
            self.footer_widget = Label(
                text='Call has been rejected by user', size_hint_y=0.1)
            self.remove_widget_evt = Clock.schedule_once(
                lambda dt: self.remove_footer_widget(), 3)
        # Active call
        elif type == 4:
            self.footer_widget = SessionFooter()

        self.ids.main_layout.add_widget(self.footer_widget)

    @mainthread
    def remove_footer_widget(self):
        """Removes footer widget.
        """

        # Checking if footer widget exists
        if hasattr(self, 'footer_widget'):
            # Unscheduling counter event if exists
            if hasattr(self.footer_widget, 'counter_update_evt'):
                self.footer_widget.counter_update_evt.cancel()

            self.ids.main_layout.remove_widget(self.footer_widget)
            del self.footer_widget


class UserSlot(BoxLayout):

    """Slot representing an online user (see .kv file for structure).

    Attributes:
        status (str): Whether the user is in call (available/in call).
        username (str): Username.
    """

    def __init__(self, username, status='available'):
        """Constructor method.

        Args:
            username (str): Username.
            status (str): Whether the user is available (i.e. not in call).
        """

        self.username = username
        self.status = status
        BoxLayout.__init__(self)

    def on_call_btn_press(self):
        """Sends call request with the following user to server.
        """

        app = App.get_running_app()
        screen = app.root_sm.get_screen('main_screen')

        app.send_gui_evt({
            'type': 'call',
            'subtype': 'request',
            'callee': self.username
        })

    def switch_status(self):
        """Switches user status.
        """

        if self.status == 'available':
            self.status = 'in call'
            self.ids.status_lbl.text = 'in call'
        else:
            self.status = 'available'
            self.ids.status_lbl.text = 'available'


class CallSlot(BoxLayout):

    """Slot representing an active call (see .kv file for structure).

    Attributes:
        master (str): Username of call master.
        user_lst (list): List of all users in call.
    """

    def __init__(self, user_lst, master):
        """Constructor method.

        Args:
            user_lst (list): List of users in call.
            master (str): Call master.
        """

        self.user_lst = user_lst
        self.master = master
        BoxLayout.__init__(self)
        self.ids.user_lbl.text = ', '.join(user_lst)

    def update(self, mode, user, new_master=None):
        """Updates call slot on user join/leave.

        Args:
            mode (str): Join/leave.
            user (str): Username that joined or left.
            new_master (str, optional): New call master.
        """

        if mode == 'join':
            self.user_lst.append(user)
        else:
            self.user_lst.remove(user)

        if new_master:
            self.master = new_master

        self.ids.user_lbl.text = ', '.join(self.user_lst)


class UserLayout(BoxLayout):

    """Class representing the user layout (see .kv file for structure).

    Attributes:
        user_slot_dct (dict): Dictionary mapping online users to their slots.
    """

    def __init__(self, user_info_lst):
        """Constructor method.

        Args:
            user_info_lst (list): List of online users and their status.
        """

        self.user_slot_dct = {}
        BoxLayout.__init__(self)
        for user in user_info_lst:
            self.user_slot_dct[user['name']] = UserSlot(
                user['name'], user['status'])
            # Adding all slots to layout
            self.ids.user_slot_layout.add_widget(
                self.user_slot_dct[user['name']])
        self.ids.user_num_lbl.text = 'Online users ({})'.format(
            len(self.user_slot_dct))

    @mainthread
    def update(self, mode, username):
        """Updates layout on user join, leave or status change.

        Args:
            mode (str): join/leave/status.
            username (str): Username.
        """

        # User join
        if mode == 'join':
            self.user_slot_dct[username] = UserSlot(username)
            self.ids.user_slot_layout.add_widget(
                self.user_slot_dct[username])
        # User leave
        elif mode == 'leave':
            self.ids.user_slot_layout.remove_widget(
                self.user_slot_dct[username])
            del self.user_slot_dct[username]
        # User status change
        else:
            self.user_slot_dct[username].switch_status()

        # Updating online user number
        self.ids.user_num_lbl.text = 'Online users ({})'.format(
            len(self.user_slot_dct))


class CallLayout(BoxLayout):

    """Class representing the call layout (see .kv file for structure).

    Attributes:
        call_slot_dct (dict): Dictionary mapping call masters to their respective calls.
    """

    def __init__(self, call_info_lst):
        """Constructor method.

        Args:
            call_info_lst (list): List of users in each call and their masters.
        """

        self.call_slot_dct = {}
        BoxLayout.__init__(self)
        for call in call_info_lst:
            self.call_slot_dct[call['master']] = CallSlot(
                call['master'], call['user_lst'])
            # Adding all slots to layout
            self.ids.call_slot_layout.add_widget(
                self.call_slot_dct[call['master']])
        self.ids.call_num_lbl.text = 'Active calls ({})'.format(
            len(self.call_slot_dct))

    @mainthread
    def update(self, mode, master, **kwargs):
        """Updates layout on call or user add or remove.

        Args:
            mode (str): call_add/call_remove/user_join/user_leave.
            master (str): Call master.
            **kwargs: Additional necessary keyword arguments.
        """

        # Adding call
        if mode == 'call_add':
            self.call_slot_dct[master] = CallSlot(
                kwargs['user_lst'], master)
            self.ids.call_slot_layout.add_widget(
                self.call_slot_dct[master])
        # Removing call
        elif mode == 'call_remove':
            self.ids.call_slot_layout.remove_widget(
                self.call_slot_dct[master])
            del self.call_slot_dct[master]
        # Adding user to call
        elif mode == 'user_join':
            self.call_slot_dct[master].update('join', kwargs['user'])
        # Removing user from call
        else:
            self.call_slot_dct[master].update(
                'leave', kwargs['user'], new_master=kwargs['new_master'])
        # Updating active call number
        self.ids.call_num_lbl.text = 'Active calls ({})'.format(
            len(self.call_slot_dct))


class PendingCallFooter(BoxLayout):

    """Footer widget to be shown when a call is pending (see .kv file for structure).

    Attributes:
        counter_update_evt (ClockEvent): Event scheduled by Kivy clock for
         updating counter every second. 
        elapsed_time (int): Description
        username (str): The user to call.
    """

    def __init__(self, username):
        """Constructor method.

        Args:
            username (str): The user to call.
        """

        self.username = username
        self.elapsed_time = 0
        BoxLayout.__init__(self)
        self.counter_update_evt = Clock.schedule_interval(
            lambda dt: self.update_counter(), 1)

    def update_counter(self):
        """Updates pending call counter every second.
        """

        self.elapsed_time += 1
        self.ids.counter.text = '{:0=2d}:{:0=2d}'.format(
            self.elapsed_time / 60, self.elapsed_time % 60)


class CallFooter(BoxLayout):

    """Footer widget to be shown when a user is calling (see .kv file for structure).

    Attributes:
        username (str): Name of calling user.
    """

    def __init__(self, username):
        """Constructor method.

        Args:
            username (str): Name of calling user.
        """

        self.username = username
        BoxLayout.__init__(self)

    def on_call_btn_press(self, status):
        """Notifies server that the call was accepted/rejected by user.

        Args:
            status (str): Call status (accept/reject)
        """

        app = App.get_running_app()
        app.send_gui_evt({
            'type': 'call',
            'subtype': 'response',
            'caller': self.username,
            'status': status
        })


class SessionDisplay(BoxLayout):

    """Display user sees during a call (see .kv file for structure).
    """

    pass


class SessionFooter(BoxLayout):

    """Footer displayed during a call (see .kv file for structure).

    Attributes:
        counter_update_evt (ClockEvent): Event scheduled by Kivy clock for
         updating counter every second. 
        elapsed_time (int): Description
    """

    def __init__(self):
        """Constructor method.
        """

        self.elapsed_time = 0
        BoxLayout.__init__(self)
        self.counter_update_evt = Clock.schedule_interval(
            lambda dt: self.update_counter(), 1)

    def update_counter(self):
        """Updates pending call counter every second.
        """

        self.elapsed_time += 1
        self.ids.counter.text = '{:0=2d}:{:0=2d}'.format(
            self.elapsed_time / 60, self.elapsed_time % 60)


class PypeApp(App):

    """Main app class.

    Attributes:
        gui_evt_port (int): Port of GUI event listener.
        gui_evt_sender (socket.socket): UDP socket that sends GUI events to
         the communication component of app.
        peer (PypePeer): App's communication component.
        root_sm (ScreenManager): Root screen manager.
        WINDOW_HEIGHT (int): Window height.
        WINDOW_WIDTH (int): Window width.
    """

    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 720

    def send_gui_evt(self, data):
        """Sends GUI event to communication component of app.

        Args:
            data (dict): Event data (in JSON format).
        """

        self.gui_evt_sender.sendto(json.dumps(
            data), ('localhost', self.gui_evt_port))

    def on_stop(self):
        """Application close event callback.
        """

        self.send_gui_evt({
            'type': 'terminate'
        })

    def build(self):
        """App builder.

        Returns:
            ScreenManager: Root screen manager.
        """

        # Setting window size
        Config.set('graphics', 'width', PypeApp.WINDOW_WIDTH)
        Config.set('graphics', 'height', PypeApp.WINDOW_HEIGHT)

        # Creating root object with all app screens
        self.root_sm = ScreenManager()
        self.root_sm.switch_to(EntryScreen())

        # Creating communication thread
        self.peer = PypePeer()
        self.gui_evt_port = self.peer.get_gui_evt_port()
        threading.Thread(target=self.peer.run).start()

        # Creating user event sender
        self.gui_evt_sender = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM)

        return self.root_sm

    @mainthread
    def switch_to_main_screen(self, username, user_info_lst, call_info_lst):
        """Switches current screen to main screen.

        Args:
            username (str): Username.
            user_info_lst (list): List of online users and their status.
            call_info_lst (list): List of users in each call and their masters.
        """

        main_screen = MainScreen(username, user_info_lst, call_info_lst)
        self.root_sm.switch_to(main_screen)

# Running app
if __name__ == '__main__':
    PypeApp().run()
