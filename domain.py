from atproto import Client
from tqdm import tqdm
from util import *

def get_neighbor_users(client: Client):
    self_did = get_self_did(client)
    following = set(get_following(client, self_did))
    followers_count = get_followers_count(client, self_did)
    # フォロワーF1を取得
    with tqdm(total=followers_count, desc="Followers", unit="user", position=0) as pbar:
        for follower in get_followers(client, self_did):
            follower_handle = get_handle(client, follower.did)
            follower_following_count = get_following_count(client, follower.did)
            if follower_following_count > 1000:
                pbar.update(1)
                continue
            # フォロワーのフォローF2を取得
            with tqdm(total=follower_following_count, desc="> Followings", unit="user", position=1, leave=False) as pbar2:
                pbar2.set_postfix_str(follower_handle)
                for follower_following in get_following(client, follower.did):
                    follower_following_handle = get_handle(client, follower_following)
                    follower_following_following_count = get_following_count(client, follower_following)
                    if follower_following_following_count > 1000:
                        pbar2.update(1)
                        continue
                    with tqdm(total=follower_following_following_count, desc=">> Followings", unit="user", position=2, leave=False) as pbar3:
                        pbar3.set_postfix_str(follower_following_handle)
                        for follower_following_following in get_following(client, follower_following):
                            if follower_following_following in following:
                                yield follower_following
                                break
                            pbar3.update(1)
                    pbar2.update(1)
            pbar.update(1)

def update_list(client: Client, list_name: str, list_users: set[str]):
    list_id, current_list_users = get_list_users(client, list_name)
    current_list_users_did = set(current_list_users)

    users_to_remove = current_list_users_did - list_users
    print(f"Removing {len(users_to_remove)} users from the list")
    with tqdm(total=len(users_to_remove), desc="Removing", unit="user") as pbar:
        for did in remove_users_from_list(client, list_id, users_to_remove):
            pbar.set_postfix_str(get_handle(client, did))
            pbar.update(1)

    users_to_add = list_users - current_list_users_did
    print(f"Adding {len(users_to_add)} users to the list")
    with tqdm(total=len(users_to_add), desc="Adding", unit="user") as pbar:
        for did in add_users_to_list(client, list_id, users_to_add):
            pbar.set_postfix_str(get_handle(client, did))
            pbar.update(1)