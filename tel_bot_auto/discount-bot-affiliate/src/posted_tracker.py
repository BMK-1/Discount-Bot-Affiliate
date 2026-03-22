"""
Posted Tracker — Remembers which deals were posted to avoid reposts.
"""

import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
TRACKER_FILE = "data/posted.json"


class PostedTracker:
    def __init__(self):
        self.ttl_days = int(os.getenv("POSTED_TTL_DAYS", 7))
        self._data: dict = {}
        self._load()

    def _load(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(TRACKER_FILE, "r") as f:
                self._data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}
        self._purge_old()

    def _save(self):
        with open(TRACKER_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def _purge_old(self):
        cutoff = (datetime.utcnow() - timedelta(days=self.ttl_days)).isoformat()
        before = len(self._data)
        self._data = {k: v for k, v in self._data.items() if v > cutoff}
        if len(self._data) < before:
            self._save()

    def already_posted(self, product_id: str) -> bool:
        return product_id in self._data

    def mark_posted(self, product_id: str):
        self._data[product_id] = datetime.utcnow().isoformat()
        self._save()
