"""
A Slack app for unfurling ATProto microblog links

Apps built on AT Protocol, such as Bluesky or Blacksky, show up just ok when posted to Slack.
This app handles those links better by adding rich content, like video.
"""
import os
import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

class SkyfurlApp:
    def __init__(self):
        #Init the Slack app with bot token
        self.app = App(
                token=os.environ.get("SLACK_BOT_TOKEN"),
                signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
        )

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
                    unfurls[url]

            # Send unfurls back to Slack
            if unfurls:
                try:
                    client.chat_unfurl(
                            channel=event["channl"],
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

    def start(self):
        """Start the Slack app"""
        port = int(os.environ.get("PORT", 3000))


if __name__ == "__main__":
    app = SkyfurlApp()
    app.start

