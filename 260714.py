# [준비] (import / 환경변수 / session생성)
# 1-1. 라이브러리(도구)

  # 1) 기본 내장 라이브러리
import os                          # 운영체제(OS)기능 접근용 (파일존재확인, 환경변수읽기, 파일명처리 등)
import smtplib                     # 이메일 전송 (SMTP서버로 메일보내기)
import re                          # 문자패턴찾기 (게시글 제목 분석시)
import time
import zipfile

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
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")


  # 3) 웹사이트 접속용 브라우저(자동접속(봇) 차단 우회기능 강화버전_requests의 강화버전) & 안정적기능(retry등)
scraper = cloudscraper.create_scraper()        # create_scraper : 브라우저 하나 생성
session = requests.Session()                   # 연결유지하는 requests 객체생성(매번 새접속없이 연결 재사용)




def safe_get(url, headers=None, **kwargs):

    print("현재 URL:", url)

  
    for attempt in range(1, 4):

        try:

            print(f"[접속시도 {attempt}/3] {url}")

            res = session.get(
                url,
                headers=headers,
                timeout=5,
                **kwargs
            )

            print("=" * 60)
            print(f"과기부 접속 성공 (시도횟수: {attempt}/3)")
            print("=" * 60)
            res.raise_for_status()

            return res

        except Exception as e:

            print(
                f"[실패] {attempt}/3 : "
                f"{type(e).__name__}"
            )

            if attempt < 3:
                print("5초 후 재시도...")
                time.sleep(5)

    raise Exception(
        "과기부 사이트 접속 실패 (3회 재시도 후 포기)"
    )


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

    res = safe_get(                                         # 웹페이지 다운로드 요청
        LIST_URL,
        headers=headers
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

    res = safe_get(                                    # 상세페이지 HTML 다운로드
        detail_url,
        headers={
            "User-Agent":"Mozilla/5.0",
            "Referer":"https://msit.go.kr/",
            "Accept-Language":"ko-KR,ko;q=0.9"
        },
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



# AI분석함수


def analyze_with_ai(document_text):

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return "OPENROUTER_API_KEY 없음"

    prompt = f"""
당신은 LG유플러스 NW협력팀 정책담당자이다.

아래 행정예고 또는 정책 문서를 분석하라.

특히 다음 항목을 중점 검토한다.

- 통신사업자 영향
- 유선/무선 네트워크 영향
- 기술기준 영향
- 규제 변화
- 비용 증가 가능성
- 대응 필요사항

출력 형식:

[1. 핵심 요약]
- 5줄 이내

[2. 주요 내용]

[3. 통신업계 영향도]

[4. LG유플러스 검토사항]

[5. 한줄 결론]

문서:
{document_text}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "openai/gpt-oss-20b:free",
        "messages": [
            {
                "role": "system",
                "content": "반드시 한국어만 사용한다."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1800
    }

    try:

        print("OPENROUTER 요청 시작")

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=120
        )

        print("OPENROUTER 응답 수신")
        print("STATUS:", response.status_code)
        print(response.text[:500])
      
        result = response.json()


        print("JSON 파싱 완료")
        print(result.keys())
                

        if "choices" in result:
            content = result["choices"][0]["message"]["content"]

            print("=" * 60)
            print("AI 분석 결과")
            print("=" * 60)
            print(content[:3000])
        
            return content



      
        return str(result)

    except Exception as e:

        print("AI 분석 실패:", e)

        return f"AI 분석 실패: {e}"




# hwpx 읽기 함수

def extract_hwpx_text(filepath):

    try:

        text = ""

        with zipfile.ZipFile(filepath, "r") as z:

            for name in z.namelist():

                if (
                    "section" in name.lower()
                    and name.endswith(".xml")
                ):

                    xml = z.read(name)

                    soup = BeautifulSoup(
                        xml,
                        "xml"
                    )

                    text += soup.get_text(
                        separator=" ",
                        strip=True
                    )

        return text

    except Exception as e:

        print("HWPX 추출 실패:", e)

        return ""


# =========================
# 메일 보내기 (첨부 포함)
# =========================

def send_email(title, filepath, meta, deadline, reason, main_points, link, ai_result=""):
    
    msg = MIMEMultipart()

    msg["Subject"] = f"📢 신규 입법행정예고 공고 - {title}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    body = f"""

    공고명: {title}

    작성일: {meta.get("작성일")}
    부서: {meta.get("부서")}
    담당자: {meta.get("담당자")}
    연락처: {meta.get("연락처")}
    의견제출기한: {deadline}

    
    ==================================================
    🤖 AI 분석
    ==================================================
 
    {ai_result}
    
    ==================================================
    원문 요약
    ==================================================
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


    print(
        "OPENROUTER_API_KEY 존재:",
        bool(os.getenv("OPENROUTER_API_KEY"))
    )

    try:

        latest_id, title, link = get_latest_notice()

    except Exception as e:

        print("=" * 60)
        print("과기부 접속 실패")
        print(e)
        print("=" * 60)

        raise




  

    if os.path.exists("last_id.txt"):

        with open("last_id.txt", "r") as f:
            old_id = f.read().strip()

    else:
        old_id = None


    if latest_id != old_id:

        print("새 공지 발견")
    
        attachments = get_attachment_info(link)
    
        filepaths = []
    
        for file_id, file_sn, ext in attachments:
    
            filepath = download_file(
                file_id,
                file_sn,
                ext,
                link
            )
    
            filepaths.append(filepath)
    
        ai_result = ""
    
        for fp in filepaths:
    
            if fp.lower().endswith(".hwpx"):
    
                print("AI 분석 시작")
    
                document_text = extract_hwpx_text(fp)
    
                print("문서길이:", len(document_text))
    
                if document_text:
    
                    ai_result = analyze_with_ai(
                        document_text[:30000]
                    )
    
                break
    
        # 본문 상세 파싱
        res = safe_get(link, verify=False)
        soup = BeautifulSoup(res.text, "html.parser")

        print("=" * 60)
        print("제목 후보 확인")
        print("=" * 60)
        
        for h in soup.find_all(["h1", "h2", "h3", "h4", "strong"]):
            txt = h.get_text(" ", strip=True)
            if txt:
                print(txt[:200])


        for h in soup.find_all(["h1", "h2", "h3", "h4", "strong"]):
        
            txt = h.get_text(" ", strip=True)
        
            if "행정예고" in txt and len(txt) > 20:
                title = txt
                print("제목 추출 성공:", title)
                break

      
        meta = {}

        for dl in soup.select(".meta dl.tit_con"):
            k = dl.select_one("dt").get_text(strip=True)
            v = dl.select_one("dd").get_text(strip=True)

            meta[k] = v


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

        send_email(title, filepaths, meta, deadline, reason, main_points, link, ai_result)



        with open("last_id.txt", "w") as f:
            f.write(latest_id)

    else:

        print("변경 없음")


if __name__ == "__main__":
    main()
