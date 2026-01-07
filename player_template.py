"""
HTML template rendering for video player
"""


def render_video_player(video_url: str) -> str:
    """
    Render HTML5 video player page

    Args:
        video_url: URL to the video file

    Returns:
        HTML string for iframe-embeddable video player
    """
    return f"""
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
