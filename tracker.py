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


def exp_moving_avg(avg, val, weight):
    """Calculates exponential moving average.

    Args:
        avg (float): Current average.
        val (float): New value.
        weight (float): Weight for new average calculation.

    Returns:
        float: The new average.
    """

    if avg == 0:
        return val
    return weight * val + (1 - weight) * avg


class Tracker(object):

    """Statistics class file.

    Attributes:
        arrived_lst (list): Temporary list of packets that have arrived out of order.
        call_start (float): Timestamp of user join to call.
        first_packet_flag (bool): Flag indicating whether the arrived packet is the first one.
        last_update_dct (dict): Dictionary mapping statistics type to its last update.
        lost_packets (int): The number of lost packets.
        recvd_packets_framedrop (int): The number of received packets
        recvd_packets_framerate (int): The number of received packets
        seq (int): Current packet sequence number.
        stat_dct (dict): Dictionary mapping statistics type to value.
        tracking_dct (dict): Dictionary for tracking sequence numbers of
         packets yet to arrive.
        xlst (list): Time values (for latency plot).
        ylst (list): Latency values (for latency plot).
    """

    def __init__(self):
        """Constructor method
        """

        self.call_start = time.time()
        self.xlst = []
        self.ylst = []
        self.first_packet_flag = True
        self.seq = 0
        self.recvd_packets_framerate = 0
        self.recvd_packets_framedrop = 0
        self.lost_packets = 0
        self.stat_dct = {
            'framerate': 0,
            'latency': 0,
            'framedrop': 0
        }
        self.tracking_dct = {}
        self.arrived_lst = []
        self.last_update_dct = {stat: time.time() for stat in self.stat_dct}

    def update(self, **kwargs):
        """Updates all statistics based on new packet.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # Updating framerate
        self.update_framerate(**kwargs)

        # Updating latency
        self.update_latency(**kwargs)

        # Updating framedrop
        self.update_framedrop(**kwargs)

    def update_framerate(self, **kwargs):
        """Measures and updates average framerate.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.recvd_packets_framerate += 1
        delta_t = time.time() - self.last_update_dct['framerate']

        if delta_t > 0.5:
            # Updating average framerate
            new_framerate = self.recvd_packets_framerate / delta_t
            weight = exp_weight(delta_t)
            self.stat_dct['framerate'] = exp_moving_avg(
                self.stat_dct['framerate'], new_framerate, weight)

            self.recvd_packets_framerate = 0

            self.last_update_dct['framerate'] = time.time()

    def update_latency(self, **kwargs):
        """Measures and updates average latency.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        # Calculating latency of received packet
        new_latency = time.time() - kwargs['timestamp']

        # Adding time values to plot (for testing purposes)
        self.xlst.append(time.time() - self.call_start)

        # Updating average latency
        delta_t = time.time() - self.last_update_dct['latency']
        weight = exp_weight(delta_t)
        self.stat_dct['latency'] = exp_moving_avg(
            self.stat_dct['latency'], new_latency, weight)

        # Adding average latency values to plot (for testing purposes)
        self.ylst.append(self.stat_dct['latency'] * 1000)

        self.last_update_dct['latency'] = time.time()

    def update_framedrop(self, **kwargs):
        """Measures and updates average framedrop rate.

        Args:
            **kwargs: Keyword arguments supplied in dictionary form.
        """

        self.recvd_packets_framedrop += 1

        if self.first_packet_flag:
        	# Adapting local sequence number with first packet that arrived
            self.seq = kwargs['seq'] + 1
            self.first_packet_flag = False
        else:
            # Adding pending packets to tracking dictionary
            if kwargs['seq'] > self.seq:
                for seq in xrange(self.seq, kwargs['seq']):
                    if seq not in self.tracking_dct and seq not in self.arrived_lst:
                        self.tracking_dct[seq] = 0
                self.arrived_lst.append(kwargs['seq'])

            # Removing arrived packets from tracking dictionary
            if kwargs['seq'] in self.tracking_dct:
                del self.tracking_dct[kwargs['seq']]
                self.arrived_lst.append(kwargs['seq'])
                if len(self.arrived_lst) > 3:
                    self.arrived_lst.pop(0)

            # Tracking pending packets
            lost_packet_lst = []
            for seq in self.tracking_dct:
                if self.tracking_dct[seq] == 2:
                    lost_packet_lst.append(seq)
                    if kwargs['seq'] > seq:
                        self.lost_packets += 1
                    continue
                self.tracking_dct[seq] += 1

            # Removing lost packets from dictionary
            for seq in lost_packet_lst:
                del self.tracking_dct[seq]
                self.seq += 1

            self.seq += 1

            delta_t = time.time() - self.last_update_dct['framedrop']
            if delta_t > 0.5:
                # Updating average framedrop
                new_framedrop = self.lost_packets / \
                    float(self.lost_packets + self.recvd_packets_framedrop)
                weight = exp_weight(delta_t)
                self.stat_dct['framedrop'] = exp_moving_avg(
                    self.stat_dct['framedrop'], new_framedrop, weight)

                self.recvd_packets_framedrop = 0
                self.lost_packets = 0

                self.last_update_dct['framedrop'] = time.time()
