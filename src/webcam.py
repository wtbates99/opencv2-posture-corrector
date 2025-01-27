import platform
import os
import cv2
import time
import threading
from threading import Event, Thread


class Webcam:
    def __init__(self, camera_id=0, backend=None, fps=30):
        self.camera_id = camera_id
        self.backend = backend
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
        """Start the camera capture with the specified backend."""
        if self.is_running.is_set():
            return False

        if self.backend is not None:
            self.cap = cv2.VideoCapture(self.camera_id, self.backend)
        else:
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
    def list_available_cameras(max_tests=10):
        """List cameras with OS-specific backends and names."""
        available_cameras = []
        for index in range(max_tests):
            backend = None
            if platform.system() == "Windows":
                backend = cv2.CAP_DSHOW
            elif platform.system() == "Darwin":
                backend = cv2.CAP_AVFOUNDATION

            cap = (
                cv2.VideoCapture(index, backend) if backend else cv2.VideoCapture(index)
            )
            if not cap.isOpened():
                cap.release()
                continue

            device_name = f"Camera {index}"
            os_name = platform.system()
            if os_name == "Linux":
                sysfs_path = f"/sys/class/video4linux/video{index}/name"
                if os.path.exists(sysfs_path):
                    with open(sysfs_path, "r") as f:
                        device_name = f.read().strip()
            # For Windows and macOS, just use the index-based name since
            # CAP_PROP_DEVICE_DESCRIPTION isn't consistently available

            cap.release()
            available_cameras.append((index, device_name, backend))

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
