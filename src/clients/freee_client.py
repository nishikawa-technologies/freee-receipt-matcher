"""
freee API クライアント
未処理取引の取得、領収書のアップロード・添付を行う
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

from ..core.models import Transaction

logger = logging.getLogger(__name__)


class FreeeClient:
    """freee API クライアント"""

    BASE_URL = "https://api.freee.co.jp/api/1"

    def __init__(self, access_token: str, company_id: int):
        """
        Args:
            access_token: freee APIアクセストークン
            company_id: 事業所ID
        """
        self.access_token = access_token
        self.company_id = company_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
        )

    def get_walletables(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
    ) -> List[Transaction]:
        """
        未処理取引を取得（ページネーション対応）

        Args:
            date_from: 検索開始日
            date_to: 検索終了日

        Returns:
            取引のリスト
        """
        logger.info(f"Fetching deals from {date_from} to {date_to}")

        url = f"{self.BASE_URL}/deals"
        transactions = []
        offset = 0
        limit = 100  # 1回あたり最大100件

        try:
            while True:
                params = {
                    "company_id": self.company_id,
                    "start_issue_date": date_from.strftime("%Y-%m-%d"),
                    "end_issue_date": date_to.strftime("%Y-%m-%d"),
                    "limit": limit,
                    "offset": offset,
                }

                response = self._request_with_retry("GET", url, params=params)
                data = response.json()

                deals = data.get("deals", [])
                logger.info(f"Fetched {len(deals)} deals (offset: {offset})")

                if not deals:
                    # データがなくなったら終了
                    break

                for item in deals:
                    try:
                        # 領収書添付済みかチェック
                        receipts = item.get("receipts", [])
                        has_receipt = len(receipts) > 0

                        transaction = Transaction(
                            id=str(item["id"]),
                            date=datetime.strptime(item["issue_date"], "%Y-%m-%d").date(),
                            amount=float(item.get("amount", 0)),
                            description="",  # dealsにはdescriptionがない
                            merchant_name=item.get("partner_name"),
                            status=item.get("status", "unknown"),
                            has_receipt=has_receipt,
                        )
                        transactions.append(transaction)
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Failed to parse deal {item.get('id')}: {e}")
                        continue

                # 取得件数がlimitより少ない場合、最後のページ
                if len(deals) < limit:
                    break

                offset += limit

            logger.info(f"Extracted {len(transactions)} transactions (total)")
            return transactions

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch deals: {e}")
            return []

    def upload_receipt(
        self,
        file_path: str,
        receipt_data: Optional[Dict] = None,
    ) -> Optional[str]:
        """
        領収書ファイルをアップロード

        Args:
            file_path: 領収書ファイルパス（PDF、画像）
            receipt_data: 追加メタデータ（オプション）

        Returns:
            アップロードされた領収書ID、失敗時はNone
        """
        logger.info(f"Uploading receipt: {file_path}")

        url = f"{self.BASE_URL}/receipts"

        try:
            with open(file_path, "rb") as f:
                files = {
                    "receipt": (file_path.split("/")[-1], f, "application/pdf"),
                }

                data = {
                    "company_id": self.company_id,
                }

                # メタデータがあれば追加
                if receipt_data:
                    if "description" in receipt_data:
                        data["description"] = receipt_data["description"]
                    if "issue_date" in receipt_data:
                        data["issue_date"] = receipt_data["issue_date"]

                # Note: receipts endpointはmultipart/form-dataを使用
                # Authorizationヘッダーは別途設定
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                }

                response = self._request_with_retry(
                    "POST",
                    url,
                    data=data,
                    files=files,
                    headers=headers,
                )

                result = response.json()
                receipt_id = str(result["receipt"]["id"])
                logger.info(f"Uploaded receipt with ID: {receipt_id}")
                return receipt_id

        except FileNotFoundError:
            logger.error(f"Receipt file not found: {file_path}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to upload receipt: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse upload response: {e}")
            return None

    def attach_receipt_to_transaction(
        self,
        transaction_id: str,
        receipt_id: str,
    ) -> bool:
        """
        領収書を取引に添付

        Args:
            transaction_id: 取引ID（deal_id）
            receipt_id: 領収書ID

        Returns:
            成功時True、失敗時False
        """
        logger.info(f"Attaching receipt {receipt_id} to transaction {transaction_id}")

        # deals エンドポイント
        url = f"{self.BASE_URL}/deals/{transaction_id}"
        params = {"company_id": self.company_id}

        try:
            # 1. 現在の deal を取得
            get_response = self._request_with_retry("GET", url, params=params)
            if get_response.status_code != 200:
                logger.error(f"Failed to get deal: HTTP {get_response.status_code}")
                return False

            deal_data = get_response.json()["deal"]

            # 2. receipt_ids を追加
            existing_receipt_ids = [r["id"] for r in deal_data.get("receipts", [])]
            if int(receipt_id) in existing_receipt_ids:
                logger.info(f"Receipt {receipt_id} already attached")
                return True

            receipt_ids = existing_receipt_ids + [int(receipt_id)]

            # 3. null フィールドを除外
            def clean_object(obj):
                """null値を除外（ネストされたオブジェクトも対応）"""
                if isinstance(obj, dict):
                    return {k: clean_object(v) for k, v in obj.items() if v is not None}
                elif isinstance(obj, list):
                    return [clean_object(item) for item in obj]
                else:
                    return obj

            cleaned_details = [clean_object(d) for d in deal_data["details"]]
            cleaned_payments = [clean_object(p) for p in deal_data.get("payments", [])]

            # 4. すべての重要フィールドを含めて PUT（既存データを保持）
            payload = {
                "company_id": self.company_id,
                "issue_date": deal_data["issue_date"],
                "type": deal_data["type"],
                "details": cleaned_details,
                "payments": cleaned_payments,
                "receipt_ids": receipt_ids,
            }

            # オプションフィールド（存在する場合のみ追加）
            if deal_data.get("partner_id"):
                payload["partner_id"] = deal_data["partner_id"]
            if deal_data.get("partner_code"):
                payload["partner_code"] = deal_data["partner_code"]
            if deal_data.get("ref_number") is not None:
                payload["ref_number"] = deal_data["ref_number"]

            response = self._request_with_retry("PUT", url, json=payload)

            if response.status_code == 200:
                logger.info(f"Successfully attached receipt to transaction {transaction_id}")
                return True
            else:
                logger.error(f"Failed to attach receipt: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to attach receipt: {e}")
            return False
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse deal data: {e}")
            return False

    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs,
    ) -> requests.Response:
        """
        リトライ機能付きHTTPリクエスト

        Args:
            method: HTTPメソッド
            url: リクエストURL
            max_retries: 最大リトライ回数
            **kwargs: requests.requestに渡す追加パラメータ

        Returns:
            Responseオブジェクト

        Raises:
            requests.exceptions.RequestException: リトライ後も失敗した場合
        """
        for attempt in range(max_retries):
            try:
                # filesがある場合はsessionを使わない（multipartのため）
                if "files" in kwargs:
                    response = requests.request(method, url, **kwargs)
                else:
                    response = self.session.request(method, url, **kwargs)

                # ステータスコードチェック
                if response.status_code == 401:
                    logger.error("Authentication failed - check access token")
                    raise requests.exceptions.HTTPError("401 Unauthorized: Invalid access token")

                elif response.status_code == 429:
                    # Rate limit - 指数バックオフ
                    wait_time = min(2 ** attempt, 60)
                    logger.warning(f"Rate limit hit, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                elif response.status_code == 400:
                    # Bad Request - エラー詳細をログ
                    try:
                        error_detail = response.json()
                        logger.error(f"400 Bad Request: {error_detail}")
                    except:
                        logger.error(f"400 Bad Request: {response.text}")
                    response.raise_for_status()

                elif response.status_code >= 500:
                    # Server error - リトライ
                    logger.warning(
                        f"Server error (HTTP {response.status_code}), "
                        f"attempt {attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue

                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue

            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(2 ** attempt)

        raise requests.exceptions.RequestException(f"Failed after {max_retries} attempts")
