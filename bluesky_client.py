"""
Bluesky API client for fetching post data and handling OAuth.
"""
from atproto import Client, models
from typing import Optional, Dict, Any, List
import re
from urllib.parse import urlparse

# Supported AT Protocol site domains for link unfurling
# Add new alternative sites here
SUPPORTED_DOMAINS = [
    'bsky.app',           # Official Bluesky web app
    'blacksky.community', # Blacksky alternative site
]


class BlueskyClient:
    def __init__(self):
        # Always create a client - it can be used without authentication for public posts
        # Use the public API endpoint which allows access to public posts without auth
        self.client = Client(base_url='https://public.api.bsky.app')
        self.authenticated = False

    def login_with_password(self, handle: str, password: str):
        """Login to Bluesky with handle and app password."""
        profile = self.client.login(handle, password)
        self.authenticated = True
        return profile

    def login_with_token(self, access_token: str):
        """Login to Bluesky with access token."""
        # Note: atproto library's OAuth support is limited in current version
        # For production, you'd want to implement full OAuth2 flow
        # This is a simplified approach - in production use proper OAuth
        self.client._access_jwt = access_token
        self.authenticated = True

    def extract_post_info(self, url: str) -> Optional[Dict[str, str]]:
        """
        Extract handle and post ID from Bluesky URL.

        Supports all domains in SUPPORTED_DOMAINS with format:
        - https://{domain}/profile/{handle}/post/{post_id}

        Examples:
        - https://bsky.app/profile/{handle}/post/{post_id}
        - https://blacksky.community/profile/{handle}/post/{post_id}
        """
        # Build regex pattern from supported domains
        domains_pattern = '|'.join(re.escape(domain) for domain in SUPPORTED_DOMAINS)
        pattern = f'(?:{domains_pattern})/profile/([^/]+)/post/([^/?]+)'
        match = re.search(pattern, url)

        if match:
            return {
                'handle': match.group(1),
                'post_id': match.group(2)
            }
        return None

    def get_post(self, handle: str, post_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a Bluesky post by handle and post ID.

        Returns post data including text, author, images, and video info.
        Works for public posts without authentication.
        """
        try:
            # Resolve handle to DID
            profile = self.client.get_profile(handle)
            did = profile.did

            # Construct AT URI for the post
            at_uri = f"at://{did}/app.bsky.feed.post/{post_id}"

            # Fetch the post thread to get full context
            thread = self.client.get_post_thread(uri=at_uri)

            if not thread or not thread.thread:
                return None

            post = thread.thread.post

            # Extract post data
            post_data = {
                'uri': post.uri,
                'cid': post.cid,
                'author': {
                    'handle': post.author.handle,
                    'display_name': post.author.display_name or post.author.handle,
                    'avatar': post.author.avatar,
                    'did': post.author.did
                },
                'text': post.record.text if hasattr(post.record, 'text') else '',
                'created_at': post.record.created_at if hasattr(post.record, 'created_at') else None,
                'images': [],
                'video': None,
                'external': None,
                'reply_count': post.reply_count or 0,
                'repost_count': post.repost_count or 0,
                'like_count': post.like_count or 0,
            }

            # Extract embedded content
            if hasattr(post.record, 'embed') and post.record.embed:
                embed = post.record.embed

                # Handle images
                if hasattr(embed, 'images') and embed.images:
                    for img in embed.images:
                        post_data['images'].append({
                            'alt': img.alt if hasattr(img, 'alt') else '',
                            'thumb': img.thumb if hasattr(img, 'thumb') else None,
                            'fullsize': img.fullsize if hasattr(img, 'fullsize') else None,
                        })

                # Handle video
                embed_type = getattr(embed, '$type', '')
                if hasattr(embed, 'video') or (embed_type and 'video' in str(embed_type)):
                    post_data['video'] = {
                        'has_video': True,
                        'thumbnail': getattr(embed, 'thumbnail', None),
                        'alt': getattr(embed, 'alt', ''),
                    }

                # Handle external links
                if hasattr(embed, 'external') and embed.external:
                    ext = embed.external
                    post_data['external'] = {
                        'uri': ext.uri if hasattr(ext, 'uri') else None,
                        'title': ext.title if hasattr(ext, 'title') else None,
                        'description': ext.description if hasattr(ext, 'description') else None,
                        'thumb': ext.thumb if hasattr(ext, 'thumb') else None,
                    }

            # Handle embedded media from post.embed (processed version)
            if hasattr(post, 'embed') and post.embed:
                embed = post.embed

                # Images from processed embed
                if hasattr(embed, 'images') and embed.images:
                    post_data['images'] = []
                    for img in embed.images:
                        post_data['images'].append({
                            'alt': img.alt if hasattr(img, 'alt') else '',
                            'thumb': img.thumb if hasattr(img, 'thumb') else None,
                            'fullsize': img.fullsize if hasattr(img, 'fullsize') else None,
                        })

                # Video from processed embed
                embed_type = getattr(embed, '$type', '')
                if hasattr(embed, 'playlist') or (embed_type and 'video' in str(embed_type)):
                    # Extract video URL and thumbnail
                    video_url = getattr(embed, 'playlist', None)
                    thumbnail_url = getattr(embed, 'thumbnail', None)
                    aspect_ratio = getattr(embed, 'aspectRatio', None)

                    # If thumbnail is a blob reference, construct full URL
                    if thumbnail_url and hasattr(thumbnail_url, 'ref'):
                        thumbnail_url = self.get_blob_url(did, thumbnail_url.ref.toString() if hasattr(thumbnail_url.ref, 'toString') else str(thumbnail_url.ref))

                    post_data['video'] = {
                        'has_video': True,
                        'video_url': video_url,
                        'thumbnail_url': thumbnail_url,
                        'alt': getattr(embed, 'alt', 'Video'),
                        'aspect_ratio': aspect_ratio,
                    }

            return post_data

        except Exception as e:
            print(f"Error fetching post: {e}")
            return None

    def get_blob_url(self, did: str, cid: str) -> str:
        """Construct URL for a blob (image/video)."""
        return f"https://bsky.social/xrpc/com.atproto.sync.getBlob?did={did}&cid={cid}"

    def get_thread_posts(self, handle: str, post_id: str, max_posts: int = 25) -> Optional[Dict[str, Any]]:
        """
        Fetch a Bluesky thread and return posts by the original author.

        This unrolls a thread, filtering to only include posts from the
        original author (not replies from others).

        Args:
            handle: Bluesky handle (e.g., user.bsky.social)
            post_id: Post ID
            max_posts: Maximum number of posts to return (default: 25)

        Returns:
            Dictionary with:
                - posts: List of post data dictionaries in chronological order (limited to max_posts)
                - total_count: Total number of posts in the thread
                - truncated: True if thread was truncated to max_posts
            Returns None if thread cannot be fetched.
        Works for public threads without authentication.
        """
        try:
            # Resolve handle to DID
            profile = self.client.get_profile(handle)
            original_author_did = profile.did

            # Construct AT URI for the post
            at_uri = f"at://{original_author_did}/app.bsky.feed.post/{post_id}"

            # Fetch the post thread with depth=100 to get all replies
            thread = self.client.get_post_thread(uri=at_uri, depth=100, parent_height=0)

            if not thread or not thread.thread:
                return None

            # Collect posts by the original author
            author_posts = []
            self._collect_author_posts(thread.thread, original_author_did, author_posts)

            # Sort by creation time to maintain chronological order
            author_posts.sort(key=lambda p: p.get('created_at', ''))

            total_count = len(author_posts)
            truncated = total_count > max_posts

            # Limit to max_posts
            limited_posts = author_posts[:max_posts]

            return {
                'posts': limited_posts,
                'total_count': total_count,
                'truncated': truncated
            }

        except Exception as e:
            print(f"Error fetching thread: {e}")
            return None

    def _collect_author_posts(self, thread_node, author_did: str, posts_list: List):
        """
        Recursively collect all posts by the specified author from a thread.

        Args:
            thread_node: Thread node from getPostThread response
            author_did: DID of the author to filter for
            posts_list: List to append matching posts to
        """
        if not thread_node or not hasattr(thread_node, 'post'):
            return

        post = thread_node.post

        # Check if this post is by the original author
        if post.author.did == author_did:
            # Extract post data (similar to get_post but simpler)
            post_data = {
                'uri': post.uri,
                'cid': post.cid,
                'text': post.record.text if hasattr(post.record, 'text') else '',
                'created_at': post.record.created_at if hasattr(post.record, 'created_at') else None,
                'author': {
                    'handle': post.author.handle,
                    'display_name': post.author.display_name or post.author.handle,
                    'did': post.author.did
                },
                'like_count': post.like_count or 0,
                'repost_count': post.repost_count or 0,
                'reply_count': post.reply_count or 0,
            }

            # Build URL for this post
            # Extract post ID from URI (at://did/app.bsky.feed.post/POST_ID)
            post_url_id = post.uri.split('/')[-1]
            post_data['url'] = f"https://bsky.app/profile/{post.author.handle}/post/{post_url_id}"

            posts_list.append(post_data)

        # Recursively process replies
        if hasattr(thread_node, 'replies') and thread_node.replies:
            for reply in thread_node.replies:
                self._collect_author_posts(reply, author_did, posts_list)

