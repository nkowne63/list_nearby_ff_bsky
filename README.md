# Followed by Followers

そういうリストを構築します。
初回の構築では大量にリストにユーザーを追加するため、Rate Limitにご注意ください。
ずっと放置しておけばexponential backoffにより自動でリトライされます。

## requirements

- python3
- atproto
- python-dotenv

## how to use

.env.templateを.envにコピーし、適切な値を入れてください。
`python run.py`で後は動きます。