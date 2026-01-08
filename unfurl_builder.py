"""
Unfurl builder for creating and updating Slack message unfurls
"""
from typing import Dict, Any, List


class UnfurlBuilder:
    """Builds Slack Block Kit unfurls for Bluesky posts"""

    def __init__(self, bluesky_client):
        """
        Initialize unfurl builder

        Args:
            bluesky_client: BlueskyClient instance for fetching post data
        """
        self.bluesky_client = bluesky_client

    def create_unfurl(self, url: str) -> Dict[str, Any]:
        """
        Create initial unfurl for a Bluesky link

        Args:
            url: Bluesky post URL

        Returns:
            Unfurl data dict with blocks, or None if URL is invalid
        """
        # Extract post info from the URL
        post_info = self.bluesky_client.extract_post_info(url)
        if not post_info:
            return None

        post_data = self.bluesky_client.get_post(
            post_info['handle'],
            post_info['post_id']
        )

        if not post_data:
            return self._build_error_unfurl("Post not accessible")

        # Build the blocks for the unfurl
        unfurl_blocks = []

        # Add author header
        unfurl_blocks.append(self._build_author_block(post_data))

        # Add post text
        text = post_data.get('text', '')
        if text:
            unfurl_blocks.append(self._build_text_block(text))

        # Check for video - add placeholder if present
        video = post_data.get('video')
        if video and video.get('has_video'):
            unfurl_blocks.append(self._build_processing_placeholder())

        return {"blocks": unfurl_blocks}

    def create_complete_unfurl(self, url: str, video_url: str, thumbnail_url: str) -> Dict[str, Any]:
        """
        Create complete unfurl with processed video

        Args:
            url: Bluesky post URL
            video_url: Direct URL to video file (.mp4)
            thumbnail_url: URL to video thumbnail

        Returns:
            Complete unfurl data dict with video block
        """
        # Get the original post data
        post_info = self.bluesky_client.extract_post_info(url)
        if not post_info:
            return None

        post_data = self.bluesky_client.get_post(
            post_info['handle'],
            post_info['post_id']
        )

        if not post_data:
            return None

        # Build unfurl blocks
        unfurl_blocks = []

        # Add author header
        unfurl_blocks.append(self._build_author_block(post_data))

        # Add post text
        text = post_data.get('text', '')
        if text:
            unfurl_blocks.append(self._build_text_block(text))

        # Add video block
        unfurl_blocks.append(self._build_video_block(video_url, thumbnail_url))

        return {"blocks": unfurl_blocks}

    def create_error_unfurl(self, url: str, error_message: str) -> Dict[str, Any]:
        """
        Create unfurl with error message

        Args:
            url: Bluesky post URL
            error_message: Error message to display

        Returns:
            Unfurl data dict with error message
        """
        # Get the original post data to maintain context
        post_info = self.bluesky_client.extract_post_info(url)
        if not post_info:
            return None

        post_data = self.bluesky_client.get_post(
            post_info['handle'],
            post_info['post_id']
        )

        if not post_data:
            return None

        # Build unfurl blocks with error
        unfurl_blocks = []

        # Add author header
        unfurl_blocks.append(self._build_author_block(post_data))

        # Add post text
        text = post_data.get('text', '')
        if text:
            unfurl_blocks.append(self._build_text_block(text))

        # Add error message
        unfurl_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": error_message
            }
        })

        return {"blocks": unfurl_blocks}

    def _build_author_block(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build author header block"""
        author = post_data.get('author', {})
        author_text = f"*{author.get('display_name', 'Unknown')}*"
        if author.get('handle'):
            author_text += f" @{author['handle']}"

        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": author_text
                }
            ]
        }

    def _build_text_block(self, text: str) -> Dict[str, Any]:
        """Build text content block"""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        }

    def _build_processing_placeholder(self) -> Dict[str, Any]:
        """Build video processing placeholder block"""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🎬 *Processing video...* ⏳"
            }
        }

    def _build_video_block(self, video_url: str, thumbnail_url: str) -> Dict[str, Any]:
        """Build video player block"""
        return {
            "type": "video",
            "video_url": video_url,
            "alt_text": "Video from Bluesky post",
            "title": {"type": "plain_text", "text": "Video", "emoji": True},
            "thumbnail_url": thumbnail_url
        }

    def _build_error_unfurl(self, message: str) -> Dict[str, Any]:
        """Build error unfurl for invalid/inaccessible posts"""
        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{message}*\n\nThis post may not be viewable without being logged in or has been deleted."
                    }
                }
            ]
        }
