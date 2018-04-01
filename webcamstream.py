"""Live webcam stream class file.
"""

# Imports
import cv2

from decorators import new_thread


class WebcamStream(object):

    """Live webcam stream class.

    Attributes:
        cap (cv2.VideoCapture): Webcam video captuer object.
        frame (Image): Current frame.
        keep_streaming (bool): Indicates whether to keep reading frames in a seperate thread.
    """

    COMPRESSION_QUALITY = 20

    def __init__(self):
        """Constructor method.
        """

        self.cap = cv2.VideoCapture(1)
        self.frame = self.cap.read()[1]
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

    def read(self):
        """Retrieves current frame from webcam.

        Returns:
            Image: The current frame.
        """

        return self.frame

    def terminate(self):
        """Terminates webcam stream.
        """

        self.keep_streaming = False
        self.cap.release()
