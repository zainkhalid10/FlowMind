"""In-memory storage for progress tracking"""
from typing import Dict, Optional
from services.progress_service import ProgressTracker
import uuid

# Global storage for progress trackers
_progress_trackers: Dict[str, ProgressTracker] = {}


def create_progress_tracker() -> tuple[str, ProgressTracker]:
    """Create a new progress tracker and return its ID."""
    tracker = ProgressTracker()
    tracker_id = str(uuid.uuid4())
    _progress_trackers[tracker_id] = tracker
    return tracker_id, tracker


def get_progress_tracker(tracker_id: str) -> Optional[ProgressTracker]:
    """Get a progress tracker by ID."""
    return _progress_trackers.get(tracker_id)


def remove_progress_tracker(tracker_id: str):
    """Remove a progress tracker (cleanup)."""
    _progress_trackers.pop(tracker_id, None)


def cleanup_old_trackers(max_age_seconds: int = 3600):
    """Clean up old progress trackers."""
    import time
    current_time = time.time()
    to_remove = []
    
    for tracker_id, tracker in _progress_trackers.items():
        if tracker.start_time:
            age = current_time - tracker.start_time
            if age > max_age_seconds:
                to_remove.append(tracker_id)
    
    for tracker_id in to_remove:
        remove_progress_tracker(tracker_id)

