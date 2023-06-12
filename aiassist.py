import httpx
import re
import asyncio


async def get_value(prompt):
    ans = ""
    url = "http://aiassist.art/api/chat-process"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Host": "aiassist.art",
        "Origin": "http://aiassist.art",
        "Referer": "http://aiassist.art/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    }

    data = {
        "prompt": prompt,
        "options": {},
        "systemMessage": "You are ChatGPT, a large language model trained by OpenAI. Follow the user's instructions carefully. Respond using markdown.",
        "temperature": 0.8,
        "top_p": 1,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=data)

    # Regular expression pattern to search for the specified substring
    pattern = r'"text":"(.*?)","detail":'
    # Perform the regular expression search
    result = re.findall(pattern, resp.text)

    # Extract and print the desired substring
    if result:
        ans = result[-1]
    print(ans)
    return ans
