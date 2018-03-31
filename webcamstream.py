"""Live webcam stream class file.
"""

# Imports
import cv2

from decorators import new_thread


class WebcamStream(object):

    """Live webcam stream class.

    Attributes:
        cap (cv2.VideoCapture): Description
        COMPRESSION_QUALITY (int): Value indicating the resultant quality of frame
         after JPEG compression.
        frame (Image): Current frame.
        keep_streaming (bool): Indicates whether to keep reading frames in a seperate thread.
    """

    COMPRESSION_QUALITY = 20

    def __init__(self):
        """Constructor method.
        """

        self.cap = cv2.VideoCapture(1)
        self.frame = cv2.imencode('.jpg', self.cap.read()[1],
                                  [cv2.IMWRITE_JPEG_QUALITY,
                                   WebcamStream.COMPRESSION_QUALITY])[1]
        self.keep_streaming = True
        self.update_loop()

    @new_thread('webcam_stream_thread')
    def update_loop(self):
        """Reads frames from webcam in a seperate thread and compresses
        them using JPEG.
        """

        while self.keep_streaming:
            ret, frame = self.cap.read()
            if ret:
                ret, encoded_frame = cv2.imencode('.jpg', frame,
                                                  [cv2.IMWRITE_JPEG_QUALITY,
                                                   WebcamStream.COMPRESSION_QUALITY])
                if ret:
                    self.frame = encoded_frame

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
