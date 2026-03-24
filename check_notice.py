import requests                            # 웹사이트 HTML 가져오기
from bs4 import BeautifulSoup              # HTML 파싱해서 원하는 정보 추출
import re                                  # 
import os                                  # 환경변수 읽기 (GitHub Secrets)
import smtplib                             # 메일보내기
import urllib3
urllib3.disable_warnings()
from email.mime.text import MIMEText       # 메일 내용 포맷 만들기
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders


# ✅ MSIT 공고 목록 페이지
LIST_URL = "https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=103&mId=109"

# ✅ GitHub Secrets에서 불러오기 (GitHub에 저장한 비밀값 꺼내는 코드)

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")

print("EMAIL_ADDRESS:", EMAIL_ADDRESS)
print("EMAIL_PASSWORD:", EMAIL_PASSWORD)
print("TO_EMAIL:", TO_EMAIL)


def get_latest_notice():                              # 공지 가져오는 함수

    
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Referer": LIST_URL
    }
    
    # 사이트가 봇 차단 할수 있어서 브라우저인척 하는 명령어
    

    response = session.get(
        LIST_URL,
        headers=headers,
        timeout=20,
        verify=False   # ⭐ 중요
    )     # 웹사이트 HTML 가져오기
    
    response.raise_for_status()


    print("DEBUG status:", response.status_code)
    print("DEBUG length:", len(response.text))
    print(response.text[:1000])

    
    soup = BeautifulSoup(response.text, "html.parser")                 # HTML 분석 준비

    # fn_detail 포함된 링크만 찾기
    notice_links = soup.find_all("a", onclick=True)                    

    for link in notice_links:
        onclick = link.get("onclick", "")
        if "fn_detail" in onclick:
            match = re.search(r"\d+", onclick)
            if match:
                notice_id = match.group()                        # URL에서 nttSeqNo 번호만 추출

                # 제목은 내부 p.title에서 가져오기
                title = link.get_text(strip=True)
                detail_url = f"https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=103&mId=109&nttSeqNo={notice_id}"

                print("크롤링된 제목:", title)


                print("DEBUG link:", link)
                print("DEBUG title:", title)
                
                return notice_id, title, detail_url              # 최신글 id + 제목 반환.

    raise Exception("게시글을 찾을 수 없습니다.")

# ✅ 파일 다운로드 함수

def download_file(file_id, file_sn, ext):

    url = "https://www.msit.go.kr/ssm/file/fileDown.do"

    data = {
        "fileId": file_id,
        "fileSn": file_sn,
        "fileExt": ext
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": LIST_URL
    }

    res = requests.post(url, data=data, headers=headers)

    filename = f"attach.{ext}"

    with open(filename, "wb") as f:
        f.write(res.content)

    return filename


# ✅ 첨부파일 정보 추출

def get_attachment_info(detail_url):

    session = requests.Session()
    
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


def main():

    latest_id, title, link = get_latest_notice()

    if os.path.exists("last_id.txt"):
        with open("last_id.txt", "r") as f:
            old_id = f.read().strip()
    else:
        old_id = None

    if latest_id != old_id:

        print("새 공지 발견!")

        # ✅ 첨부파일 정보 가져오기
        file_id, file_sn, ext = get_attachment_info(link)

        # ✅ 파일 다운로드
        filepath = download_file(file_id, file_sn, ext)

        # ✅ 메일 보내기 (첨부 포함)
        send_email(title, filepath)

        with open("last_id.txt", "w") as f:
            f.write(latest_id)

    else:
        print("변경 없음")


if __name__ == "__main__":                                           # 이 파일이 직접 실행될 때만 main() 실행. GitHub Action가 여기서 시작함.
    main()
