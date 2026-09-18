#!/usr/bin/env python3
import argparse
import http.client
import json
import mimetypes
import os
import sys
import time
import uuid
import webbrowser
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


VERSION = "0.7.1"
DEFAULT_API_BASE = "https://wooboo.ycszai.com"
DEFAULT_H5_BASE = "https://wooboo.ycszai.com"
CONFIG_DIR = Path.home() / ".wooboo-ai"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
CONFIG_PATH = CONFIG_DIR / "config.json"


def parse_args():
    parser = argparse.ArgumentParser(description="Wooboo AI system media generation CLI.")
    parser.add_argument("--version", action="version", version=f"wooboo {VERSION}")
    parser.add_argument("--api-base", default="", help="API base URL. Overrides WOOBOO_API_BASE and config.")
    parser.add_argument("--h5-base", default="", help="H5 web base URL. Overrides WOOBOO_H5_BASE and config.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login = subparsers.add_parser("login")
    login_sub = login.add_subparsers(dest="login_command", required=True)
    login_web = login_sub.add_parser("web")
    login_web.add_argument("--open", action="store_true", help="Open the authorization URL in the default browser.")
    login_web.add_argument("--client-name", default="Wooboo AI CLI")
    login_web.add_argument("--poll-interval", type=float, default=2.0)

    subparsers.add_parser("logout")

    account_parser = subparsers.add_parser("account")
    account_sub = account_parser.add_subparsers(dest="account_command")
    account_sub.add_parser("show")
    account_points = account_sub.add_parser("points")
    account_points.add_argument("--page", type=int, default=1)
    account_points.add_argument("--page-size", type=int, default=20)
    account_password = account_sub.add_parser("change-password")
    account_password.add_argument("--old-password", required=True)
    account_password.add_argument("--new-password", required=True)
    account_invitation = account_sub.add_parser("bind-invitation")
    account_invitation.add_argument("code")
    account_avatar = account_sub.add_parser("avatar")
    account_avatar.add_argument("--image", required=True)
    account_redeem = account_sub.add_parser("redeem")
    account_redeem.add_argument("card_code")

    config = subparsers.add_parser("config")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("list")
    config_get = config_sub.add_parser("get")
    config_get.add_argument("key", choices=["api-base", "h5-base", "output-dir"])
    config_set = config_sub.add_parser("set")
    config_set.add_argument("key", choices=["api-base", "h5-base", "output-dir"])
    config_set.add_argument("value")
    config_unset = config_sub.add_parser("unset")
    config_unset.add_argument("key", choices=["api-base", "h5-base", "output-dir"])

    content = subparsers.add_parser("content")
    content_sub = content.add_subparsers(dest="content_command", required=True)
    content_sub.add_parser("bootstrap")
    content_sub.add_parser("hot-creations")
    content_legal = content_sub.add_parser("legal")
    content_legal.add_argument("document_type")

    image = subparsers.add_parser("image")
    image_sub = image.add_subparsers(dest="image_command", required=True)
    image_models = image_sub.add_parser("models")
    image_models.add_argument("--scene", default="图片生成")
    image_sub.add_parser("history")
    generate = image_sub.add_parser("generate")
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--scene", default="图片生成")
    generate.add_argument("--aspect-ratio", default="")
    generate.add_argument("--quality", default="")
    generate.add_argument("--variant-key", default="")
    generate.add_argument("--model-config-id", default="")
    generate.add_argument("--model", default="", help="Model display name or provider model name.")
    generate.add_argument("--reference-image", action="append", default=[])
    generate.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    generate.add_argument("--poll-interval", type=float, default=3.0)
    generate.add_argument("--timeout", type=int, default=600)
    generate.add_argument("--output-dir", default="")
    image_status = image_sub.add_parser("status")
    image_status.add_argument("id")
    image_download = image_sub.add_parser("download")
    image_download.add_argument("id")
    image_download.add_argument("--output-dir", default="")

    video = subparsers.add_parser("video")
    video_sub = video.add_subparsers(dest="video_command", required=True)
    video_sub.add_parser("models")
    video_optimize = video_sub.add_parser("optimize-prompt")
    video_optimize.add_argument("--prompt", required=True)
    video_optimize.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "first_last_frame", "r2v", "video_extend", "video_edit"])
    video_optimize.add_argument("--series", default="")
    video_optimize.add_argument("--model", default="")
    video_optimize.add_argument("--model-config-id", default="")
    video_optimize.add_argument("--aspect-ratio", default="")
    video_optimize.add_argument("--max-duration-seconds", type=int, default=0)
    video_optimize.add_argument("--has-video-reference", action=argparse.BooleanOptionalAction, default=False)
    video_optimize.add_argument("--material", action="append", default=[], help="Material as kind:role, for example image:reference or audio:voice.")
    video_generate_parser = video_sub.add_parser("generate")
    video_generate_parser.add_argument("--series", default="", help="System video series name returned by 'wooboo video models'.")
    video_generate_parser.add_argument("--model", default="", help="System model display name.")
    video_generate_parser.add_argument("--prompt", required=True)
    video_generate_parser.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "first_last_frame", "r2v", "video_extend", "video_edit"])
    video_generate_parser.add_argument("--aspect-ratio", default="")
    video_generate_parser.add_argument("--duration-seconds", type=int, default=5)
    video_generate_parser.add_argument("--resolution", default="")
    video_generate_parser.add_argument("--variant-key", default="")
    video_generate_parser.add_argument("--model-config-id", default="")
    video_generate_parser.add_argument("--first-frame", default="")
    video_generate_parser.add_argument("--last-frame", default="")
    video_generate_parser.add_argument("--extend-video", default="")
    video_generate_parser.add_argument("--edit-video", default="")
    video_generate_parser.add_argument("--reference-image", action="append", default=[])
    video_generate_parser.add_argument("--reference-video", action="append", default=[])
    video_generate_parser.add_argument("--reference-audio", action="append", default=[])
    video_generate_parser.add_argument("--reference-file", default="")
    video_generate_parser.add_argument("--reference-link", default="")
    video_generate_parser.add_argument("--negative-prompt", default="")
    video_generate_parser.add_argument("--audio", action=argparse.BooleanOptionalAction, default=None)
    video_generate_parser.add_argument("--prompt-extend", action=argparse.BooleanOptionalAction, default=None)
    video_generate_parser.add_argument("--watermark", action=argparse.BooleanOptionalAction, default=None)
    video_generate_parser.add_argument("--camera-fixed", action=argparse.BooleanOptionalAction, default=False)
    video_generate_parser.add_argument("--trim-long-media", action=argparse.BooleanOptionalAction, default=False)
    video_generate_parser.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    video_generate_parser.add_argument("--poll-interval", type=float, default=5.0)
    video_generate_parser.add_argument("--timeout", type=int, default=1800)
    video_generate_parser.add_argument("--output-dir", default="")
    video_status = video_sub.add_parser("status")
    video_status.add_argument("id")
    video_download = video_sub.add_parser("download")
    video_download.add_argument("id")
    video_download.add_argument("--output-dir", default="")

    video_package = subparsers.add_parser("video-package")
    video_package_sub = video_package.add_subparsers(dest="video_package_command", required=True)
    video_package_sub.add_parser("bootstrap")
    video_package_templates = video_package_sub.add_parser("templates")
    video_package_templates.add_argument("--offset", type=int, default=0)
    video_package_templates.add_argument("--limit", type=int, default=30)
    video_package_music = video_package_sub.add_parser("music")
    video_package_music.add_argument("--offset", type=int, default=0)
    video_package_music.add_argument("--limit", type=int, default=30)
    video_package_sub.add_parser("list")
    video_package_generate = video_package_sub.add_parser("generate")
    video_package_generate.add_argument("--video", required=True)
    video_package_generate.add_argument("--title", required=True)
    video_package_generate.add_argument("--duration-seconds", type=float, required=True)
    video_package_generate.add_argument("--style-id", default="")
    video_package_generate.add_argument("--music-id", default="")
    video_package_generate.add_argument("--identity-name", default="")
    video_package_generate.add_argument("--identity-desc", default="")
    video_package_generate.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    video_package_generate.add_argument("--poll-interval", type=float, default=8.0)
    video_package_generate.add_argument("--timeout", type=int, default=3600)
    video_package_generate.add_argument("--output-dir", default="")
    video_package_status = video_package_sub.add_parser("status")
    video_package_status.add_argument("id")
    video_package_download = video_package_sub.add_parser("download")
    video_package_download.add_argument("id")
    video_package_download.add_argument("--output-dir", default="")
    video_package_delete = video_package_sub.add_parser("delete")
    video_package_delete.add_argument("id")

    voice = subparsers.add_parser("voice")
    voice_sub = voice.add_subparsers(dest="voice_command", required=True)
    voice_sub.add_parser("list")
    voice_clone = voice_sub.add_parser("clone")
    voice_clone.add_argument("--audio", required=True)
    voice_clone.add_argument("--name", "--prefix", dest="name", default="我的音色")
    voice_clone.add_argument("--sex", type=int, default=0, help=argparse.SUPPRESS)
    voice_clone.add_argument("--language", default="")
    voice_clone.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    voice_clone.add_argument("--poll-interval", type=float, default=5.0)
    voice_clone.add_argument("--timeout", type=int, default=1800)
    voice_delete = voice_sub.add_parser("delete")
    voice_delete.add_argument("id")
    voice_status = voice_sub.add_parser("status")
    voice_status.add_argument("id")

    avatar = subparsers.add_parser("avatar")
    avatar_sub = avatar.add_subparsers(dest="avatar_command", required=True)
    avatar_sub.add_parser("list")
    avatar_create = avatar_sub.add_parser("create")
    avatar_create.add_argument("--video", required=True)
    avatar_create.add_argument("--title", default="我的形象")
    avatar_create.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    avatar_create.add_argument("--poll-interval", type=float, default=8.0)
    avatar_create.add_argument("--timeout", type=int, default=7200)
    avatar_delete = avatar_sub.add_parser("delete")
    avatar_delete.add_argument("id")
    avatar_status = avatar_sub.add_parser("status")
    avatar_status.add_argument("id")
    avatar_accept = avatar_sub.add_parser("accept-voice-offer")
    avatar_accept.add_argument("id")
    avatar_dismiss = avatar_sub.add_parser("dismiss-voice-offer")
    avatar_dismiss.add_argument("id")

    human = subparsers.add_parser("digital-human")
    human_sub = human.add_subparsers(dest="human_command", required=True)
    human_generate = human_sub.add_parser("generate")
    human_generate.add_argument("--avatar-record-id", required=True)
    human_generate.add_argument("--drive-mode", choices=["text", "audio"], default="text")
    human_generate.add_argument("--text", default="")
    human_generate.add_argument("--voice-record-id", default="")
    human_generate.add_argument("--audio", default="")
    human_generate.add_argument("--title", default="")
    human_generate.add_argument("--subtitle", action=argparse.BooleanOptionalAction, default=None)
    human_generate.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    human_generate.add_argument("--poll-interval", type=float, default=5.0)
    human_generate.add_argument("--timeout", type=int, default=7200)
    human_generate.add_argument("--output-dir", default="")
    human_status = human_sub.add_parser("status")
    human_status.add_argument("id")
    human_download = human_sub.add_parser("download")
    human_download.add_argument("id")
    human_download.add_argument("--output-dir", default="")

    history = subparsers.add_parser("history")
    history_sub = history.add_subparsers(dest="history_command", required=True)
    history_sub.add_parser("list")
    history_delete = history_sub.add_parser("delete")
    history_delete.add_argument("id")
    history_delete.add_argument("--type", default="")
    history_download = history_sub.add_parser("download")
    history_download.add_argument("id")
    history_download.add_argument("--output-dir", default="")

    favorite = subparsers.add_parser("favorite")
    favorite_sub = favorite.add_subparsers(dest="favorite_command", required=True)
    favorite_sub.add_parser("list")
    favorite_add = favorite_sub.add_parser("add")
    favorite_add.add_argument("--kind", required=True, choices=["image", "video"])
    favorite_add.add_argument("--record-id", required=True)
    favorite_remove = favorite_sub.add_parser("remove")
    favorite_remove.add_argument("id")

    viral = subparsers.add_parser("viral-video")
    viral_sub = viral.add_subparsers(dest="viral_command", required=True)
    viral_analyze = viral_sub.add_parser("analyze")
    viral_analyze.add_argument("--url", required=True)
    viral_analyze.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    viral_analyze.add_argument("--poll-interval", type=float, default=5.0)
    viral_analyze.add_argument("--timeout", type=int, default=900)
    viral_sub.add_parser("latest")
    viral_status = viral_sub.add_parser("status")
    viral_status.add_argument("id")

    ip_clone = subparsers.add_parser("ip-clone")
    ip_clone_sub = ip_clone.add_subparsers(dest="ip_clone_command", required=True)
    ip_clone_sub.add_parser("list")
    ip_clone_create = ip_clone_sub.add_parser("create")
    ip_clone_create.add_argument("--name", required=True)
    ip_clone_create.add_argument("--company", required=True)
    ip_clone_create.add_argument("--business", required=True)
    ip_clone_update = ip_clone_sub.add_parser("update")
    ip_clone_update.add_argument("id")
    ip_clone_update.add_argument("--name", default="")
    ip_clone_update.add_argument("--company", default="")
    ip_clone_update.add_argument("--business", default="")
    ip_clone_delete = ip_clone_sub.add_parser("delete")
    ip_clone_delete.add_argument("id")
    ip_clone_upload = ip_clone_sub.add_parser("upload")
    ip_clone_upload.add_argument("id")
    ip_clone_upload.add_argument("--type", required=True, choices=["photo", "video", "voice"])
    ip_clone_upload.add_argument("--file", required=True)
    ip_clone_parse = ip_clone_sub.add_parser("parse-file")
    ip_clone_parse.add_argument("--file", required=True)

    agent = subparsers.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    agent_bootstrap = agent_sub.add_parser("bootstrap")
    agent_bootstrap.add_argument("code")
    agent_conversations = agent_sub.add_parser("conversations")
    agent_conversations.add_argument("code")
    agent_messages = agent_sub.add_parser("messages")
    agent_messages.add_argument("conversation_id")
    agent_clear = agent_sub.add_parser("clear")
    agent_clear.add_argument("code")
    agent_chat = agent_sub.add_parser("chat")
    agent_chat.add_argument("code")
    agent_chat.add_argument("--text", default="")
    agent_chat.add_argument("--conversation-id", default="")
    agent_chat.add_argument("--ip-clone-id", default="")
    agent_chat.add_argument("--file", action="append", default=[])
    agent_chat.add_argument("--timeout", type=int, default=900)
    agent_cancel = agent_sub.add_parser("cancel")
    agent_cancel.add_argument("code")
    agent_cancel.add_argument("job_id")

    return parser.parse_args()


def normalize_base(url):
    return url.rstrip("/")


def resolve_api_base(args):
    return normalize_base(
        args.api_base
        or os.environ.get("WOOBOO_API_BASE", "")
        or str(load_config().get("api_base", "") or "")
        or DEFAULT_API_BASE
    )


def resolve_h5_base(args):
    return normalize_base(
        args.h5_base
        or os.environ.get("WOOBOO_H5_BASE", "")
        or str(load_config().get("h5_base", "") or "")
        or DEFAULT_H5_BASE
    )


def request_json(method, url, payload=None, token="", timeout=30, extra_headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers.update({str(key): str(value) for key, value in (extra_headers or {}).items()})
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
            message = payload.get("message") or payload.get("error", {}).get("message") or body
        except json.JSONDecodeError:
            message = body
        raise RuntimeError(f"HTTP {error.code}: {message}") from error


def request_ndjson(method, url, payload, token, timeout=900):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Agent-Stream": "ndjson",
        },
        method=method,
    )
    events = []
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                event = json.loads(line)
                events.append(event)
                if event.get("type") == "error":
                    raise RuntimeError(str(event.get("message") or "Agent request failed"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(body)
            message = error_payload.get("message") or error_payload.get("error", {}).get("message") or body
        except json.JSONDecodeError:
            message = body
        raise RuntimeError(f"HTTP {error.code}: {message}") from error
    return events


def resolve_local_file(path, label="File"):
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise RuntimeError(f"{label} does not exist: {file_path}")
    return file_path


def guess_content_type(file_path, fallback="application/octet-stream"):
    return mimetypes.guess_type(str(file_path))[0] or fallback


def put_file_to_signed_url(url, file_path, headers=None, timeout=1800):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise RuntimeError("Invalid signed upload URL")
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_class(parsed.hostname, parsed.port, timeout=timeout)
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    request_headers = {str(name): str(value) for name, value in (headers or {}).items()}
    request_headers["Content-Length"] = str(file_path.stat().st_size)
    try:
        connection.putrequest("PUT", target)
        for name, value in request_headers.items():
            connection.putheader(name, value)
        connection.endheaders()
        with file_path.open("rb") as file_handle:
            while True:
                chunk = file_handle.read(1024 * 1024)
                if not chunk:
                    break
                connection.send(chunk)
        response = connection.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Signed upload failed: HTTP {response.status}: {body}")
    finally:
        connection.close()


def delete_media_upload(api_base, token, upload_id):
    try:
        request_json(
            "DELETE",
            f"{api_base}/api/h5/media-uploads/{urllib.parse.quote(upload_id)}",
            token=token,
        )
    except Exception:
        pass


def direct_upload_file(api_base, token, path, purpose, field_name, fallback_content_type="application/octet-stream"):
    file_path = resolve_local_file(path)
    content_type = guess_content_type(file_path, fallback_content_type)
    _, initialized = request_json(
        "POST",
        f"{api_base}/api/h5/media-uploads/init",
        {
            "purpose": purpose,
            "fieldName": field_name,
            "fileName": file_path.name,
            "mimeType": content_type,
            "sizeBytes": file_path.stat().st_size,
        },
        token=token,
    )
    intent = initialized.get("upload") or {}
    upload_id = str(intent.get("uploadId") or "")
    upload_url = str(intent.get("uploadUrl") or "")
    if not upload_id or not upload_url:
        raise RuntimeError("Media upload initialization returned an invalid response")
    try:
        put_file_to_signed_url(upload_url, file_path, intent.get("headers") or {})
        request_json(
            "POST",
            f"{api_base}/api/h5/media-uploads/{urllib.parse.quote(upload_id)}/complete",
            {},
            token=token,
        )
        return {"uploadId": upload_id, "fieldName": field_name, "path": str(file_path), "mimeType": content_type}
    except Exception:
        delete_media_upload(api_base, token, upload_id)
        raise


def encode_multipart(fields, files):
    boundary = f"----wooboo-{uuid.uuid4().hex}"
    chunks = []
    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for name, path in files:
        file_path = resolve_local_file(path)
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{file_path.name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        chunks.append(file_path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def request_multipart(url, fields, files, token, timeout=60):
    data, content_type = encode_multipart(fields, files)
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
            message = payload.get("message") or payload.get("error", {}).get("message") or body
        except json.JSONDecodeError:
            message = body
        raise RuntimeError(f"HTTP {error.code}: {message}") from error


def save_credentials(api_base, h5_base, token, user):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(
        json.dumps(
            {
                "api_base": api_base,
                "h5_base": h5_base,
                "token": token,
                "user": user,
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if os.name != "nt":
        CREDENTIALS_PATH.chmod(0o600)


def load_credentials():
    if not CREDENTIALS_PATH.is_file():
        raise RuntimeError("Not logged in. Run: wooboo login web")
    return json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))


def load_config():
    if not CONFIG_PATH.is_file():
        return {}
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_config_key(key):
    if key == "api-base":
        return "api_base"
    if key == "h5-base":
        return "h5_base"
    if key == "output-dir":
        return "output_dir"
    raise RuntimeError(f"Unsupported config key: {key}")


def login_web(args):
    api_base = resolve_api_base(args)
    h5_base = resolve_h5_base(args)
    _, grant = request_json("POST", f"{api_base}/api/cli/auth/grants", {"clientName": args.client_name})
    code = grant["code"]
    authorize_url = f"{h5_base}/cli/authorize?code={urllib.parse.quote(code)}"
    print(f"Open this URL to authorize:\n{authorize_url}", flush=True)
    if args.open:
        webbrowser.open(authorize_url)
    while True:
        status, payload = request_json("POST", f"{api_base}/api/cli/auth/grants/{code}/exchange")
        if status == 200:
            save_credentials(api_base, h5_base, payload["token"], payload["user"])
            print(json.dumps({"ok": True, "user": payload["user"], "credentials": str(CREDENTIALS_PATH)}, ensure_ascii=False))
            return
        time.sleep(max(0.5, args.poll_interval))


def logout(_args):
    if CREDENTIALS_PATH.exists():
        credentials = load_credentials()
        api_base = normalize_base(credentials.get("api_base") or DEFAULT_API_BASE)
        token = str(credentials.get("token") or "")
        if token:
            try:
                request_json("POST", f"{api_base}/api/auth/user/logout", {}, token=token)
            except Exception:
                pass
        CREDENTIALS_PATH.unlink()
    print(json.dumps({"ok": True}, ensure_ascii=False))


def account(_args):
    credentials = load_credentials()
    api_base = normalize_base(credentials.get("api_base") or DEFAULT_API_BASE)
    token = credentials["token"]
    _, payload = request_json("GET", f"{api_base}/api/auth/user/me", token=token)
    credentials["user"] = payload["user"]
    save_credentials(api_base, credentials.get("h5_base") or DEFAULT_H5_BASE, token, payload["user"])
    print(json.dumps(payload, ensure_ascii=False))


def account_points(args):
    api_base, token = get_cli_credentials()
    query = urllib.parse.urlencode({"page": max(1, args.page), "pageSize": max(1, min(50, args.page_size))})
    _, payload = request_json("GET", f"{api_base}/api/h5/point-ledger?{query}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def account_change_password(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "POST",
        f"{api_base}/api/auth/user/change-password",
        {"oldPassword": args.old_password, "newPassword": args.new_password},
        token=token,
    )
    print(json.dumps(payload, ensure_ascii=False))


def account_bind_invitation(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "POST",
        f"{api_base}/api/auth/user/invitation",
        {"invitationCode": args.code},
        token=token,
    )
    print(json.dumps(payload, ensure_ascii=False))


def account_avatar(args):
    api_base, token = get_cli_credentials()
    uploaded = direct_upload_file(api_base, token, args.image, "user_avatar", "file", "image/png")
    try:
        _, payload = request_json(
            "POST",
            f"{api_base}/api/auth/user/avatar",
            {"uploadId": uploaded["uploadId"]},
            token=token,
        )
    except Exception:
        delete_media_upload(api_base, token, uploaded["uploadId"])
        raise
    print(json.dumps(payload, ensure_ascii=False))


def account_redeem(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "POST",
        f"{api_base}/api/h5/recharge-cards/redeem",
        {"cardCode": args.card_code},
        token=token,
    )
    print(json.dumps(payload, ensure_ascii=False))


def config_list(_args):
    print(json.dumps(load_config(), ensure_ascii=False, indent=2))


def config_get(args):
    key = normalize_config_key(args.key)
    config = load_config()
    print(json.dumps({key: config.get(key, "")}, ensure_ascii=False))


def config_set(args):
    key = normalize_config_key(args.key)
    value = args.value.strip()
    if not value:
        raise RuntimeError(f"{args.key} cannot be empty")
    if key in ("api_base", "h5_base"):
        value = normalize_base(value)
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise RuntimeError(f"{args.key} must be an http(s) URL")
    elif key == "output_dir":
        if not value:
            raise RuntimeError("output-dir cannot be empty")
        value = str(Path(value).expanduser().resolve())
    config = load_config()
    config[key] = value
    save_config(config)
    print(json.dumps({"ok": True, key: value, "config": str(CONFIG_PATH)}, ensure_ascii=False))


def config_unset(args):
    key = normalize_config_key(args.key)
    config = load_config()
    removed = key in config
    config.pop(key, None)
    save_config(config)
    print(json.dumps({"ok": True, "removed": removed, "config": str(CONFIG_PATH)}, ensure_ascii=False))


def content_query(args):
    if CREDENTIALS_PATH.is_file():
        api_base, token = get_cli_credentials()
    else:
        api_base, token = resolve_api_base(args), ""
    if args.content_command == "bootstrap":
        path = "/api/h5/bootstrap"
    elif args.content_command == "hot-creations":
        path = "/api/h5/hot-creations"
    else:
        path = f"/api/h5/legal-documents/{urllib.parse.quote(args.document_type)}"
    _, payload = request_json("GET", f"{api_base}{path}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def download_record(api_base, token, record_id, output_dir):
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        f"{api_base}/api/h5/image-generations/{urllib.parse.quote(record_id)}/download",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        content_type = response.headers.get("content-type", "image/png").split(";")[0]
        extension = mimetypes.guess_extension(content_type) or ".png"
        target = output_path / f"{record_id}{extension}"
        target.write_bytes(response.read())
        return str(target)


def download_video_record(api_base, token, task_id, output_dir):
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        f"{api_base}/api/h5/video-generations/{urllib.parse.quote(task_id)}/download",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        content_type = response.headers.get("content-type", "video/mp4").split(";")[0]
        extension = mimetypes.guess_extension(content_type) or ".mp4"
        target = output_path / f"{task_id}{extension}"
        target.write_bytes(response.read())
        return str(target)


def download_authenticated_url(url, token, output_dir, filename, fallback_extension=""):
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"} if token else {},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        content_type = response.headers.get("content-type", "").split(";")[0]
        extension = mimetypes.guess_extension(content_type) or fallback_extension or Path(urllib.parse.urlparse(url).path).suffix or ""
        target = output_path / f"{filename}{extension}"
        target.write_bytes(response.read())
        return str(target)


def resolve_output_dir(explicit=""):
    config = load_config()
    return explicit or os.environ.get("WOOBOO_OUTPUT_DIR", "") or str(config.get("output_dir", "") or "") or os.getcwd()


def download_url(url, output_dir, filename):
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=300) as response:
        content_type = response.headers.get("content-type", "").split(";")[0]
        extension = mimetypes.guess_extension(content_type) or Path(urllib.parse.urlparse(url).path).suffix or ""
        target = output_path / f"{filename}{extension}"
        target.write_bytes(response.read())
        return str(target)


def get_cli_credentials():
    credentials = load_credentials()
    return normalize_base(credentials.get("api_base") or DEFAULT_API_BASE), credentials["token"]


def selector_matches(model, selector):
    normalized = str(selector or "").strip().casefold()
    if not normalized:
        return False
    return normalized in {
        str(model.get("id") or "").strip().casefold(),
        str(model.get("name") or "").strip().casefold(),
        str(model.get("modelName") or "").strip().casefold(),
    }


def fetch_image_bootstrap(api_base, token, scene):
    query = urllib.parse.urlencode({"scene": scene})
    _, payload = request_json("GET", f"{api_base}/api/h5/image-generation/bootstrap?{query}", token=token)
    return payload


def image_models(args):
    api_base, token = get_cli_credentials()
    print(json.dumps(fetch_image_bootstrap(api_base, token, args.scene), ensure_ascii=False))


def image_history(_args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/image-generations/history", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def image_status(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/image-generations/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def image_download(args):
    api_base, token = get_cli_credentials()
    path = download_record(api_base, token, args.id, resolve_output_dir(args.output_dir))
    print(json.dumps({"id": args.id, "downloadedPath": path}, ensure_ascii=False))


def select_image_model(bootstrap, model_config_id="", model_selector=""):
    models = bootstrap.get("models") or []
    if model_config_id:
        selected = next((item for item in models if str(item.get("id") or "") == model_config_id), None)
        if not selected:
            raise RuntimeError(f"Image model config not found: {model_config_id}")
        return selected
    if model_selector:
        selected = next((item for item in models if selector_matches(item, model_selector)), None)
        if not selected:
            raise RuntimeError(f"Image model not found: {model_selector}")
        return selected
    if not models:
        raise RuntimeError("No enabled image model found")
    return models[0]


def select_image_variant(model, variant_key="", quality=""):
    variants = [item for item in (model.get("variants") or []) if item.get("status") == "启用"]
    if variant_key:
        selected = next((item for item in variants if str(item.get("variantKey") or "") == variant_key), None)
        if not selected:
            raise RuntimeError(f"Image model variant not found or disabled: {variant_key}")
        variant_quality = str(selected.get("quality") or "")
        if quality and variant_quality and variant_quality.casefold() != quality.casefold():
            raise RuntimeError(f"Image variant {variant_key} uses quality {variant_quality}, not {quality}")
        return selected
    if quality:
        selected = next((item for item in variants if str(item.get("quality") or "").casefold() == quality.casefold()), None)
        if not selected:
            raise RuntimeError(f"Image quality is not available for the selected model: {quality}")
        return selected
    default_variant = model.get("defaultVariant") or {}
    if default_variant and default_variant.get("status") == "启用":
        return default_variant
    if variants:
        return variants[0]
    raise RuntimeError("The selected image model has no enabled variant")


def image_generate(args):
    credentials = load_credentials()
    config = load_config()
    api_base = normalize_base(credentials.get("api_base") or resolve_api_base(args))
    token = credentials["token"]
    output_dir = args.output_dir or os.environ.get("WOOBOO_OUTPUT_DIR", "") or str(config.get("output_dir", "") or "")
    bootstrap = fetch_image_bootstrap(api_base, token, args.scene)
    model = select_image_model(bootstrap, args.model_config_id, args.model)
    variant = select_image_variant(model, args.variant_key, args.quality)
    quality = args.quality or str(variant.get("quality") or model.get("defaultQuality") or "1k")
    supported_aspect_ratios = model.get("aspectRatios") or bootstrap.get("aspectRatios") or []
    if args.aspect_ratio:
        aspect_ratio = args.aspect_ratio
    elif str(model.get("modelName") or "").strip().casefold() == "gpt-image-2" and "auto" in supported_aspect_ratios:
        aspect_ratio = "auto"
    else:
        aspect_ratio = str((supported_aspect_ratios or ["1:1"])[0])
    if supported_aspect_ratios and aspect_ratio not in supported_aspect_ratios:
        raise RuntimeError(f"Image aspect ratio is not available for the selected model: {aspect_ratio}")
    max_references = max(0, int(model.get("maxReferenceImages") or 0))
    if len(args.reference_image) > max_references:
        raise RuntimeError(f"The selected image model accepts at most {max_references} reference images")
    fields = [
        ("prompt", args.prompt),
        ("scene", args.scene),
        ("aspectRatio", aspect_ratio),
        ("quality", quality),
        ("variantKey", variant.get("variantKey") or ""),
        ("modelConfigId", model.get("id") or ""),
    ]
    completed_uploads = []
    try:
        for path in args.reference_image:
            completed_uploads.append(direct_upload_file(
                api_base, token, path, "image_generation_reference", "referenceImages", "image/png"
            ))
        body = dict(fields)
        body["referenceUploadIds"] = [item["uploadId"] for item in completed_uploads]
        _, payload = request_json("POST", f"{api_base}/api/h5/image-generations", body, token=token, timeout=60)
    except Exception:
        for item in completed_uploads:
            delete_media_upload(api_base, token, item["uploadId"])
        raise
    record = payload.get("record", {})
    record_id = record.get("id", "")
    if not args.wait or not record_id:
        print(json.dumps(payload, ensure_ascii=False))
        return

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, detail = request_json("GET", f"{api_base}/api/h5/image-generations/{urllib.parse.quote(record_id)}", token=token)
        item = detail.get("item", {})
        if item.get("status") in ("成功", "失败"):
            result = {"record": item}
            if item.get("status") == "成功" and output_dir:
                result["downloadedPath"] = download_record(api_base, token, record_id, output_dir)
            print(json.dumps(result, ensure_ascii=False))
            return
        time.sleep(max(1.0, args.poll_interval))
    raise RuntimeError(f"Timed out waiting for image generation record: {record_id}")


def fetch_video_bootstrap(api_base, token):
    _, payload = request_json("GET", f"{api_base}/api/h5/video-generation/bootstrap", token=token)
    return payload


def video_models(_args):
    api_base, token = get_cli_credentials()
    print(json.dumps(fetch_video_bootstrap(api_base, token), ensure_ascii=False))


def video_optimize_prompt(args):
    api_base, token = get_cli_credentials()
    bootstrap = fetch_video_bootstrap(api_base, token)
    model = select_video_model(bootstrap, args.series, args.model_config_id, args.model, args.mode)
    materials = []
    valid_kinds = {"image", "video", "audio", "file", "link"}
    valid_roles = {"reference", "first_frame", "last_frame", "source", "voice"}
    for value in args.material:
        kind, separator, role = value.partition(":")
        if not separator or kind not in valid_kinds or role not in valid_roles:
            raise RuntimeError(f"Invalid material {value!r}; expected kind:role")
        materials.append({"kind": kind, "role": role})
    body = {
        "prompt": args.prompt,
        "modelConfigId": model.get("id") or "",
        "mode": args.mode,
        "hasVideoReference": bool(args.has_video_reference),
        "materials": materials,
    }
    if args.aspect_ratio:
        body["aspectRatio"] = args.aspect_ratio
    if args.max_duration_seconds > 0:
        body["maxDurationSeconds"] = args.max_duration_seconds
    _, payload = request_json("POST", f"{api_base}/api/h5/video-generation/optimize-prompt", body, token=token, timeout=180)
    print(json.dumps(payload, ensure_ascii=False))


def resolve_video_series(bootstrap, selector):
    normalized = str(selector or "").strip().casefold()
    if not normalized:
        return ""
    for item in bootstrap.get("seriesConfigs") or []:
        series_key = str(item.get("seriesKey") or "").strip()
        if normalized in {
            series_key.casefold(),
            str(item.get("displayName") or "").strip().casefold(),
        }:
            return series_key
    public_name_fallbacks = {
        "闪影": "wanx",
        "灵光": "happyhorse",
        "速影": "agnes",
    }
    return public_name_fallbacks.get(normalized, str(selector or "").strip())


def select_video_model(bootstrap, series="", model_config_id="", model_selector="", mode=""):
    series = resolve_video_series(bootstrap, series)
    models = bootstrap.get("models") or []
    selected = None
    if model_config_id:
        selected = next((item for item in models if str(item.get("id") or "") == model_config_id), None)
        if not selected:
            raise RuntimeError(f"Video model config not found: {model_config_id}")
    elif model_selector:
        selected = next((item for item in models if selector_matches(item, model_selector)), None)
        if not selected:
            raise RuntimeError(f"Video model not found: {model_selector}")
    else:
        candidates = [
            item for item in models
            if (not series or str((item.get("capability") or {}).get("series") or "") == series)
            and (not mode or mode in ((item.get("capability") or {}).get("modes") or []))
        ]
        selected = candidates[0] if candidates else None
    if not selected:
        label = f" for series {series}" if series else ""
        raise RuntimeError(f"No enabled video model found{label} supporting mode {mode}")
    capability = selected.get("capability") or {}
    if series and str(capability.get("series") or "") != series:
        raise RuntimeError(f"Selected video model does not belong to series: {series}")
    if mode and mode not in (capability.get("modes") or []):
        raise RuntimeError(f"Selected video model does not support mode: {mode}")
    return selected


def select_video_variant(model, variant_key="", resolution=""):
    variants = [item for item in (model.get("variants") or []) if item.get("status") == "启用"]
    if variant_key:
        selected = next((item for item in variants if str(item.get("variantKey") or "") == variant_key), None)
        if not selected:
            raise RuntimeError(f"Video model variant not found or disabled: {variant_key}")
        variant_resolution = str(selected.get("resolution") or "")
        if resolution and variant_resolution and variant_resolution.casefold() != resolution.casefold():
            raise RuntimeError(f"Video variant {variant_key} uses resolution {variant_resolution}, not {resolution}")
        return selected
    if resolution:
        selected = next(
            (item for item in variants if str(item.get("resolution") or "").casefold() == resolution.casefold()),
            None,
        )
        if not selected:
            raise RuntimeError(f"Video resolution is not available for the selected model: {resolution}")
        return selected
    default_variant = model.get("defaultVariant") or {}
    if default_variant and default_variant.get("status") == "启用":
        return default_variant
    if variants:
        return variants[0]
    raise RuntimeError("The selected video model has no enabled variant")


def build_video_upload_entries(args, series):
    entries = []
    for field_name, path in (
        ("firstFrameFile", args.first_frame),
        ("lastFrameFile", args.last_frame),
        ("extendVideoFile", args.extend_video),
        ("editVideoFile", args.edit_video),
    ):
        if path:
            entries.append((field_name, path))
    reference_file = getattr(args, "reference_file", "")
    reference_audio = getattr(args, "reference_audio", [])
    if reference_file:
        entries.append(("referenceDocumentFile", reference_file))
    audio_field = "textAudioFile" if args.mode == "t2v" else "referenceAudioFiles"
    entries.extend((audio_field, path) for path in reference_audio)

    materials = []
    if args.mode == "r2v" and series in ("wanx", "kling", "seedance"):
        for path in args.reference_image:
            materials.append({"source": "local", "mediaFileIndex": len(materials), "mediaKind": "reference_image"})
            entries.append(("wanxR2vMediaFiles", path))
        for path in args.reference_video:
            materials.append({"source": "local", "mediaFileIndex": len(materials), "mediaKind": "reference_video"})
            entries.append(("wanxR2vMediaFiles", path))
        return entries, materials

    entries.extend(("referenceImageFiles", path) for path in args.reference_image)
    entries.extend(("referenceVideoFiles", path) for path in args.reference_video)
    return entries, materials


def validate_video_inputs(args, capability):
    series = str(capability.get("series") or "")
    image_count = len(args.reference_image)
    video_count = len(args.reference_video)
    reference_audio = getattr(args, "reference_audio", [])
    reference_file = getattr(args, "reference_file", "")
    reference_link = getattr(args, "reference_link", "")
    audio_count = len(reference_audio)
    mode_inputs = {
        "first_frame": bool(args.first_frame),
        "last_frame": bool(args.last_frame),
        "extend_video": bool(args.extend_video),
        "edit_video": bool(args.edit_video),
        "reference_image": bool(args.reference_image),
        "reference_video": bool(args.reference_video),
        "reference_audio": bool(reference_audio),
        "reference_file": bool(reference_file),
        "reference_link": bool(reference_link),
    }
    allowed_inputs = {
        "t2v": {"reference_audio"} if series == "wanx" else set(),
        "i2v": {"first_frame"},
        "first_last_frame": {"first_frame", "last_frame"},
        "r2v": {"reference_image", "reference_video", "reference_audio", "reference_file", "reference_link"},
        "video_extend": {"extend_video"},
        "video_edit": {"edit_video", "reference_image"},
    }[args.mode]
    unexpected = [name for name, present in mode_inputs.items() if present and name not in allowed_inputs]
    if unexpected:
        raise RuntimeError(f"Video mode {args.mode} does not accept: {', '.join(unexpected)}")
    if args.mode in ("i2v", "first_last_frame") and not args.first_frame:
        raise RuntimeError(f"Video mode {args.mode} requires --first-frame")
    if args.mode == "video_extend" and not args.extend_video:
        raise RuntimeError("Video extend mode requires --extend-video")
    if args.mode == "video_edit" and not args.edit_video:
        raise RuntimeError("Video edit mode requires --edit-video")
    if image_count > int(capability.get("maxReferenceImages") or 0):
        raise RuntimeError("Reference image count exceeds the selected model limit")
    if video_count > int(capability.get("maxReferenceVideos") or 0):
        raise RuntimeError("Reference video count exceeds the selected model limit")
    if audio_count > int(capability.get("maxReferenceAudios") or 0):
        raise RuntimeError("Reference audio count exceeds the selected model limit")
    if reference_file and int(capability.get("maxReferenceFiles") or 0) < 1:
        raise RuntimeError("The selected model does not support reference files")
    if reference_link and int(capability.get("maxReferenceLinks") or 0) < 1:
        raise RuntimeError("The selected model does not support reference links")
    if reference_file and reference_link:
        raise RuntimeError("Reference file and reference link cannot be used together")
    if args.mode == "t2v" and audio_count > 1:
        raise RuntimeError("Text-to-video accepts at most one reference audio file")
    if args.mode == "r2v" and not image_count and not video_count and not audio_count and not reference_file and not reference_link:
        raise RuntimeError("Reference-to-video mode requires at least one reference material")
    if series == "happyhorse" and video_count:
        raise RuntimeError("HappyHorse reference-to-video supports images only")
    if series == "kling" and video_count and image_count > 4:
        raise RuntimeError("Kling accepts at most four reference images when a video reference is present")
    if series == "seedance" and video_count > 1:
        raise RuntimeError("Seedance accepts at most one video reference")
    constraint = (capability.get("durationConstraints") or {}).get(args.mode) or {}
    minimum = int(constraint.get("min") or 0)
    maximum = int(
        constraint.get("maxWithVideoReference")
        if video_count and constraint.get("maxWithVideoReference") is not None
        else constraint.get("max") or 0
    )
    if minimum and args.duration_seconds < minimum:
        raise RuntimeError(f"Video duration must be at least {minimum} seconds for the selected model and mode")
    if maximum and args.duration_seconds > maximum:
        raise RuntimeError(f"Video duration must be at most {maximum} seconds for the selected model and mode")


def video_generate(args):
    api_base, token = get_cli_credentials()
    config = load_config()
    output_dir = args.output_dir or os.environ.get("WOOBOO_OUTPUT_DIR", "") or str(config.get("output_dir", "") or "")
    bootstrap = fetch_video_bootstrap(api_base, token)
    model = select_video_model(bootstrap, args.series, args.model_config_id, args.model, args.mode)
    capability = model.get("capability") or {}
    series = str(capability.get("series") or "")
    validate_video_inputs(args, capability)
    variant = select_video_variant(model, args.variant_key, args.resolution)
    variant_key = str(variant.get("variantKey") or "")
    resolution = str(variant.get("resolution") or args.resolution or "720P")
    aspect_ratio = args.aspect_ratio or ("adaptive" if series == "seedance" else "9:16")
    model_config_id = str(model.get("id") or "")

    fields = [
        ("clientSubmissionId", str(uuid.uuid4())),
        ("modelConfigId", model_config_id),
        ("mode", args.mode),
        ("prompt", args.prompt),
        ("resolution", resolution),
        ("durationSeconds", args.duration_seconds),
        ("aspectRatio", aspect_ratio),
        ("trimLongMedia", "true" if args.trim_long_media else "false"),
    ]
    model_settings = model.get("settings") or {}
    for field_name, explicit_value, default_value in (
        ("audio", getattr(args, "audio", None), model_settings.get("audio")),
        ("promptExtend", getattr(args, "prompt_extend", None), model_settings.get("promptExtend")),
        ("watermark", getattr(args, "watermark", None), model_settings.get("watermark")),
    ):
        if explicit_value is not None or default_value is not None:
            fields.append((field_name, "true" if (explicit_value if explicit_value is not None else default_value) else "false"))
    if variant_key:
        fields.append(("variantKey", variant_key))
    if args.negative_prompt:
        fields.append(("negativePrompt", args.negative_prompt))
    if args.camera_fixed:
        fields.append(("cameraFixed", "true"))
    if getattr(args, "reference_link", ""):
        fields.append(("referenceWebLink", args.reference_link))

    upload_entries, materials = build_video_upload_entries(args, series)
    if materials:
        fields.append(("wanxR2vMaterials", json.dumps(materials, ensure_ascii=False)))
    completed_uploads = []
    try:
        for field_name, path in upload_entries:
            completed_uploads.append(
                direct_upload_file(api_base, token, path, "video_generation", field_name)
            )
        if completed_uploads:
            fields.append(("mediaUploads", json.dumps([
                {"fieldName": item["fieldName"], "uploadId": item["uploadId"]}
                for item in completed_uploads
            ], ensure_ascii=False)))
        _, payload = request_json("POST", f"{api_base}/api/h5/video-generations", dict(fields), token=token, timeout=300)
    except Exception:
        for item in completed_uploads:
            delete_media_upload(api_base, token, item["uploadId"])
        raise
    task = payload.get("task", {})
    task_id = task.get("taskId", "")
    if not args.wait or not task_id:
        print(json.dumps(payload, ensure_ascii=False))
        return

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, detail = request_json("GET", f"{api_base}/api/h5/video-generations/{urllib.parse.quote(task_id)}", token=token)
        task = detail.get("task", {})
        record = detail.get("record", {})
        status = str(task.get("taskStatus") or record.get("status") or "")
        if status in ("成功", "失败", "succeeded", "failed"):
            result = {"task": task, "record": record}
            video_url = task.get("videoUrl") or record.get("resultVideoUrl") or record.get("videoUrl")
            if status in ("成功", "succeeded") and output_dir and video_url:
                result["downloadedPath"] = download_video_record(api_base, token, task_id, output_dir)
            print(json.dumps(result, ensure_ascii=False))
            return
        time.sleep(max(1.0, args.poll_interval))
    raise RuntimeError(f"Timed out waiting for video generation task: {task_id}")


def video_status(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/video-generations/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def video_download(args):
    api_base, token = get_cli_credentials()
    output_dir = resolve_output_dir(args.output_dir)
    path = download_video_record(api_base, token, args.id, output_dir)
    print(json.dumps({"id": args.id, "downloadedPath": path}, ensure_ascii=False))


def video_package_bootstrap(_args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/video-packages/bootstrap", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def video_package_page(args, kind):
    api_base, token = get_cli_credentials()
    query = urllib.parse.urlencode({"offset": max(0, args.offset), "limit": max(1, min(50, args.limit))})
    _, payload = request_json("GET", f"{api_base}/api/h5/video-packages/{kind}?{query}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def video_package_list(_args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/video-packages", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def video_package_generate(args):
    api_base, token = get_cli_credentials()
    config = load_config()
    output_dir = args.output_dir or os.environ.get("WOOBOO_OUTPUT_DIR", "") or str(config.get("output_dir", "") or "")
    _, bootstrap = request_json("GET", f"{api_base}/api/h5/video-packages/bootstrap", token=token)
    if not bootstrap.get("ready"):
        raise RuntimeError(str(bootstrap.get("upstreamError") or "Video packaging is not ready"))
    style_id = args.style_id or str(((bootstrap.get("templates") or [{}])[0]).get("id") or "")
    if not style_id:
        raise RuntimeError("No enabled video package template is available")
    upload = direct_upload_file(api_base, token, args.video, "video_package", "videoFile", "video/mp4")
    try:
        _, created = request_json(
            "POST",
            f"{api_base}/api/h5/video-packages",
            {
                "uploadId": upload["uploadId"],
                "title": args.title,
                "estimatedDurationSeconds": args.duration_seconds,
                "styleId": style_id,
                "musicId": args.music_id,
                "identityName": args.identity_name,
                "identityDesc": args.identity_desc,
                "catalogRevision": bootstrap.get("catalogRevision") or "",
            },
            token=token,
        )
    except Exception:
        delete_media_upload(api_base, token, upload["uploadId"])
        raise
    item = created.get("item") or {}
    project_id = str(item.get("id") or "")
    if not args.wait or not project_id:
        print(json.dumps(created, ensure_ascii=False))
        return
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, detail = request_json("GET", f"{api_base}/api/h5/video-packages/{urllib.parse.quote(project_id)}", token=token)
        item = detail.get("item") or {}
        if item.get("status") in ("succeeded", "failed"):
            result = {"item": item}
            if item.get("status") == "succeeded" and output_dir:
                result["downloadedPath"] = download_authenticated_url(
                    f"{api_base}/api/h5/video-packages/{urllib.parse.quote(project_id)}/download",
                    token,
                    output_dir,
                    project_id,
                    ".mp4",
                )
            print(json.dumps(result, ensure_ascii=False))
            return
        time.sleep(max(1.0, args.poll_interval))
    raise RuntimeError(f"Timed out waiting for video package task: {project_id}")


def video_package_status(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/video-packages/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def video_package_download(args):
    api_base, token = get_cli_credentials()
    path = download_authenticated_url(
        f"{api_base}/api/h5/video-packages/{urllib.parse.quote(args.id)}/download",
        token,
        resolve_output_dir(args.output_dir),
        args.id,
        ".mp4",
    )
    print(json.dumps({"id": args.id, "downloadedPath": path}, ensure_ascii=False))


def video_package_delete(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("DELETE", f"{api_base}/api/h5/video-packages/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload or {"ok": True}, ensure_ascii=False))


def voice_list(_args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/digital-human/bootstrap", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def voice_delete(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "DELETE",
        f"{api_base}/api/h5/digital-human/voices/{urllib.parse.quote(args.id)}",
        token=token,
    )
    print(json.dumps(payload or {"ok": True}, ensure_ascii=False))


def voice_status(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/digital-human/voices/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def voice_clone(args):
    api_base, token = get_cli_credentials()
    uploaded = direct_upload_file(
        api_base,
        token,
        args.audio,
        "digital_human_voice",
        "voiceAudio",
        "audio/mpeg",
    )
    try:
        _, payload = request_json(
            "POST",
            f"{api_base}/api/h5/digital-human/voices/clone",
            {
                "uploadId": uploaded["uploadId"],
                "voiceName": args.name,
                "language": args.language or "zh",
            },
            token=token,
        )
    except Exception:
        delete_media_upload(api_base, token, uploaded["uploadId"])
        raise
    item = payload.get("item") or {}
    voice_id = str(item.get("id") or "")
    if not args.wait or not voice_id:
        print(json.dumps(payload, ensure_ascii=False))
        return
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, detail = request_json(
            "GET",
            f"{api_base}/api/h5/digital-human/voices/{urllib.parse.quote(voice_id)}",
            token=token,
        )
        item = detail.get("item") or {}
        if item.get("cloneStatus") in ("ready", "failed", "migration_pending"):
            print(json.dumps({"item": item}, ensure_ascii=False))
            return
        time.sleep(max(1.0, args.poll_interval))
    raise RuntimeError(f"Timed out waiting for voice clone: {voice_id}")


def avatar_list(_args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/digital-human/bootstrap", token=token)
    print(json.dumps({"config": payload.get("config") or {}, "avatars": payload.get("avatars") or []}, ensure_ascii=False))


def avatar_create(args):
    api_base, token = get_cli_credentials()
    uploaded = direct_upload_file(
        api_base,
        token,
        args.video,
        "digital_human_avatar",
        "avatarVideo",
        "video/mp4",
    )
    try:
        _, payload = request_json(
            "POST",
            f"{api_base}/api/h5/digital-human/avatars",
            {"uploadId": uploaded["uploadId"], "title": args.title},
            token=token,
        )
    except Exception:
        delete_media_upload(api_base, token, uploaded["uploadId"])
        raise
    item = payload.get("item") or {}
    avatar_id = str(item.get("id") or "")
    if not args.wait or not avatar_id:
        print(json.dumps(payload, ensure_ascii=False))
        return
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, detail = request_json(
            "GET",
            f"{api_base}/api/h5/digital-human/avatars/{urllib.parse.quote(avatar_id)}",
            token=token,
        )
        item = detail.get("item") or {}
        if item.get("status") in ("ready", "failed", "deleted"):
            print(json.dumps({"item": item}, ensure_ascii=False))
            return
        time.sleep(max(1.0, args.poll_interval))
    raise RuntimeError(f"Timed out waiting for digital-human avatar creation: {avatar_id}")


def avatar_delete(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "DELETE",
        f"{api_base}/api/h5/digital-human/avatars/{urllib.parse.quote(args.id)}",
        token=token,
    )
    print(json.dumps(payload or {"ok": True}, ensure_ascii=False))


def avatar_status(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/digital-human/avatars/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def avatar_voice_offer(args, action):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "POST",
        f"{api_base}/api/h5/digital-human/avatars/{urllib.parse.quote(args.id)}/voice-offer/{action}",
        {},
        token=token,
    )
    print(json.dumps(payload, ensure_ascii=False))


def digital_human_generate(args):
    api_base, token = get_cli_credentials()
    config = load_config()
    output_dir = args.output_dir or os.environ.get("WOOBOO_OUTPUT_DIR", "") or str(config.get("output_dir", "") or "")
    if args.drive_mode == "text":
        if not args.text.strip():
            raise RuntimeError("Text drive mode requires --text")
        if not args.voice_record_id.strip():
            raise RuntimeError("Text drive mode requires --voice-record-id")
        if args.audio:
            raise RuntimeError("Text drive mode does not accept --audio")
    elif not args.audio:
        raise RuntimeError("Audio drive mode requires --audio")

    uploaded = None
    if args.drive_mode == "audio":
        uploaded = direct_upload_file(
            api_base,
            token,
            args.audio,
            "digital_human_audio_drive",
            "driveAudio",
            "audio/mpeg",
        )
    title = args.title.strip()
    if not title:
        title = args.text.strip()[:20] if args.drive_mode == "text" else resolve_local_file(args.audio).stem[:20]
    payload_body = {
        "driveMode": args.drive_mode,
        "avatarRecordId": args.avatar_record_id,
        "voiceRecordId": args.voice_record_id if args.drive_mode == "text" else "",
        "audioUploadId": uploaded["uploadId"] if uploaded else "",
        "title": title or "数字人视频",
        "text": args.text.strip() if args.drive_mode == "text" else "",
    }
    if args.subtitle is not None:
        payload_body["subtitleSettings"] = {"enabled": bool(args.subtitle) and args.drive_mode == "text"}
    try:
        _, payload = request_json(
            "POST",
            f"{api_base}/api/h5/digital-human/tasks",
            payload_body,
            token=token,
        )
    except Exception:
        if uploaded:
            delete_media_upload(api_base, token, uploaded["uploadId"])
        raise
    item = payload.get("item", {})
    task_id = item.get("id", "")
    if not args.wait or not task_id:
        print(json.dumps(payload, ensure_ascii=False))
        return
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, detail = request_json("GET", f"{api_base}/api/h5/digital-human/tasks/{urllib.parse.quote(task_id)}", token=token)
        item = detail.get("item", {})
        if item.get("status") in ("succeeded", "failed"):
            result = {"item": item}
            if item.get("status") == "succeeded" and output_dir and item.get("videoUrl"):
                result["downloadedPath"] = download_url(item["videoUrl"], output_dir, task_id)
            print(json.dumps(result, ensure_ascii=False))
            return
        time.sleep(max(1.0, args.poll_interval))
    raise RuntimeError(f"Timed out waiting for digital human task: {task_id}")


def digital_human_status(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/digital-human/tasks/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def digital_human_download(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/digital-human/tasks/{urllib.parse.quote(args.id)}", token=token)
    item = payload.get("item") or {}
    video_url = str(item.get("videoUrl") or "")
    if item.get("status") != "succeeded" or not video_url:
        raise RuntimeError("Digital-human video is not ready for download")
    path = download_url(video_url, resolve_output_dir(args.output_dir), args.id)
    print(json.dumps({"item": item, "downloadedPath": path}, ensure_ascii=False))


def history_list(_args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/user/history", token=token, timeout=180)
    print(json.dumps(payload, ensure_ascii=False))


def history_delete(args):
    api_base, token = get_cli_credentials()
    query = urllib.parse.urlencode({"type": args.type}) if args.type else ""
    suffix = f"?{query}" if query else ""
    _, payload = request_json("DELETE", f"{api_base}/api/user/history/{urllib.parse.quote(args.id)}{suffix}", token=token)
    print(json.dumps(payload or {"ok": True}, ensure_ascii=False))


def history_download(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/user/history", token=token, timeout=180)
    item = next((entry for entry in payload.get("items") or [] if str(entry.get("recordId") or "") == args.id), None)
    if not item:
        raise RuntimeError(f"History record not found: {args.id}")
    media_url = str(item.get("mediaUrl") or item.get("imageUrl") or item.get("coverUrl") or "")
    if not media_url:
        raise RuntimeError("The history record does not have a downloadable result")
    path = download_url(media_url, resolve_output_dir(args.output_dir), args.id)
    print(json.dumps({"item": item, "downloadedPath": path}, ensure_ascii=False))


def favorite_list(_args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/favorites", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def favorite_add(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "POST",
        f"{api_base}/api/h5/favorites",
        {"kind": args.kind, "recordId": args.record_id},
        token=token,
        timeout=600,
    )
    print(json.dumps(payload, ensure_ascii=False))


def favorite_remove(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("DELETE", f"{api_base}/api/h5/favorites/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload or {"ok": True}, ensure_ascii=False))


def viral_video_analyze(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("POST", f"{api_base}/api/h5/viral-video-analyses", {"url": args.url}, token=token)
    item = payload.get("item") or {}
    task_id = str(item.get("id") or "")
    if not args.wait or not task_id:
        print(json.dumps(payload, ensure_ascii=False))
        return
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        _, detail = request_json("GET", f"{api_base}/api/h5/viral-video-analyses/{urllib.parse.quote(task_id)}", token=token)
        item = detail.get("item") or {}
        if item.get("status") in ("succeeded", "failed"):
            print(json.dumps({"item": item}, ensure_ascii=False))
            return
        time.sleep(max(1.0, args.poll_interval))
    raise RuntimeError(f"Timed out waiting for viral video analysis: {task_id}")


def viral_video_query(args, latest=False):
    api_base, token = get_cli_credentials()
    suffix = "latest" if latest else urllib.parse.quote(args.id)
    _, payload = request_json("GET", f"{api_base}/api/h5/viral-video-analyses/{suffix}", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def ip_clone_list(_args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/ip-clones", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def ip_clone_create(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "POST",
        f"{api_base}/api/h5/ip-clones",
        {"name": args.name, "companyName": args.company, "businessInfo": args.business},
        token=token,
    )
    print(json.dumps(payload, ensure_ascii=False))


def ip_clone_update(args):
    api_base, token = get_cli_credentials()
    body = {}
    if args.name:
        body["name"] = args.name
    if args.company:
        body["companyName"] = args.company
    if args.business:
        body["businessInfo"] = args.business
    if not body:
        raise RuntimeError("Provide at least one of --name, --company, or --business")
    _, payload = request_json("PATCH", f"{api_base}/api/h5/ip-clones/{urllib.parse.quote(args.id)}", body, token=token)
    print(json.dumps(payload, ensure_ascii=False))


def ip_clone_delete(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("DELETE", f"{api_base}/api/h5/ip-clones/{urllib.parse.quote(args.id)}", token=token)
    print(json.dumps(payload or {"ok": True}, ensure_ascii=False))


def ip_clone_upload(args):
    api_base, token = get_cli_credentials()
    fallback = {"photo": "image/png", "video": "video/mp4", "voice": "audio/mpeg"}[args.type]
    upload = direct_upload_file(api_base, token, args.file, "ip_clone_asset", args.type, fallback)
    try:
        _, payload = request_json(
            "POST",
            f"{api_base}/api/h5/ip-clones/{urllib.parse.quote(args.id)}/assets/{args.type}",
            {"uploadId": upload["uploadId"]},
            token=token,
            timeout=300,
        )
    except Exception:
        delete_media_upload(api_base, token, upload["uploadId"])
        raise
    print(json.dumps(payload, ensure_ascii=False))


def ip_clone_parse_file(args):
    api_base, token = get_cli_credentials()
    upload = direct_upload_file(api_base, token, args.file, "ip_clone_document", "file")
    try:
        _, payload = request_json(
            "POST",
            f"{api_base}/api/h5/ip-clones/parse-file",
            {"uploadId": upload["uploadId"]},
            token=token,
            timeout=180,
        )
    except Exception:
        delete_media_upload(api_base, token, upload["uploadId"])
        raise
    print(json.dumps(payload, ensure_ascii=False))


def agent_bootstrap(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/agents/{urllib.parse.quote(args.code)}/bootstrap", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def agent_conversations(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/agents/{urllib.parse.quote(args.code)}/conversations", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def agent_messages(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("GET", f"{api_base}/api/h5/conversations/{urllib.parse.quote(args.conversation_id)}/messages", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def agent_clear(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json("DELETE", f"{api_base}/api/h5/agents/{urllib.parse.quote(args.code)}/conversations", token=token)
    print(json.dumps(payload, ensure_ascii=False))


def agent_chat(args):
    api_base, token = get_cli_credentials()
    if not args.text.strip() and not args.file:
        raise RuntimeError("Agent chat requires --text or at least one --file")
    uploads = []
    try:
        for path in args.file:
            uploads.append(direct_upload_file(api_base, token, path, "agent_attachment", "files"))
        body = {
            "text": args.text,
            "conversationId": args.conversation_id,
            "ipCloneId": args.ip_clone_id,
            "attachmentUploadIds": [item["uploadId"] for item in uploads],
            "surface": "cli",
        }
        events = request_ndjson(
            "POST",
            f"{api_base}/api/h5/agents/{urllib.parse.quote(args.code)}/messages",
            body,
            token,
            timeout=args.timeout,
        )
    except Exception:
        for item in uploads:
            delete_media_upload(api_base, token, item["uploadId"])
        raise
    done = next((event.get("payload") for event in reversed(events) if event.get("type") == "done"), None)
    print(json.dumps(done or {"events": events}, ensure_ascii=False))


def agent_cancel(args):
    api_base, token = get_cli_credentials()
    _, payload = request_json(
        "POST",
        f"{api_base}/api/h5/agents/{urllib.parse.quote(args.code)}/messages/{urllib.parse.quote(args.job_id)}/cancel",
        {},
        token=token,
    )
    print(json.dumps(payload, ensure_ascii=False))


def main():
    args = parse_args()
    if args.command == "login" and args.login_command == "web":
        login_web(args)
    elif args.command == "logout":
        logout(args)
    elif args.command == "account" and args.account_command in (None, "show"):
        account(args)
    elif args.command == "account" and args.account_command == "points":
        account_points(args)
    elif args.command == "account" and args.account_command == "change-password":
        account_change_password(args)
    elif args.command == "account" and args.account_command == "bind-invitation":
        account_bind_invitation(args)
    elif args.command == "account" and args.account_command == "avatar":
        account_avatar(args)
    elif args.command == "account" and args.account_command == "redeem":
        account_redeem(args)
    elif args.command == "config" and args.config_command == "list":
        config_list(args)
    elif args.command == "config" and args.config_command == "get":
        config_get(args)
    elif args.command == "config" and args.config_command == "set":
        config_set(args)
    elif args.command == "config" and args.config_command == "unset":
        config_unset(args)
    elif args.command == "content":
        content_query(args)
    elif args.command == "image" and args.image_command == "models":
        image_models(args)
    elif args.command == "image" and args.image_command == "history":
        image_history(args)
    elif args.command == "image" and args.image_command == "generate":
        image_generate(args)
    elif args.command == "image" and args.image_command == "status":
        image_status(args)
    elif args.command == "image" and args.image_command == "download":
        image_download(args)
    elif args.command == "video" and args.video_command == "models":
        video_models(args)
    elif args.command == "video" and args.video_command == "optimize-prompt":
        video_optimize_prompt(args)
    elif args.command == "video" and args.video_command == "generate":
        video_generate(args)
    elif args.command == "video" and args.video_command == "status":
        video_status(args)
    elif args.command == "video" and args.video_command == "download":
        video_download(args)
    elif args.command == "video-package" and args.video_package_command == "bootstrap":
        video_package_bootstrap(args)
    elif args.command == "video-package" and args.video_package_command == "templates":
        video_package_page(args, "templates")
    elif args.command == "video-package" and args.video_package_command == "music":
        video_package_page(args, "music")
    elif args.command == "video-package" and args.video_package_command == "list":
        video_package_list(args)
    elif args.command == "video-package" and args.video_package_command == "generate":
        video_package_generate(args)
    elif args.command == "video-package" and args.video_package_command == "status":
        video_package_status(args)
    elif args.command == "video-package" and args.video_package_command == "download":
        video_package_download(args)
    elif args.command == "video-package" and args.video_package_command == "delete":
        video_package_delete(args)
    elif args.command == "voice" and args.voice_command == "list":
        voice_list(args)
    elif args.command == "voice" and args.voice_command == "clone":
        voice_clone(args)
    elif args.command == "voice" and args.voice_command == "delete":
        voice_delete(args)
    elif args.command == "voice" and args.voice_command == "status":
        voice_status(args)
    elif args.command == "avatar" and args.avatar_command == "list":
        avatar_list(args)
    elif args.command == "avatar" and args.avatar_command == "create":
        avatar_create(args)
    elif args.command == "avatar" and args.avatar_command == "delete":
        avatar_delete(args)
    elif args.command == "avatar" and args.avatar_command == "status":
        avatar_status(args)
    elif args.command == "avatar" and args.avatar_command == "accept-voice-offer":
        avatar_voice_offer(args, "accept")
    elif args.command == "avatar" and args.avatar_command == "dismiss-voice-offer":
        avatar_voice_offer(args, "dismiss")
    elif args.command == "digital-human" and args.human_command == "generate":
        digital_human_generate(args)
    elif args.command == "digital-human" and args.human_command == "status":
        digital_human_status(args)
    elif args.command == "digital-human" and args.human_command == "download":
        digital_human_download(args)
    elif args.command == "history" and args.history_command == "list":
        history_list(args)
    elif args.command == "history" and args.history_command == "delete":
        history_delete(args)
    elif args.command == "history" and args.history_command == "download":
        history_download(args)
    elif args.command == "favorite" and args.favorite_command == "list":
        favorite_list(args)
    elif args.command == "favorite" and args.favorite_command == "add":
        favorite_add(args)
    elif args.command == "favorite" and args.favorite_command == "remove":
        favorite_remove(args)
    elif args.command == "viral-video" and args.viral_command == "analyze":
        viral_video_analyze(args)
    elif args.command == "viral-video" and args.viral_command == "latest":
        viral_video_query(args, latest=True)
    elif args.command == "viral-video" and args.viral_command == "status":
        viral_video_query(args)
    elif args.command == "ip-clone" and args.ip_clone_command == "list":
        ip_clone_list(args)
    elif args.command == "ip-clone" and args.ip_clone_command == "create":
        ip_clone_create(args)
    elif args.command == "ip-clone" and args.ip_clone_command == "update":
        ip_clone_update(args)
    elif args.command == "ip-clone" and args.ip_clone_command == "delete":
        ip_clone_delete(args)
    elif args.command == "ip-clone" and args.ip_clone_command == "upload":
        ip_clone_upload(args)
    elif args.command == "ip-clone" and args.ip_clone_command == "parse-file":
        ip_clone_parse_file(args)
    elif args.command == "agent" and args.agent_command == "bootstrap":
        agent_bootstrap(args)
    elif args.command == "agent" and args.agent_command == "conversations":
        agent_conversations(args)
    elif args.command == "agent" and args.agent_command == "messages":
        agent_messages(args)
    elif args.command == "agent" and args.agent_command == "clear":
        agent_clear(args)
    elif args.command == "agent" and args.agent_command == "chat":
        agent_chat(args)
    elif args.command == "agent" and args.agent_command == "cancel":
        agent_cancel(args)
    else:
        raise RuntimeError("Unsupported command")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
