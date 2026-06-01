from integrations.twitter_client import TwitterClient


class FakeTweetClient:
    def __init__(self):
        self.payloads = []

    def create_tweet(self, **payload):
        self.payloads.append(payload)
        return type("TweetResult", (), {"data": {"id": "tweet-123"}})()


def build_client(api):
    client = TwitterClient.__new__(TwitterClient)
    client.dry_run = False
    client.api = api
    client.client = FakeTweetClient()
    return client


def test_publish_content_rejects_required_post_without_media():
    client = build_client(api=None)

    result = client.publish_content("Branded post", require_media=True)

    assert result == {
        "status": "error",
        "message": "This post requires an image, but no media was provided",
    }
    assert client.client.payloads == []


def test_publish_content_does_not_post_when_media_upload_returns_no_id():
    class EmptyMediaApi:
        def media_upload(self, filename):
            return object()

    client = build_client(api=EmptyMediaApi())

    try:
        client.publish_content("Branded post", image_bytes=b"image")
    except ValueError as exc:
        assert str(exc) == "Twitter media upload returned no media ID"
    else:
        raise AssertionError("Expected missing media ID to stop tweet publishing")

    assert client.client.payloads == []


def test_publish_content_allows_intentional_plain_text_post():
    client = build_client(api=object())

    result = client.publish_content("Plain text post")

    assert result["status"] == "posted"
    assert client.client.payloads == [{"text": "Plain text post"}]
