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
import wave
import numpy as np
import glob

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

def combine(filename, dir):
    audios = []
    for f in sorted(glob.glob(f"{dir}/audio_*.wav")):
        with wave.open(f, "rb") as fp:
            buf = fp.readframes(-1) # 全フレーム読み込み
            assert fp.getsampwidth() == 2 # と仮定（np.int16でキャスト）
            audios.append(np.frombuffer(buf, np.int16))
            params = fp.getparams()
    audio_data = np.concatenate(audios)
    # 正規化（ピーク時基準）
    scaling_factors = [np.iinfo(np.int16).max/(np.max(audio_data)+1e-8),
                       np.iinfo(np.int16).min/(np.min(audio_data)+1e-8)]
    # s>0:位相が反転しないようにする。ここをmaxにするとプチッというノイズが入るので注意
    scaling_factors = min([s for s in scaling_factors if s > 0]) 
    audio_data = (audio_data * scaling_factors).astype(np.int16)
    with wave.Wave_write(f"{filename}.wav") as fp:
        fp.setparams(params)
        fp.writeframes(audio_data.tobytes())

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
        os.makedirs(item.get_name())
        for i, t in enumerate(text_array):
            print(t)
            synthesis(t, f"{item.get_name()}/audio_{i}.wav")
        combine(item.get_name(), item.get_name())
        # with open(path, mode='w') as f:
        #      f.write("\n".join(line for line in text_array if line))
