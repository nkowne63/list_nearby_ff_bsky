import os
from atproto import Client
from dotenv import load_dotenv
from domain import *

load_dotenv()

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
LIST_NAME = os.getenv('LIST_NAME', "followed by followers")

client = Client()
client.login(USERNAME, PASSWORD)

list_users = set()
for user in get_neighbor_users(client):
    list_users.add(user)
    if len(list_users) >= 5000:
        break

update_list(client, LIST_NAME, list_users)