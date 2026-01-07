"""
A Slack app for unfurling ATProto microblog links

Apps built on AT Protocol, such as Bluesky or Blacksky, show up just ok when posted to Slack.
This app handles those links better by adding rich content, like video.
"""
import os
import logging
import threading
from typing import Dict, Any

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from flask import send_file, render_template_string

from bluesky_client import BlueskyClient
from video_processor import VideoProcessor

class SkyfurlApp:
    def __init__(self):
        #Init the Slack app
        self.app = App(
                token=os.environ.get("SLACK_BOT_TOKEN"),
                signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
        )

        # Init the Bluesky client (no auth needed for public posts)
        # TODO: add optional auth via app password for fetching non-public posts?
        self.bluesky_client = BlueskyClient()

        # Init video processor
        self.video_processor = VideoProcessor()

        # Register event handlers for Slack events (eg link_shared)
        self.register_handlers()

        # Register HTTP routes for serving videos
        self.register_routes()

    def register_handlers(self):
        """Register Salck event handlers"""

        @self.app.event("link_shared")
        def handle_link_shared(event, client, say):
            """Handle link_shared events"""
            print(f"Link shared event: {event}")

            links = event.get("links", [])
            unfurls = {}

            for link in links:
                url = link.get("url", "")

                unfurl_data = self.create_unfurl(url, event, client)
                if unfurl_data:
                    unfurls[url] = unfurl_data

            # Send unfurls back to Slack
            if unfurls:
                try:
                    client.chat_unfurl(
                            channel=event["channel"],
                            ts=event["message_ts"],
                            unfurls=unfurls
                    )
                    print(f"Succesfully unfurled {len(unfurls)} link(s)")
                except Exception as e:
                    print(f"Effor unfurling: {e}")

    def register_routes(self):
        """Register HTTP routes for serving videos"""

        @self.app.server.route("/videos/<video_id>.mp4")
        def serve_video(video_id):
            """Serve processed video file"""
            video_path = self.video_processor.get_video_path(video_id)
            if video_path:
                return send_file(video_path, mimetype='video/mp4')
            return "Video not found", 404

        @self.app.server.route("/videos/<video_id>/thumbnail.jpg")
        def serve_thumbnail(video_id):
            """Serve video thumbnail"""
            thumbnail_path = self.video_processor.get_thumbnail_path(video_id)
            if thumbnail_path:
                return send_file(thumbnail_path, mimetype='image/jpeg')
            return "Thumbnail not found", 404

        @self.app.server.route("/player/<video_id>")
        def serve_player(video_id):
            """Serve HTML video player page (iframe-embeddable)"""
            app_url = os.environ.get("APP_URL", "http://localhost:3000")
            video_url = f"{app_url}/videos/{video_id}.mp4"

            # Simple HTML5 video player
            player_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Video Player</title>
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        background: #000;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                    }}
                    video {{
                        max-width: 100%;
                        max-height: 100vh;
                        width: 100%;
                    }}
                </style>
            </head>
            <body>
                <video controls autoplay>
                    <source src="{video_url}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </body>
            </html>
            """
            return render_template_string(player_html)

    def create_unfurl(self, url: str, event: Dict[str, Any], client) -> Dict[str, Any]:
        """
        Create the unfurl data

        Returns a Slack attachment for the unfurl
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
            # Return a message the post couldn't be fetched
            return{
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "  *Post not accessible*\n\nThis post may not be viewable without being logged in or has been deleted."
                        }
                    }
                ]
            }

        # Build the blocks for the unfurl
        unfurl_blocks = []

        # Author header
        author = post_data.get('author', {})
        author_text = f"*{author.get('display_name', 'Unknown')}*"
        if author.get('handle'):
            author_text += f" @{author['handle']}"

        unfurl_blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": author_text
                }
            ]
        })

        # Post text
        text = post_data.get('text', '')
        if text:
            unfurl_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            })

        # Video - show placeholder and process in background
        video = post_data.get('video')
        if video and video.get('has_video'):
            # Show "processing" placeholder
            unfurl_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🎬 *Processing video...* ⏳"
                }
            })

            # Start background video processing
            threading.Thread(
                target=self.process_video_background,
                args=(url, video, event["channel"], event["message_ts"], client),
                daemon=True
            ).start()

        return {"blocks": unfurl_blocks}

    def process_video_background(self, url: str, video: Dict[str, Any], channel: str, ts: str, client):
        """
        Background task to download, process, and serve video
        """
        try:
            print(f"Starting video processing for {url}")

            # Download and stitch video
            video_id = self.video_processor.process_video(video.get('video_url'))

            if not video_id:
                print(f"Failed to process video for {url}")
                # Update unfurl with error message
                self._update_unfurl_with_error(url, channel, ts, client)
                return

            # Get the app's public URL (for serving videos)
            app_url = os.environ.get("APP_URL", "http://localhost:3000")

            # Build video player URL
            player_url = f"{app_url}/player/{video_id}"
            thumbnail_url = f"{app_url}/videos/{video_id}/thumbnail.jpg"

            # Update unfurl with video block
            self._update_unfurl_with_video(url, channel, ts, client, player_url, thumbnail_url)

            print(f"Successfully processed video for {url}")

        except Exception as e:
            print(f"Error processing video: {e}")
            self._update_unfurl_with_error(url, channel, ts, client)

    def _update_unfurl_with_video(self, url: str, channel: str, ts: str, client, player_url: str, thumbnail_url: str):
        """Update the unfurl with the processed video"""
        try:
            # Get the original post data again to rebuild the unfurl
            post_info = self.bluesky_client.extract_post_info(url)
            if not post_info:
                return

            post_data = self.bluesky_client.get_post(
                post_info['handle'],
                post_info['post_id']
            )

            if not post_data:
                return

            # Rebuild unfurl blocks
            unfurl_blocks = []

            # Author header
            author = post_data.get('author', {})
            author_text = f"*{author.get('display_name', 'Unknown')}*"
            if author.get('handle'):
                author_text += f" @{author['handle']}"

            unfurl_blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": author_text
                    }
                ]
            })

            # Post text
            text = post_data.get('text', '')
            if text:
                unfurl_blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text
                    }
                })

            # Video block
            video_block = {
                "type": "video",
                "video_url": player_url,
                "alt_text": "Video from Bluesky post",
                "title": {"type": "plain_text", "text": "Video", "emoji": True},
                "thumbnail_url": thumbnail_url
            }
            unfurl_blocks.append(video_block)

            # Update the unfurl
            client.chat_unfurl(
                channel=channel,
                ts=ts,
                unfurls={url: {"blocks": unfurl_blocks}}
            )

        except Exception as e:
            print(f"Error updating unfurl with video: {e}")

    def _update_unfurl_with_error(self, url: str, channel: str, ts: str, client):
        """Update the unfurl with an error message"""
        try:
            # Get the original post data to maintain context
            post_info = self.bluesky_client.extract_post_info(url)
            if not post_info:
                return

            post_data = self.bluesky_client.get_post(
                post_info['handle'],
                post_info['post_id']
            )

            if not post_data:
                return

            # Rebuild unfurl blocks with error
            unfurl_blocks = []

            # Author header
            author = post_data.get('author', {})
            author_text = f"*{author.get('display_name', 'Unknown')}*"
            if author.get('handle'):
                author_text += f" @{author['handle']}"

            unfurl_blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": author_text
                    }
                ]
            })

            # Post text
            text = post_data.get('text', '')
            if text:
                unfurl_blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text
                    }
                })

            # Error message
            unfurl_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🎥 *Video processing failed* - Click link to view on Bluesky"
                }
            })

            # Update the unfurl
            client.chat_unfurl(
                channel=channel,
                ts=ts,
                unfurls={url: {"blocks": unfurl_blocks}}
            )

        except Exception as e:
            print(f"Error updating unfurl with error message: {e}")

    def start(self):
        """Start the Slack app"""
        port = int(os.environ.get("PORT", 3000))

        # Use HTTP mode by default
        # Socket Mode is mostly for local dev
        socket_token = os.environ.get("SLACK_APP_TOKEN")
        if socket_token:
            handler = SocketModeHandler(self.app, socket_token)
            print("🔌 Slack app is running in Socket Mode")
            handler.start()
        else:
            print(f"⚡️ Slack app is running on port {port}!")
            self.app.start(port=port)


if __name__ == "__main__":
    app = SkyfurlApp()
    app.start()
