# save as generate_token.py and run it
from livekit.api import AccessToken, VideoGrants

token = (
    AccessToken("devkey", "secret")
    .with_grants(VideoGrants(room_join=True, room="test-room"))
    .with_identity("user1")
    .to_jwt()
)
print(token)