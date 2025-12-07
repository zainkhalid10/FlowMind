"""Progress tracking service for document processing"""
import time
from typing import Dict, Optional
from enum import Enum


class ProcessingStage(Enum):
    """Processing stages for document extraction."""
    UPLOADING = ("Uploading file", 0, 5)
    PARSING = ("Parsing document", 5, 25)
    TEXT_EXTRACTION = ("Extracting text", 25, 50)
    IMAGE_DETECTION = ("Detecting images", 50, 65)
    OCR_PROCESSING = ("Processing OCR", 65, 80)
    IMAGE_SUMMARIZATION = ("Summarizing images", 80, 90)
    FINALIZING = ("Finalizing", 90, 100)
    COMPLETE = ("Complete", 100, 100)
    
    def __init__(self, description: str, start_percent: int, end_percent: int):
        self.description = description
        self.start_percent = start_percent
        self.end_percent = end_percent


class ProgressTracker:
    """Tracks progress for document processing with time estimation."""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.current_stage: ProcessingStage = ProcessingStage.UPLOADING
        self.stage_start_time: Optional[float] = None
        self.stage_durations: Dict[str, float] = {}
        self.total_pages: int = 0
        self.current_page: int = 0
        self.total_images: int = 0
        self.current_image: int = 0
        
    def start(self):
        """Start tracking progress."""
        self.start_time = time.time()
        self.stage_start_time = self.start_time
        # Initialize with UPLOADING stage
        self.current_stage = ProcessingStage.UPLOADING
        
    def set_stage(self, stage: ProcessingStage, **kwargs):
        """Set current processing stage."""
        # Record duration of previous stage
        if self.stage_start_time and self.current_stage != stage:
            duration = time.time() - self.stage_start_time
            self.stage_durations[self.current_stage.name] = duration
        
        self.current_stage = stage
        self.stage_start_time = time.time()
        
        # Update context if provided
        if 'total_pages' in kwargs:
            self.total_pages = kwargs['total_pages']
        if 'current_page' in kwargs:
            self.current_page = kwargs['current_page']
        if 'total_images' in kwargs:
            self.total_images = kwargs['total_images']
        if 'current_image' in kwargs:
            self.current_image = kwargs['current_image']
    
    def get_progress(self) -> Dict:
        """Get current progress information."""
        if not self.start_time:
            return {
                "progress": 0,
                "stage": "not_started",
                "message": "Not started",
                "estimated_time_remaining": None
            }
        
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Calculate progress percentage based on stage
        stage_progress = self._calculate_stage_progress()
        overall_progress = stage_progress
        
        # Estimate time remaining
        estimated_remaining = self._estimate_time_remaining(elapsed, overall_progress)
        
        # Build detailed message
        message = self._build_message()
        
        return {
            "progress": min(overall_progress, 99),  # Cap at 99% until complete
            "stage": self.current_stage.name.lower(),
            "message": message,
            "estimated_time_remaining": estimated_remaining,
            "elapsed_time": round(elapsed, 1),
            "current_stage": self.current_stage.description
        }
    
    def _calculate_stage_progress(self) -> float:
        """Calculate progress within current stage."""
        stage = self.current_stage
        
        if stage == ProcessingStage.UPLOADING:
            return 5
        elif stage == ProcessingStage.PARSING:
            if self.total_pages > 0:
                page_progress = (self.current_page / self.total_pages) * 20
                return 5 + page_progress
            return 15
        elif stage == ProcessingStage.TEXT_EXTRACTION:
            return 40
        elif stage == ProcessingStage.IMAGE_DETECTION:
            return 60
        elif stage == ProcessingStage.OCR_PROCESSING:
            if self.total_images > 0:
                image_progress = (self.current_image / self.total_images) * 15
                return 65 + image_progress
            return 75
        elif stage == ProcessingStage.IMAGE_SUMMARIZATION:
            if self.total_images > 0:
                image_progress = (self.current_image / self.total_images) * 10
                return 80 + image_progress
            return 88
        elif stage == ProcessingStage.FINALIZING:
            # FINALIZING can be 90-99% depending on sub-stages
            # We'll use 90% as base, and let it progress to 99% during AI processing
            return 90
        elif stage == ProcessingStage.COMPLETE:
            return 100
        
        return stage.start_percent
    
    def _estimate_time_remaining(self, elapsed: float, progress: float) -> Optional[str]:
        """Estimate time remaining based on current progress."""
        if progress <= 0 or progress >= 100:
            return None
        
        # Calculate average speed
        if progress > 0:
            estimated_total = elapsed / (progress / 100)
            remaining = estimated_total - elapsed
            
            # Use stage-specific estimates if available
            if self.current_stage in self.stage_durations:
                avg_stage_time = self.stage_durations.get(self.current_stage.name, 0)
                if avg_stage_time > 0:
                    # Estimate based on remaining stages
                    remaining_stages = self._get_remaining_stages()
                    estimated_remaining = sum(
                        self.stage_durations.get(stage.name, avg_stage_time)
                        for stage in remaining_stages
                    )
                    remaining = max(remaining, estimated_remaining * 0.5)  # Conservative estimate
            
            if remaining < 0:
                return None
            
            # Format time remaining
            if remaining < 60:
                return f"{int(remaining)}s"
            elif remaining < 3600:
                minutes = int(remaining / 60)
                seconds = int(remaining % 60)
                return f"{minutes}m {seconds}s"
            else:
                hours = int(remaining / 3600)
                minutes = int((remaining % 3600) / 60)
                return f"{hours}h {minutes}m"
        
        return None
    
    def _get_remaining_stages(self) -> list:
        """Get list of remaining processing stages."""
        all_stages = list(ProcessingStage)
        current_index = all_stages.index(self.current_stage)
        return all_stages[current_index + 1:-1]  # Exclude COMPLETE
    
    def _build_message(self) -> str:
        """Build detailed progress message."""
        stage = self.current_stage
        base_msg = stage.description
        
        # Add context-specific details
        if stage == ProcessingStage.PARSING and self.total_pages > 0:
            return f"{base_msg} (Page {self.current_page}/{self.total_pages})"
        elif stage == ProcessingStage.OCR_PROCESSING and self.total_images > 0:
            return f"{base_msg} (Image {self.current_image}/{self.total_images})"
        elif stage == ProcessingStage.IMAGE_SUMMARIZATION and self.total_images > 0:
            return f"{base_msg} (Image {self.current_image}/{self.total_images})"
        
        return base_msg
    
    def complete(self):
        """Mark processing as complete."""
        self.set_stage(ProcessingStage.COMPLETE)
        if self.stage_start_time:
            duration = time.time() - self.stage_start_time
            self.stage_durations[ProcessingStage.COMPLETE.name] = duration

