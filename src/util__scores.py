from time import time

import numpy as np
from util__settings import get_ml_settings


class Scores:
    def __init__(self):
        ml_settings = get_ml_settings()
        self.buffer_size = ml_settings.score_buffer_size
        self.timestamps = np.zeros(self.buffer_size, dtype=np.float64)
        self.scores = np.zeros(self.buffer_size, dtype=np.float32)
        self.current_index = 0
        self.is_buffer_full = False
        self.WINDOW_SIZE = ml_settings.score_window_size
        self.SCORE_THRESHOLD = ml_settings.score_threshold

    def add_score(self, score):
        current_time = time()

        self.timestamps[self.current_index] = current_time
        self.scores[self.current_index] = score

        self.current_index = (self.current_index + 1) % self.buffer_size
        if self.current_index == 0:
            self.is_buffer_full = True

    def get_average_score(self):
        current_time = time()
        if not self.is_buffer_full and self.current_index == 0:
            return 0.0

        valid_mask = current_time - self.timestamps <= self.WINDOW_SIZE
        if self.is_buffer_full:
            valid_scores = self.scores[valid_mask]
        else:
            valid_scores = self.scores[: self.current_index][
                valid_mask[: self.current_index]
            ]

        return float(np.mean(valid_scores)) if len(valid_scores) > 0 else 0.0
