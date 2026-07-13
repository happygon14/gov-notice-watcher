import requests
import os

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]

url = "https://openrouter.ai/api/v1/chat/completions"

prompt = """
대한민국 기준으로 아래 지수 전망 작성

지수:
소비자물가지수
생산자물가지수
부동산지수
이동통신지수

조건:
- 반드시 한국어만 사용
- 중국어, 영어, 일본어 사용 금지
- 존댓말 사용
- 각 항목 단기 2~3문장
- 각 항목 중장기 2~3문장
- 현재 상황과 전망 이유 포함
- 표 형식 외 다른 설명 금지

형식:
지수|단기(1년)|중장기(3~5년)
소비자물가지수|내용|내용
생산자물가지수|내용|내용
부동산지수|내용|내용
이동통신지수|내용|내용
"""

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

data = {
    "model": "openai/gpt-oss-120b:free",
    "messages": [
        {
            "role": "system",
            "content": "반드시 한국어만 사용한다. 중국어, 영어, 일본어를 출력하지 않는다."
        },
        {
            "role": "user",
            "content": prompt
        }
    ],
    "temperature": 0.3,
    "max_tokens": 1500
}

response = requests.post(
    url,
    headers=headers,
    json=data,
    timeout=120
)

print("STATUS:", response.status_code)

try:
    result = response.json()

    if "choices" in result:
        print(result["choices"][0]["message"]["content"])
    else:
        print(result)

except Exception as e:
    print("응답 파싱 실패:", e)
    print(response.text)
