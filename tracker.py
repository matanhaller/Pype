"""Statistics tracker class file.
"""

# Imports
import time

from numpy import exp


def exp_weight(delta_t):
    """Calculate weight for exponential moving average based on time difference.

    Args:
        delta_t (float): Length of time interval.

    Returns:
        float: Resultant weight.
    """

    return 1 - exp(-delta_t)


class Tracker(object):

    """Statistics class file.

    Attributes:
        last_update (float): Timestamp of last statistics update.
        seq (int): Current packet sequence number.
        stat_dct (dict): Dictionary mapping statistics type to value.
    """

    def __init__(self):
        """Constructor method
        """

        self.seq = 0
        self.last_update = time.time()
        self.stat_dct = {
            'latency': 0,
            'loss rate': 0
        }

    def update(self, **kwargs):
        """Updates all statistics based on new packet.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # Updating latency
        self.update_latency(**kwargs)

        # Updating last update timestamp
        self.last_update = time.time()

    def update_latency(self, **kwargs):
        """Measures and updates average latency.

        Args:
            **kwargs: eyword arguments supplied in dictionary form.
        """

        # Calculating latency of received packet
        new_latency = time.time() - kwargs['timestamp']

        # Updating average latency
        if self.stat_dct['latency'] == 0:
            self.stat_dct['latency'] = new_latency
        else:
            weight = exp_weight(time.time() - self.last_update)
            self.stat_dct['latency'] = weight * new_latency + \
                (1 - weight) * self.stat_dct['latency']
