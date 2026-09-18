import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import wooboo_ai_cli as cli


def image_model():
    variants = [
        {
            "variantKey": "standard",
            "quality": "standard",
            "status": "启用",
            "isDefault": True,
        },
        {
            "variantKey": "2k",
            "quality": "2k",
            "status": "启用",
            "isDefault": False,
        },
    ]
    return {
        "id": "image-model-id",
        "name": "GPT Image 2",
        "modelName": "gpt-image-2",
        "maxReferenceImages": 5,
        "defaultQuality": "standard",
        "aspectRatios": ["auto", "1:1", "16:9", "9:16"],
        "variants": variants,
        "defaultVariant": variants[0],
    }


def video_model(model_id, series, modes, model_name=None):
    variant = {
        "variantKey": "720p",
        "resolution": "720P",
        "status": "启用",
        "isDefault": True,
    }
    return {
        "id": model_id,
        "name": model_name or model_id,
        "modelName": model_name or model_id,
        "capability": {
            "series": series,
            "modes": modes,
            "maxReferenceImages": 7 if series == "kling" else 5,
            "maxReferenceVideos": 1 if series in ("kling", "seedance") else 5,
            "maxReferenceAudios": 5 if (model_name or "").startswith("wan3.0-") else 0,
            "maxReferenceFiles": 1 if (model_name or "").startswith("wan3.0-") else 0,
            "maxReferenceLinks": 1 if (model_name or "").startswith("wan3.0-") else 0,
        },
        "variants": [variant],
        "defaultVariant": variant,
    }


class ModelSelectionTests(unittest.TestCase):
    def test_image_model_and_variant_are_dynamic(self):
        model = image_model()
        bootstrap = {"models": [model]}
        self.assertIs(cli.select_image_model(bootstrap, model_selector="GPT IMAGE 2"), model)
        self.assertEqual(cli.select_image_variant(model)["variantKey"], "standard")
        self.assertEqual(cli.select_image_variant(model, quality="2K")["variantKey"], "2k")

    def test_video_selection_filters_by_mode(self):
        t2v = video_model("wanx-t2v", "wanx", ["t2v"])
        r2v = video_model("wanx-r2v", "wanx", ["r2v"])
        selected = cli.select_video_model({"models": [t2v, r2v]}, series="wanx", mode="r2v")
        self.assertEqual(selected["id"], "wanx-r2v")

    def test_video_selection_accepts_system_series_name(self):
        model = video_model("lingguang-r2v", "happyhorse", ["r2v"])
        bootstrap = {
            "models": [model],
            "seriesConfigs": [
                {"seriesKey": "happyhorse", "displayName": "灵光"},
            ],
        }
        selected = cli.select_video_model(bootstrap, series="灵光", mode="r2v")
        self.assertIs(selected, model)

    def test_explicit_unavailable_video_resolution_is_rejected(self):
        model = video_model("wanx-t2v", "wanx", ["t2v"])
        with self.assertRaisesRegex(RuntimeError, "resolution is not available"):
            cli.select_video_variant(model, resolution="1080P")

    def test_kling_uses_mixed_reference_manifest(self):
        args = SimpleNamespace(
            first_frame="",
            last_frame="",
            extend_video="",
            edit_video="",
            mode="r2v",
            reference_image=["a.png", "b.png"],
            reference_video=["c.mp4"],
        )
        entries, materials = cli.build_video_upload_entries(args, "kling")
        self.assertEqual([item[0] for item in entries], ["wanxR2vMediaFiles"] * 3)
        self.assertEqual([item["mediaFileIndex"] for item in materials], [0, 1, 2])


class DirectUploadTests(unittest.TestCase):
    def test_direct_upload_initializes_puts_and_completes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voice.wav"
            path.write_bytes(b"audio")
            initialized = {
                "upload": {
                    "uploadId": "upload-id",
                    "uploadUrl": "https://oss.example/upload?signature=x",
                    "headers": {"Content-Type": "audio/wav"},
                }
            }
            with mock.patch.object(cli, "request_json", side_effect=[(201, initialized), (200, {"upload": {"status": "verified"}})]) as request_json, mock.patch.object(cli, "put_file_to_signed_url") as put_file:
                result = cli.direct_upload_file("https://api.example", "token", str(path), "digital_human_voice", "voiceAudio")
            self.assertEqual(result["uploadId"], "upload-id")
            put_file.assert_called_once()
            self.assertEqual(request_json.call_args_list[0].args[0], "POST")
            self.assertIn("/media-uploads/init", request_json.call_args_list[0].args[1])
            self.assertIn("/media-uploads/upload-id/complete", request_json.call_args_list[1].args[1])

    def test_direct_upload_cleans_up_after_put_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "video.mp4"
            path.write_bytes(b"video")
            initialized = {
                "upload": {
                    "uploadId": "upload-id",
                    "uploadUrl": "https://oss.example/upload",
                    "headers": {"Content-Type": "video/mp4"},
                }
            }
            with mock.patch.object(cli, "request_json", side_effect=[(201, initialized), (204, {})]) as request_json, mock.patch.object(cli, "put_file_to_signed_url", side_effect=RuntimeError("put failed")):
                with self.assertRaisesRegex(RuntimeError, "put failed"):
                    cli.direct_upload_file("https://api.example", "token", str(path), "digital_human_avatar", "avatarVideo")
            self.assertEqual(request_json.call_args_list[-1].args[0], "DELETE")


class CommandContractTests(unittest.TestCase):
    def test_image_generation_uses_bootstrap_defaults(self):
        model = image_model()
        args = SimpleNamespace(
            prompt="生成图片",
            scene="图片生成",
            aspect_ratio="",
            quality="",
            variant_key="",
            model_config_id="",
            model="",
            reference_image=[],
            wait=False,
            poll_interval=1,
            timeout=10,
            output_dir="",
            api_base="",
        )
        captured = {}

        def request_json(method, url, fields, token, timeout=60):
            self.assertEqual(method, "POST")
            captured.update({"fields": dict(fields), "files": []})
            return 202, {"record": {"id": "record-id", "status": "生成中"}}

        with mock.patch.object(cli, "load_credentials", return_value={"api_base": "https://api.example", "token": "token"}), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "fetch_image_bootstrap", return_value={"models": [model], "aspectRatios": model["aspectRatios"]}), mock.patch.object(cli, "request_json", side_effect=request_json), mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.image_generate(args)
        self.assertEqual(captured["fields"]["modelConfigId"], "image-model-id")
        self.assertEqual(captured["fields"]["variantKey"], "standard")
        self.assertEqual(captured["fields"]["quality"], "standard")
        self.assertEqual(captured["fields"]["aspectRatio"], "auto")

    def test_image_reference_uploads_and_failure_cleanup(self):
        for fail in (False, True):
            with self.subTest(fail=fail):
                with mock.patch("sys.argv", ["wooboo", "image", "generate", "--prompt", "cat", "--reference-image", "cat.png"]):
                    args = cli.parse_args()
                    args.wait = False
                with mock.patch.object(cli, "load_credentials", return_value={"api_base": "https://api.example", "token": "token"}), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "fetch_image_bootstrap", return_value={"models": [image_model()]}), mock.patch.object(cli, "direct_upload_file", return_value={"uploadId": "upload-id"}) as upload, mock.patch.object(cli, "request_json", return_value=(202, {"record": {"id": "record-id"}}), side_effect=RuntimeError("submit failed") if fail else None) as submit, mock.patch.object(cli, "delete_media_upload") as cleanup, mock.patch("sys.stdout", new_callable=io.StringIO):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "submit failed"):
                            cli.image_generate(args)
                        cleanup.assert_called_once_with("https://api.example", "token", "upload-id")
                    else:
                        cli.image_generate(args)
                        cleanup.assert_not_called()
                    upload.assert_called_once_with("https://api.example", "token", "cat.png", "image_generation_reference", "referenceImages", "image/png")
                    self.assertEqual(submit.call_args.args[0], "POST")
                    self.assertEqual(submit.call_args.args[2]["referenceUploadIds"], ["upload-id"])

    def test_generation_requests_use_json_on_wire(self):
        for path in ("image-generations", "video-generations"):
            response = mock.MagicMock()
            response.__enter__.return_value = response
            response.status = 202
            response.read.return_value = b'{}'
            with mock.patch.object(cli.urllib.request, "urlopen", return_value=response) as send:
                cli.request_json("POST", "https://api.example/api/h5/" + path, {"prompt": "cat", "referenceUploadIds": []}, token="token")
            request = send.call_args.args[0]
            self.assertEqual(request.get_header("Content-type"), "application/json")
            self.assertEqual(json.loads(request.data), {"prompt": "cat", "referenceUploadIds": []})

    def test_voice_clone_submits_upload_id_and_new_field_names(self):
        args = SimpleNamespace(
            audio="voice.wav",
            name="测试音色",
            language="zh",
            wait=False,
            poll_interval=1,
            timeout=10,
            sex=0,
        )
        captured = {}

        def request_json(method, url, payload=None, token="", timeout=30):
            captured.update({"method": method, "url": url, "payload": payload, "token": token})
            return 202, {"item": {"id": "voice-id", "cloneStatus": "creating"}}

        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "direct_upload_file", return_value={"uploadId": "upload-id"}), mock.patch.object(cli, "request_json", side_effect=request_json), mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.voice_clone(args)
        self.assertEqual(captured["payload"], {"uploadId": "upload-id", "voiceName": "测试音色", "language": "zh"})

    def test_digital_human_text_drive_contract(self):
        args = SimpleNamespace(
            avatar_record_id="avatar-id",
            drive_mode="text",
            text="大家好",
            voice_record_id="voice-id",
            audio="",
            title="测试视频",
            subtitle=True,
            wait=False,
            poll_interval=1,
            timeout=10,
            output_dir="",
        )
        captured = {}

        def request_json(method, url, payload=None, token="", timeout=30):
            captured.update({"method": method, "url": url, "payload": payload})
            return 202, {"item": {"id": "task-id", "status": "queued"}}

        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "request_json", side_effect=request_json), mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.digital_human_generate(args)
        self.assertEqual(captured["payload"]["driveMode"], "text")
        self.assertEqual(captured["payload"]["avatarRecordId"], "avatar-id")
        self.assertEqual(captured["payload"]["voiceRecordId"], "voice-id")
        self.assertEqual(captured["payload"]["subtitleSettings"], {"enabled": True})

    def test_digital_human_audio_drive_uploads_local_audio(self):
        args = SimpleNamespace(
            avatar_record_id="avatar-id",
            drive_mode="audio",
            text="",
            voice_record_id="",
            audio="drive.mp3",
            title="声音驱动",
            subtitle=None,
            wait=False,
            poll_interval=1,
            timeout=10,
            output_dir="",
        )
        captured = {}

        def request_json(method, url, payload=None, token="", timeout=30):
            captured.update({"method": method, "url": url, "payload": payload})
            return 202, {"item": {"id": "task-id", "status": "queued"}}

        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "direct_upload_file", return_value={"uploadId": "audio-upload"}) as upload, mock.patch.object(cli, "request_json", side_effect=request_json), mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.digital_human_generate(args)
        upload.assert_called_once_with(
            "https://api.example",
            "token",
            "drive.mp3",
            "digital_human_audio_drive",
            "driveAudio",
            "audio/mpeg",
        )
        self.assertEqual(captured["payload"]["audioUploadId"], "audio-upload")
        self.assertEqual(captured["payload"]["voiceRecordId"], "")

    def test_digital_human_waits_through_payment_pending(self):
        args = SimpleNamespace(
            avatar_record_id="avatar-id",
            drive_mode="text",
            text="大家好",
            voice_record_id="voice-id",
            audio="",
            title="",
            subtitle=None,
            wait=True,
            poll_interval=1,
            timeout=10,
            output_dir="",
        )
        responses = [
            (202, {"item": {"id": "task-id", "status": "queued"}}),
            (200, {"item": {"id": "task-id", "status": "payment_pending"}}),
            (200, {"item": {"id": "task-id", "status": "succeeded", "videoUrl": "https://media.example/video.mp4"}}),
        ]
        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "request_json", side_effect=responses) as request_json, mock.patch.object(cli.time, "time", return_value=0), mock.patch.object(cli.time, "sleep"), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            cli.digital_human_generate(args)
        self.assertEqual(request_json.call_count, 3)
        self.assertEqual(json.loads(stdout.getvalue())["item"]["status"], "succeeded")

    def test_digital_human_downloads_success_url_directly(self):
        args = SimpleNamespace(
            avatar_record_id="avatar-id",
            drive_mode="text",
            text="大家好",
            voice_record_id="voice-id",
            audio="",
            title="",
            subtitle=None,
            wait=True,
            poll_interval=1,
            timeout=10,
            output_dir="downloads",
        )
        responses = [
            (202, {"item": {"id": "task-id", "status": "queued"}}),
            (200, {"item": {"id": "task-id", "status": "succeeded", "videoUrl": "https://media.example/video.mp4"}}),
        ]
        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "request_json", side_effect=responses), mock.patch.object(cli, "download_url", return_value="downloads/task-id.mp4") as download, mock.patch.object(cli.time, "time", return_value=0), mock.patch.object(cli.time, "sleep"), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            cli.digital_human_generate(args)
        download.assert_called_once_with("https://media.example/video.mp4", "downloads", "task-id")
        self.assertEqual(json.loads(stdout.getvalue())["downloadedPath"], "downloads/task-id.mp4")

    def test_avatar_create_submits_upload_id(self):
        args = SimpleNamespace(video="avatar.mp4", title="主理人", wait=False, poll_interval=1, timeout=10)
        captured = {}

        def request_json(method, url, payload=None, token="", timeout=30):
            captured.update({"method": method, "url": url, "payload": payload})
            return 202, {"item": {"id": "avatar-id", "status": "creating"}}

        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "direct_upload_file", return_value={"uploadId": "avatar-upload"}), mock.patch.object(cli, "request_json", side_effect=request_json), mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.avatar_create(args)
        self.assertEqual(captured["payload"], {"uploadId": "avatar-upload", "title": "主理人"})

    def test_video_generation_uses_direct_upload_manifest_for_kling(self):
        model = video_model("kling-model", "kling", ["r2v"], "kling-v3-omni-video-generation")
        args = SimpleNamespace(
            series="kling",
            model="",
            model_config_id="",
            mode="r2v",
            prompt="参考素材生成视频",
            aspect_ratio="",
            duration_seconds=5,
            resolution="",
            variant_key="",
            first_frame="",
            last_frame="",
            extend_video="",
            edit_video="",
            reference_image=["a.png"],
            reference_video=["b.mp4"],
            negative_prompt="",
            camera_fixed=False,
            trim_long_media=False,
            wait=False,
            poll_interval=1,
            timeout=10,
            output_dir="",
        )
        uploads = iter([
            {"uploadId": "image-upload", "fieldName": "wanxR2vMediaFiles"},
            {"uploadId": "video-upload", "fieldName": "wanxR2vMediaFiles"},
        ])
        captured = {}

        def request_json(method, url, fields, token, timeout=60):
            self.assertEqual(method, "POST")
            captured.update({"url": url, "fields": dict(fields), "files": []})
            return 202, {"task": {"taskId": "task-id", "taskStatus": "生成中"}}

        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "fetch_video_bootstrap", return_value={"models": [model]}), mock.patch.object(cli, "direct_upload_file", side_effect=lambda *args, **kwargs: next(uploads)), mock.patch.object(cli, "request_json", side_effect=request_json), mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.video_generate(args)
        self.assertEqual(captured["files"], [])
        self.assertEqual(json.loads(captured["fields"]["mediaUploads"]), [
            {"fieldName": "wanxR2vMediaFiles", "uploadId": "image-upload"},
            {"fieldName": "wanxR2vMediaFiles", "uploadId": "video-upload"},
        ])
        self.assertEqual([item["mediaFileIndex"] for item in json.loads(captured["fields"]["wanxR2vMaterials"])], [0, 1])

    def test_video_submission_failure_cleans_completed_uploads(self):
        model = video_model("wanx-model", "wanx", ["i2v"])
        args = SimpleNamespace(
            series="wanx",
            model="",
            model_config_id="",
            mode="i2v",
            prompt="让图片动起来",
            aspect_ratio="",
            duration_seconds=5,
            resolution="",
            variant_key="",
            first_frame="frame.png",
            last_frame="",
            extend_video="",
            edit_video="",
            reference_image=[],
            reference_video=[],
            negative_prompt="",
            camera_fixed=False,
            trim_long_media=False,
            wait=False,
            poll_interval=1,
            timeout=10,
            output_dir="",
        )
        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "fetch_video_bootstrap", return_value={"models": [model]}), mock.patch.object(cli, "direct_upload_file", return_value={"uploadId": "frame-upload", "fieldName": "firstFrameFile"}), mock.patch.object(cli, "request_json", side_effect=RuntimeError("submit failed")), mock.patch.object(cli, "delete_media_upload") as cleanup:
            with self.assertRaisesRegex(RuntimeError, "submit failed"):
                cli.video_generate(args)
        cleanup.assert_called_once_with("https://api.example", "token", "frame-upload")

    def test_video_mode_and_dynamic_duration_are_validated_before_upload(self):
        capability = {
            "series": "kling",
            "maxReferenceImages": 7,
            "maxReferenceVideos": 1,
            "durationConstraints": {"r2v": {"min": 3, "max": 15, "maxWithVideoReference": 10}},
        }
        args = SimpleNamespace(
            mode="r2v",
            duration_seconds=11,
            first_frame="",
            last_frame="",
            extend_video="",
            edit_video="",
            reference_image=[],
            reference_video=["reference.mp4"],
        )
        with self.assertRaisesRegex(RuntimeError, "at most 10 seconds"):
            cli.validate_video_inputs(args, capability)
        args.first_frame = "unexpected.png"
        with self.assertRaisesRegex(RuntimeError, "does not accept: first_frame"):
            cli.validate_video_inputs(args, capability)

    def test_retired_commands_are_removed(self):
        for command in ("audio", "long-video"):
            result = subprocess.run(
                [sys.executable, str(Path(cli.__file__).resolve()), command],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid choice", result.stderr)

    def test_wan3_supports_audio_and_document_references(self):
        model = video_model("wan3-model", "wanx", ["r2v", "t2v"], "wan3.0-video")
        model["settings"] = {"audio": True, "promptExtend": False, "watermark": False}
        model["capability"]["durationConstraints"] = {"r2v": {"min": 2, "max": 30}}
        args = SimpleNamespace(
            series="wanx", model="", model_config_id="", mode="r2v", prompt="全能参考",
            aspect_ratio="16:9", duration_seconds=15, resolution="", variant_key="",
            first_frame="", last_frame="", extend_video="", edit_video="",
            reference_image=["image.png"], reference_video=["video.mp4"],
            reference_audio=["voice.mp3"], reference_file="brief.pdf", reference_link="",
            negative_prompt="", audio=None, prompt_extend=None, watermark=None,
            camera_fixed=False, trim_long_media=False, wait=False, poll_interval=1,
            timeout=10, output_dir="",
        )
        uploads = iter([
            {"uploadId": "document", "fieldName": "referenceDocumentFile"},
            {"uploadId": "audio", "fieldName": "referenceAudioFiles"},
            {"uploadId": "image", "fieldName": "wanxR2vMediaFiles"},
            {"uploadId": "video", "fieldName": "wanxR2vMediaFiles"},
        ])
        captured = {}

        def request_json(method, url, fields, token, timeout=60):
            self.assertEqual(method, "POST")
            captured.update({"fields": dict(fields), "files": []})
            return 202, {"task": {"taskId": "task-id", "taskStatus": "生成中"}}

        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "fetch_video_bootstrap", return_value={"models": [model]}), mock.patch.object(cli, "direct_upload_file", side_effect=lambda *args, **kwargs: next(uploads)), mock.patch.object(cli, "request_json", side_effect=request_json), mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.video_generate(args)
        manifest = json.loads(captured["fields"]["mediaUploads"])
        self.assertEqual([item["fieldName"] for item in manifest], [
            "referenceDocumentFile", "referenceAudioFiles", "wanxR2vMediaFiles", "wanxR2vMediaFiles",
        ])
        self.assertEqual(captured["fields"]["audio"], "true")

    def test_video_package_submits_current_catalog_revision(self):
        args = SimpleNamespace(
            video="source.mp4", title="标题", duration_seconds=12.5, style_id="",
            music_id="music-id", identity_name="主理人", identity_desc="产品顾问",
            wait=False, poll_interval=1, timeout=10, output_dir="",
        )
        captured = {}

        def request_json(method, url, payload=None, token="", timeout=30, extra_headers=None):
            if url.endswith("/bootstrap"):
                return 200, {"ready": True, "catalogRevision": "revision-1", "templates": [{"id": "style-id"}]}
            captured.update({"method": method, "url": url, "payload": payload})
            return 202, {"item": {"id": "package-id", "status": "preprocessing"}}

        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "load_config", return_value={}), mock.patch.object(cli, "direct_upload_file", return_value={"uploadId": "upload-id"}), mock.patch.object(cli, "request_json", side_effect=request_json), mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.video_package_generate(args)
        self.assertEqual(captured["payload"]["styleId"], "style-id")
        self.assertEqual(captured["payload"]["catalogRevision"], "revision-1")
        self.assertEqual(captured["payload"]["estimatedDurationSeconds"], 12.5)

    def test_agent_chat_uploads_attachments_and_returns_done_payload(self):
        args = SimpleNamespace(
            code="creative-agent", text="生成脚本", conversation_id="conversation-id",
            ip_clone_id="clone-id", file=["brief.docx"], timeout=30,
        )
        events = [{"type": "done", "payload": {"conversation": {"id": "conversation-id"}, "assistantMessage": {"content": "完成"}}}]
        with mock.patch.object(cli, "get_cli_credentials", return_value=("https://api.example", "token")), mock.patch.object(cli, "direct_upload_file", return_value={"uploadId": "file-upload"}) as upload, mock.patch.object(cli, "request_ndjson", return_value=events) as stream, mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            cli.agent_chat(args)
        upload.assert_called_once_with("https://api.example", "token", "brief.docx", "agent_attachment", "files")
        self.assertEqual(stream.call_args.args[2]["attachmentUploadIds"], ["file-upload"])
        self.assertEqual(json.loads(stdout.getvalue())["assistantMessage"]["content"], "完成")


class DistributionMetadataTests(unittest.TestCase):
    def test_versions_and_production_defaults_match(self):
        root = Path(cli.__file__).resolve().parent
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        pyproject_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
        self.assertIsNotNone(pyproject_version)
        self.assertEqual(package["version"], cli.VERSION)
        self.assertEqual(pyproject_version.group(1), cli.VERSION)
        self.assertEqual(cli.DEFAULT_API_BASE, "https://wooboo.ycszai.com")
        self.assertEqual(cli.DEFAULT_H5_BASE, "https://wooboo.ycszai.com")

    def test_distribution_is_named_wooboo_ai_cli(self):
        root = Path(cli.__file__).resolve().parent
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertEqual(package["name"], "wooboo-ai-cli")
        self.assertEqual(
            package["repository"]["url"],
            "git+https://github.com/FUTUREWORKER/wooboo-ai-cli.git",
        )
        self.assertIn("install-wooboo-ai-cli.ps1", package["files"])
        self.assertIn("install-wooboo-ai-cli.sh", package["files"])
        self.assertIn('name = "wooboo-ai-cli"', pyproject)
        self.assertIn("FUTUREWORKER/wooboo-ai-cli", readme)
        self.assertTrue((root / "install-wooboo-ai-cli.ps1").is_file())
        self.assertTrue((root / "install-wooboo-ai-cli.sh").is_file())

    def test_project_has_no_retired_brand_references(self):
        root = Path(cli.__file__).resolve().parent
        retired_brand = re.compile("spe" + r"ed[ -]?ai", re.IGNORECASE)
        text_suffixes = {".in", ".js", ".json", ".md", ".ps1", ".py", ".sh", ".toml"}
        for path in root.rglob("*"):
            relative = path.relative_to(root)
            if any(part in {".git", "__pycache__"} for part in relative.parts):
                continue
            self.assertIsNone(retired_brand.search(str(relative)), f"retired brand in path: {relative}")
            if path.is_file() and path.suffix.lower() in text_suffixes:
                content = path.read_text(encoding="utf-8")
                self.assertIsNone(retired_brand.search(content), f"retired brand in file: {relative}")

    def test_skill_frontmatter_matches_directory_names(self):
        root = Path(cli.__file__).resolve().parent
        skills_root = root / "skills"
        skill_directories = sorted(path for path in skills_root.iterdir() if path.is_dir())
        expected_skills = {
            "wooboo-creative-agent",
            "wooboo-digital-human-avatar",
            "wooboo-digital-human-video",
            "wooboo-image-generation",
            "wooboo-video-lingguang",
            "wooboo-video-package",
            "wooboo-video-shanying",
            "wooboo-video-suying-2-5-flash",
            "wooboo-voice-clone",
            "wooboo-voice-list",
        }
        self.assertEqual({path.name for path in skill_directories}, expected_skills)
        readme = (root / "README.md").read_text(encoding="utf-8")
        for skill_name in expected_skills:
            self.assertIn(f"--skill {skill_name}", readme)
        for directory in skill_directories:
            skill_path = directory / "SKILL.md"
            self.assertTrue(skill_path.is_file(), f"missing {skill_path}")
            content = skill_path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"), f"missing frontmatter in {skill_path}")
            match = re.search(r"^name:\s*(\S+)\s*$", content, re.MULTILINE)
            self.assertIsNotNone(match, f"missing skill name in {skill_path}")
            self.assertEqual(match.group(1), directory.name)
            description = re.search(r"^description:\s*(.+)\s*$", content, re.MULTILINE)
            self.assertIsNotNone(description, f"missing skill description in {skill_path}")
            self.assertRegex(description.group(1), r"[\u4e00-\u9fff]", f"skill description must be Chinese: {skill_path}")

        for directory in skill_directories:
            if not directory.name.startswith("wooboo-video-") or directory.name == "wooboo-video-package":
                continue
            content = (directory / "SKILL.md").read_text(encoding="utf-8").casefold()
            for provider_model_name in (
                "wan3.0-video",
                "kling-v3-omni-video-generation",
                "doubao-seedance-2-0-260128",
                "agnes-video-2.5-flash",
            ):
                self.assertNotIn(provider_model_name, content)

        for directory in skill_directories:
            content = (directory / "SKILL.md").read_text(encoding="utf-8").casefold()
            for implementation_term in (
                "底层模型",
                "供应商",
                "直连",
                "ndjson",
                "payment_pending",
                "migration_pending",
                "catalog revision",
                "server-side",
                "backward-compatible",
                "retired",
                "audiourl",
                "oss",
                "task queues",
                "creation history",
                "bypass",
                "不得绕过",
            ):
                self.assertNotIn(implementation_term, content)

    def test_readme_documents_new_workflows(self):
        root = Path(cli.__file__).resolve().parent
        readme = (root / "README.md").read_text(encoding="utf-8")
        for command in (
            "wooboo image models",
            "wooboo video models",
            '--model "专业模型"',
            '--model "速影 2.5Flash"',
            "wooboo video-package generate",
            "wooboo agent chat creative-agent",
            "wooboo ip-clone create",
            "wooboo viral-video analyze",
            "wooboo avatar create",
            "wooboo digital-human generate",
        ):
            self.assertIn(command, readme)


if __name__ == "__main__":
    unittest.main()
