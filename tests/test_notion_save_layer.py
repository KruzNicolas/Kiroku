import app.shared.notion.save_layer as save_layer_module
from types import SimpleNamespace
from app.shared.notion.client import _NOTION_API_VERSION
from app.shared.notion.contracts import NotionSaveCommand, NotionUpsertDescriptor
from app.shared.notion.save_layer import NotionSaveLayer, NotionSaveLayerError


class StubPages:
    def __init__(self):
        self.updated_calls = []
        self.created_calls = []

    def update(self, page_id, properties):
        self.updated_calls.append({"page_id": page_id, "properties": properties})

    def create(self, parent, properties, children):
        self.created_calls.append(
            {
                "parent": parent,
                "properties": properties,
                "children": children,
            }
        )
        return {"id": "created_page_id"}


class StubNotionClient:
    def __init__(self, query_results=None):
        self.query_results = query_results if query_results is not None else []
        self.request_calls = []
        self.pages = StubPages()

    def request(self, path, method, body):
        self.request_calls.append({"path": path, "method": method, "body": body})
        return {"results": self.query_results}


class StubFileUploadClient:
    def __init__(self, status: str = "uploaded"):
        self.pages = StubPages()
        self.status = status


def test_upsert_uses_rich_text_descriptor_filter_and_updates():
    client = StubNotionClient(query_results=[{"id": "existing_page_id"}])
    layer = NotionSaveLayer(client)

    command = NotionSaveCommand(
        database_id="db_study",
        properties={"Status": {"select": {"name": "Pending"}}},
        upsert=NotionUpsertDescriptor(
            property_name="Asset ID",
            property_type="rich_text",
            equals="20260324-120000-abc123",
        ),
    )

    page_id = layer.upsert_page(command)

    assert page_id == "existing_page_id"
    assert len(client.request_calls) == 1
    assert client.request_calls[0]["path"] == "databases/db_study/query"
    assert client.request_calls[0]["body"] == {
        "filter": {
            "property": "Asset ID",
            "rich_text": {"equals": "20260324-120000-abc123"},
        }
    }
    assert client.pages.updated_calls == [
        {
            "page_id": "existing_page_id",
            "properties": {"Status": {"select": {"name": "Pending"}}},
        }
    ]
    assert client.pages.created_calls == []


def test_upsert_without_descriptor_creates_page_without_query():
    client = StubNotionClient()
    layer = NotionSaveLayer(client)

    command = NotionSaveCommand(
        database_id="db_videos",
        properties={"Title": {"title": [{"text": {"content": "hello"}}]}},
        children=[
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}
        ],
    )

    page_id = layer.upsert_page(command)

    assert page_id == "created_page_id"
    assert client.request_calls == []
    assert client.pages.updated_calls == []
    assert len(client.pages.created_calls) == 1


def test_upsert_uses_url_descriptor_filter():
    client = StubNotionClient(query_results=[])
    layer = NotionSaveLayer(client)

    command = NotionSaveCommand(
        database_id="db_videos",
        properties={"URL": {"url": "https://youtube.com/watch?v=test"}},
        upsert=NotionUpsertDescriptor(
            property_name="URL",
            property_type="url",
            equals="https://youtube.com/watch?v=test",
        ),
    )

    layer.upsert_page(command)

    assert client.request_calls[0]["body"] == {
        "filter": {
            "property": "URL",
            "url": {"equals": "https://youtube.com/watch?v=test"},
        }
    }


def test_unsupported_upsert_filter_type_raises_error():
    client = StubNotionClient()
    layer = NotionSaveLayer(client)

    try:
        layer._build_upsert_filter(
            NotionUpsertDescriptor(
                property_name="Foo",
                property_type="invalid",  # type: ignore[arg-type]
                equals="bar",
            )
        )
        assert False, "Expected NotionSaveLayerError"
    except NotionSaveLayerError as exc:
        assert "Unsupported upsert filter property type" in str(exc)


def test_number_upsert_filter_requires_numeric_equals():
    layer = NotionSaveLayer(StubNotionClient())

    try:
        layer._build_upsert_filter(
            NotionUpsertDescriptor(
                property_name="Confidence",
                property_type="number",
                equals="0.9",  # type: ignore[arg-type]
            )
        )
        assert False, "Expected NotionSaveLayerError"
    except NotionSaveLayerError as exc:
        assert "must be int or float" in str(exc)


def test_create_page_creates_without_query():
    client = StubNotionClient()
    layer = NotionSaveLayer(client)

    command = NotionSaveCommand(
        database_id="db_study",
        properties={"Title": {"title": [{"text": {"content": "hello"}}]}},
    )

    page_id = layer.create_page(command)

    assert page_id == "created_page_id"
    assert client.request_calls == []
    assert len(client.pages.created_calls) == 1


def test_upload_file_returns_file_upload_id(monkeypatch):
    captured = {"posts": []}

    class FakeResponse:
        def __init__(self, *, status_code=200, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

    def _fake_post(url, headers=None, json=None, files=None, timeout=None):
        captured["posts"].append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "files": files,
                "timeout": timeout,
            }
        )
        if url.endswith("/v1/file_uploads"):
            return FakeResponse(
                payload={"id": "upload-id-123"},
            )
        if url.endswith("/v1/file_uploads/upload-id-123/send"):
            return FakeResponse()
        return FakeResponse(status_code=500, text="unexpected url")

    def _fake_get(url, headers=None, timeout=None):
        captured["get"] = {"url": url, "headers": headers, "timeout": timeout}
        return FakeResponse(payload={"id": "upload-id-123", "status": "uploaded"})

    monkeypatch.setattr(
        save_layer_module,
        "get_settings",
        lambda: SimpleNamespace(notion_token="test-token"),
    )
    monkeypatch.setattr(save_layer_module.requests, "post", _fake_post)
    monkeypatch.setattr(save_layer_module.requests, "get", _fake_get)

    client = StubFileUploadClient(status="uploaded")
    layer = NotionSaveLayer(client)

    upload_id = layer.upload_file(
        content=b"img-bytes",
        filename="asset.png",
        content_type="image/png",
    )

    assert upload_id == "upload-id-123"
    assert captured["posts"][0] == {
        "url": "https://api.notion.com/v1/file_uploads",
        "headers": {
            "Authorization": "Bearer test-token",
            "Notion-Version": _NOTION_API_VERSION,
        },
        "json": {
            "mode": "single_part",
            "filename": "asset.png",
            "content_type": "image/png",
        },
        "files": None,
        "timeout": 30,
    }
    assert captured["posts"][1]["url"] == (
        "https://api.notion.com/v1/file_uploads/upload-id-123/send"
    )
    assert captured["posts"][1]["headers"] == {
        "Authorization": "Bearer test-token",
        "Notion-Version": _NOTION_API_VERSION,
    }
    assert captured["posts"][1]["files"] == {
        "file": ("asset.png", b"img-bytes", "image/png")
    }
    assert captured["get"] == {
        "url": "https://api.notion.com/v1/file_uploads/upload-id-123",
        "headers": {
            "Authorization": "Bearer test-token",
            "Notion-Version": _NOTION_API_VERSION,
        },
        "timeout": 30,
    }


def test_upload_file_raises_when_not_uploaded(monkeypatch):
    class FakeResponse:
        def __init__(self, *, status_code=200, payload=None):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = ""

        def json(self):
            return self._payload

    def _fake_post(url, headers=None, json=None, files=None, timeout=None):
        if url.endswith("/v1/file_uploads"):
            return FakeResponse(payload={"id": "upload-id-123"})
        return FakeResponse()

    def _fake_get(url, headers=None, timeout=None):
        return FakeResponse(payload={"id": "upload-id-123", "status": "failed"})

    monkeypatch.setattr(
        save_layer_module,
        "get_settings",
        lambda: SimpleNamespace(notion_token="test-token"),
    )
    monkeypatch.setattr(save_layer_module.requests, "post", _fake_post)
    monkeypatch.setattr(save_layer_module.requests, "get", _fake_get)

    client = StubFileUploadClient(status="failed")
    layer = NotionSaveLayer(client)

    try:
        layer.upload_file(
            content=b"img-bytes",
            filename="asset.png",
            content_type="image/png",
        )
        assert False, "Expected NotionSaveLayerError"
    except NotionSaveLayerError as exc:
        assert "status: failed" in str(exc)


def test_upload_file_raises_when_upload_url_rejects(monkeypatch):
    class FakeResponse:
        def __init__(self, *, status_code=200, payload=None, text=""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

    def _fake_post(url, headers=None, json=None, files=None, timeout=None):
        if url.endswith("/v1/file_uploads"):
            return FakeResponse(payload={"id": "upload-id-123"})
        if url.endswith("/v1/file_uploads/upload-id-123/send"):
            return FakeResponse(status_code=500, text="bad request")
        return FakeResponse(status_code=500, text="unexpected url")

    def _fake_get(url, headers=None, timeout=None):
        return FakeResponse(payload={"id": "upload-id-123", "status": "uploaded"})

    monkeypatch.setattr(
        save_layer_module,
        "get_settings",
        lambda: SimpleNamespace(notion_token="test-token"),
    )
    monkeypatch.setattr(save_layer_module.requests, "post", _fake_post)
    monkeypatch.setattr(save_layer_module.requests, "get", _fake_get)

    client = StubFileUploadClient(status="uploaded")
    layer = NotionSaveLayer(client)

    try:
        layer.upload_file(
            content=b"img-bytes",
            filename="asset.png",
            content_type="image/png",
        )
        assert False, "Expected NotionSaveLayerError"
    except NotionSaveLayerError as exc:
        assert "send failed" in str(exc)
        assert "bad request" in str(exc)
