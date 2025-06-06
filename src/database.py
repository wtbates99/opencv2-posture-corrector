import sqlite3
from datetime import datetime

from util__settings import POSTURE_LANDMARKS


class Database:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.posture_landmarks = POSTURE_LANDMARKS
        self._create_tables()

    def _create_tables(self):
        self.create_table(
            "posture_scores",
            [
                ("timestamp", "DATETIME"),
                ("score", "FLOAT"),
            ],
        )

        self.create_table(
            "pose_landmarks",
            [
                ("timestamp", "DATETIME"),
                ("landmark_name", "TEXT"),
                ("x", "FLOAT"),
                ("y", "FLOAT"),
                ("z", "FLOAT"),
                ("visibility", "FLOAT"),
            ],
        )

    def create_table(self, table_name: str, columns: list[tuple[str, str]]):
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join([f'{col[0]} {col[1]}' for col in columns])})"
        )
        self.conn.commit()

    def insert(self, table_name: str, values: list[tuple]):
        placeholders = ", ".join(["?" for _ in values[0]])
        self.cursor.executemany(
            f"INSERT INTO {table_name} VALUES ({placeholders})",
            values,
        )
        self.conn.commit()

    def save_pose_data(self, landmarks, score):
        timestamp = datetime.now().isoformat()

        self.insert("posture_scores", [(timestamp, score)])

        landmark_data = []
        for landmark_enum in self.posture_landmarks:
            landmark = landmarks.landmark[landmark_enum]
            landmark_data.append(
                (
                    timestamp,
                    landmark_enum.name,
                    landmark.x,
                    landmark.y,
                    landmark.z,
                    landmark.visibility,
                )
            )
        self.insert("pose_landmarks", landmark_data)

    def close(self):
        self.conn.close()
