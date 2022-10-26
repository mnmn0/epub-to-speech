import sys
import os
import ebooklib
from ebooklib import epub
import requests
import json
import pandas as pd
import time
import re
from bs4 import BeautifulSoup

def synthesis(text, filename, speaker=1, max_retry=20):
    # Internal Server Error(500)が出ることがあるのでリトライする
    # （HTTPAdapterのretryはうまくいかなかったので独自実装）
    # connect timeoutは10秒、read timeoutは300秒に設定（処理が重いので長めにとっておく）
    # audio_query
    query_payload = {"text": text, "speaker": speaker}
    for query_i in range(max_retry):
        r = requests.post("http://voicevox:50021/audio_query", 
                        params=query_payload, timeout=(10.0, 3000.0))
        if r.status_code == 200:
            query_data = r.json()
            break
        time.sleep(1)
    else:
        raise ConnectionError("リトライ回数が上限に到達しました。 audio_query : ", filename, "/", text[:30], r.text)

    # synthesis
    synth_payload = {"speaker": speaker}    
    for synth_i in range(max_retry):
        r = requests.post("http://voicevox:50021/synthesis", params=synth_payload, 
                          data=json.dumps(query_data), timeout=(10.0, 3000.0))
        if r.status_code == 200:
            with open(filename, "wb") as fp:
                fp.write(r.content)
            print(f"{filename} は query={query_i+1}回, synthesis={synth_i+1}回のリトライで正常に保存されました")
            break
        time.sleep(1)
    else:
        raise ConnectionError("リトライ回数が上限に到達しました。 synthesis : ", filename, "/", text[:30], r,text)

book = epub.read_epub('./oreilly-978-4-8144-0002-7e.epub')

title = book.get_metadata('DC', 'title')
creator = book.get_metadata('DC', 'creator')
publisher = book.get_metadata('DC', 'publisher')
language = book.get_metadata('DC', 'language')

items = book.get_items()
for item in items:
    print(item.get_name())
    print(re.compile("ch").search(item.get_name()))
    if item.get_type() == ebooklib.ITEM_DOCUMENT and re.compile("ch").search(item.get_name()):
        soup = BeautifulSoup(item.get_content().decode(), "xml")
        for script in soup(["script", "style"]):
            script.decompose()
        html_text = soup.get_text()
        lines = [line.strip() for line in html_text.splitlines()]
        text_array = "".join(line for line in lines if line).split('。')
        path = "./book/" + item.get_name() + ".txt" # ファイル名
        print(text_array)

        for i, t in enumerate(text_array):
            print(t)
            synthesis(t, f"audio_{i}.wav")
            if i == 6:
                break
        # with open(path, mode='w') as f:
        #      f.write("\n".join(line for line in text_array if line))
