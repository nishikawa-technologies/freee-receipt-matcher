"""
為替レート取得モジュール
Frankfurter.app API（ECB公式データ）から過去の為替レートを取得し、ローカルキャッシュで管理
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


class FXRateClient:
    """為替レート取得クライアント"""

    def __init__(self, cache_dir: str = "./cache", provider: str = "frankfurter.app"):
        """
        Args:
            cache_dir: キャッシュディレクトリパス
            provider: レートプロバイダー名（デフォルト: frankfurter.app）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "fx_rates.json"
        self.provider = provider
        self.base_url = "https://api.frankfurter.app"
        self.cache: Dict[str, Dict[str, float]] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, float]]:
        """キャッシュファイルから過去レートを読み込み"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} cached FX rates")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                return {}
        return {}

    def _save_cache(self) -> None:
        """キャッシュファイルに保存"""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
            logger.debug(f"Saved {len(self.cache)} rates to cache")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        date: datetime.date,
    ) -> Optional[float]:
        """
        指定日の為替レートを取得（キャッシュ優先）

        Args:
            from_currency: 変換元通貨コード（例: "USD"）
            to_currency: 変換先通貨コード（例: "JPY"）
            date: 対象日付

        Returns:
            為替レート（例: 1 USD = 150.5 JPY）、取得失敗時はNone
        """
        # 同一通貨の場合
        if from_currency == to_currency:
            return 1.0

        date_str = date.strftime("%Y-%m-%d")
        cache_key = f"{date_str}_{from_currency}_{to_currency}"

        # キャッシュ確認
        if cache_key in self.cache:
            rate = self.cache[cache_key].get("rate")
            logger.debug(f"Cache hit: {from_currency}/{to_currency} on {date_str} = {rate}")
            return rate

        # API経由で取得
        logger.info(f"Fetching {from_currency}/{to_currency} rate for {date_str}")
        rate = self._fetch_from_api(from_currency, to_currency, date)

        if rate is not None:
            # キャッシュに保存
            self.cache[cache_key] = {
                "rate": rate,
                "fetched_at": datetime.now().isoformat(),
            }
            self._save_cache()

        return rate

    def _fetch_from_api(
        self,
        from_currency: str,
        to_currency: str,
        date: datetime.date,
        max_retries: int = 3,
    ) -> Optional[float]:
        """
        APIから為替レートを取得（リトライ機能付き）
        Frankfurter.app API を使用（ECB公式データ、APIキー不要）

        Args:
            from_currency: 変換元通貨
            to_currency: 変換先通貨
            date: 対象日付
            max_retries: 最大リトライ回数

        Returns:
            為替レート、取得失敗時はNone
        """
        date_str = date.strftime("%Y-%m-%d")
        url = f"{self.base_url}/{date_str}"

        # Frankfurter API のクエリパラメータ
        params = {
            "from": from_currency,
            "to": to_currency,
        }

        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()

                # Frankfurter API レスポンス形式:
                # {
                #   "amount": 1.0,
                #   "base": "USD",
                #   "date": "2026-02-13",
                #   "rates": {
                #     "JPY": 150.5
                #   }
                # }

                # レート抽出
                rates = data.get("rates", {})
                rate = rates.get(to_currency)

                if rate is None:
                    logger.error(f"Rate for {to_currency} not found in response")
                    # 週末・祝日の場合、近似日付で再試行
                    return self._try_nearby_dates(from_currency, to_currency, date)

                logger.info(f"Fetched rate: 1 {from_currency} = {rate} {to_currency}")
                return float(rate)

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # 日付が利用不可（週末・祝日）の場合、近似日付で再試行
                    logger.warning(f"Date {date_str} not available, trying nearby dates")
                    return self._try_nearby_dates(from_currency, to_currency, date)
                logger.warning(f"HTTP error (attempt {attempt + 1}/{max_retries}): {e}")
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
            except (KeyError, ValueError) as e:
                logger.error(f"Failed to parse API response: {e}")
                return None

            # 指数バックオフ
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.debug(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)

        logger.error(f"Failed to fetch rate after {max_retries} attempts")
        return None

    def _try_nearby_dates(
        self,
        from_currency: str,
        to_currency: str,
        target_date: datetime.date,
        max_days: int = 3,
    ) -> Optional[float]:
        """
        週末・祝日の場合、前後の日付で再試行

        Args:
            from_currency: 変換元通貨
            to_currency: 変換先通貨
            target_date: 対象日付
            max_days: 最大探索日数

        Returns:
            為替レート、取得失敗時はNone
        """
        logger.info(f"Trying nearby dates around {target_date}")

        # 前の日付を優先（市場終了後のレート）
        for offset in range(1, max_days + 1):
            for delta in [-offset, offset]:
                nearby_date = target_date + timedelta(days=delta)
                date_str = nearby_date.strftime("%Y-%m-%d")
                url = f"{self.base_url}/{date_str}"

                params = {
                    "from": from_currency,
                    "to": to_currency,
                }

                try:
                    response = requests.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    if to_currency in data.get("rates", {}):
                        rate = float(data["rates"][to_currency])
                        logger.info(
                            f"Using rate from nearby date {nearby_date}: "
                            f"1 {from_currency} = {rate} {to_currency}"
                        )
                        return rate

                except Exception as e:
                    logger.debug(f"Failed to fetch rate for {nearby_date}: {e}")
                    continue

        logger.warning(f"Could not find rate for {target_date} or nearby dates")
        return None
