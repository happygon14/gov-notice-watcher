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
LIST_URL = "https://www.msit.go.kr/bbs/list.do?sCode=user&mPid=103&mId=109"    # 과기부 행정예고 목록페이지

  # 2) 이메일 환경변수 (Github Secret에 저장한 내용 불러오기)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")

  # 3) 웹사이트 접속용 브라우저(자동접속(봇) 차단 우회기능 강화버전_requests의 강화버전) & 안정적기능(retry등)
scraper = cloudscraper.create_scraper()        # create_scraper : 브라우저 하나 생성
session = requests.Session()                   # 연결유지하는 requests 객체생성(매번 새접속없이 연결 재사용)
retries = Retry(                               # 접속실패시 자동재시도
    total=5,                                        # 최대 5번
    backoff_factor=2,                               # 실패할수록 대기시간 2배씩 증가
    status_forcelist=[429,500,502,503,504],         # 이 오류코드 나오면 재시도 (429:너무많이 접속, 500:서버오류, 503:서버점검 등)
)
adapter = HTTPAdapter(max_retries=retries)     # requests에 retry 기능 장착

session.mount("https://", adapter)             # 모든 웹접속시 retry기능 적용
session.mount("http://", adapter)



# [기능 정의(def)]  1.공지찾기, 2.첨부찾기, 3.다운로드, 4.메일발송

# 2-1. 최신 공지찾기

def get_latest_notice():
    headers = {                                                # 브라우저 설정
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://www.msit.go.kr/",                  # 어디서 들어왔는지..(과기부 메인홈페이지에서 들어왔고)
        "Accept-Language": "ko-KR,ko;q=0.9"
    }

    res = session.get(                                         # 웹페이지 다운로드 요청
        LIST_URL,
        headers=headers,
        timeout=30,
        verify=False
    )

    print("status=", res.status_code)                           # 접속성공여부 확인용, 오류코드 등도 확인가능

    soup = BeautifulSoup(res.text,"html.parser")                # HTML 분석 객체 생성 (웹페이지 분해)

    links = soup.find_all("a", onclick=True)                    # onclick(자바스크립트방식 링크)에 있는 a태그 전부 찾기

    for a in links:                                             # 링크 하나씩 검사

        onclick = a.get("onclick","")                           # onclick 내용 가져오기

        if "fn_detail" in onclick:                              # 상세보기 링크만 선택

            m = re.search(r"\d{5,}", onclick)                   # 숫자 5자리 이상 찾기(공지번호 추출용)

            if m:
                notice_id = m.group()                           # 최상단(최신) 게시글번호 추출
                title = a.get_text(strip=True)                  # 제목 추출

                detail_url = (                                  # url 추출
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
                
                return notice_id,title,detail_url                 # 게시글번호, 제목, url 반환

    
    raise Exception("공지 못찾음")


# 2-2. 첨부파일 찾기
# 흐름 : 상세페이지접속  →  HTML분석  →  첨부파일 링크 찾기  →  다운로드용 파일번호 추출  →  리스트로 반환

def get_attachment_info(detail_url):                      # 상세페이지(detail_url)에서 첨부파일정보 추출하는 기능 정의

    res = session.get(                                    # 상세페이지 HTML 다운로드
        detail_url,
        headers={
            "User-Agent":"Mozilla/5.0",
            "Referer":"https://msit.go.kr/",
            "Accept-Language":"ko-KR,ko;q=0.9"
        },
        timeout=30,
        verify=False
    )

    soup = BeautifulSoup(res.text, "html.parser")         # HTML 분석 객체 생성 (웹페이지 분해)

    links = soup.select("a[href], a[onclick]")            # href(일반링크) 또는 onclick(자바스크립트링크)가진 a태그 전부 찾기

    attachments = []                                      # 첨부파일정보 저장용 빈 리스트

    for a in links:                                       # 링크 하나씩검사

        target = (
            a.get("onclick","")
            + " "
            + a.get("href","")
        )

        if "fn_download" in target or "fileDown" in target:    # 다운로드 링크인지 판별

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
# 메일 보내기 (첨부 포함)
# =========================

def send_email(title, filepath, meta, deadline, reason, main_points, link):
    
    msg = MIMEMultipart()

    msg["Subject"] = "📢 새 공지 발견!"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    body = f"""

    공고명: {title}

    작성일: {meta.get("작성일")}
    부서: {meta.get("부서")}
    담당자: {meta.get("담당자")}
    연락처: {meta.get("연락처")}
    의견제출기한: {deadline}

    [개정이유]
    {reason[:500]}

    [주요내용]
    {main_points[:1000]}

    📎 원문 확인:
    {link}
    """

    msg.attach(MIMEText(body,"plain","utf-8"))

    if filepath:

        if isinstance(filepath, str):
            filepath = [filepath]

        for fp in filepath:
            with open(fp,"rb") as f:
                part = MIMEBase("application","octet-stream")
                part.set_payload(f.read())

            encoders.encode_base64(part)

            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(fp)}"'
            )

            msg.attach(part)

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

    latest_id, title, link = get_latest_notice()

    if os.path.exists("last_id.txt"):

        with open("last_id.txt", "r") as f:
            old_id = f.read().strip()

    else:
        old_id = None


    if latest_id != old_id:

        print("새 공지 발견")

        attachments = get_attachment_info(link)

        if attachments:

            filepaths = []

            for file_id, file_sn, ext in attachments:

                filepath = download_file(
                    file_id,
                    file_sn,
                    ext,
                    link
                )

                filepaths.append(filepath)




         # =========================
        # 본문 상세 파싱
        # =========================

            res = session.get(link, verify=False)
            soup = BeautifulSoup(res.text, "html.parser")


        # 1. 메타정보
            meta = {}

            for dl in soup.select(".meta dl.tit_con"):
                k = dl.select_one("dt").get_text(strip=True)
                v = dl.select_one("dd").get_text(strip=True)

                meta[k] = v

            title_tag = (
                soup.select_one(".board_view_tit")
                or soup.select_one("h3")
                or soup.select_one(".view_tit")
            )

            if title_tag:
                title = title_tag.get_text(" ", strip=True)    


        # 2. 본문텍스트
            content_tag = soup.select_one("#cont-wrap")

            for tag in content_tag.select("script, style"):
                tag.decompose()

            content = content_tag.get_text(" ", strip=True)
            content = re.sub(r"\s+", " ", content)


        # 3. 의견제출기한
            deadline_match = re.search(
                r'(\d{4}\s*년\s*\d+\s*월\s*\d+\s*일)\s*까지',
                content,
                re.S
            )

            deadline = (
                deadline_match.group(1)
                if deadline_match
                else "미추출"
            )

            deadline = re.sub(r"\s+", " ", deadline).strip()


        # 4. 개정이유
            reason_match = re.search(
                r'1\.\s*개정이유(.*?)2\.\s*주요내용',
                content,
                re.S
            )        

            reason = (
                reason_match.group(1).strip()
                if reason_match else ""
            )


        # 5. 주요내용
            main_match = re.search(
                r'2\.\s*주요내용(.*?)3\.\s*의견제출',
                content,
                re.S
            )

            main_points = (
                main_match.group(1).strip()
                if main_match else ""
            )

 
                        
            # ===== 텍스트 정제 추가 =====
            reason = re.sub(r"\s+", " ", reason).strip()
            # 줄바꿈은 살리고 과한 공백만 정리
            main_points = re.sub(r'[ \t]+', ' ', main_points).strip()
            # 항목 시작 줄바꿈 보강
            main_points = re.sub(r'\s*([가-하])\s*\.', r'\n\n\1.', main_points)
            
            # 인용문 앞 줄바꿈
            main_points = re.sub(r'\s*(“)', r'\n\1', main_points)
            
            # 가. 나. 다. 줄바꿈 복원
            main_points = re.sub(r'([가-하])\.', r'\n\1.', main_points)

        # =========================
        # 로그 테스트
        # =========================

            print("공고명:", title)
            print("작성일:", meta.get("작성일"))
            print("소관부서:", meta.get("부서"))
            print("담당자:", meta.get("담당자"))
            print("연락처:", meta.get("연락처"))
            print("의견제출기한:", deadline)

            print("개정이유:")
            print(reason[:500])

            print("주요내용:")
            print(main_points[:1000])

            send_email(title, filepaths, meta, deadline, reason, main_points, link)

        else:

            send_email(title, None, meta, deadline, reason, main_points, link)



        with open("last_id.txt", "w") as f:
            f.write(latest_id)

    else:

        print("변경 없음")


if __name__ == "__main__":
    main()
