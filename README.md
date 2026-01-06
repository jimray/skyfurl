# SKYFURL

A Slack app that automatically unfurls links from Bluesky (and related) with rich content.

## Features

* **Automatic unfurls**: Paste a link from Bluesky (or Blacksky) and it automatically expands with rich content
* **Video embeds**: Play videos natively right in Slack

## Installation and Setup

### Prerequisites

* [Slack CLI](https://docs.slack.dev/tools/slack-cli/)

```bash
curl -fsSL https://downloads.slack-edge.com/slack-cli/install.sh | bash
```

* Python 3.8+
* A Bluesky (or Blacksky) account with an [app password](https://bsky.app/settings/app-passwords)

### Install

Use the Slack CLI to install the app as a template

```bash
slack create --template https://tangled.org/jimray/skyfurl.git
```

### Configuration

#### Adding more domains

By default, SKYFURL will unfurl links from Bluesky and Blacksky. To add other microblogging services (e.g. Eurosky or Northsky), include the domains in the `manifest.yaml` file under the `unfurl_domains` param.
