"""Configuration file parsing interface.

Attributes:
    config (ConfigParser): Configuration file parser object.
    CONFIG_FILE_PATH (str): Configuration file path.
"""

# Imports
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
        str/int/bool/list: The value of the requested option.
    """

    global config
    try:
        return config.getint('Header', option)
    except ValueError:
        try:
            return config.getboolean('Header', option)
        except ValueError:
            option = config.get('Header', option)
            if ',' in option:
                return option.split(',')
            return option
