"""
A Slack app for unfurling ATProto microblog links

Apps built on AT Protocol, such as Bluesky or Blacksky, show up just ok when posted to Slack.
This app handles those links better by adding rich content, like video.
"""
import os
import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from bluesky_client import BlueskyClient

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

                unfurl_data = self.create_unfurl(url)
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

    def create_unfurl(self, url: str) -> Dict[str, Any]:
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

        return {"blocks": unfurl_blocks}

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
