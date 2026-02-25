"""
Gmail API クライアント
領収書メールの検索とPDF添付ファイルのダウンロード
"""

import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..core.models import Message, Attachment

logger = logging.getLogger(__name__)

# Gmail APIスコープ（読み取り専用）
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    """Gmail API クライアント"""

    def __init__(
        self,
        credentials_path: str = "credentials/gmail_credentials.json",
        token_path: str = "credentials/gmail_token.json",
    ):
        """
        Args:
            credentials_path: OAuth2 credentials.jsonのパス
            token_path: 保存済みトークンのパス
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        """
        OAuth2認証を実行してGmail APIサービスを構築

        Returns:
            Gmail APIサービスオブジェクト
        """
        creds = None

        # 既存トークンの読み込み
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                logger.info("Loaded existing Gmail credentials")
            except Exception as e:
                logger.warning(f"Failed to load existing credentials: {e}")

        # トークンが無効または期限切れの場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired Gmail token")
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}")
                    creds = None

            # 新規OAuth認証フロー
            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Gmail credentials file not found: {self.credentials_path}\n"
                        "Please download credentials.json from Google Cloud Console:\n"
                        "https://console.cloud.google.com/apis/credentials"
                    )

                logger.info("Starting OAuth2 flow (browser will open)")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # トークン保存
            try:
                Path(self.token_path).parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_path, "w") as token:
                    token.write(creds.to_json())
                logger.info(f"Saved Gmail credentials to {self.token_path}")
            except Exception as e:
                logger.warning(f"Failed to save credentials: {e}")

        return build("gmail", "v1", credentials=creds)

    def search_messages(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        query: Optional[str] = None,
    ) -> List[Message]:
        """
        領収書メールを検索

        Args:
            date_from: 検索開始日
            date_to: 検索終了日
            query: 追加検索クエリ（オプション）

        Returns:
            メッセージのリスト
        """
        # デフォルトクエリ: PDF添付ファイルを持つメール
        base_query = (
            f"has:attachment filename:pdf "
            f"after:{date_from.strftime('%Y/%m/%d')} "
            f"before:{date_to.strftime('%Y/%m/%d')}"
        )

        if query:
            search_query = f"{base_query} {query}"
        else:
            search_query = base_query

        logger.info(f"Searching Gmail with query: {search_query}")

        messages = []

        try:
            # メッセージID一覧を取得
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=search_query, maxResults=500)
                .execute()
            )

            message_ids = results.get("messages", [])
            logger.info(f"Found {len(message_ids)} matching messages")

            # 各メッセージの詳細を取得
            for msg_ref in message_ids:
                try:
                    msg_data = (
                        self.service.users()
                        .messages()
                        .get(userId="me", id=msg_ref["id"], format="metadata")
                        .execute()
                    )

                    # ヘッダーから情報抽出
                    headers = {
                        h["name"].lower(): h["value"]
                        for h in msg_data.get("payload", {}).get("headers", [])
                    }

                    # 日付パース
                    date_str = headers.get("date", "")
                    try:
                        # RFC 2822形式をパース
                        msg_date = datetime.strptime(
                            date_str.split("(")[0].strip(), "%a, %d %b %Y %H:%M:%S %z"
                        )
                    except:
                        # パース失敗時は内部タイムスタンプ使用
                        timestamp_ms = int(msg_data.get("internalDate", 0))
                        msg_date = datetime.fromtimestamp(timestamp_ms / 1000)

                    message = Message(
                        id=msg_ref["id"],
                        date=msg_date,
                        subject=headers.get("subject", "(No subject)"),
                        sender=headers.get("from", "(Unknown)"),
                    )

                    messages.append(message)
                    logger.debug(f"Parsed message: {message}")

                except HttpError as e:
                    logger.warning(f"Failed to fetch message {msg_ref['id']}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(messages)} messages")
            return messages

        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return []

    def get_attachments(self, message_id: str) -> List[Attachment]:
        """
        メッセージからPDF添付ファイルを取得

        Args:
            message_id: メッセージID

        Returns:
            添付ファイルのリスト
        """
        logger.debug(f"Fetching attachments for message {message_id}")

        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            attachments = []

            # パート構造を再帰的に探索
            parts = message.get("payload", {}).get("parts", [])
            self._extract_attachments(parts, message_id, attachments)

            # マルチパートでない場合（単一添付ファイル）
            if not attachments:
                payload = message.get("payload", {})
                if payload.get("filename") and payload.get("body", {}).get("attachmentId"):
                    self._extract_attachment_from_part(payload, message_id, attachments)

            logger.info(f"Found {len(attachments)} attachments in message {message_id}")
            return attachments

        except HttpError as e:
            logger.error(f"Failed to fetch attachments for message {message_id}: {e}")
            return []

    def _extract_attachments(
        self,
        parts: List,
        message_id: str,
        attachments: List[Attachment],
    ) -> None:
        """
        メッセージパートから添付ファイルを再帰的に抽出

        Args:
            parts: メッセージパートのリスト
            message_id: メッセージID
            attachments: 抽出結果を格納するリスト
        """
        for part in parts:
            # ネストされたパートを再帰処理
            if "parts" in part:
                self._extract_attachments(part["parts"], message_id, attachments)

            # 添付ファイルかチェック
            filename = part.get("filename", "")
            if filename and filename.lower().endswith(".pdf"):
                self._extract_attachment_from_part(part, message_id, attachments)

    def _extract_attachment_from_part(
        self,
        part: dict,
        message_id: str,
        attachments: List[Attachment],
    ) -> None:
        """
        パートから添付ファイルをダウンロード

        Args:
            part: メッセージパート
            message_id: メッセージID
            attachments: 抽出結果を格納するリスト
        """
        filename = part.get("filename", "")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")

        if not attachment_id:
            # インライン添付（小さいファイル）
            data = body.get("data", "")
            if data:
                file_data = base64.urlsafe_b64decode(data)
                attachments.append(
                    Attachment(
                        filename=filename,
                        data=file_data,
                        message_id=message_id,
                    )
                )
                logger.debug(f"Extracted inline attachment: {filename}")
            return

        # 外部添付ファイルをダウンロード
        try:
            attachment = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )

            data = attachment.get("data", "")
            if data:
                file_data = base64.urlsafe_b64decode(data)
                attachments.append(
                    Attachment(
                        filename=filename,
                        data=file_data,
                        message_id=message_id,
                    )
                )
                logger.debug(f"Downloaded attachment: {filename} ({len(file_data)} bytes)")

        except HttpError as e:
            logger.warning(f"Failed to download attachment {filename}: {e}")

    def download_attachment(
        self,
        message_id: str,
        attachment_id: str,
        output_path: str,
    ) -> bool:
        """
        添付ファイルをダウンロードして保存（個別ダウンロード用）

        Args:
            message_id: メッセージID
            attachment_id: 添付ファイルID
            output_path: 保存先パス

        Returns:
            成功時True、失敗時False
        """
        try:
            attachment = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )

            data = attachment.get("data", "")
            if not data:
                logger.error("No data in attachment response")
                return False

            file_data = base64.urlsafe_b64decode(data)

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(file_data)

            logger.info(f"Saved attachment to {output_path}")
            return True

        except HttpError as e:
            logger.error(f"Failed to download attachment: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to save attachment: {e}")
            return False
