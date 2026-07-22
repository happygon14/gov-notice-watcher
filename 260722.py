# [준비] (import / 환경변수 / session생성)
# 1-1. 라이브러리(도구)

  # 1) 기본 내장 라이브러리
import os                          # 운영체제(OS)기능 접근용 (파일존재확인, 환경변수읽기, 파일명처리 등)
import smtplib                     # 이메일 전송 (SMTP서버로 메일보내기)
import re                          # 문자패턴찾기 (게시글 제목 분석시)
import time
import zipfile
from urllib.parse import unquote

  # 2) 웹 크롤링 계열
import requests                     # 웹사이트 접속(GET/POST)
from bs4 import BeautifulSoup       # HTML 분석
import cloudscraper                 # request강화버전 (차단 우회용) (일반 requests 막히는 경우)

  # 3) 접속 안정화
import urllib3                            # SSL경고 숨김
urllib3.disable_warnings()                # SSL경고메시지 숨김
from urllib3.util.retry import Retry      # 실패시 자동 재시도 (서버 일시오류 대응)
from requests.adapters import HTTPAdapter # requests 세션에 재시도 기능 연결

  # 3-1) 카드뉴스형태 만들기
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import textwrap

  # 4) 이메일 MIME계열
from email.mime.text import MIMEText            # 메일본문만들기
from email.mime.multipart import MIMEMultipart  # 본문+이미지+첨부파일 합체 
from email.mime.base import MIMEBase            # 엑셀/이미지 첨부
from email import encoders                      # 첨부파일 메일용 변환
from email.utils import encode_rfc2231
from email.header import Header

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

   # 4) 맑은고딕 폰트추가
FONT_TITLE = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
FONT_BODY = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"


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

def get_latest_notices(limit=3):
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

    notices = []

    for a in links:                                             # 링크 하나씩 검사

        onclick = a.get("onclick","")                           # onclick 내용 가져오기

        if "fn_detail" not in onclick:                              # 상세보기 링크만 선택
            continue
          
        m = re.search(r"\d{5,}", onclick)                   # 숫자 5자리 이상 찾기(공지번호 추출용)

        if not m:
            continue
          
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

        notices.append({
            "id": notice_id,
            "title": title,
            "link": detail_url
        })

        if len(notices) >= limit:
            break
    if not notices :
        raise Exception("공지 못찾음")
    
    return notices                 # 게시글번호, 제목, url 반환

    

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

    # 원본 파일명 추출
    content_disposition = res.headers.get(
        "content-disposition",
        ""
    )
    
    m = re.search(
        r'filename="(.*?)"',
        content_disposition
    )
    
    if m:
        filename = unquote(m.group(1))
    else:
        filename = f"attach.{ext}"
    
    
    with open(filename, "wb") as f:
        f.write(res.content)

    return filename



# AI분석함수


def analyze_with_ai(document_text):

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return "OPENROUTER_API_KEY 없음"

    prompt = f"""
당신은 LG유플러스 NW협력팀 정책담당자이다. 이는 통신,네트워크 산업 전문 정책분석가이자 기업 전략기획 전문가이다.

아래 행정예고 또는 정책 문서를 분석하라.

특히 다음 항목을 중점 검토한다.

- 통신사업자 영향
- 유선/무선 네트워크 영향
- 기술기준 영향
- 규제 변화
- 비용 증가 가능성
- 대응 필요사항
- 아래 4개항목 중 처음 3개항목(핵심 요약, 통신업계 영향도, LG유플러스 검토사항)은 각 3개 항목으로 작성하고 마지막 항목(한줄 결론)은 1개 항목으로 작성하되, 각각의 항목은 60자 이내로 작성
- 처음 3개항목(핵심 요약, 통신업계 영향도, LG유플러스 검토사항)의 각 항목은 반드시 "- "로 시작
- "변화내용 + 영향 또는 검토필요성"형태로 작성

출력 형식:

■ 핵심 요약
- ㅇㅇㅇㅇ
- ㅇㅇㅇㅇ
- ㅇㅇㅇㅇ

■ 통신업계 영향도
- ㅇㅇㅇㅇ
- ㅇㅇㅇㅇ
- ㅇㅇㅇㅇ

■ LG유플러스 검토사항
- ㅇㅇㅇㅇ
- ㅇㅇㅇㅇ
- ㅇㅇㅇㅇ

■ 한줄 결론
ㅇㅇㅇㅇ

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
                "content": "반드시 한국어만 사용한다. 사고과정(reasoning)은 출력하지 말고 최종 결과만 출력한다."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 3000
    }

    try:

        print("OPENROUTER 요청 시작")

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=120
        )

        # =========================
        # 429 재시도 1회
        # =========================
        
        if response.status_code == 429:
        
            retry_after = 10
        
            try:
                err = response.json()
        
                retry_after = int(
                    err["error"]["metadata"]
                       .get("retry_after_seconds", 10)
                )
        
            except:
                pass
        
            print(
                f"429 발생 → {retry_after}초 대기 후 재시도"
            )
        
            time.sleep(retry_after)
        
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
            print("=" * 60)
            print("message 확인")
            print("=" * 60)
            print(result["choices"][0].get("message"))
            print("finish_reason=")
            print(result["choices"][0].get("finish_reason"))  
        
        if (
            "choices" not in result
            or not result["choices"]
        ):
            return """
        ■ 핵심 요약
        AI 응답 없음
        
        ■ 통신업계 영향도
        AI 응답 없음
        
        ■ LG유플러스 검토사항
        AI 응답 없음
        
        ■ 한줄 결론
        AI 응답 없음
        """
        
        content = (
            result["choices"][0]
            .get("message", {})
            .get("content")
        )

        print("=" * 60)
        print("content 확인")
        print("=" * 60)
        print(repr(content))

        print("=" * 60)
        print("finish_reason 확인")
        print("=" * 60)
        
        print(
            result["choices"][0]
            .get("finish_reason")
        )
        
        if not content:
            return """
        ■ 핵심 요약
        AI 응답 없음
        
        ■ 통신업계 영향도
        AI 응답 없음
        
        ■ LG유플러스 검토사항
        AI 응답 없음
        
        ■ 한줄 결론
        AI 응답 없음
        """
        
        return content
        
        if "error" in result:
    
            print("AI 호출 실패")
            print(result["error"])
    
            return """
■ 핵심 요약
AI 분석 실패

■ 통신업계 영향도
AI 분석 실패

■ LG유플러스 검토사항
AI 분석 실패

■ 한줄 결론
AI 분석 실패
"""
    
        return """
■ 핵심 요약
AI 분석 실패

■ 통신업계 영향도
AI 분석 실패

■ LG유플러스 검토사항
AI 분석 실패

■ 한줄 결론
AI 분석 실패
"""
    
    except Exception as e:
    
        print("AI 분석 실패:", e)
    
        return f"""
■ 핵심 요약
AI 분석 실패

■ 통신업계 영향도
AI 분석 실패

■ LG유플러스 검토사항
AI 분석 실패

■ 한줄 결론
{str(e)}
"""


def parse_ai_result(ai_text):

    summary = ""
    impact = ""
    review = ""
    conclusion = ""

    m = re.search(
        r'■ 핵심 요약(.*?)■ 통신업계 영향도',
        ai_text,
        re.S
    )
    if m:
        summary = m.group(1).strip()

    m = re.search(
        r'■ 통신업계 영향도(.*?)■ LG유플러스 검토사항',
        ai_text,
        re.S
    )
    if m:
        impact = m.group(1).strip()

    m = re.search(
        r'■ LG유플러스 검토사항(.*?)■ 한줄 결론',
        ai_text,
        re.S
    )
    if m:
        review = m.group(1).strip()

    m = re.search(
        r'■ 한줄 결론(.*)',
        ai_text,
        re.S
    )
    if m:
        conclusion = m.group(1).strip()

        conclusion = re.sub(
            r'^[-•]\s*',
            '',
            conclusion
        )
      
    return (
        summary,
        impact,
        review,
        conclusion
    )





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

def wrap_text(text, width=35):

    result = []

    for line in text.splitlines():

        if not line.strip():
            result.append("")
            continue

        result.extend(
            textwrap.wrap(
                line,
                width=width
            )
        )

    return "\n".join(result)




#카드뉴스 생성

def create_card_news(title, summary, impact, review, conclusion, write_date, dept, manager):

    print("=" * 60)
    print("카드뉴스 입력값 확인")
    print("=" * 60)
    print(summary[:500])
  
    WIDTH = 1080
    HEIGHT = 2200

    img = Image.new(
        "RGB",
        (WIDTH, HEIGHT),
        "#FFFFFF"
    )

    draw = ImageDraw.Draw(img)

    title_font = ImageFont.truetype(
        FONT_TITLE,
        46
    )

    sub_font = ImageFont.truetype(
        FONT_TITLE,
        32
    )

    body_font = ImageFont.truetype(
        FONT_BODY,
        24
    )

    small_font = ImageFont.truetype(
        FONT_BODY,
        22
    )

    small_bold_font = ImageFont.truetype(
        FONT_TITLE,
        22
    )  

    # ====================
    # 헤더
    # ====================

    title_wrapped = wrap_text(title, 28)
    
    title_lines = title_wrapped.count("\n") + 1
    
    header_height = 90 + (title_lines * 55)
    
    draw.rectangle(
        (0, 0, WIDTH, header_height),
        fill="#C8102E"
    )
    
    draw.text(
        (40, 20),
        "과기부 입법행정예고 분석",
        fill="white",
        font=sub_font
    )
    
    draw.text(
        (40, 65),
        title_wrapped,
        fill="white",
        font=title_font
    )
    
    # ====================
    # 메타정보 영역
    # ====================
    
    meta_y = header_height + 20
    
    draw.rounded_rectangle(
        (
            40,
            meta_y,
            1040,
            meta_y + 80
        ),
        radius=20,
        fill="#F2F4F7"
    )
    
    draw.text(
        (180, meta_y + 40),
        f"작성일 : {write_date}",
        fill="#333333",
        font=small_bold_font,
        anchor="mm"
    )
    
    draw.text(
        (540, meta_y + 40),
        f"부서 : {dept}",
        fill="#333333",
        font=small_bold_font,
        anchor="mm"
    )
    
    draw.text(
        (900, meta_y + 40),
        f"담당자 : {manager}",
        fill="#333333",
        font=small_bold_font,
        anchor="mm"
    )
    
    y = meta_y + 110


    def draw_box(box_title, text, y):

        text = re.sub(
            r'^\s*[-•]\s*',
            '• ',
            text,
            flags=re.M
        )
        
        text = text.strip()

        wrapped = wrap_text(text, 42)
    
        line_count = wrapped.count("\n") + 1
    
        box_height = 90 + (line_count * 30)
    
        draw.rounded_rectangle(
            (40, y, 1040, y + box_height),
            radius=25,
            fill="#F5F7FA"
        )

        # 제목
        draw.text(
            (70, y + 20),
            box_title,
            fill="#003366",
            font=sub_font
        )

        # 본문
        draw.text(
            (70, y + 65),
            wrapped,
            fill="black",
            font=body_font,
            spacing=5
        )
    
        return y + box_height + 20


    y = draw_box(
        "▶ 핵심요약",
        summary,
        y
    )

    y = draw_box(
        "▶ 통신업계 영향",
        impact,
        y
    )

    y = draw_box(
        "▶ LG유플러스 검토사항",
        review,
        y
    )

    conclusion_text = wrap_text(
        conclusion,
        45
    )
    
    line_count = conclusion_text.count("\n") + 1

    conclusion_height = 80 + (line_count * 35)
  
    draw.rounded_rectangle(
        (40, y, 1040, y + conclusion_height),
        radius=25,
        fill="#E8F4FF"
    )

    draw.text(
        (70, y + 20),
        "▶ 한줄 결론",
        fill="#003366",
        font=sub_font
    )

    draw.text(
        (540, y + 95),
        conclusion_text,
        fill="black",
        font=body_font,
        anchor="mm"
    )


    filename = "card_news.png"

    img = img.crop(
        (
            0,
            0,
            WIDTH,
            y + conclusion_height + 80
        )
    )
    
    img.save(filename)
    
    return filename




# =========================
# 메일 보내기 (첨부 포함)
# =========================

def send_email(title, filepath, meta, deadline, reason, main_points, link, ai_result=""):
    
    msg = MIMEMultipart()

    msg["Subject"] = f"📢 신규 입법행정예고 공고 - {title}"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = TO_EMAIL

    body = f"""

    📎 Link :
    {link}
    """

    msg.attach(MIMEText(body,"plain","utf-8"))
    
    attachments = []
    
    if filepath:
    
        if isinstance(filepath, str):
            filepath = [filepath]
    
        attachments.extend(filepath)
    
    if os.path.exists("card_news.png"):
        attachments.append("card_news.png")
    
    for fp in attachments:
    
        with open(fp,"rb") as f:
            part = MIMEBase("application","octet-stream")
            part.set_payload(f.read())
    
        encoders.encode_base64(part)
    
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=Header(
                os.path.basename(fp),
                "utf-8"
            ).encode()
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

        notices = get_latest_notices(limit=3)
        latest_id = notices[0]["id"]

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

    new_notices = []

    for notice in notices:
    
        if notice["id"] == old_id:
            break
    
        new_notices.append(notice)
    
    new_notices = new_notices[:3]
    
    new_notices.reverse()
  
    if latest_id != old_id:
    
        print("새 공지 발견")
        print("발송 대상:", len(new_notices))
    
        for notice in new_notices:
    
            title = notice["title"]
            link = notice["link"]
    
            print("=" * 60)
            print("처리중:", title)
            print("=" * 60)
    
            attachments = get_attachment_info(link)
    
            filepaths = []
    
            for file_id, file_sn, ext in attachments:
    
                if ext.lower() != "hwpx":
                    continue
            
                filepath = download_file(
                    file_id,
                    file_sn,
                    ext,
                    link
                )
            
                filepaths.append(filepath)
        
            ai_result = ""
    
            all_text = ""
            
            for fp in filepaths:
            
                if fp.lower().endswith(".hwpx"):
            
                    print("HWPX 읽기:", fp)
            
                    document_text = extract_hwpx_text(fp)
            
                    print("문서길이:", len(document_text))
            
                    all_text += document_text
                    all_text += "\n\n"
    
    
    
            if all_text:
      
                print("전체 문서길이:", len(all_text))
              
                ai_result = analyze_with_ai(
                    all_text[:8000]
                )
              
                print("AI결과 길이:", len(ai_result))
              
        
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
            
                if "예고" in txt and len(txt) > 20:
                    title = txt
                    print("제목 추출 성공:", title)
                    break
    
          
            meta = {}
    
            for dl in soup.select(".meta dl.tit_con"):
                k = dl.select_one("dt").get_text(strip=True)
                v = dl.select_one("dd").get_text(strip=True)
    
                meta[k] = v
            from datetime import datetime
    
            raw_date = meta.get("작성일", "")
            
            try:
            
                dt = datetime.strptime(
                    raw_date,
                    "%b %d, %Y"
                )
            
                display_date = (
                    f"{str(dt.year)[2:]}.{dt.month}.{dt.day}"
                )
            
            except:
            
                display_date = raw_date
    
    
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
    
            summary, impact, review, conclusion = parse_ai_result(ai_result)
    
            print("summary=", summary)
            print("impact=", impact)
            print("review=", review)
            print("conclusion=", conclusion)
            
            card_file = create_card_news(
                title,
                summary,
                impact,
                review,
                conclusion,
                display_date,
                meta.get("부서",""),
                meta.get("담당자","")
            )
    
          
    
            send_email(title, filepaths, meta, deadline, reason, main_points, link, ai_result)



        with open("last_id.txt", "w") as f:
            f.write(latest_id)

    else:

        print("변경 없음")


if __name__ == "__main__":
    main()
