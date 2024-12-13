import os
from atproto import Client
from tqdm import tqdm
from dotenv import load_dotenv
from domain import *
from util import get_handle

load_dotenv()

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
LIST_NAME = os.getenv('LIST_NAME', "followed by followers")

client = Client()
client.login(USERNAME, PASSWORD)

list_users = set()
max_user_count = 5000
with tqdm(total=max_user_count, desc="list size", unit="user", leave=False) as pbar:
    for user in get_neighbor_users(client):
        list_users.add(user)
        if len(list_users) >= max_user_count:
            break
        pbar.set_postfix_str(get_handle(client, user))
        pbar.update(1)

update_list(client, LIST_NAME, list_users)