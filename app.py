"""Main app file (GUI component).
"""

# Imports
import json
import threading
import socket
import re
import time
import datetime
import base64

import numpy as np
import cv2

from kivy.app import App
from kivy.config import Config
from kivy.clock import Clock, mainthread
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget
from kivy.uix.camera import Camera
from kivy.uix.image import Image
from kivy.graphics.texture import Texture

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

        # Checking is username is valid
        try:
            username.decode('ascii')
            if not re.match(EntryScreen.USERNAME_REGEX, username):
                err_msg = 'Invalid username'
                self.add_bottom_lbl(err_msg)
            else:
                # Notifying communication component
                app.send_gui_evt({
                    'type': 'join',
                    'subtype': 'request',
                    'name': username
                })
        except UnicodeEncodeError:
            err_msg = 'Invalid username'
            self.add_bottom_lbl(err_msg)

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
        remove_widget_evt (ClockEvent): Event used for removing widgets.
        session_footer (SessionFooter): Footer widget displayed during called.
        session_layout (SessionLayout): Layout used for active call.
        user_layout (UserLayout): Layout of all online users.
        username (str): Username.
    """

    def __init__(self, **kwargs):
        """Constructor method

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.username = kwargs['name']
        self.user_layout = UserLayout(kwargs['user_info_lst'])
        self.call_layout = CallLayout(kwargs['call_info_lst'])
        Screen.__init__(self, name='main_screen')
        for layout in [self.user_layout, self.call_layout]:
            self.ids.interface_layout.add_widget(layout)

    @mainthread
    def add_footer_widget(self, **kwargs):
        """Adds footer widget to main screen.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # Checking if there already exists a footer widget
        if hasattr(self, 'footer_widget'):
            self.ids.footer_layout.remove_widget(self.footer_widget)
        if hasattr(self, 'remove_widget_evt'):
            self.remove_widget_evt.cancel()
            del self.remove_widget_evt

        # Pending call
        if kwargs['mode'] == 'pending_call':
            self.footer_widget = PendingCallFooter(kwargs['callee'])

        # User not available
        elif kwargs['mode'] == 'user_not_available':
            self.footer_widget = Label(text='User is in call')

        # Call
        elif kwargs['mode'] == 'call':
            self.footer_widget = CallFooter(kwargs['caller'])

        # Rejected call
        elif kwargs['mode'] == 'rejected_call':
            self.footer_widget = Label(
                text='Call has been rejected by user')

        # Scheduling widget removal if necessary
        if kwargs['mode'] in ['user_not_available', 'rejected_call']:
            self.remove_widget_evt = Clock.schedule_once(
                lambda dt: self.remove_footer_widget(), 3)

        self.ids.footer_layout.add_widget(self.footer_widget)

    @mainthread
    def remove_footer_widget(self):
        """Removes footer widget.
        """

        # Deleting event attribute if widget removal was scheduled
        if hasattr(self, 'remove_widget_evt'):
            del self.remove_widget_evt

        self.ids.footer_layout.remove_widget(self.footer_widget)
        del self.footer_widget

    @mainthread
    def switch_to_session_layout(self, **kwargs):
        """Removes call layout and shows session layout during active call.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # Removing footer widget if necessary
        if hasattr(self, 'footer_widget'):
            self.remove_footer_widget()

        self.ids.interface_layout.remove_widget(self.call_layout)
        self.session_layout = SessionLayout(**kwargs)
        self.ids.interface_layout.add_widget(self.session_layout)
        self.session_footer = SessionFooter()
        self.ids.footer_layout.add_widget(self.session_footer)

    @mainthread
    def switch_to_call_layout(self, **kwargs):
        """Removes session layout and shows call layout after call end.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.ids.interface_layout.remove_widget(self.session_layout)
        del self.session_layout
        self.ids.footer_layout.remove_widget(self.session_footer)
        del self.session_footer
        self.ids.interface_layout.add_widget(self.call_layout)


class UserSlot(BoxLayout):

    """Slot representing an online user (see .kv file for structure).

    Attributes:
        status (str): Whether the user is in call (available/in call).
        username (str): Username.
    """

    def __init__(self, **kwargs):
        """Constructor method.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.username = kwargs['name']
        self.status = kwargs['status']
        BoxLayout.__init__(self)

    def on_call_btn_press(self):
        """Sends call request with the following user to server.
        """

        app = App.get_running_app()

        app.send_gui_evt({
            'type': 'call',
            'subtype': 'request',
            'callee': self.username,
            'group': False
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

    def __init__(self, **kwargs):
        """Constructor method.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.user_lst = kwargs['user_lst']
        self.master = kwargs['master']
        BoxLayout.__init__(self)
        self.ids.user_lbl.text = ', '.join(kwargs['user_lst'])

    def update(self, **kwargs):
        """Updates call slot on user join/leave.

        Args:
            **kwargs: Keyword arguments supplied in dictioanry form.
        """

        if kwargs['mode'] == 'join':
            self.user_lst.append(kwargs['name'])
        else:
            self.user_lst.remove(kwargs['name'])

        if 'new_master' in kwargs:
            self.master = kwargs['new_master']

        self.ids.user_lbl.text = ', '.join(self.user_lst)

    def on_join_btn_press(self):
        """Sends call request with call master to server.
        """

        app = App.get_running_app()

        app.send_gui_evt({
            'type': 'call',
            'subtype': 'request',
            'callee': self.master,
            'group': True
        })


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
            self.user_slot_dct[user['name']] = UserSlot(**user)

            # Adding all slots to layout
            self.ids.user_slot_layout.add_widget(
                self.user_slot_dct[user['name']])
            self.ids.user_slot_layout.height += self.user_slot_dct[
                user['name']].height

        self.ids.user_num_lbl.text = 'Online users ({})'.format(
            len(self.user_slot_dct))

    @mainthread
    def update(self, **kwargs):
        """Updates layout on user join, leave or status change.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # User join
        if kwargs['subtype'] == 'join':
            self.user_slot_dct[kwargs['name']
                               ] = UserSlot(**kwargs)
            self.ids.user_slot_layout.add_widget(
                self.user_slot_dct[kwargs['name']])
            self.ids.user_slot_layout.height += self.user_slot_dct[
                kwargs['name']].height

        # User leave
        elif kwargs['subtype'] == 'leave':
            self.ids.user_slot_layout.remove_widget(
                self.user_slot_dct[kwargs['name']])
            self.ids.user_slot_layout.height -= self.user_slot_dct[
                kwargs['name']].height
            del self.user_slot_dct[kwargs['name']]

        # User status change
        else:
            self.user_slot_dct[kwargs['name']].switch_status()

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
            self.call_slot_dct[call['master']] = CallSlot(**call)
            # Adding all slots to layout
            self.ids.call_slot_layout.add_widget(
                self.call_slot_dct[call['master']])
            self.ids.call_slot_layout.height += self.call_slot_dct[
                call['master']].height
        self.ids.call_num_lbl.text = 'Active calls ({})'.format(
            len(self.call_slot_dct))

    @mainthread
    def update(self, **kwargs):
        """Updates layout on call or user add or remove.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # Adding call
        if kwargs['subtype'] == 'call_add':
            self.call_slot_dct[kwargs['master']] = CallSlot(**kwargs)
            self.ids.call_slot_layout.add_widget(
                self.call_slot_dct[kwargs['master']])
            self.ids.call_slot_layout.height += self.call_slot_dct[
                kwargs['master']].height

        # Removing call
        elif kwargs['subtype'] == 'call_remove':
            self.ids.call_slot_layout.remove_widget(
                self.call_slot_dct[kwargs['master']])
            self.ids.call_slot_layout.height -= self.call_slot_dct[
                kwargs['master']].height
            del self.call_slot_dct[kwargs['master']]

        # Adding user to call
        elif kwargs['subtype'] == 'user_join':
            self.call_slot_dct[kwargs['master']].update(
                mode='join', **kwargs)

        # Removing user from call
        else:
            self.call_slot_dct[kwargs['master']].update(
                mode='leave', **kwargs)
            if 'new_master' in kwargs:
                call = self.call_slot_dct[kwargs['master']]
                del self.call_slot_dct[kwargs['master']]
                self.call_slot_dct[kwargs['new_master']] = call

        # Updating active call number
        self.ids.call_num_lbl.text = 'Active calls ({})'.format(
            len(self.call_slot_dct))


class PendingCallFooter(BoxLayout):

    """Footer widget to be shown when a call is pending (see .kv file for structure).

    Attributes:
        counter_update_evt (ClockEvent): Event scheduled by Kivy clock for
         updating counter every second.
        elapsed_time (int): Time elapsed since widget appearance.
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


class SessionLayout(BoxLayout):

    """Layout user sees during a call (see .kv file for structure).

    Attributes:
        chat_layout (ChatLayout): Chat message display layout.
        master (str): Current call master.
        video_layout (VideoLayout): Video capture display layout.
    """

    def __init__(self, **kwargs):
        """Constructor method.

        Args:
            **kwargs: Keyword arguments supplied in dictioanry form.
        """

        BoxLayout.__init__(self)
        self.master = kwargs['master']
        self.video_layout = VideoLayout(kwargs['user_lst'])
        self.add_widget(self.video_layout)
        self.chat_layout = ChatLayout()
        self.add_widget(self.chat_layout)

    def update(self, **kwargs):
        """Updates session layout when changes in call occur.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.video_layout.update(**kwargs)

        # User join
        if kwargs['subtype'] == 'user_join':
            kwargs['msg'] = '{} joined.'.format(kwargs['name'])

        # User leave
        elif kwargs['subtype'] == 'user_leave':
            if 'new_master' in kwargs:
                self.master = kwargs['new_master']
            kwargs['msg'] = '{} left.'.format(kwargs['name'])
        self.chat_layout.add_msg(**kwargs)


class VideoLayout(FloatLayout):

    """Layout of all active video transmissions (see .kv file for structure).

    Attributes:
        show_stats (bool): Whether to display statistics on screen.
        video_display_dct (dict): Dictionary mapping username to video display.
    """

    def __init__(self, user_lst):
        """Constructor method.

        Args:
            user_lst (list): List of users in call.
        """

        FloatLayout.__init__(self)
        self.video_display_dct = {}
        self.show_stats = False
        username = App.get_running_app().root_sm.current_screen.username
        for user in user_lst:
            if user != username:
                self.video_display_dct[
                    user] = PeerVideoDisplay(user, self.show_stats)
                self.ids.video_display_layout.add_widget(
                    self.video_display_dct[user])

    def update(self, **kwargs):
        """Updates video layout on user join or leave.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # User join
        if kwargs['subtype'] == 'user_join':
            video_display = PeerVideoDisplay(kwargs['name'], self.show_stats)
            self.video_display_dct[kwargs['name']] = video_display
            self.ids.video_display_layout.add_widget(video_display)

        # User leave
        elif kwargs['subtype'] == 'user_leave':
            self.ids.video_display_layout.remove_widget(
                self.video_display_dct[kwargs['name']])
            del self.video_display_dct[kwargs['name']]

    @mainthread
    def update_frame(self, **kwargs):
        """Updates video frame corresponding to user.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        username = App.get_running_app().root_sm.current_screen.username
        if kwargs['src'] != username and kwargs['src'] in self.video_display_dct:
            # Decoding JPEG frame
            frame = base64.b64decode(kwargs['frame'])
            frame = np.fromstring(frame, dtype='uint8')
            decoded_frame = cv2.imdecode(frame, 1)
            decoded_frame = cv2.flip(decoded_frame, 0)
            frame_texture = Texture.create(
                size=(decoded_frame.shape[1], decoded_frame.shape[0]),
                colorfmt='bgr')
            frame_texture.blit_buffer(
                decoded_frame.tostring(), colorfmt='bgr', bufferfmt='ubyte')

            # Displaying the new video frame on the correct display
            if kwargs['src'] in self.video_display_dct:
                self.video_display_dct[kwargs['src']
                                       ].ids.frame.texture = frame_texture

            # Updating video statistics
            peer = App.get_running_app().peer
            if peer.session and kwargs['src'] in peer.session.user_lst:
                tracker = peer.session.video_stat_dct[kwargs['src']]
                tracker.update(**kwargs)


class SelfVideoDisplay(Camera):

    """Display of self video capture (see .kv file for structure).
    """

    pass


class PeerVideoDisplay(BoxLayout):

    """Display of other peers' video capture (see .kv file for structure).

    Attributes:
        show_stats (bool): Whether to display statistics on display.
        stat_lbl (Label): Label for showing call statistics.
        user (str): Name of user in video.
    """

    def __init__(self, user, show_stats):
        """Constructor method

        Args:
            user (str): Name of user in video.
            show_stats (bool): Whether to display statistics on display.
        """

        self.user = user
        self.show_stats = show_stats
        BoxLayout.__init__(self)
        self.stat_lbl = StatisticsLabel(latency=0)
        if self.show_stats:
            self.ids.display.add_widget(self.stat_lbl)

    def flip_stats(self):
        """Showing/hiding statistics label.
        """

        if not self.show_stats:
            self.ids.display.add_widget(self.stat_lbl)
        else:
            self.ids.display.remove_widget(self.stat_lbl)

        self.show_stats = not self.show_stats


class StatisticsLabel(Label):
    """Label used for displaying call statistics (see .kv file for structure).

    Attributes:
        FORMAT_DCT (dict): Dictionary mapping each data type to its format.
    """

    FORMAT_DCT = {
        'framerate': lambda val: '{} fps'.format(round(val, 2)),
        'latency': lambda val: '{} ms'.format(round(val * 1000, 2)),
        'framedrop': lambda val: '{}%'.format(round(val * 100, 2))
    }

    def __init__(self, **kwargs):
        """Constructor method.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        Label.__init__(self)
        self.update(**kwargs)

    @mainthread
    def update(self, **kwargs):
        """Updates statistics with new data.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.text = '\n'.join(['{}: {}'.format(key, StatisticsLabel.FORMAT_DCT[
                              key](val)) for key, val in kwargs.items()])


class ChatLayout(BoxLayout):

    """Chat messages display layout (see .kv file for structure).
    """

    def __init__(self):
        """Constructor method.
        """

        BoxLayout.__init__(self)

    @mainthread
    def add_msg(self, **kwargs):
        """Adds message to chat layout.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # Building message to be added
        msg = kwargs['msg']
        if 'src' in kwargs:
            msg = '[b]{}[/b]: {}'.format(kwargs['src'], msg)
        time = datetime.datetime.fromtimestamp(
            kwargs['timestamp']).strftime('%H:%M')
        msg = '[{}] {}'.format(time, msg)

        # Adding message to chat layout
        msg_lbl = MessageLabel(msg)
        self.ids.chat_msg_layout.add_widget(msg_lbl)
        self.ids.chat_msg_layout.height += msg_lbl.height
        self.ids.scroll_layout.scroll_to(msg_lbl)

    def on_send_btn_press(self):
        """Sends chat message to group.
        """

        # Sending chat GUI event
        msg = self.ids.chat_input.text
        self.ids.chat_input.text = ''
        app = App.get_running_app()
        app.send_gui_evt({
            'type': 'session',
            'subtype': 'self_chat',
            'src': app.root_sm.current_screen.username,
            'msg': msg
        })


class MessageLabel(Label):

    """Label for displaying chat message (see .kv file do structure).

    Attributes:
        msg (str): Chat message
    """

    def __init__(self, msg):
        """Constructor method.

        Args:
            msg (str): Chat message
        """

        self.msg = msg
        Label.__init__(self)


class SessionFooter(BoxLayout):

    """Footer displayed during a call (see .kv file for structure).

    Attributes:
        counter_update_evt (ClockEvent): Event scheduled by Kivy clock for
         updating counter every second.
        elapsed_time (int): Time elapsed since widget appearance.
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

    def on_stat_btn_press(self):
        """Shows/hides call statistics from display.
        """

        root = App.get_running_app().root_sm.current_screen
        video_layout = root.session_layout.video_layout
        video_display_dct = video_layout.video_display_dct

        video_layout.show_stats = not video_layout.show_stats
        for user in video_display_dct:
            video_display_dct[user].flip_stats()

    def on_end_call_btn_press(self):
        """Leaves current call and notifies server.
        """

        app = App.get_running_app()
        app.send_gui_evt({
            'type': 'session',
            'subtype': 'leave'
        })


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

        # Adjusting maximum callback iterations at the end of frame
        Clock.max_iteration = 20

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
    def switch_to_main_screen(self, **kwargs):
        """Switches current screen to main screen.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        main_screen = MainScreen(**kwargs)
        self.root_sm.switch_to(main_screen)

# Running app
if __name__ == '__main__':
    PypeApp().run()
