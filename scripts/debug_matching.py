#!/usr/bin/env python3
"""
マッチング失敗の原因を詳細分析
"""

import yaml
from datetime import datetime, timedelta
from pathlib import Path
import logging
import sys

from src.clients import FreeeClient, FXRateClient, GmailClient, ReceiptExtractor
from src.core import ReceiptMatcher

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_credentials(config: dict):
    """認証情報読み込み"""
    import os

    # freee
    freee_creds_file = config.get("freee", {}).get("credentials_file")
    if freee_creds_file and Path(freee_creds_file).exists():
        with open(freee_creds_file, "r") as f:
            freee_creds = yaml.safe_load(f)
            config["freee"]["access_token"] = freee_creds.get("access_token")
            config["freee"]["company_id"] = freee_creds.get("company_id")

    # Claude API
    llm_config = config.get("llm", {})
    creds_file = llm_config.get("credentials_file")
    if creds_file and Path(creds_file).exists():
        with open(creds_file, "r") as f:
            config["llm"]["api_key"] = f.read().strip()
    else:
        api_key_env = llm_config.get("api_key_env", "CLAUDE_API_KEY")
        config["llm"]["api_key"] = os.environ.get(api_key_env)


def main():
    # 設定読み込み
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    load_credentials(config)

    # 日付範囲
    date_from = datetime(2026, 2, 1).date()
    date_to = datetime(2026, 2, 25).date()

    logger.info(f"Analyzing period: {date_from} to {date_to}")
    logger.info("=" * 80)

    # クライアント初期化
    freee_config = config.get("freee", {})
    freee_client = FreeeClient(
        access_token=freee_config.get("access_token"),
        company_id=freee_config.get("company_id"),
    )

    gmail_config = config.get("gmail", {})
    gmail_client = GmailClient(
        credentials_path=gmail_config.get("credentials_path"),
        token_path=gmail_config.get("token_path"),
    )

    fx_config = config.get("fx_rates", {})
    fx_client = FXRateClient(
        cache_dir=fx_config.get("cache_dir", "./cache"),
        provider=fx_config.get("provider", "frankfurter.app"),
    )

    llm_config = config.get("llm", {})
    extractor = ReceiptExtractor(
        api_key=llm_config.get("api_key"),
        model=llm_config.get("model", "claude-4-6-sonnet"),
        cache_dir=fx_config.get("cache_dir", "./cache"),
    )

    # 取引取得
    all_transactions = freee_client.get_walletables(date_from, date_to)
    transactions = [tx for tx in all_transactions if not tx.has_receipt]

    logger.info(f"\n📊 UNMATCHED TRANSACTIONS (without receipts): {len(transactions)}")
    logger.info("-" * 80)

    # 日付でグループ化
    tx_by_date = {}
    for tx in transactions:
        if tx.date not in tx_by_date:
            tx_by_date[tx.date] = []
        tx_by_date[tx.date].append(tx)

    for date in sorted(tx_by_date.keys()):
        logger.info(f"\n[{date}]")
        for tx in tx_by_date[date]:
            logger.info(f"  • ID:{tx.id} | ¥{tx.amount:,.0f} | {tx.merchant_name or '(no name)'}")

    # 領収書取得
    logger.info(f"\n\n📧 GMAIL RECEIPT EMAILS")
    logger.info("-" * 80)

    messages = gmail_client.search_messages(date_from, date_to)
    logger.info(f"Found {len(messages)} emails\n")

    temp_dir = Path("./temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    receipts = []
    for message in messages:
        attachments = gmail_client.get_attachments(message.id)

        for attachment in attachments:
            temp_file = temp_dir / f"{message.id}_{attachment.filename}"
            with open(temp_file, "wb") as f:
                f.write(attachment.data)

            receipt_data = extractor.extract_from_pdf(str(temp_file))
            if receipt_data:
                receipts.append(receipt_data)

    logger.info(f"\n📄 EXTRACTED RECEIPTS: {len(receipts)}")
    logger.info("-" * 80)

    # 日付でグループ化
    receipt_by_date = {}
    for r in receipts:
        if r.date not in receipt_by_date:
            receipt_by_date[r.date] = []
        receipt_by_date[r.date].append(r)

    for date in sorted(receipt_by_date.keys()):
        logger.info(f"\n[{date}]")
        for r in receipt_by_date[date]:
            # USD→JPY変換
            if r.currency == "USD":
                rate = fx_client.get_rate("USD", "JPY", r.date)
                amount_jpy = r.amount * rate if rate else None
                amount_str = f"{r.amount} USD (≈¥{amount_jpy:,.0f} @ {rate:.2f})" if amount_jpy else f"{r.amount} USD"
            else:
                amount_str = f"¥{r.amount:,.0f}"

            logger.info(
                f"  • {r.merchant_name} | {amount_str} | "
                f"conf:{r.confidence:.2f} | {Path(r.source_file).name}"
            )

    # マッチング分析
    logger.info(f"\n\n🔍 MATCHING ANALYSIS")
    logger.info("=" * 80)

    matching_config = config.get("matching", {})
    matcher = ReceiptMatcher(
        fx_client=fx_client,
        tolerance_percent=matching_config.get("tolerance_percent", 3.0),
        min_confidence=matching_config.get("min_confidence", 0.7),
    )

    # 日付ごとに詳細分析
    all_dates = sorted(set(list(tx_by_date.keys()) + list(receipt_by_date.keys())))

    for date in all_dates:
        txs_on_date = tx_by_date.get(date, [])
        receipts_on_date = receipt_by_date.get(date, [])

        if txs_on_date and receipts_on_date:
            logger.info(f"\n[{date}] - {len(txs_on_date)} transactions, {len(receipts_on_date)} receipts")

            for tx in txs_on_date:
                logger.info(f"\n  Transaction: {tx.merchant_name or '(no name)'} | ¥{tx.amount:,.0f}")

                for receipt in receipts_on_date:
                    # USD→JPY変換
                    if receipt.currency == "USD":
                        rate = fx_client.get_rate("USD", "JPY", receipt.date)
                        amount_jpy = receipt.amount * rate if rate else None
                    else:
                        amount_jpy = receipt.amount

                    if amount_jpy:
                        diff_pct = abs(amount_jpy - tx.amount) / tx.amount * 100
                        match_status = "✓ MATCH" if diff_pct <= 3.0 and receipt.confidence >= 0.7 else "✗ NO MATCH"

                        logger.info(
                            f"    vs {receipt.merchant_name} | {receipt.amount} {receipt.currency} "
                            f"(¥{amount_jpy:,.0f}) | diff:{diff_pct:.2f}% | conf:{receipt.confidence:.2f} | {match_status}"
                        )

                        if diff_pct > 3.0:
                            logger.info(f"      ⚠ Amount difference {diff_pct:.2f}% exceeds tolerance 3.0%")
                        if receipt.confidence < 0.7:
                            logger.info(f"      ⚠ Confidence {receipt.confidence:.2f} below threshold 0.7")

        elif txs_on_date:
            logger.info(f"\n[{date}] - {len(txs_on_date)} transactions, 0 receipts (no receipts on this date)")
        elif receipts_on_date:
            logger.info(f"\n[{date}] - 0 transactions, {len(receipts_on_date)} receipts (no transactions on this date)")


if __name__ == "__main__":
    main()
