import time
import random
import os
from atproto import Client
from atproto_client.exceptions import RequestException
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
LIST_NAME = os.getenv('LIST_NAME', "followed by followers") 

# 1. クライアントの認証
client = Client()
client.login(USERNAME, PASSWORD)

# 2. 自分のフォロワー、フォロー中のユーザーを取得
def get_followers_and_following(client):
    # 自分のDIDを取得
    did = client.me.did
    
    # フォロワーを全件取得
    followers = []
    cursor = None
    while True:
        response = client.app.bsky.graph.get_followers({'actor': did, 'cursor': cursor})
        followers.extend(response.followers)
        if not response.cursor:
            break
        cursor = response.cursor
    
    # フォロー中のユーザーを全件取得
    following = []
    cursor = None
    while True:
        response = client.app.bsky.graph.get_follows({'actor': did, 'cursor': cursor})
        following.extend(response.follows)
        if not response.cursor:
            break
        cursor = response.cursor
    
    return followers, following

def retry_with_backoff(func, max_retries=16, initial_delay=1):
    """
    Exponential backoffを使用してAPI呼び出しをリトライする
    """
    for attempt in range(max_retries):
        try:
            return func()
        except RequestException as e:
            if "RateLimitExceeded" not in str(e) or attempt == max_retries - 1:
                raise e
            
            # 遅延時間を計算 (2^attempt * initial_delay + random jitter)
            delay = (2 ** attempt * initial_delay + 
                    random.uniform(0, 0.1 * (2 ** attempt)))
            next_retry_time = time.time() + delay
            print(f"Rate limit exceeded. Retrying in {delay:.1f} seconds at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_retry_time))}...", end="")
            time.sleep(delay)

def get_list_users(client, list_name):
    # リストが存在するか確認
    lists = client.app.bsky.graph.get_lists({'actor': client.me.did}).lists
    list_data = next((lst for lst in lists if lst['name'] == list_name), None)
    
    if not list_data:
        # リストが存在しない場合は新規作成
        list_id = client.app.bsky.graph.create_list(name=list_name).uri
        return list_id, []
    
    # リストのユーザーを全件取得
    list_id = list_data['uri']
    list_users = []
    cursor = None
    while True:
        response = client.app.bsky.graph.get_list({'list': list_id, 'cursor': cursor})
        list_users.extend(response.items)
        if not response.cursor:
            break
        cursor = response.cursor
    return list_id, list_users

# 3. リストを更新
def calculate_list_changes(client, followers, following, list_name):
    following_set = {user.did for user in following}
    followers_set = {user.did for user in followers}
    
    # フォロワーのフォローを取得
    followers_following = set()
    with tqdm(total=len(followers_set), desc="Fetching follows", unit="follower") as pbar:
        global_start_time = time.time()
        for follower_did in followers_set:
            follower_handle = next((user.handle for user in followers if user.did == follower_did), "Unknown")
            # 最終投稿が30日以上前の場合はスキップ
            # ユーザーの最新の投稿を取得
            try:
                response = client.app.bsky.feed.get_author_feed({'actor': follower_did, 'limit': 1})
                latest_post = response.feed[0] if response.feed else None
                if latest_post:
                    latest_post_time_str = latest_post.post.record.created_at
                    latest_post_time = time.mktime(time.strptime(latest_post_time_str.split('.')[0], "%Y-%m-%dT%H:%M:%S"))
                else:
                    pbar.set_postfix_str(f"Skip {follower_handle} for no post.")
                    pbar.update(1)
                    continue
            except Exception as e:
                pbar.set_postfix_str(f"Skip {follower_handle} for error")
                print(f"error {e}")
                pbar.update(1)
                continue
            if (time.time() - latest_post_time) > 30 * 24 * 60 * 60:
                pbar.set_postfix_str(f"Skip {follower_handle} for inactive")
                pbar.update(1)
                continue

            start_time = time.time()
            cursor = None
            total_fetched = 0
            while True:
                response = retry_with_backoff(
                    lambda: client.app.bsky.graph.get_follows({'actor': follower_did, 'cursor': cursor})
                )
                follower_following = response.follows
                current_follower_following = set(user.did for user in follower_following)
                followers_following.update(current_follower_following)
                total_fetched += len(follower_following)
                if not response.cursor or total_fetched >= 300:
                    break
                cursor = response.cursor
                elapsed_time = time.time() - start_time
                if elapsed_time > 5:
                    pbar.set_postfix_str(f"Heavy fetching in handle: {follower_handle}")
            elapsed_time = time.time() - global_start_time
            remaining_count = len(followers_set) - pbar.n
            eta = elapsed_time / (pbar.n + 1) * remaining_count
            pbar.set_postfix_str(f"Handle: {follower_handle}, ETA: {pbar.format_interval(eta)}")
            pbar.update(1)
    
    # リストのユーザーを取得
    list_id, list_users = get_list_users(client, list_name)
    list_users_set = {user.subject.did for user in list_users}
    
    followers_following_following_dict = {}
    with tqdm(total=len(followers_following), desc="Processing followers_following", unit="follower") as pbar:
        global_start_time = time.time()
        for follower_did in followers_following:
            start_time = time.time()
            cursor = None
            follower_following_set = set()
            while True:
                response = retry_with_backoff(
                    lambda: client.app.bsky.graph.get_follows({'actor': follower_did, 'cursor': cursor})
                )
                follower_following = response.follows
                follower_following_set.update(user.did for user in follower_following)
                if not response.cursor or len(follower_following_set) > 100:
                    break
                cursor = response.cursor
                elapsed_time = time.time() - start_time
                if elapsed_time > 5:
                    pbar.set_postfix_str(f"Heavy feting {follower_did}")
            followers_following_following_dict[follower_did] = follower_following_set            
            
            elapsed_time = time.time() - global_start_time
            remaining_count = len(followers_following) - pbar.n
            eta = elapsed_time / (pbar.n + 1) * remaining_count
            pbar.set_postfix_str(f"ETA: {pbar.format_interval(eta)}")
            pbar.update(1)
    
    # 自分のfollowingと共通のfollowingを持つユーザーを抽出
    common_following_users = set()
    for follower_did, follower_following_set in followers_following_following_dict.items():
        # 自分のfollowingと共通のfollowingがあるか確認
        if following_set & follower_following_set:
            common_following_users.add(follower_did)
    
    # followers_followingを共通のfollowingを持つユーザーに限定
    followers_following = common_following_users
    
    # フォロワーのフォローのうち、自分がフォローしていないユーザー
    non_followed = followers_following - following_set
    
    # リストに追加すべきユーザー
    to_add = non_followed - list_users_set
    
    # リストから削除すべきユーザー
    to_remove = list_users_set - non_followed
    
    return list_id, to_add, to_remove

def update_list(client, list_id, to_add, to_remove):    
    # リストのアイテムを全件取得
    items = []
    cursor = None
    while True:
        response = retry_with_backoff(
            lambda: client.app.bsky.graph.get_list({'list': list_id, 'cursor': cursor})
        )
        items.extend(response.items)
        if not response.cursor:
            break
        cursor = response.cursor
    print("list items fetched")

    # リストから削除
    with tqdm(total=len(to_remove), desc="Removing users", unit="user") as pbar:
        for remove_count, did in enumerate(to_remove, start=1):
            # 該当するユーザーのアイテムを探す
            item = next((item for item in items if item.subject.did == did), None)
            if item:
                uri_parts = item.uri.split('/')
                rkey = uri_parts[-1]
                profile = retry_with_backoff(
                    lambda: client.app.bsky.actor.get_profile({'actor': did})
                )
                retry_with_backoff(lambda: client.app.bsky.graph.listitem.delete(
                    repo=client.me.did,
                    rkey=rkey
                ))
                eta = pbar.format_interval(pbar.format_dict['elapsed'] * (len(to_remove) - remove_count))
                pbar.set_postfix_str(f"ETA: {eta}, Removed: {profile.handle}")
                pbar.update(1)

    # リストに追加
    with tqdm(total=len(to_add), desc="Adding users", unit="user") as pbar:
        for i, did in enumerate(to_add, 1):
            record = {
                "subject": did,
                "list": list_id,
                "createdAt": client.get_current_time_iso()
            }
            
            # createとget_profileの呼び出しをリトライ可能に
            retry_with_backoff(lambda: client.app.bsky.graph.listitem.create(
                repo=client.me.did,
                record=record
            ))
            
            profile = retry_with_backoff(
                lambda: client.app.bsky.actor.get_profile({'actor': did})
            )
            
            eta = pbar.format_interval(pbar.format_dict['elapsed'] * (len(to_add) - i))
            pbar.set_postfix_str(f"ETA: {eta}, Added: {profile.handle}")
            pbar.update(1)


# 実行
followers, following = get_followers_and_following(client)
print(f"Followers: {len(followers)}, Following: {len(following)}")

list_id, to_add, to_remove = calculate_list_changes(client, followers, following, LIST_NAME)
print(f"Adding {len(to_add)} users, removing {len(to_remove)} users...")

update_list(client, list_id, to_add, to_remove)

print("List updated successfully.")