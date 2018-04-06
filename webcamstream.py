"""Live webcam stream class file.
"""

# Imports
import ConfigParser
import cv2
from decorators import new_thread

from configparser import get_option


class WebcamStream(object):

    """Live webcam stream class.

    Attributes:
        cap (cv2.VideoCapture): Webcam video captuer object.
        frame (Image): Current frame.
        keep_streaming (bool): Indicates whether to keep reading frames in a seperate thread.
        updated_frame (bool): Whether a frame hasn't been read yet.
    """

    def __init__(self):
        """Constructor method.
        """

        self.cap = cv2.VideoCapture(get_option('cam_index'))
        self.frame = self.cap.read()[1]
        self.updated_frame = True
        self.keep_streaming = True
        self.update_loop()

    @new_thread('webcam_stream_thread')
    def update_loop(self):
        """Reads frames from webcam in a seperate thread.
        """

        while self.keep_streaming:
            ret, frame = self.cap.read()
            if ret:
                self.frame = frame
                self.updated_frame = True

    def read(self):
        """Retrieves current frame from webcam if it's updated.

        Returns:
            Image: The current frame.
        """

        if self.updated_frame:
            self.updated_frame = False
            return self.frame

        return None

    def terminate(self):
        """Terminates webcam stream.
        """

        self.keep_streaming = False
        self.cap.release()
