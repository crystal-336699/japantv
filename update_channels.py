import urllib.request
import re
import json

# utako IPTV-JP 프로젝트 (클린 리스트)
M3U_URL = "https://gitflic.ru/project/utako/utako/blob/raw?file=jp_clean.m3u"
HTML_FILE = "index.html"
JSON_FILE = "channels.json"  # PC앱(JapanTV.py/exe)이 읽는 파일
PLACEHOLDER_RE = re.compile(r'(?:null|\[.*?\]); // EMBEDDED_DATA_PLACEHOLDER', re.DOTALL)

GENRE_MAP = {
    "📰 뉴스":  ["news","nhk","news24","ann","jnn","fnn","nnn"],
    "🎬 지상파": ["ntv","nippon tv","tbs","fuji","tv asahi","tv tokyo","ytv","mbs","abc","関西","tokyo mx","tvk","nhk g","nhk e"],
    "📡 BS·CS": ["bs","cs","wowow","sky","at-x","dlife"],
    "🛒 쇼핑":  ["shop","qvc","japanet","gstv"],
}

def guess_genre(name):
    nl = name.lower()
    for genre, keys in GENRE_MAP.items():
        if any(k in nl for k in keys):
            return genre
    return "🎌 기타"

def parse_m3u(text):
    channels = []
    seen_urls = set()
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
                if url.startswith("http") and url not in seen_urls:
                    seen_urls.add(url)
                    channels.append({"name": name, "url": url, "genre": guess_genre(name)})
                    i = j + 1
                    continue
        i += 1
    return channels

def main():
    print(f"[1/4] 채널 목록 다운로드 중...")
    print(f"  소스: {M3U_URL}")
    try:
        req = urllib.request.Request(M3U_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  [오류] 다운로드 실패: {e}")
        return

    channels = parse_m3u(text)
    channels.sort(key=lambda c: (c["genre"], c["name"]))
    print(f"  총 {len(channels)}개 채널 파싱됨")

    # channels.json 저장 (PC앱용)
    print(f"[2/4] {JSON_FILE} 저장 중... (PC앱/exe 동기화용)")
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False)
    print(f"  → {JSON_FILE} 저장 완료")

    # index.html 업데이트 (웹앱용)
    print(f"[3/4] {HTML_FILE} 업데이트 중...")
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    json_data = json.dumps(channels, ensure_ascii=False)
    new_data = f"{json_data}; // EMBEDDED_DATA_PLACEHOLDER"
    html = PLACEHOLDER_RE.sub(new_data, html)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[4/4] 완료! {len(channels)}개 채널")
    print(f"  → 웹앱(index.html) + PC앱(channels.json) 동시 업데이트됨")

if __name__ == "__main__":
    main()
