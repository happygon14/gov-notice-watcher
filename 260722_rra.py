# [준비] (import / 환경변수 / session생성)
# 1-1. 라이브러리(도구)

  # 1) 기본 내장 라이브러리
import os                          # 운영체제(OS)기능 접근용 (파일존재확인, 환경변수읽기, 파일명처리 등)
import smtplib                     # 이메일 전송 (SMTP서버로 메일보내기)
import re                          # 문자패턴찾기 (게시글 제목 분석시)
import zipfile
import json

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
from PIL import Image, ImageDraw, ImageFont
import textwrap
from urllib.parse import unquote

  # 4) 이메일 MIME계열
from email.mime.text import MIMEText            # 메일본문만들기
from email.mime.multipart import MIMEMultipart  # 본문+이미지+첨부파일 합체 
from email.mime.base import MIMEBase            # 엑셀/이미지 첨부
from email import encoders                      # 첨부파일 메일용 변환
from email.mime.image import MIMEImage
from email.header import Header

# 1-2. 환경변수 
  # 1) 사이트 주소 (크롤링 대상 웹사이트)
LIST_URL = "https://www.rra.go.kr/ko/notice/atnList.do"    # 국립전파연구원 행정예고 목록페이지

  # 2) 이메일 환경변수 (Github Secret에 저장한 내용 불러오기)
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

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

   # 4) 맑은고딕 폰트추가
FONT_TITLE = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
FONT_BODY = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"




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
            
        tds = row.find_all("td")
    
        date_text = ""
    
        if len(tds) >= 3:
            date_text = tds[2].get_text(strip=True)
      
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
            "link": detail_url,
            "date": date_text
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




def download_files(files):

    os.makedirs(
        "downloads",
        exist_ok=True
    )

    saved_files = []

    for f in files:

        file_name = f["name"]

        save_path = os.path.join(
            "downloads",
            file_name
        )

        print("다운로드 :", file_name)

        res = session.get(
            f["url"],
            timeout=(10, 60),
            verify=False
        )

        with open(
            save_path,
            "wb"
        ) as fp:

            fp.write(res.content)

        saved_files.append(
            save_path
        )

        print(
            "저장완료 :",
            save_path
        )

    return saved_files


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
        "국립전파연구원 행정예고 분석",
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

    msg["Subject"] = f"📢 신규 행정예고 공고 - {title}"
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


    saved_files = download_files(files)
    
    print()
    print("다운로드 결과")
    
    for f in saved_files:
        print(f)

    print("=" * 60)
    print("문서 추출 시작")
    print("=" * 60)

    document_text = ""
  
    for file_path in saved_files:
    
        if file_path.lower().endswith(".hwpx"):
    
            document_text = extract_hwpx_text(
                file_path
            )
    
            print(
                document_text[:3000]
            )
    
            break
          
    print("=" * 60)
    print("AI 분석 시작")
    print("=" * 60)
    
    ai_result = analyze_with_ai(
        document_text
    )
    
    summary, impact, review, conclusion = parse_ai_result(
        ai_result
    )
    
    card_file = create_card_news(
        info.get("제목",""),
        summary,
        impact,
        review,
        conclusion,
        notice[0].get("date",""),
        info.get("담당부서",""),
        info.get("연락처","")
    )
    
    print("카드뉴스 생성:", card_file)

    send_email(
        info.get("제목",""),
        saved_files,
        "",
        "",
        "",
        "",
        notices[0]["link"]
    )
    
    print("메일 발송 완료")

  
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
