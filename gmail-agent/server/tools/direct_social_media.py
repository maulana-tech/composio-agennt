"""
Direct Twitter/Facebook API approach for media uploads.
This file provides direct API calls to social media platforms for media uploads.
"""

import os
import base64
import json
from composio import Composio


def upload_media_to_twitter(user_id: str, image_path: str) -> str:
    """Upload media to Twitter and get media_id."""
    try:
        composio_client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))

        # Try different media upload approaches
        media_slugs = [
            ("TWITTER_UPLOAD_MEDIA", {"media": image_path}),
            ("TWITTER_UPLOAD_MEDIA", {"media_file_path": image_path}),
            ("TWITTER_POST_MEDIA", {"media": image_path}),
            ("UPLOAD_MEDIA", {"file": image_path}),
        ]

        for slug, args in media_slugs:
            try:
                payload = {
                    "tools": [{"tool_slug": slug, "arguments": args}],
                    "sync_response_to_workbench": False,
                    "session_id": user_id,
                }

                result = composio_client.tools.execute(
                    slug="COMPOSIO_MULTI_EXECUTE_TOOL",
                    arguments=payload,
                    user_id=user_id,
                    dangerously_skip_version_check=True,
                )

                return json.dumps(result)

            except Exception as e:
                error_str = str(e).lower()
                if "not found" in error_str or "404" in error_str:
                    continue
                else:
                    continue

        return json.dumps({"error": "No media upload tool found", "available": False})

    except Exception as e:
        return json.dumps({"error": str(e)})


def post_tweet_with_media(user_id: str, caption: str, media_id: str = None) -> str:
    """Post tweet with or without media."""
    try:
        composio_client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))

        if media_id:
            args = {"text": caption, "media_ids": media_id}
        else:
            args = {"text": caption}

        payload = {
            "tools": [{"tool_slug": "TWITTER_CREATION_OF_A_POST", "arguments": args}],
            "sync_response_to_workbench": False,
            "session_id": user_id,
        }

        result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": str(e)})


def upload_media_to_facebook(user_id: str, image_path: str) -> str:
    """Upload photo to Facebook."""
    try:
        composio_client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))

        # Get pages first
        pages_payload = {
            "tools": [
                {
                    "tool_slug": "FACEBOOK_LIST_MANAGED_PAGES",
                    "arguments": {"user_id": "me", "limit": 1, "fields": "id,name"},
                }
            ],
            "sync_response_to_workbench": False,
            "session_id": user_id,
        }

        pages_result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=pages_payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        # Parse page ID
        try:
            pages_data = (
                json.loads(pages_result)
                if isinstance(pages_result, str)
                else pages_result
            )
            results = pages_data.get("data", {}).get("results", [])
            if results:
                page_id = (
                    results[0]
                    .get("response", {})
                    .get("data", {})
                    .get("data", [{}])[0]
                    .get("id")
                )
            else:
                return json.dumps({"error": "No Facebook pages found"})
        except:
            return json.dumps({"error": "Failed to parse Facebook pages"})

        # Try different photo upload approaches
        photo_slugs = [
            ("FACEBOOK_UPLOAD_PHOTO", {"page_id": page_id, "photo": image_path}),
            (
                "FACEBOOK_UPLOAD_PHOTO",
                {"page_id": page_id, "photo_file_path": image_path},
            ),
            ("FACEBOOK_ADD_PHOTO", {"page_id": page_id, "image": image_path}),
        ]

        for slug, args in photo_slugs:
            try:
                payload = {
                    "tools": [{"tool_slug": slug, "arguments": args}],
                    "sync_response_to_workbench": False,
                    "session_id": user_id,
                }

                result = composio_client.tools.execute(
                    slug="COMPOSIO_MULTI_EXECUTE_TOOL",
                    arguments=payload,
                    user_id=user_id,
                    dangerously_skip_version_check=True,
                )

                return json.dumps(result)

            except Exception as e:
                error_str = str(e).lower()
                if "not found" in error_str or "404" in error_str:
                    continue
                else:
                    continue

        return json.dumps({"error": "No photo upload tool found"})

    except Exception as e:
        return json.dumps({"error": str(e)})


def post_facebook_with_photo(user_id: str, caption: str, photo_id: str = None) -> str:
    """Post to Facebook with photo."""
    try:
        composio_client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))

        # Get pages first
        pages_payload = {
            "tools": [
                {
                    "tool_slug": "FACEBOOK_LIST_MANAGED_PAGES",
                    "arguments": {"user_id": "me", "limit": 1, "fields": "id"},
                }
            ],
            "sync_response_to_workbench": False,
            "session_id": user_id,
        }

        pages_result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=pages_payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        # Parse page ID
        try:
            pages_data = (
                json.loads(pages_result)
                if isinstance(pages_result, str)
                else pages_result
            )
            results = pages_data.get("data", {}).get("results", [])
            if results:
                page_id = (
                    results[0]
                    .get("response", {})
                    .get("data", {})
                    .get("data", [{}])[0]
                    .get("id")
                )
            else:
                return json.dumps({"error": "No Facebook pages found"})
        except:
            return json.dumps({"error": "Failed to parse Facebook pages"})

        # Try to upload photo and post together
        args = {
            "page_id": page_id,
            "message": caption,
            "published": True,
        }

        if photo_id:
            args["attached_media"] = [{"media_fbid": photo_id}]

        payload = {
            "tools": [{"tool_slug": "FACEBOOK_CREATE_POST", "arguments": args}],
            "sync_response_to_workbench": False,
            "session_id": user_id,
        }

        result = composio_client.tools.execute(
            slug="COMPOSIO_MULTI_EXECUTE_TOOL",
            arguments=payload,
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

        return json.dumps(result)

    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    user_id = "pg-test-a199d8f3-e74a-42e0-956b-b1fbb2808b58"
    image_path = "/Users/em/web/AI-Agent/composio-agent/gmail-agent/attachment/quote_winston_churchi_20260204_193854.png"

    print("Testing Twitter media upload...")
    media_result = upload_media_to_twitter(user_id, image_path)
    print(f"Media upload result: {media_result}")

    print("\nTesting Facebook photo upload...")
    photo_result = upload_media_to_facebook(user_id, image_path)
    print(f"Photo upload result: {photo_result}")
