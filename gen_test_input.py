# 在 Colab 运行时里执行：合成一段日语测试语音到 /content/input/test_ja.mp3
# 仅用于端到端冒烟测试（有真实视频后走 upload / INPUT_URL，不需要这个）
import subprocess, sys, os

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gTTS"], check=True)
from gtts import gTTS

text = (
    "こんにちは。今日はとても良い天気ですね。"
    "私は毎朝七時に起きて、コーヒーを飲んでから仕事に行きます。"
    "昨日の夜、友達と一緒に映画を見ました。とても面白かったです。"
    "明日は雨が降るかもしれませんから、傘を持って行ったほうがいいですよ。"
)
os.makedirs("/content/input", exist_ok=True)
gTTS(text=text, lang="ja").save("/content/input/test_ja.mp3")
print("saved", os.path.getsize("/content/input/test_ja.mp3"), "bytes")
print("expected text:", text)
