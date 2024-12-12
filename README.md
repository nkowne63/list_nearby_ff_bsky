# Followed by Followers

以下の条件を満たすユーザーから成るリストを構築します
- 自分がフォローしていない
- 自分のフォロワーがフォローしている
- 自分とその人が両方フォローしている人がいる

初回の構築では大量にリストにユーザーを追加するため、Rate Limitにご注意ください。
ずっと放置しておけばexponential backoffにより自動でリトライされます。

## how to use

- .env.templateを.envにコピーし、適切な値を入れてください。
- `pip install -r requirements.txt`などで依存パッケージを入れてください
- `python run.py`で動かせます