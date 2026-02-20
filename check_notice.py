import requests
from bs4 import BeautifulSoup
import re
import os
import smtplib
from email.mime.text import MIMEText

# ✅ MSIT 공고 목록 페이지
LIST_URL = "https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=103&mId=109"

# ✅ GitHub Secrets에서 불러오기

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")

print("EMAIL_ADDRESS:", EMAIL_ADDRESS)
print("EMAIL_PASSWORD:", EMAIL_PASSWORD)
print("TO_EMAIL:", TO_EMAIL)


def get_latest_notice():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(LIST_URL, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # fn_detail 포함된 링크만 찾기
    notice_links = soup.find_all("a", onclick=True)

    for link in notice_links:
        onclick = link.get("onclick", "")
        if "fn_detail" in onclick:
            match = re.search(r"\d+", onclick)
            if match:
                notice_id = match.group()

                # 제목은 내부 p.title에서 가져오기
                title_tag = link.select_one(".title")
                if title_tag:
                    title = title_tag.text.strip()
                else:
                    title = link.text.strip()

                detail_url = f"https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=103&mId=109&nttSeqNo={notice_id}"

                return notice_id, title, detail_url

    raise Exception("게시글을 찾을 수 없습니다.")


def send_email(title, link):
    subject = "📢 새 공지 발견!"
    body = f"""새 공지가 등록되었습니다.

제목: {title}

링크:
{link}
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)


def main():
    latest_id, title, link = get_latest_notice()

    if os.path.exists("last_id.txt"):
        with open("last_id.txt", "r") as f:
            old_id = f.read().strip()
    else:
        old_id = None

    if latest_id != old_id:
        print("새 공지 발견!")
        send_email(title, link)

        with open("last_id.txt", "w") as f:
            f.write(latest_id)
    else:
        print("변경 없음")


if __name__ == "__main__":
    main()
