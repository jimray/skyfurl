"""
Video processor for downloading and stitching Bluesky M3U8 videos
"""
import os
import uuid
import subprocess
from pathlib import Path
from typing import Optional


class VideoProcessor:
    def __init__(self, storage_dir: str = "videos"):
        """
        Initialize video processor

        Args:
            storage_dir: Directory to store processed videos
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def process_video(self, m3u8_url: str) -> Optional[str]:
        """
        Download and stitch M3U8 video into MP4

        Args:
            m3u8_url: URL to the M3U8 playlist

        Returns:
            video_id if successful, None otherwise
        """
        if not m3u8_url:
            return None

        try:
            # Generate unique video ID
            video_id = str(uuid.uuid4())
            output_path = self.storage_dir / f"{video_id}.mp4"
            thumbnail_path = self.storage_dir / f"{video_id}_thumbnail.jpg"

            print(f"Processing video {video_id} from {m3u8_url}")

            # Download and convert M3U8 to MP4 using ffmpeg
            # ffmpeg can handle M3U8 playlists directly
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", m3u8_url,
                "-c", "copy",  # Copy codec (no re-encoding for speed)
                "-movflags", "+faststart",  # Optimize for streaming
                "-y",  # Overwrite output file
                str(output_path)
            ]

            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                print(f"ffmpeg error: {result.stderr}")
                return None

            # Generate thumbnail from first frame
            thumbnail_cmd = [
                "ffmpeg",
                "-i", str(output_path),
                "-ss", "00:00:01",  # 1 second in
                "-vframes", "1",  # Extract 1 frame
                "-vf", "scale=640:-1",  # Scale to 640px width
                "-y",
                str(thumbnail_path)
            ]

            subprocess.run(
                thumbnail_cmd,
                capture_output=True,
                timeout=30
            )

            print(f"Successfully processed video {video_id}")
            return video_id

        except subprocess.TimeoutExpired:
            print(f"Video processing timed out for {m3u8_url}")
            return None
        except Exception as e:
            print(f"Error processing video: {e}")
            return None

    def get_video_path(self, video_id: str) -> Optional[Path]:
        """Get the file path for a processed video"""
        path = self.storage_dir / f"{video_id}.mp4"
        return path if path.exists() else None

    def get_thumbnail_path(self, video_id: str) -> Optional[Path]:
        """Get the file path for a video thumbnail"""
        path = self.storage_dir / f"{video_id}_thumbnail.jpg"
        return path if path.exists() else None

    def delete_video(self, video_id: str):
        """Delete a processed video and its thumbnail"""
        video_path = self.storage_dir / f"{video_id}.mp4"
        thumbnail_path = self.storage_dir / f"{video_id}_thumbnail.jpg"

        if video_path.exists():
            video_path.unlink()

        if thumbnail_path.exists():
            thumbnail_path.unlink()
