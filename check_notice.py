import requests
from bs4 import BeautifulSoup
import re
import os

# 🔹 목록 페이지 URL (여기 네 사이트 주소로 바꿔)
LIST_URL = "https://사이트주소/list.do"

def get_latest_notice_id():
    response = requests.get(LIST_URL, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 첫 번째 공지 선택
    first_notice = soup.select_one(".toggle a")

    if not first_notice:
        raise Exception("게시글을 찾을 수 없습니다.")

    onclick = first_notice.get("onclick", "")

    # fn_detail(3186342);
    match = re.search(r"\d+", onclick)
    if not match:
        raise Exception("게시글 번호를 찾을 수 없습니다.")

    return match.group()

def main():
    latest_id = get_latest_notice_id()

    # 이전 ID 읽기
    if os.path.exists("last_id.txt"):
        with open("last_id.txt", "r") as f:
            old_id = f.read().strip()
    else:
        old_id = None

    if latest_id != old_id:
        print("새 공지 발견!")
        with open("last_id.txt", "w") as f:
            f.write(latest_id)
    else:
        print("변경 없음")

if __name__ == "__main__":
    main()
