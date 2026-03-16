import urllib.request
import urllib.error
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

M3U_URL = "https://iptv-org.github.io/iptv/countries/jp.m3u"
HTML_FILE = "index.html"
PLACEHOLDER = "null; // EMBEDDED_DATA_PLACEHOLDER"

GENRE_MAP = {
    "📰 뉴스":  ["news","nhk","news24","ann","jnn","fnn","nnn"],
    "🎬 지상파": ["ntv","nippon tv","tbs","fuji","tv asahi","tv tokyo","ytv","mbs","abc","関西"],
    "📡 BS·CS": ["bs","cs","wowow","sky","at-x","dlife"],
    "🛒 쇼핑":  ["shop","qvc","japanet"],
}

def guess_genre(name):
    nl = name.lower()
    for genre, keys in GENRE_MAP.items():
        if any(k in nl for k in keys):
            return genre
    return "🎌 기타"

def parse_m3u(text):
    channels = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            name_m = re.search(r',(.+)$', line)
            name = name_m.group(1).strip() if name_m else "알 수 없음"
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                url = lines[j].strip()
                if url.startswith("http"):
                    channels.append({"name": name, "url": url, "genre": guess_genre(name)})
                    i = j + 1
                    continue
        i += 1
    return channels

def check_url(item, timeout=6):
    try:
        req = urllib.request.Request(
            item["url"],
            headers={"User-Agent": "Mozilla/5.0 VLC/3.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status < 400
    except urllib.error.HTTPError as e:
        return e.code < 500
    except:
        return False

def main():
    print("[1/4] 채널 목록 다운로드 중...")
    req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode("utf-8", errors="ignore")

    channels = parse_m3u(text)
    print(f"  총 {len(channels)}개 채널 발견")

    print("[2/4] 채널 접속 테스트 중...")
    live = []
    done = [0]

    def on_done(fut, item):
        done[0] += 1
        if fut.result():
            live.append(item)
        if done[0] % 10 == 0:
            print(f"  {done[0]}/{len(channels)} 완료, 살아있는 채널: {len(live)}개")

    with ThreadPoolExecutor(max_workers=30) as ex:
        futs = {ex.submit(check_url, ch): ch for ch in channels}
        for fut, item in futs.items():
            fut.add_done_callback(lambda f, i=item: on_done(f, i))

    live.sort(key=lambda c: (c["genre"], c["name"]))
    print(f"\n[3/4] 살아있는 채널 {len(live)}개 확인됨")

    print(f"[4/4] {HTML_FILE} 업데이트 중...")
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()

    json_data = json.dumps(live, ensure_ascii=False)
    new_data = f"{json_data}; // EMBEDDED_DATA_PLACEHOLDER"

    if PLACEHOLDER in html:
        html = html.replace(PLACEHOLDER, new_data)
    else:
        # 이미 데이터가 내장된 경우 교체
        html = re.sub(
            r'\[.*?\]; // EMBEDDED_DATA_PLACEHOLDER',
            new_data,
            html,
            flags=re.DOTALL
        )

    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  완료! {len(live)}개 채널이 index.html에 내장됨")

if __name__ == "__main__":
    main()
