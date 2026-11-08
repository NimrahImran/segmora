import io
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import contact as contact_svc
from app.services import persona
from app.services.segmentation import name_clusters


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def csv_bytes(df):
    return df.to_csv(index=False).encode()


def upload(client, content, name="c.csv", **data):
    return client.post("/api/analyze", files={"file": (name, content)}, data=data)


CUSTOMER = {"recency_days": 5, "orders": 20, "total_spend": 15000, "tenure_days": 360, "product_variety": 200}


def test_health(client):
    assert client.get("/api/health").json()["model_loaded"] is True


def test_baseline_shape(client):
    data = client.get("/api/analysis").json()
    assert data["customers"] == 4338
    assert [s["key"] for s in data["segments"]] == ["vip", "regular", "deal", "new"]
    assert abs(sum(s["revenue_share"] for s in data["segments"]) - 1) < 0.01
    assert len(data["table"]) == 4338


def test_vip_customer(client):
    res = client.post("/api/predict", json=CUSTOMER).json()
    assert res["segment"] == "vip" and 0 < res["strength"] <= 1 and len(res["reasons"]) == 3


def test_new_customer(client):
    res = client.post("/api/predict", json={"recency_days": 7, "orders": 1, "total_spend": 250,
                                            "tenure_days": 7, "product_variety": 15}).json()
    assert res["segment"] == "new"


def test_lapsed_small_buyer_is_deal_hunter(client):
    res = client.post("/api/predict", json={"recency_days": 280, "orders": 1, "total_spend": 90,
                                            "tenure_days": 280, "product_variety": 5}).json()
    assert res["segment"] == "deal"


@pytest.mark.parametrize("patch_", [{"orders": 0}, {"total_spend": -1}, {"recency_days": -2}])
def test_predict_rejects_bad_values(client, patch_):
    assert client.post("/api/predict", json={**CUSTOMER, **patch_}).status_code == 422


def customers_frame(n=120):
    return pd.DataFrame({"Customer ID": range(n), "Email": ["a@b.c"] * n, "Recency": [5 + i * 2 for i in range(n)],
                         "Frequency": [1 + i % 9 for i in range(n)], "Monetary": [100 + i * 30 for i in range(n)]})


def test_upload_customers_csv_drops_personal_columns(client):
    data = upload(client, csv_bytes(customers_frame())).json()
    assert data["customers"] == 120 and data["source"]["shape"] == "customers"
    assert "Email" not in data["table"][0] and "a@b.c" not in str(data)


def test_upload_excel(client):
    buffer = io.BytesIO()
    customers_frame().to_excel(buffer, index=False)
    assert upload(client, buffer.getvalue(), "c.xlsx").json()["customers"] == 120


def test_upload_transactions_are_aggregated(client):
    tx = pd.DataFrame({"InvoiceNo": ["1", "1", "2", "C3"], "CustomerID": [7, 7, 7, 8],
                       "InvoiceDate": ["2024-01-01", "2024-01-01", "2024-02-01", "2024-02-02"],
                       "Quantity": [2, 1, 3, -1], "UnitPrice": [5, 10, 2, 5], "StockCode": ["a", "b", "a", "a"]})
    data = upload(client, csv_bytes(tx)).json()
    row = data["table"][0]
    assert data["source"]["shape"] == "transactions" and data["customers"] == 1
    assert row["orders"] == 2 and row["total_spend"] == 26 and row["product_variety"] == 2


def test_unknown_columns_ask_for_matching_then_work(client):
    df = customers_frame().rename(columns={"Recency": "Quiet", "Frequency": "Visits", "Monetary": "Cash"})
    res = upload(client, csv_bytes(df))
    assert res.status_code == 422 and set(res.json()["missing"]) == {"recency_days", "orders", "total_spend"}
    mapping = '{"recency_days":"Quiet","orders":"Visits","total_spend":"Cash"}'
    assert upload(client, csv_bytes(df), mapping=mapping).status_code == 200


def test_own_mode_needs_enough_customers(client):
    data = upload(client, csv_bytes(customers_frame(20)), mode="own").json()
    assert data["source"]["mode"] == "standard" and data["source"]["note"]
    assert upload(client, csv_bytes(customers_frame(120)), mode="own").json()["source"]["mode"] == "own"


@pytest.mark.parametrize("content,name", [(b"\x00\x01garbage", "x.csv"), (b"a,b\n", "x.csv"), (b"hello", "x.exe")])
def test_bad_files_get_clear_errors(client, content, name):
    res = upload(client, content, name)
    assert res.status_code == 422 and res.json()["detail"]


def report_body(data):
    return {"source_label": "<b>x</b> & co.csv", "currency": "", "customers": data["customers"], "total_revenue": data["total_revenue"],
            "segments": data["segments"], "priority": data["priority"]}


def test_pdf_report_handles_markup_in_file_names(client):
    data = upload(client, csv_bytes(customers_frame())).json()
    res = client.post("/api/report.pdf", json=report_body(data))
    assert res.status_code == 200 and res.content[:4] == b"%PDF"


def test_too_many_customers(client):
    from app.main import settings
    with patch.object(settings, "max_customers", 10):
        assert upload(client, csv_bytes(customers_frame())).status_code == 422


def good_contact(**extra):
    return {"name": "Sara Khan", "email": "sara@shop.com", "message": "We want to understand our customers.", **extra}


def test_contact_without_settings_is_clear(client):
    with patch.object(contact_svc, "get_settings") as s:
        s.return_value.gmail_user, s.return_value.gmail_app_password = "", ""
        assert client.post("/api/contact", json=good_contact()).status_code == 503


def test_contact_sends_with_reply_to(client):
    with patch.object(contact_svc, "get_settings") as s, patch.object(contact_svc.smtplib, "SMTP_SSL") as smtp:
        s.return_value.gmail_user, s.return_value.gmail_app_password = "me@gmail.com", "abcd efgh"
        assert client.post("/api/contact", json=good_contact(email="reply@shop.com")).json() == {"ok": True}
    box = smtp.return_value.__enter__.return_value
    box.login.assert_called_once_with("me@gmail.com", "abcdefgh")
    assert box.send_message.call_args[0][0]["Reply-To"] == "Sara Khan <reply@shop.com>"


def test_contact_bot_is_ignored(client):
    with patch.object(contact_svc.smtplib, "SMTP_SSL") as smtp:
        assert client.post("/api/contact", json=good_contact(botcheck=True)).status_code == 200
    smtp.assert_not_called()


@pytest.mark.parametrize("bad", [{"email": "nope"}, {"message": "short"}, {"name": ""}])
def test_contact_validation(client, bad):
    assert client.post("/api/contact", json=good_contact(**bad)).status_code == 422


def test_own_mode_runs_without_sklearn():
    import subprocess
    import sys
    code = "import sys; sys.modules['sklearn']=None; import app.main; print('ok')"
    assert "ok" in subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout


def test_persona_without_key_is_labelled(client):
    data = client.get("/api/analysis").json()
    res = client.post("/api/personas", json={"segment": data["segments"][0], "currency": "£"}).json()
    assert res["source"] == "built_in" and res["observed"][0]["label"] == "Share of customers"


def test_persona_only_sends_averages():
    seen = {}

    class Fake:
        def raise_for_status(self): ...

        def json(self):
            import json
            payload = {"story": "s", "day": "d", "likes": ["a"], "frustrations": ["b"],
                       "offer": {"subject": "x", "email": "y", "whatsapp": "z"}}
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]}

    def fake_post(url, headers, json, timeout):
        seen["body"] = str(json)
        return Fake()

    segment = {"key": "vip", "name": "VIP", "tagline": "t", "customer_share": .2, "revenue_share": .7, "customers": 900,
               "medians": {"orders": 8, "avg_order_value": 360, "recency_days": 10}}
    persona._cache.clear()
    with patch.object(persona, "get_settings") as s, patch.object(persona.httpx, "post", fake_post):
        s.return_value.gemini_api_key, s.return_value.gemini_model = "k", "m"
        out = persona.make(segment, "£")
    assert out["source"] == "gemini" and "customer_id" not in seen["body"]


def test_persona_falls_back_when_ai_fails():
    segment = {"key": "new", "name": "New", "tagline": "t", "customer_share": .2, "revenue_share": .1, "customers": 5,
               "medians": {}}
    with patch.object(persona, "get_settings") as s, patch.object(persona.httpx, "post", side_effect=TimeoutError):
        s.return_value.gemini_api_key, s.return_value.gemini_model = "k", "m"
        assert persona.make(segment, "")["source"] == "built_in"


def test_naming_does_not_depend_on_cluster_order():
    a = pd.DataFrame({"total_spend": [5000, 900, 200, 300], "tenure_days": [360, 300, 280, 20],
                      "avg_order_value": [400, 350, 150, 260]})
    assert name_clusters(a) == ["vip", "regular", "deal", "new"]
    assert name_clusters(a.iloc[::-1].reset_index(drop=True)) == ["new", "deal", "regular", "vip"]


def test_model_card(client):
    card = client.get("/api/model").json()
    assert len(card["comparison"]) == 12 and card["limits"]


def test_slider_calls_are_not_blocked_by_upload_limit(client):
    assert all(client.post("/api/predict", json=CUSTOMER).status_code == 200 for _ in range(60))


def test_persona_tries_the_next_model_when_one_is_retired():
    import json as jsonlib

    import httpx
    tried = []
    payload = {"story": "s", "day": "d", "likes": ["a"], "frustrations": ["b"], "offer": {"subject": "x", "email": "y", "whatsapp": "z"}}

    def fake_post(url, headers, json, timeout):
        tried.append(url)
        request = httpx.Request("POST", url)
        if "old" in url:
            return httpx.Response(404, request=request)
        return httpx.Response(200, request=request, json={"candidates": [{"content": {"parts": [{"text": jsonlib.dumps(payload)}]}}]})

    segment = {"key": "deal", "name": "D", "tagline": "t", "customer_share": .25, "revenue_share": .03, "customers": 9,
               "medians": {"orders": 1}}
    persona._cache.clear()
    with patch.object(persona, "get_settings") as s, patch.object(persona.httpx, "post", fake_post):
        s.return_value.gemini_api_key, s.return_value.gemini_model = "k", "old-model, new-model"
        assert persona.make(segment, "")["source"] == "gemini"
    assert len(tried) == 2 and "new-model" in tried[1]
