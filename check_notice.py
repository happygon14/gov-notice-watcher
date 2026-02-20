import requests                            # 웹사이트 HTML 가져오기
from bs4 import BeautifulSoup              # HTML 파싱해서 원하는 정보 추출
import re                                  # 
import os                                  # 환경변수 읽기 (GitHub Secrets)
import smtplib                             # 메일보내기
from email.mime.text import MIMEText       # 메일 내용 포맷 만들기

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
    headers = {
        "User-Agent": "Mozilla/5.0"                   # 사이트가 봇 차단 할수 있어서 브라우저인척 하는 명령어
    }

    response = requests.get(LIST_URL, headers=headers, timeout=10)     # 웹사이트 HTML 가져오기
    response.raise_for_status()

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
                title_tag = link.select_one(".title")
                if title_tag:
                    title = title_tag.text.strip()               # 제모 가져오기
                else:
                    title = link.text.strip()

                detail_url = f"https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=103&mId=109&nttSeqNo={notice_id}"

                return notice_id, title, detail_url              # 최신글 id + 제목 반환.

    raise Exception("게시글을 찾을 수 없습니다.")


def send_email(title):                                            # 메일 보내는 기능 시작
    subject = "📢 새 공지 발견!"                                  # 메일 제목 설정
    body = f"""새 공지가 등록되었습니다.                           # 메일 내용 작성 f" " " → 문자열 안에 변수 넣기 가

제목: {title}

목록 바로가기:
https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=103&mId=109
"""

    msg = MIMEText(body)                                            # 메일본문 생성
    msg["Subject"] = subject                                        # 메일 헤더정보 설정(아래 2줄 포함)
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:          # Gmail 서버연결 (465는 SSL포트)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)                  # Gmail 로그인
        server.send_message(msg)                                     # 메일 발송


def main():
    latest_id, title, link = get_latest_notice()                     # id, title, link 가져오기

    if os.path.exists("last_id.txt"):
        with open("last_id.txt", "r") as f:                          # 이전에 저장해둔 ID 읽기
            old_id = f.read().strip()
    else:
        old_id = None

    if latest_id != old_id:                                          # 최신ID가 기존ID와 다르면
        print("새 공지 발견!")                                        # 새 공지발견 텍스트를
        send_email(title)                                            # 메일로 보내

        with open("last_id.txt", "w") as f:                          # txt파일 불러내서
            f.write(latest_id)                                       # 새로운 id 저장
    else:
        print("변경 없음")                                           # 다르지않다면 변경없음 확인 후 아무행위없음


if __name__ == "__main__":                                           # 이 파일이 직접 실행될 때만 main() 실행. GitHub Action가 여기서 시작함.
    main()
