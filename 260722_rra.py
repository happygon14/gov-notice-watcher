# [준비] (import / 환경변수 / session생성)
# 1-1. 라이브러리(도구)

  # 1) 기본 내장 라이브러리
import os                          # 운영체제(OS)기능 접근용 (파일존재확인, 환경변수읽기, 파일명처리 등)
import smtplib                     # 이메일 전송 (SMTP서버로 메일보내기)
import re                          # 문자패턴찾기 (게시글 제목 분석시)

  # 2) 웹 크롤링 계열
import requests                     # 웹사이트 접속(GET/POST)
from bs4 import BeautifulSoup       # HTML 분석
import cloudscraper                 # request강화버전 (차단 우회용) (일반 requests 막히는 경우)

  # 3) 접속 안정화
import urllib3                            # SSL경고 숨김
urllib3.disable_warnings()                # SSL경고메시지 숨김
from urllib3.util.retry import Retry      # 실패시 자동 재시도 (서버 일시오류 대응)
from requests.adapters import HTTPAdapter # requests 세션에 재시도 기능 연결

  # 4) 이메일 MIME계열
from email.mime.text import MIMEText            # 메일본문만들기
from email.mime.multipart import MIMEMultipart  # 본문+이미지+첨부파일 합체 
from email.mime.base import MIMEBase            # 엑셀/이미지 첨부
from email import encoders                      # 첨부파일 메일용 변환

# 1-2. 환경변수 
  # 1) 사이트 주소 (크롤링 대상 웹사이트)
LIST_URL = "https://www.rra.go.kr/ko/notice/atnList.do"    # 국립전파연구원 행정예고 목록페이지

  # 2) 이메일 환경변수 (Github Secret에 저장한 내용 불러오기)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")

  # 3) 웹사이트 접속용 브라우저(자동접속(봇) 차단 우회기능 강화버전_requests의 강화버전) & 안정적기능(retry등)
scraper = cloudscraper.create_scraper()        # create_scraper : 브라우저 하나 생성
session = requests.Session()                   # 연결유지하는 requests 객체생성(매번 새접속없이 연결 재사용)
retries = Retry(                               # 접속실패시 자동재시도
    total=2,                                        # 최대 5번
    connect=2,
    read=0,
    backoff_factor=1,
    status_forcelist=[429,500,502,503,504],         # 이 오류코드 나오면 재시도 (429:너무많이 접속, 500:서버오류, 503:서버점검 등)
)
adapter = HTTPAdapter(max_retries=retries)     # requests에 retry 기능 장착

session.mount("https://", adapter)             # 모든 웹접속시 retry기능 적용
session.mount("http://", adapter)



# [기능 정의(def)]  1.공지찾기, 2.첨부찾기, 3.다운로드, 4.메일발송

# 2-1. 최신 공지찾기

def get_latest_notices(limit=3):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://www.rra.go.kr/",
        "Accept-Language": "ko-KR,ko;q=0.9"
    }

    res = session.get(
        LIST_URL,
        headers=headers,
        timeout=(10, 20),
        verify=False
    )

    print("status =", res.status_code)

    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.select("table.table_organ0 tbody tr")

    notices = []

    for row in rows:

        a = row.select_one("a")

        if not a:
            continue

        href = a.get("href","")

        m = re.search(
            r"nb_seq=(\d+)",
            href
        )

        if not m:
            continue

        notice_id = m.group(1)

        title = a.get_text(
            " ",
            strip=True
        )

        title = (
            title
            .replace("진행중","")
            .replace("완료","")
            .strip()
        )

        detail_url = (
            "https://www.rra.go.kr"
            + href
        )

        notices.append({
            "id": notice_id,
            "title": title,
            "link": detail_url
        })

        if len(notices) >= limit:
            break

    if not notices:
        raise Exception("공지 못찾음")

    return notices




def get_notice_detail(detail_url):

    res = session.get(
        detail_url,
        timeout=(10,20),
        verify=False
    )

    soup = BeautifulSoup(
        res.text,
        "html.parser"
    )

    table = soup.select_one("table")

    rows = table.select("tr")

    info = {}

    for row in rows:

        ths = row.select("th")
        tds = row.select("td")

        if len(ths) == 1 and len(tds) == 1:
            info[
                ths[0].get_text(strip=True)
            ] = tds[0].get_text(
                " ",
                strip=True
            )

        elif len(ths) == 2 and len(tds) == 2:

            info[
                ths[0].get_text(strip=True)
            ] = tds[0].get_text(
                " ",
                strip=True
            )

            info[
                ths[1].get_text(strip=True)
            ] = tds[1].get_text(
                " ",
                strip=True
            )

    files = []

    for a in soup.select(
        'a[href*="FileDownSvl"]'
    ):
    
        name = a.get_text(
            " ",
            strip=True
        )
    
        href = a.get("href", "")
    
        if href.startswith("/"):
            href = (
                "https://www.rra.go.kr"
                + href
            )
    
        files.append({
            "name": name,
            "url": href
        })

    return info, files


# =========================
# 메일 보내기 (첨부 포함)
# =========================

def send_email(info, files, link):

    msg = MIMEMultipart()

    msg["Subject"] = "[RRA 행정예고]"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    body = f"""
[RRA 행정예고]

제목
{info.get('제목','')}

담당부서
{info.get('담당부서','')}

연락처
{info.get('연락처','')}

기간
{info.get('기간','')}

내용
{info.get('내용','')[:1500]}

첨부파일
{chr(10).join(files)}

원문
{link}
"""

    msg.attach(
        MIMEText(body, "plain", "utf-8")
    )

    with smtplib.SMTP_SSL(
        "smtp.gmail.com",
        465
    ) as server:

        server.login(
            EMAIL_ADDRESS,
            EMAIL_PASSWORD
        )

        server.send_message(msg)

# =========================
# 메인
# =========================
def main():

    notices = get_latest_notices(limit=3)

    latest_id = notices[0]["id"]

    print("최신 게시글:", latest_id)

    # 이전 ID 읽기
    if os.path.exists("last_id_rra.txt"):

        with open(
            "last_id_rra.txt",
            "r",
            encoding="utf-8"
        ) as f:

            old_id = f.read().strip()

    else:

        old_id = ""

    print("이전 게시글:", old_id)

    # 변경 없음
    if latest_id == old_id:

        print("변경 없음")
        return

    print("새 행정예고 발견!")

    info, files = get_notice_detail(
        notices[0]["link"]
    )
    
    print("=" * 60)
    print("제목 :", info.get("제목", ""))
    
    print("담당부서 :", info.get("담당부서", ""))
    
    print("연락처 :", info.get("연락처", ""))
    
    print("기간 :", info.get("기간", ""))
    
    print("첨부파일")
    for f in files:
            
        print("-" * 30)
        print("파일명 :", f["name"])
        print("URL :", f["url"])
    
    print("=" * 60)



  
    # 새 ID 저장
    with open(
        "last_id_rra.txt",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(latest_id)

    print("저장 완료")



if __name__ == "__main__":
    main()
