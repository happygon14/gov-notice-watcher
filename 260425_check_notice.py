import requests
import cloudscraper
from bs4 import BeautifulSoup
import re
import os
import smtplib
import urllib3


from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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

retries = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429,500,502,503,504],
)

adapter = HTTPAdapter(max_retries=retries)

session.mount("https://", adapter)
session.mount("http://", adapter)



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

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://www.msit.go.kr/",
        "Accept-Language": "ko-KR,ko;q=0.9"
    }

    res = session.get(
        LIST_URL,
        headers=headers,
        timeout=30,
        verify=False
    )

    print("status=", res.status_code)
    print("html length=", len(res.text))

    soup = BeautifulSoup(res.text,"html.parser")

    links = soup.find_all("a", onclick=True)

    for a in links:

        onclick = a.get("onclick","")

        if "fn_detail" in onclick:

            m = re.search(r"\d{5,}", onclick)    

            if m:
                notice_id = m.group()
                title = a.get_text(strip=True)

                detail_url = (
                        "https://msit.go.kr/bbs/view.do"
                        "?sCode=user"
                        "&mId=109"
                        "&mPid=103"
                        "&pageIndex="
                        "&bbsSeqNo=84"
                        f"&nttSeqNo={notice_id}"
                        "&searchOpt=ALL"
                        "&searchTxt="
                )

                print(detail_url)
                
                return notice_id,title,detail_url

    
    raise Exception("공지 못찾음")

# =========================
# 첨부파일 정보 찾기
# =========================

def get_attachment_info(detail_url):

    res = session.get(
        detail_url,
        headers={
            "User-Agent":"Mozilla/5.0",
            "Referer":"https://msit.go.kr/",
            "Accept-Language":"ko-KR,ko;q=0.9"
        },
        timeout=30,
        verify=False
    )

    soup = BeautifulSoup(res.text, "html.parser")
    print(res.text[:5000])

    links = soup.select("a[href], a[onclick]")

    attachments = []

    for a in links:

        target = (
            a.get("onclick","")
            + " "
            + a.get("href","")
        )

        if "fn_download" in target or "fileDown" in target:

            print("첨부링크 발견:", target)

            m = re.findall(r"'(.*?)'", target)

            if len(m) >= 3:
                attachments.append(
                    (m[0], m[1], m[2])
                )

    return attachments


# =========================
# 파일 다운로드
# =========================

def download_file(file_id, file_sn, ext, detail_url):

    url = "https://msit.go.kr/ssm/file/fileDown.do"

    data = {
        "atchFileNo": file_id,
        "fileOrd": file_sn,
        "fileBtn": "A"
    }

    headers = {
        "User-Agent":"Mozilla/5.0",
        "Referer": detail_url,
        "Origin":"https://msit.go.kr"
    }

    res = session.post(
        url,
        data=data,
        headers=headers,
        verify=False
    )

    print(res.headers.get("content-disposition"))
    print("download size=", len(res.content))

    filename = f"attach.{ext}"

    with open(filename,"wb") as f:
        f.write(res.content)

    return filename


# =========================
# HTML 레포트생성
# =========================

def build_report_html(title, meta, content, attachments, url):

    attachment_html = ""
    if attachments:
        for fp in attachments:
            attachment_html += f"""
            <li>
            📎 <b>{os.path.basename(fp)}</b>
            </li>
            """
    else:
        attachment_html = "<li>첨부파일 없음</li>"

    html = f"""
    <html>
    <body style="font-family:Arial; background:#f6f6f6; padding:20px;">

        <div style="max-width:850px;margin:auto;background:#fff;padding:25px;border-radius:10px;box-shadow:0 4px 18px rgba(0,0,0,0.08);">

            <h2 style="border-bottom:2px solid #222;padding-bottom:10px;font-size:20px;line-height:1.4;">
                📢 입법행정예고 등록 ({meta.get('부서','')})<br>
                {title}
            </h2>

            <h3>📌 기본정보</h3>
            <table style="width:100%;border-collapse:collapse;">
                <tr><th style="text-align:left;background:#eee;padding:6px;">부서</th><td>{meta.get('부서','')}</td></tr>
                <tr><th style="text-align:left;background:#eee;padding:6px;">담당자</th><td>{meta.get('담당자','')}</td></tr>
                <tr><th style="text-align:left;background:#eee;padding:6px;">연락처</th><td>{meta.get('연락처','')}</td></tr>
                <tr><th style="text-align:left;background:#eee;padding:6px;">작성일</th><td>{meta.get('작성일','')}</td></tr>
            </table>

            <h3>📄 주요내용 요약</h3>
            <div style="white-space:pre-wrap;background:#fafafa;padding:15px;border:1px solid #ddd;line-height:1.6;">
                {content[:2000]}
            </div>

            <h3>📎 첨부파일</h3>
            <ul>
                {attachment_html}
            </ul>

            <h3>🔗 원문 링크</h3>
            <a href="{url}">{url}</a>

        </div>

    </body>
    </html>
    """

    return html
    
# =========================
# 메일 보내기 (첨부 포함)
# =========================
print("EMAIL:", EMAIL_ADDRESS)
print("PWD length:", len(EMAIL_PASSWORD or ""))
print("TO:", TO_EMAIL)
print("메일 보내기 직전")

def send_email(subject, html_body, attachments=None):

    try:
        print("SMTP 시작")

        msg = MIMEMultipart("alternative")

        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = TO_EMAIL

        text_fallback = "새 공지가 등록되었습니다."

        msg.attach(MIMEText(text_fallback, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        print("SMTP 서버 연결")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.set_debuglevel(1)

            print("로그인 시도")
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            print("메일 전송 시도")
            server.send_message(msg)

        print("📧 메일 전송 완료")

    except Exception as e:
        print("❌ SMTP 에러 발생:", repr(e))
        raise

# =========================
# 메인
# =========================

def main():

    latest_id, title, link = get_latest_notice()

    old_id = None
    if os.path.exists("last_id.txt"):
        with open("last_id.txt", "r") as f:
            old_id = f.read().strip()

    if latest_id != old_id:

        print("새 공지 발견")

        attachments = get_attachment_info(link)

        filepaths = []

        if attachments:

            for file_id, file_sn, ext in attachments:

                filepath = download_file(file_id, file_sn, ext, link)
                filepaths.append(filepath)

        # ----------------------------
        # 본문/메타 추출 (추가 필요)
        # ----------------------------
        res = session.get(link, verify=False)
        soup = BeautifulSoup(res.text, "html.parser")

        meta = {}
        for dl in soup.select(".meta dl.tit_con"):
            k = dl.select_one("dt").get_text(strip=True)
            v = dl.select_one("dd").get_text(strip=True)
            meta[k] = v

        content_tag = soup.select_one("#cont-wrap")

        for tag in content_tag.select("script, style"):
            tag.decompose()

        content = content_tag.get_text("\n", strip=True)

        # ----------------------------
        # 레포트 생성
        # ----------------------------
        html = build_report_html(title, meta, content, filepaths, link)
 
        subject = f"📢입법행정예고 등록({meta.get('부서','')}) | {title}"
        send_email(subject, html, filepaths)

        with open("last_id.txt", "w") as f:
            f.write(latest_id)

    else:
        print("변경 없음")
