import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText

# ---- 1. 과기부 행정예고 게시판
URL = "https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=103&mId=109"

def get_latest_notice():
    res = requests.get(URL)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    # 게시판의 가장 첫번째 row
    # 실제로는 CSS selector 구조에 따라 살짝 바뀔 수 있어
    row = soup.select_one("table tbody tr")
    title = row.select_one("td a").get_text(strip=True)
    link = row.select_one("td a")["href"]
    # 절대경로로 만들어주기
    link = "https://www.msit.go.kr" + link

    return title, link

# ---- 2. 이전 글 비교
def is_new_notice(title):
    try:
        with open("last_notice.txt", "r", encoding="utf-8") as f:
            old_title = f.read().strip()
    except FileNotFoundError:
        old_title = ""

    if title != old_title:
        with open("last_notice.txt", "w", encoding="utf-8") as f:
            f.write(title)
        return True
    return False

# ---- 3. 이메일 전송 함수
def send_email(subject, body):
    # 환경변수 받기 (GitHub Secrets에 넣을 것)
    import os
    sender = os.environ["EMAIL_USER"]
    password = os.environ["EMAIL_PASS"]

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = "jaegon@lguplus.co.kr"

    with smtplib.SMTP("smtp.office365.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

# ---- 4. 메인 실행부
if __name__ == "__main__":
    title, link = get_latest_notice()
    message_body = f"{title}\n{link}"

    if is_new_notice(title):
        send_email("📌 신규 과기부 행정예고가 있습니다!", message_body)
    else:
        send_email("✔ 과기부 행정예고 변동 없음", "새 공고가 없습니다.")
