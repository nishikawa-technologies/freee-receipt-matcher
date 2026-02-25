"""
LLM情報抽出モジュール
領収書PDFからClaude Vision APIで情報を抽出
キャッシュ機能により、同一PDFは再処理しない
"""

import base64
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import anthropic
from pdf2image import convert_from_path
from PIL import Image

from ..core.models import ReceiptData

logger = logging.getLogger(__name__)


class ReceiptExtractor:
    """領収書情報抽出クライアント"""

    # Claude Vision対応モデル
    MODEL = "claude-4-6-sonnet"

    # 抽出プロンプト
    EXTRACTION_PROMPT = """領収書画像から以下の情報をJSON形式で抽出してください:

{
    "merchant_name": "会社名・店舗名",
    "date": "YYYY-MM-DD",
    "amount": 数値のみ（カンマや通貨記号なし）,
    "currency": "USD" or "JPY" など,
    "confidence": 0.0-1.0（情報の明瞭度）
}

重要なルール:
- 合計金額（Total / Grand Total / Amount Due）を使用してください
- 小計（Subtotal）ではなく最終請求額を使用
- 日付は取引日・請求日を使用（支払期限ではない）
- amount は数値のみ（例: 12500.50）、通貨記号やカンマは除く
- 情報が不明確な場合は confidence を 0.7 未満にする
- 読み取れない項目は null にする

JSON のみを返してください（説明文は不要）。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = MODEL,
        cache_dir: str = "./cache",
    ):
        """
        Args:
            api_key: Claude APIキー（未指定時は環境変数CLAUDE_API_KEYを使用）
            model: 使用モデル
            cache_dir: キャッシュディレクトリ
        """
        self.api_key = api_key or os.environ.get("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Claude API key is required. "
                "Set CLAUDE_API_KEY environment variable or pass api_key parameter."
            )

        self.model = model
        self.client = anthropic.Anthropic(api_key=self.api_key)

        # キャッシュ設定
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "receipt_ocr_cache.json"
        self.cache: Dict[str, dict] = self._load_cache()

    def _load_cache(self) -> Dict[str, dict]:
        """キャッシュファイルから読み込み"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} cached OCR results")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load OCR cache: {e}")
                return {}
        return {}

    def _save_cache(self) -> None:
        """キャッシュファイルに保存"""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
            logger.debug(f"Saved {len(self.cache)} OCR results to cache")
        except Exception as e:
            logger.error(f"Failed to save OCR cache: {e}")

    def _get_file_hash(self, file_path: str) -> str:
        """ファイルのMD5ハッシュを計算"""
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate file hash: {e}")
            return ""

    def extract_from_pdf(
        self,
        pdf_path: str,
        max_pages: int = 3,
    ) -> Optional[ReceiptData]:
        """
        PDFファイルから情報を抽出（キャッシュ対応）

        Args:
            pdf_path: PDFファイルパス
            max_pages: 処理する最大ページ数

        Returns:
            抽出データ、失敗時はNone
        """
        # キャッシュチェック
        file_hash = self._get_file_hash(pdf_path)
        if file_hash and file_hash in self.cache:
            logger.info(f"Cache hit: {pdf_path}")
            cached = self.cache[file_hash]
            return ReceiptData(
                merchant_name=cached["merchant_name"],
                date=datetime.strptime(cached["date"], "%Y-%m-%d").date(),
                amount=cached["amount"],
                currency=cached["currency"],
                confidence=cached["confidence"],
                raw_text=cached.get("raw_text", ""),
                source_file=pdf_path,
            )

        logger.info(f"Extracting data from PDF: {pdf_path}")

        try:
            # PDF → 画像変換
            images = convert_from_path(pdf_path, first_page=1, last_page=max_pages)

            if not images:
                logger.error(f"No images extracted from PDF: {pdf_path}")
                return None

            logger.debug(f"Converted {len(images)} pages to images")

            # 最初のページで試行（通常は1ページ目に情報あり）
            receipt_data = None
            for i, image in enumerate(images):
                logger.debug(f"Processing page {i + 1}/{len(images)}")

                receipt_data = self.extract_from_image(image, pdf_path)

                if receipt_data and receipt_data.confidence >= 0.5:
                    logger.info(f"Successfully extracted from page {i + 1}")
                    break

            # キャッシュに保存
            if receipt_data and file_hash:
                self.cache[file_hash] = {
                    "merchant_name": receipt_data.merchant_name,
                    "date": receipt_data.date.strftime("%Y-%m-%d"),
                    "amount": receipt_data.amount,
                    "currency": receipt_data.currency,
                    "confidence": receipt_data.confidence,
                    "raw_text": receipt_data.raw_text,
                    "cached_at": datetime.now().isoformat(),
                }
                self._save_cache()

            if not receipt_data or receipt_data.confidence < 0.5:
                logger.warning(f"Could not extract high-confidence data from {pdf_path}")

            return receipt_data

        except Exception as e:
            logger.error(f"Failed to process PDF {pdf_path}: {e}")
            return None

    def extract_from_image(
        self,
        image: Image.Image,
        source_file: str = "",
    ) -> Optional[ReceiptData]:
        """
        画像から情報を抽出

        Args:
            image: PIL Image オブジェクト
            source_file: ソースファイル名（ログ用）

        Returns:
            抽出データ、失敗時はNone
        """
        try:
            # 画像をbase64エンコード
            image_data = self._encode_image(image)

            # Claude APIに送信
            logger.debug("Calling Claude Vision API")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": self.EXTRACTION_PROMPT,
                            },
                        ],
                    }
                ],
            )

            # レスポンスからテキスト抽出
            if not response.content:
                logger.error("Empty response from Claude API")
                return None

            raw_text = response.content[0].text
            logger.debug(f"Claude response: {raw_text}")

            # JSON パース
            receipt_data = self._parse_response(raw_text, source_file)

            if receipt_data:
                logger.info(f"Extracted: {receipt_data}")

            return receipt_data

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to extract from image: {e}")
            return None

    def _encode_image(self, image: Image.Image) -> str:
        """
        PIL ImageをBase64エンコード

        Args:
            image: PIL Image

        Returns:
            Base64エンコード文字列
        """
        from io import BytesIO

        # PNG形式でバイト列に変換
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        # Base64エンコード
        return base64.b64encode(image_bytes).decode("utf-8")

    def _parse_response(
        self,
        raw_text: str,
        source_file: str,
    ) -> Optional[ReceiptData]:
        """
        Claude APIレスポンスをパース

        Args:
            raw_text: APIレスポンステキスト
            source_file: ソースファイル名

        Returns:
            ReceiptDataオブジェクト、パース失敗時はNone
        """
        try:
            # JSONブロック抽出（マークダウンコードブロック対応）
            json_text = raw_text.strip()

            if json_text.startswith("```"):
                # コードブロックから抽出
                lines = json_text.split("\n")
                json_text = "\n".join(lines[1:-1])  # 最初と最後の行を除去

            data = json.loads(json_text)

            # 必須フィールドチェック
            required_fields = ["merchant_name", "date", "amount", "currency"]
            for field in required_fields:
                if field not in data or data[field] is None:
                    logger.warning(f"Missing required field: {field}")
                    return None

            # 日付パース
            try:
                date = datetime.strptime(data["date"], "%Y-%m-%d").date()
            except ValueError as e:
                logger.error(f"Invalid date format: {data['date']}: {e}")
                return None

            # 金額パース
            try:
                amount = float(data["amount"])
                if amount <= 0:
                    logger.warning(f"Invalid amount: {amount}")
                    return None
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid amount: {data['amount']}: {e}")
                return None

            # 信頼度（デフォルト0.5）
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))  # 0-1にクランプ

            # 通貨コード正規化
            currency = data["currency"].upper()
            if currency not in ["JPY", "USD", "EUR", "GBP", "CNY"]:
                logger.warning(f"Unknown currency: {currency}, defaulting to JPY")
                currency = "JPY"

            return ReceiptData(
                merchant_name=data["merchant_name"],
                date=date,
                amount=amount,
                currency=currency,
                confidence=confidence,
                raw_text=raw_text,
                source_file=source_file,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {raw_text}")
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse response: {e}")
            return None
