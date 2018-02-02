"""Main app file (GUI component).
"""

# Imports
import json
import threading
import socket
import re

from kivy.app import App
from kivy.config import Config
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty, ListProperty
from kivy.uix.widget import Widget

from peer import PypePeer


class EntryScreen(Screen):

    """Entry screen class (see .kv file for structure).

    Attributes:
        bottom_lbl (Label): Bottom label to be added 
         (when username is invalid or taken).
        USERNAME_REGEX (str): Regex of valid username format: Non-empty, doesn't
         start with spaces and is no longer than 256 characters.
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
            if hasattr(self, 'bottom_lbl'):
                self.bottom_lbl.text = err_msg
            else:
                self.bottom_lbl = Label(text=err_msg)
                self.ids.main_layout.add_widget(self.bottom_lbl)
        else:
            # Notifying communication component
            app.send_gui_event({
                'type': 'join',
                'subtype': 'request',
                'username': username
            })

    def add_bottom_lbl(self, dt):
        """Adds bottom label to screen (scheduled by Kivy clock).

        Args:
            dt (float): Time elapsed between scheduling
             and execution (passed autiomatically).
        """

        err_msg = 'Username already exists'

        # Checking if there already exists a bottom label
        if hasattr(self, 'bottom_lbl'):
            self.bottom_lbl.text = err_msg
        else:
            self.bottom_lbl = Label(text=err_msg)
            self.ids.main_layout.add_widget(self.bottom_lbl)


class MainScreen(Screen):

    """Main screen class (see .kv file for structure).

    Attributes:
        user_slot_dct (dict): Dictionary mapping online users to their slots.
        username (str): Username.
    """

    def __init__(self, username, user_info_lst):
        """Constructor method

        Args:
            username (str): Username of current user.
            user_info_lst (TYPE): Description

        Deleted Parameters:
            user_lst (list): List of online users.
        """

        self.username = username
        self.user_slot_dct = {}
        for name, status in user_info_lst:
            self.user_slot_dct[name] = UserSlot(name, status)
        Screen.__init__(self, name='main_screen')

        # Adding all slots to online user layout
        for name in self.user_slot_dct:
            self.ids.user_slots_layout.add_widget(self.user_slot_dct[name])
            self.ids.user_slots_layout.height += self.user_slot_dct[
                name].height

    def update_user_slots_layout(self, mode, username, dt):
        """Updates user slots layout when user joins or leave (scheduled by kivy clock).

        Args:
            mode (str): join/leave.
            username (str): Username.
            dt (float): Time elapsed between scheduling
             and execution (passed autiomatically).
        """

        # User join
        if mode == 'join':
            self.user_slot_dct[username] = UserSlot(username, 'available')
            self.ids.user_slots_layout.add_widget(
                self.user_slot_dct[username])
        # User leave
        else:
            self.ids.user_slots_layout.remove_widget(
                self.user_slot_dct[username])
            del self.user_slot_dct[username]
        self.ids.user_num_lbl.text = 'Online users ({})'.format(
            len(self.user_slot_dct))


class UserSlot(BoxLayout):

    """Slot representing an online user (see .kv file for structure).

    Attributes:
        status (str): Whether the user is in call (available/occupied).
        username (str): Username.
    """

    def __init__(self, username, status):
        """Constructor method.

        Args:
            username (str): Username.
            status (str): Whether the user is available (i.e. not in call).
        """

        self.username = username
        self.status = status
        BoxLayout.__init__(self)


class PypeApp(App):

    """Main app class.

    Attributes:
        gui_event_port (int): Port of GUI event listener.
        gui_event_sender (socket.socket): UDP socket that sends GUI events to
         the communication component of app.
        peer (PypePeer): App's communication component.
        root_sm (ScreenManager): Root screen manager.
        WINDOW_HEIGHT (int): Window height.
        WINDOW_WIDTH (int): Window width.
    """

    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 720

    def send_gui_event(self, data):
        """Sends GUI event to communication component of app.

        Args:
            data (dict): Event data (in JSON format).
        """

        self.gui_event_sender.sendto(json.dumps(
            data), ('localhost', self.gui_event_port))

    def on_stop(self):
        """Application close event callback.
        """

        self.send_gui_event({
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
        self.root_sm.add_widget(EntryScreen())

        # Creating communication thread
        self.peer = PypePeer()
        self.gui_event_port = self.peer.get_gui_event_port()
        threading.Thread(target=self.peer.run).start()

        # Creating user event sender
        self.gui_event_sender = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM)

        return self.root_sm

    def switch_to_main_screen(self, username, user_info_lst, dt):
        """Switches current screen to main screen (scheduled by kivy clock).

        Args:
            username (str): Username.
            user_info_lst (list): List of online users and their status.
            dt (float): Time elapsed between scheduling
             and execution (passed autiomatically).
        """

        main_screen = MainScreen(username, user_info_lst)
        self.root_sm.add_widget(main_screen)
        self.root_sm.current = 'main_screen'


# Running app
if __name__ == '__main__':
    PypeApp().run()
