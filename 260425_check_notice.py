import requests
import cloudscraper
import subprocess
from bs4 import BeautifulSoup
import re
import os
import smtplib
import urllib3


from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

urllib3.disable_warnings()


# ✅ MSIT 공고 목록 페이지
LIST_URL = "https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=103&mId=109"


# ✅ scraper 생성 (cloudscraper)
scraper = cloudscraper.create_scraper()


# ✅ requests session (첨부 다운로드용)
session = requests.Session()


# ✅ GitHub Secrets
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")

print("EMAIL_ADDRESS:", EMAIL_ADDRESS)
print("EMAIL_PASSWORD:", EMAIL_PASSWORD)
print("TO_EMAIL:", TO_EMAIL)


# =========================
# 최신 공지 가져오기
# =========================

def get_latest_notice():

    headers = [
        "-H", "User-Agent: Mozilla/5.0",
        "-H", "Accept: text/html",
        "-H", "Accept-Language: ko-KR,ko;q=0.9",
        "-H", "Referer: https://www.msit.go.kr/",
    ]

    cmd = [
        "curl",
        "-L",
        LIST_URL,
        *headers
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    html = result.stdout

    soup = BeautifulSoup(html, "html.parser")

    links = soup.find_all("a", onclick=True)

    for link in links:

        onclick = link.get("onclick", "")

        if "fn_detail" in onclick:

            m = re.search(r"\d+", onclick)

            if m:

                notice_id = m.group()

                title = link.get_text(strip=True)

                detail_url = (
                    "https://www.msit.go.kr/bbs/view.do"
                    "?sCode=user&mPid=103&mId=109"
                    f"&nttSeqNo={notice_id}"
                )

                return notice_id, title, detail_url

    raise Exception("공지 못찾음")

# =========================
# 첨부파일 정보 찾기
# =========================

def get_attachment_info(detail_url):

    res = session.get(detail_url, verify=False)

    soup = BeautifulSoup(res.text, "html.parser")

    links = soup.find_all("a", onclick=True)

    for a in links:

        onclick = a.get("onclick", "")

        if "fn_download" in onclick:

            m = re.findall(r"'(.*?)'", onclick)

            if len(m) >= 3:

                file_id = m[0]
                file_sn = m[1]
                ext = m[2]

                return file_id, file_sn, ext

    return None, None, None


# =========================
# 파일 다운로드
# =========================

def download_file(file_id, file_sn, ext):

    url = "https://www.msit.go.kr/ssm/file/fileDown.do"

    data = {
        "fileId": file_id,
        "fileSn": file_sn,
        "fileExt": ext,
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": LIST_URL,
    }

    res = session.post(
        url,
        data=data,
        headers=headers,
        verify=False
    )

    filename = f"attach.{ext}"

    with open(filename, "wb") as f:
        f.write(res.content)

    return filename


# =========================
# 메일 보내기 (첨부 포함)
# =========================

def send_email(title, filepath):

    msg = MIMEMultipart()

    msg["Subject"] = "📢 새 공지 발견!"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    body = f"새 공지: {title}"

    msg.attach(MIMEText(body, "plain"))

    with open(filepath, "rb") as f:

        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())

    encoders.encode_base64(part)

    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{filepath}"'
    )

    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:

        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)


# =========================
# 메인
# =========================

def main():

    latest_id, title, link = get_latest_notice()

    if os.path.exists("last_id.txt"):

        with open("last_id.txt", "r") as f:
            old_id = f.read().strip()

    else:
        old_id = None

    if latest_id != old_id:

        print("새 공지 발견")

        file_id, file_sn, ext = get_attachment_info(link)

        if file_id:

            filepath = download_file(file_id, file_sn, ext)

            send_email(title, filepath)

        else:

            send_email(title, None)

        with open("last_id.txt", "w") as f:
            f.write(latest_id)

    else:

        print("변경 없음")


if __name__ == "__main__":
    main()
