#!/usr/bin/env python3
"""
GO領収書メールの詳細確認
"""

import yaml
from pathlib import Path
from datetime import datetime

from src.clients import GmailClient

# 設定読み込み
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

gmail_config = config.get("gmail", {})
gmail_client = GmailClient(
    credentials_path=gmail_config.get("credentials_path"),
    token_path=gmail_config.get("token_path"),
)

print("=" * 80)
print("GO領収書メール検索")
print("=" * 80)

# 1. 広範囲で検索（2026年1月〜今日まで）
date_from = datetime(2026, 1, 1).date()
date_to = datetime(2026, 2, 26).date()  # 明日まで

print(f"\n検索範囲: {date_from} 〜 {date_to}")
print("\n[検索1] 全PDF添付メール")
all_messages = gmail_client.search_messages(date_from, date_to)
print(f"  → {len(all_messages)}件")

print("\n[検索2] GOを含むメール")
# GOを含む検索
try:
    results = (
        gmail_client.service.users()
        .messages()
        .list(
            userId="me",
            q=f"GO after:{date_from.strftime('%Y/%m/%d')} before:{date_to.strftime('%Y/%m/%d')}",
            maxResults=500,
        )
        .execute()
    )
    go_messages = results.get("messages", [])
    print(f"  → {len(go_messages)}件")
except Exception as e:
    print(f"  エラー: {e}")

print("\n[検索3] GO + PDF添付")
try:
    results = (
        gmail_client.service.users()
        .messages()
        .list(
            userId="me",
            q=f"GO has:attachment filename:pdf after:{date_from.strftime('%Y/%m/%d')} before:{date_to.strftime('%Y/%m/%d')}",
            maxResults=500,
        )
        .execute()
    )
    go_pdf_messages = results.get("messages", [])
    print(f"  → {len(go_pdf_messages)}件")

    print("\n詳細:")
    for msg_ref in go_pdf_messages:
        msg_data = (
            gmail_client.service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata")
            .execute()
        )

        headers = {
            h["name"].lower(): h["value"]
            for h in msg_data.get("payload", {}).get("headers", [])
        }

        subject = headers.get("subject", "(No subject)")
        sender = headers.get("from", "(Unknown)")
        date_str = headers.get("date", "")

        print(f"  • {subject}")
        print(f"    From: {sender}")
        print(f"    Date: {date_str}")
        print(f"    ID: {msg_ref['id']}")
        print()

except Exception as e:
    print(f"  エラー: {e}")

print("\n[検索4] 今日受信したメール")
try:
    today = datetime.now().date()
    results = (
        gmail_client.service.users()
        .messages()
        .list(
            userId="me",
            q=f"after:{today.strftime('%Y/%m/%d')}",
            maxResults=100,
        )
        .execute()
    )
    today_messages = results.get("messages", [])
    print(f"  → {len(today_messages)}件")

    print("\n  PDF添付メール:")
    for msg_ref in today_messages[:20]:  # 最大20件表示
        msg_data = (
            gmail_client.service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata")
            .execute()
        )

        headers = {
            h["name"].lower(): h["value"]
            for h in msg_data.get("payload", {}).get("headers", [])
        }

        subject = headers.get("subject", "(No subject)")

        # PDF添付があるかチェック
        payload = msg_data.get("payload", {})
        has_pdf = False

        def check_pdf(parts):
            for part in parts:
                if "parts" in part:
                    if check_pdf(part["parts"]):
                        return True
                filename = part.get("filename", "")
                if filename.lower().endswith(".pdf"):
                    return True
            return False

        parts = payload.get("parts", [])
        has_pdf = check_pdf(parts)

        if has_pdf or "GO" in subject or "領収書" in subject:
            print(f"    • {subject} (ID: {msg_ref['id']})")

except Exception as e:
    print(f"  エラー: {e}")
