import random
import time
from typing import Generator
from atproto import Client
from atproto_client.models.app.bsky.actor.defs import ProfileView
from atproto_client.exceptions import RequestException

def get_followers(client: Client, did: str) -> Generator[ProfileView, None, None]:
    cursor: str | None = None
    def fetch_followers():
        nonlocal cursor
        response = client.app.bsky.graph.get_followers({'actor': did, 'cursor': cursor})
        cursor = response.cursor
        return response.followers
    while True:        
        followers = retry_with_backoff(fetch_followers)
        yield from followers
        if not cursor:
            break

# dict of { did: (followings, last_cursor) }
following_cache: dict[str, tuple[set[str], str | None]] = {}

def get_following(client: Client, did: str) -> Generator[str, None, None]:
    if did in following_cache:
        cached_followings, cursor = following_cache[did]
        yield from cached_followings
    else:
        cursor: str | None = None
        cached_followings = set()
    def fetch_follows():
        nonlocal cursor, cached_followings
        response = client.app.bsky.graph.get_follows({'actor': did, 'cursor': cursor})
        cursor = response.cursor
        follows = [follower.did for follower in response.follows]
        cached_followings.update(follows)
        return follows
    while True:
        follows = retry_with_backoff(fetch_follows)
        yield from follows
        if not cursor:
            break
    following_cache[did] = (cached_followings, cursor)

def get_handle(client: Client, did: str) -> str:
    return retry_with_backoff(lambda: client.app.bsky.actor.get_profile({'actor': did})).handle

def get_following_count(client: Client, did: str) -> int:
    return retry_with_backoff(lambda: client.app.bsky.actor.get_profile({'actor': did})).follows_count

def get_followers_count(client: Client, did: str) -> int:
    return retry_with_backoff(lambda: client.app.bsky.actor.get_profile({'actor': did})).followers_count

def add_users_to_list(client: Client, list_id: str, users_to_add: list[str]) -> Generator[str, None, None]:
    for did in users_to_add:
        record = {
            "subject": did,
            "list": list_id,
            "createdAt": client.get_current_time_iso()
        }
        retry_with_backoff(lambda: client.app.bsky.graph.listitem.create(
            repo=client.me.did,
            record=record
        ))
        yield did

def remove_users_from_list(client: Client, list_id: str, users_to_remove: list[str]) -> Generator[str, None, None]:
    def fetch_users():
        cursor = None
        while True:
            response = retry_with_backoff(
                lambda: client.app.bsky.graph.get_list({'list': list_id, 'cursor': cursor})
            )
            yield from response.items
            if not response.cursor:
                break
            cursor = response.cursor
    items = fetch_users()
    for did in users_to_remove:
        item = next((item for item in items if item.subject.did == did), None)
        if item:
            uri_parts = item.uri.split('/')
            rkey = uri_parts[-1]
            retry_with_backoff(lambda: client.app.bsky.graph.listitem.delete(
                repo=client.me.did,
                rkey=rkey
            ))
            yield did

def retry_with_backoff(func, max_retries=16, initial_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except RequestException as e:
            if "RateLimitExceeded" not in str(e) or attempt == max_retries - 1:
                raise e
            delay = (2 ** attempt * initial_delay +
                    random.uniform(0, 0.1 * (2 ** attempt)))
            next_retry_time = time.time() + delay
            print(f"Rate limit exceeded. Retrying in {delay:.1f} seconds at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_retry_time))}...", end="")
            time.sleep(delay)

def get_self_did(client: Client) -> str:
    return client.me.did

def get_list_users(client: Client, list_name: str):
    # リストが存在するか確認
    lists = client.app.bsky.graph.get_lists({'actor': client.me.did}).lists
    list_data = next((lst for lst in lists if lst['name'] == list_name), None)

    if not list_data:
        # リストが存在しない場合はエラー
        raise ValueError(f"List '{list_name}' not found.")

    # リストのユーザーを全件取得
    list_id = list_data.uri
    def fetch_list_users():
        cursor = None
        while True:
            response = client.app.bsky.graph.get_list({'list': list_id, 'cursor': cursor})
            yield from [item.subject.did for item in response.items]
            if not response.cursor:
                break
            cursor = response.cursor
    return list_id, fetch_list_users()
