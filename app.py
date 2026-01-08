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
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.state_store import FileOAuthStateStore
from flask import Flask, send_file, Response, request

from bluesky_client import BlueskyClient
from video_processor import VideoProcessor
from unfurl_builder import UnfurlBuilder
from player_template import render_video_player
from validated_installation_store import ValidatedInstallationStore, WorkspaceNotApprovedException

class SkyfurlApp:
    def __init__(self):
        #Init the Slack app
        # Check if OAuth credentials are provided
        client_id = os.environ.get("SLACK_CLIENT_ID")
        client_secret = os.environ.get("SLACK_CLIENT_SECRET")

        if client_id and client_secret:
            # OAuth mode - for public "Add to Slack" installations
            print("🔐 Initializing with OAuth support")

            # Use volume path for database on Railway, or local path for dev
            db_path = os.environ.get("DATABASE_PATH", "slack_installations.db")

            self.app = App(
                signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
                installation_store=ValidatedInstallationStore(database=db_path),
                oauth_settings=OAuthSettings(
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=["links:read", "links:write"],
                    install_path="/slack/install",
                    redirect_uri_path="/slack/oauth_redirect",
                    state_store=FileOAuthStateStore(expiration_seconds=600),
                    install_page_rendering_enabled=False
                )
            )
        else:
            # Simple mode - single workspace with bot token
            print("🤖 Initializing with bot token")
            self.app = App(
                token=os.environ.get("SLACK_BOT_TOKEN"),
                signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
            )

        # Init the Bluesky client (no auth needed for public posts)
        # TODO: add optional auth via app password for fetching non-public posts?
        self.bluesky_client = BlueskyClient()

        # Init video processor
        self.video_processor = VideoProcessor()

        # Init unfurl builder
        self.unfurl_builder = UnfurlBuilder(self.bluesky_client)

        # Create Flask app for HTTP mode
        self.flask_app = Flask(__name__)
        self.handler = SlackRequestHandler(self.app)

        # Register event handlers for Slack events (eg link_shared)
        self.register_handlers()

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
        """Register HTTP routes for serving videos and Slack events"""

        # Slack event endpoints
        @self.flask_app.route("/slack/events", methods=["POST"])
        def slack_events():
            return self.handler.handle(request)

        @self.flask_app.route("/slack/install", methods=["GET"])
        def slack_install():
            return self.handler.handle(request)

        @self.flask_app.route("/slack/oauth_redirect", methods=["GET"])
        def slack_oauth_redirect():
            try:
                return self.handler.handle(request)
            except WorkspaceNotApprovedException as e:
                # Return friendly error page for unapproved workspaces
                error_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Installation Not Approved</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        }}
                        .container {{
                            background: white;
                            padding: 3rem;
                            border-radius: 12px;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                            max-width: 500px;
                            text-align: center;
                        }}
                        h1 {{
                            color: #333;
                            margin-bottom: 1rem;
                        }}
                        p {{
                            color: #666;
                            line-height: 1.6;
                        }}
                        .emoji {{
                            font-size: 4rem;
                            margin-bottom: 1rem;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="emoji">🔒</div>
                        <h1>Workspace Not Approved</h1>
                        <p>{str(e)}</p>
                    </div>
                </body>
                </html>
                """
                return Response(error_html, status=403, mimetype='text/html')
            except Exception as e:
                # Handle other unexpected errors
                print(f"OAuth redirect error: {e}")
                error_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Installation Error</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        }}
                        .container {{
                            background: white;
                            padding: 3rem;
                            border-radius: 12px;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                            max-width: 500px;
                            text-align: center;
                        }}
                        h1 {{
                            color: #333;
                            margin-bottom: 1rem;
                        }}
                        p {{
                            color: #666;
                            line-height: 1.6;
                        }}
                        .emoji {{
                            font-size: 4rem;
                            margin-bottom: 1rem;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="emoji">⚠️</div>
                        <h1>Installation Failed</h1>
                        <p>An error occurred during installation. Please try again or contact the app administrator.</p>
                    </div>
                </body>
                </html>
                """
                return Response(error_html, status=500, mimetype='text/html')

        # Video serving endpoints
        @self.flask_app.route("/videos/<video_id>.mp4")
        def serve_video(video_id):
            """Serve processed video file"""
            video_path = self.video_processor.get_video_path(video_id)
            if video_path:
                return send_file(video_path, mimetype='video/mp4')
            return "Video not found", 404

        @self.flask_app.route("/videos/<video_id>/thumbnail.jpg")
        def serve_thumbnail(video_id):
            """Serve video thumbnail"""
            thumbnail_path = self.video_processor.get_thumbnail_path(video_id)
            if thumbnail_path:
                return send_file(thumbnail_path, mimetype='image/jpeg')
            return "Thumbnail not found", 404

        @self.flask_app.route("/player/<video_id>")
        def serve_player(video_id):
            """Serve HTML video player page (iframe-embeddable)"""
            app_url = os.environ.get("APP_URL", "http://localhost:3000")
            video_url = f"{app_url}/videos/{video_id}.mp4"
            return Response(render_video_player(video_url), mimetype='text/html')

    def create_unfurl(self, url: str, event: Dict[str, Any], client) -> Dict[str, Any]:
        """
        Create the unfurl data

        Returns a Slack attachment for the unfurl
        """
        # Create initial unfurl using builder
        unfurl_data = self.unfurl_builder.create_unfurl(url)

        if not unfurl_data:
            return None

        # Check if post has video - start background processing
        post_info = self.bluesky_client.extract_post_info(url)
        if post_info:
            post_data = self.bluesky_client.get_post(
                post_info['handle'],
                post_info['post_id']
            )

            if post_data:
                video = post_data.get('video')
                if video and video.get('has_video'):
                    # Start background video processing
                    threading.Thread(
                        target=self.process_video_background,
                        args=(url, video, event["channel"], event["message_ts"], client),
                        daemon=True
                    ).start()

        return unfurl_data

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

            # Build video URLs - Slack video block needs direct video file URL
            video_url = f"{app_url}/videos/{video_id}.mp4"
            thumbnail_url = f"{app_url}/videos/{video_id}/thumbnail.jpg"

            print(f"Successfully processed video {video_id}")
            print(f"Video URL: {video_url}")
            print(f"Thumbnail URL: {thumbnail_url}")

            # Update unfurl with video block
            self._update_unfurl_with_video(url, channel, ts, client, video_url, thumbnail_url)

            print(f"Successfully unfurled video for {url}")

        except Exception as e:
            print(f"Error processing video: {e}")
            self._update_unfurl_with_error(url, channel, ts, client)

    def _update_unfurl_with_video(self, url: str, channel: str, ts: str, client, video_url: str, thumbnail_url: str):
        """Update the unfurl with the processed video"""
        try:
            # Create complete unfurl with video using builder
            unfurl_data = self.unfurl_builder.create_complete_unfurl(url, video_url, thumbnail_url)

            if not unfurl_data:
                return

            print(f"Unfurl data: {unfurl_data}")

            # Update the unfurl
            response = client.chat_unfurl(
                channel=channel,
                ts=ts,
                unfurls={url: unfurl_data}
            )

            if not response.get("ok"):
                print(f"Slack API error: {response}")

        except Exception as e:
            print(f"Error updating unfurl with video: {e}")
            import traceback
            traceback.print_exc()

    def _update_unfurl_with_error(self, url: str, channel: str, ts: str, client):
        """Update the unfurl with an error message"""
        try:
            # Create error unfurl using builder
            error_message = "🎥 *Video processing failed* - Click link to view on Bluesky"
            unfurl_data = self.unfurl_builder.create_error_unfurl(url, error_message)

            if not unfurl_data:
                return

            # Update the unfurl
            client.chat_unfurl(
                channel=channel,
                ts=ts,
                unfurls={url: unfurl_data}
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
            # Register HTTP routes for serving videos (only needed in HTTP mode)
            self.register_routes()
            print(f"⚡️ Slack app is running on port {port}!")
            self.flask_app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    app = SkyfurlApp()
    app.start()
