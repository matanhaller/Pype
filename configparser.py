"""Configuration file parsing interface.

Attributes:
    config (ConfigParser): Configuration file parser object.
    CONFIG_FILE_PATH (str): Configuration file path.
"""

# Imports
import json
from ConfigParser import ConfigParser

# Retreiving configuration options
CONFIG_FILE_PATH = 'config.cfg'
config = ConfigParser()
config.readfp(open(CONFIG_FILE_PATH))


def get_option(option):
    """Retreives specified option from configuration file.

    Args:
        option (str): Name of option to retreive from configuration file.

    Returns:
        str/int/float//bool: The value of the requested option.
    """

    global config
    try:
        return config.getint('Header', option)
    except ValueError:
        try:
            return config.getfloat('Header', option)
        except ValueError:
            try:
                return config.getboolean('Header', option)
            except ValueError:
                return config.get('Header', option)
