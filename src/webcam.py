import threading
import time
from threading import Event, Thread

import cv2


class Webcam:
    def __init__(self, camera_id=0, fps=30):
        self.camera_id = camera_id
        self.cap = None
        self.is_running = Event()
        self.thread = None
        self.fps = fps
        self.frame_time = 1 / fps
        self._latest_frame = None
        self._latest_score = 0
        self._callback = None
        self._latest_pose_results = None

    def start(self, callback=None):
        """Start the camera capture with optional callback for frame processing"""
        if self.is_running.is_set():
            return False

        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            return False

        self._callback = callback
        self.is_running.set()
        self.thread = Thread(target=self._capture_loop)
        self.thread.daemon = True
        self.thread.start()
        return True

    def stop(self):
        """Stop the camera capture"""
        self.is_running.clear()
        if self.cap:
            self.cap.release()
        self.cap = None
        # Only try to join the thread if it's not the current thread
        if self.thread and self.thread != threading.current_thread():
            self.thread.join()  # Wait for thread to finish
        self.thread = None

    def _capture_loop(self):
        """Main capture loop running in separate thread"""
        while self.is_running.is_set():
            start_time = time.time()

            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to read frame from camera")
                    self.stop()
                    break

                if self._callback:
                    try:
                        frame, score, results = self._callback(frame)
                        self._latest_score = score
                        self._latest_pose_results = results
                    except Exception as e:
                        print(f"Error in frame callback: {e}")

                self._latest_frame = frame

            except Exception as e:
                print(f"Error capturing frame: {e}")
                self.stop()
                break

            processing_time = time.time() - start_time
            if processing_time < self.frame_time:
                time.sleep(self.frame_time - processing_time)

    @staticmethod
    def list_available_cameras(max_tests=3):
        """List all available cameras by testing indices up to max_tests"""
        available_cameras = []
        for i in range(max_tests):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
        return available_cameras

    def get_latest_frame(self):
        """Get the most recent frame and score"""
        return self._latest_frame, self._latest_score

    def get_latest_pose_results(self):
        """Get the most recent pose detection results"""
        return self._latest_pose_results

    def __del__(self):
        """Ensure cleanup on destruction"""
        self.stop()
