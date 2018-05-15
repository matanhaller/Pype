"""App design file.
(credit to Designmodo for widget colors)
(credit to Lukasz Dziedzic for fonts)

Attributes:
    DARK_COLOR_DCT (dict): Dictionary of dark widget colors.
    GRAY (str): Gray color (not intended to be used as widget background color).
    LIGHT_COLOR_DCT (dict): Dictionary of light widget colors.
    WINDOW_COLOR (str): Window color.
    WINDOW_HEIGHT (int): Window height.
    WINDOW_WIDTH (int): Window width.
"""

# Imports
import random

from kivy.config import Config
from kivy.utils import rgba

# Setting window size (must be done before window creation)
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
Config.set('graphics', 'width', WINDOW_WIDTH)
Config.set('graphics', 'height', WINDOW_HEIGHT)

from kivy.core.window import Window
from kivy.core.text import LabelBase

WINDOW_COLOR = '#2C3E50'
GRAY = '#34495E'
LIGHT_COLOR_DCT = {'turqoise': '#1ABC9C',
                   'green': '#2ECC71',
                   'blue': '#3498DB',
                   'purple': '#9B59B6',
                   'yellow': '#F1C40F',
                   'orange': '#E67E22',
                   'red': '#E74C3C'}
DARK_COLOR_DCT = {'turqoise': '#16A085',
                  'green': '#27AE60',
                  'blue': '#2980B9',
                  'purple': '#8E44AD',
                  'yellow': '#F39C12',
                  'orange': '#D35400',
                  'red': '#C0392B'}

# Setting window color
Window.clearcolor = rgba(WINDOW_COLOR)

# Registering external fonts to the app
LabelBase.register(name='LatoRegular',
                   fn_regular='fonts/Lato-Regular.ttf', fn_bold='fonts/Lato-Bold.ttf')
LabelBase.register(name='LatoBold', fn_regular='fonts/Lato-Bold.ttf')
LabelBase.register(name='LatoLight', fn_regular='fonts/Lato-Light.ttf')


def get_color(type, name):
    """Retrieves a specific color.

    Args:
        type (str): Color type (light/dark).
        name (str): Color name.

    Returns:
        str: The chosen color in RGBA format.
    """

    if type == 'light':
        return rgba(LIGHT_COLOR_DCT[name])
    return rgba(DARK_COLOR_DCT[name])


def get_random_color():
    """Chooses a random widget color.

    Returns:
        str: Randomly chosen color name
    """

    return random.choice(LIGHT_COLOR_DCT.keys())
