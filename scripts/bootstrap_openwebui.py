import json
import mimetypes
import os
import sys
import time
import uuid
import urllib.request
import urllib.parse
import urllib.error


BASE_URL = os.getenv("OPENWEBUI_URL", "http://open-webui:8080").rstrip("/")
ADMIN_EMAIL = os.getenv("WEBUI_ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("WEBUI_ADMIN_PASSWORD")


def log(message):
    print(f"[bootstrap] {message}", flush=True)


def request_json(method, url, data=None, token=None, headers=None, timeout=15):
    req_headers = headers.copy() if headers else {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="ignore")
        return {"_error": err.code, "_body": raw}


def wait_for_health():
    log("Waiting for Open WebUI...")
    url = f"{BASE_URL}/health"
    for _ in range(120):
        try:
            with urllib.request.urlopen(url, timeout=3):
                log("Open WebUI is up.")
                return True
        except Exception:
            time.sleep(2)
    return False


def encode_multipart(fields, files):
    boundary = f"----bootstrap-{uuid.uuid4().hex}"
    lines = []
    for name, value in fields.items():
        lines.append(f"--{boundary}")
        lines.append(f'Content-Disposition: form-data; name="{name}"')
        lines.append("")
        lines.append(str(value))

    for name, filename, content, content_type in files:
        lines.append(f"--{boundary}")
        lines.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
        )
        lines.append(f"Content-Type: {content_type}")
        lines.append("")
        lines.append(content)

    lines.append(f"--{boundary}--")
    body = b""
    for line in lines:
        if isinstance(line, bytes):
            body += line + b"\r\n"
        else:
            body += line.encode("utf-8") + b"\r\n"

    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def upload_file(path, token):
    filename = os.path.basename(path)
    with open(path, "rb") as file_handle:
        content = file_handle.read()

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    body, content_type = encode_multipart({}, [("file", filename, content, content_type)])
    headers = {"Content-Type": content_type, "Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/api/v1/files/?process=true&process_in_background=true"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="ignore")
        return {"_error": err.code, "_body": raw}


def wait_for_file(file_id, token):
    for _ in range(120):
        status = request_json(
            "GET",
            f"{BASE_URL}/api/v1/files/{file_id}/process/status",
            token=token,
        )
        if status.get("status") == "completed":
            return True
        if status.get("status") == "failed":
            log(f"File processing failed: {status}")
            return False
        time.sleep(2)
    return False


def find_knowledge_id(name, token):
    query = urllib.parse.quote(name)
    resp = request_json(
        "GET", f"{BASE_URL}/api/v1/knowledge/search?query={query}", token=token
    )
    for item in resp.get("items", []):
        if item.get("name") == name:
            return item.get("id")
    return None


def knowledge_has_file(knowledge_id, filename, token):
    query = urllib.parse.quote(filename)
    resp = request_json(
        "GET",
        f"{BASE_URL}/api/v1/knowledge/{knowledge_id}/files?query={query}",
        token=token,
    )
    for item in resp.get("items", []):
        if item.get("filename") == filename:
            return True
    return False


def main():
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        log("WEBUI_ADMIN_EMAIL/PASSWORD not set, skipping.")
        return 0

    if not wait_for_health():
        log("Open WebUI did not become ready.")
        return 1

    auth = request_json(
        "POST",
        f"{BASE_URL}/api/v1/auths/signin",
        data={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    token = auth.get("token")
    if not token:
        log(f"Auth failed: {auth}")
        return 1

    log("Seeding default models and suggestions...")
    request_json(
        "POST",
        f"{BASE_URL}/api/v1/configs/models",
        token=token,
        data={
            "DEFAULT_MODELS": "qwen2.5:14b-instruct",
            "DEFAULT_PINNED_MODELS": "qwen2.5:14b-instruct",
            "MODEL_ORDER_LIST": [],
        },
    )
    request_json(
        "POST",
        f"{BASE_URL}/api/v1/configs/suggestions",
        token=token,
        data={
            "suggestions": [
                {"title": ["Setup coach"], "content": "/setup_coach"},
                {"title": ["Warm-up"], "content": "/warmup"},
                {"title": ["Roleplay"], "content": "/roleplay"},
                {"title": ["Pronounce"], "content": "/pronounce"},
                {"title": ["Shadowing"], "content": "/shadow"},
                {"title": ["Debrief"], "content": "/debrief"},
            ]
        },
    )

    log("Seeding prompts...")
    prompts = [
        {
            "command": "/setup_coach",
            "title": "Setup coach",
            "content": """Set today’s lesson. Use #english_profile if available.

{{goal | text:placeholder="Goal for today (e.g., small talk, meetings, travel)":required}}
{{accent | select:options=["General American (GA)","British RP","Australian","Just neutral/clear"]:default="General American (GA)"}}
{{strictness | select:options=["gentle","medium","strict"]:default="gentle"}}
{{topic | text:placeholder="Topic (work, hobbies, news, travel, etc.)":required}}

Start with a 60-second warm-up question about the topic. Keep replies voice-friendly (1–3 sentences). End with: “Your turn: …”.""",
        },
        {
            "command": "/warmup",
            "title": "Warm-up",
            "content": """Warm-up me for speaking: ask 3 short questions (one at a time) about:
{{topic | text:placeholder="topic":default="today"}}
Keep your turns very short and end with “Your turn: …”.""",
        },
        {
            "command": "/roleplay",
            "title": "Roleplay",
            "content": """Roleplay with me.

Scenario: {{scenario | select:options=["Coffee shop","Job interview","Team meeting","Airport / travel","Doctor appointment","Dating / casual chat"]:required}}
My role: {{my_role | text:default="me"}}
Your role: {{your_role | text:default="the other person"}}
Difficulty: {{level | select:options=["easy","medium","hard"]:default="medium"}}

Rules:
- 2–3 turns total, then stop and give feedback.
- After each of my turns, correct only the single most important mistake.
End each message with “Your turn: …”.""",
        },
        {
            "command": "/pronounce",
            "title": "Pronunciation drill",
            "content": """Pronunciation drill.

Focus: {{focus | select:options=["TH (think/this)","R (right/very)","L vs R","V vs W","Short vs long vowels","Sentence stress & linking"]:required}}

Do:
1) Give one model sentence (short).
2) Give 1–2 mouth/tongue tips.
3) Give 3 minimal pairs.
Then ask me to repeat the sentence once.
End with “Your turn: …”.""",
        },
        {
            "command": "/shadow",
            "title": "Shadowing",
            "content": """Shadowing exercise.

Accent target: {{accent | select:options=["GA","RP","Neutral"]:default="GA"}}
Length: {{length | select:options=["1 short sentence","2 short sentences","one mini-paragraph (3 sentences)"]:default="1 short sentence"}}

Give me the text and tell me how to stress it (CAPS on stressed words).
Then say: “Repeat after me.” and wait for my repetition.
End with “Your turn: …”.""",
        },
        {
            "command": "/debrief",
            "title": "Debrief",
            "content": """Debrief the session:
- 3 key corrections (grammar/phrasing)
- 3 pronunciation notes
- 5 useful phrases from today
- Homework: 2 minutes (easy) + 5 minutes (hard)
Keep it voice-friendly and concise.
End with “Your turn: choose warmup / roleplay / pronounce next”.""",
        },
    ]
    for prompt in prompts:
        request_json(
            "POST",
            f"{BASE_URL}/api/v1/prompts/create",
            token=token,
            data=prompt,
        )

    log("Seeding knowledge bases...")
    knowledge_items = [
        (
            "english_profile",
            "Stable learner profile and preferences.",
            "/seed/knowledge/english_profile.txt",
        ),
        (
            "error_log",
            "Running list of mistakes and corrections.",
            "/seed/knowledge/error_log.txt",
        ),
    ]

    for name, description, path in knowledge_items:
        knowledge_id = find_knowledge_id(name, token)
        if not knowledge_id:
            created = request_json(
                "POST",
                f"{BASE_URL}/api/v1/knowledge/create",
                token=token,
                data={"name": name, "description": description},
            )
            knowledge_id = created.get("id")

        if not knowledge_id:
            log(f"Failed to create knowledge base: {name}")
            continue

        filename = os.path.basename(path)
        if knowledge_has_file(knowledge_id, filename, token):
            continue

        uploaded = upload_file(path, token)
        file_id = uploaded.get("id")
        if not file_id:
            log(f"File upload failed for {path}: {uploaded}")
            continue

        if not wait_for_file(file_id, token):
            continue

        request_json(
            "POST",
            f"{BASE_URL}/api/v1/knowledge/{knowledge_id}/file/add",
            token=token,
            data={"file_id": file_id},
        )

    log("Bootstrap done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
