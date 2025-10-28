import time
from util__settings import get_runtime_settings
from util__send_notification import send_notification


class Notifications:
    def __init__(self, icon_path):
        self.last_notification_time = 0
        self.icon_path = icon_path
        self.interval_message = None

    def set_interval_message(self, message):
        """Set and immediately send a one-time interval change notification"""
        self.interval_message = message
        runtime_settings = get_runtime_settings()
        if (
            message
            and runtime_settings.notifications_enabled
            and not runtime_settings.focus_mode_enabled
        ):
            send_notification(message, "Tracking Interval Changed", self.icon_path)

    def check_and_notify(self, posture_score):
        current_time = time.time()
        # only apply cooldown to posture notifications
        runtime_settings = get_runtime_settings()
        if (
            not runtime_settings.notifications_enabled
            or runtime_settings.focus_mode_enabled
        ):
            return
        if posture_score < runtime_settings.poor_posture_threshold:
            if (
                current_time - self.last_notification_time
                > runtime_settings.notification_cooldown
            ):
                send_notification(
                    runtime_settings.default_posture_message,
                    "Posture Alert!",
                    self.icon_path,
                )
                self.last_notification_time = current_time
