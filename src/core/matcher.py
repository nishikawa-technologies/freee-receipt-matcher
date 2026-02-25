"""
マッチングエンジン
日付×金額ロジックで領収書と取引をマッチング
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from .models import Transaction, ReceiptData, Match, MatchScore
from ..clients.fx_rate_client import FXRateClient

logger = logging.getLogger(__name__)


class ReceiptMatcher:
    """領収書マッチングエンジン"""

    def __init__(
        self,
        fx_client: FXRateClient,
        tolerance_percent: float = 3.0,
        min_confidence: float = 0.7,
    ):
        """
        Args:
            fx_client: 為替レートクライアント
            tolerance_percent: 金額許容誤差（パーセント）
            min_confidence: 最低信頼度閾値
        """
        self.fx_client = fx_client
        self.tolerance_percent = tolerance_percent
        self.min_confidence = min_confidence

    def match(
        self,
        transactions: List[Transaction],
        receipts: List[ReceiptData],
    ) -> Tuple[List[Match], List[Transaction], List[ReceiptData]]:
        """
        取引と領収書をマッチング

        Args:
            transactions: 取引リスト
            receipts: 領収書リスト

        Returns:
            (マッチリスト, 未マッチ取引リスト, 未マッチ領収書リスト)
        """
        logger.info(
            f"Matching {len(transactions)} transactions with {len(receipts)} receipts "
            f"(tolerance: {self.tolerance_percent}%, min_confidence: {self.min_confidence})"
        )

        matches = []
        matched_transaction_ids = set()
        matched_receipt_files = set()

        # 各取引に対してマッチング
        for transaction in transactions:
            best_match = None
            best_score = None

            logger.debug(f"Matching transaction: {transaction}")

            for receipt in receipts:
                # 既にマッチ済みの領収書はスキップ
                if receipt.source_file in matched_receipt_files:
                    continue

                # 低信頼度の領収書はスキップ
                if receipt.confidence < self.min_confidence:
                    logger.debug(
                        f"Skipping low confidence receipt: {receipt.source_file} "
                        f"(confidence: {receipt.confidence:.2f})"
                    )
                    continue

                # スコア計算
                score = self._match_single(transaction, receipt)

                if score and score.is_valid:
                    # より良いマッチが見つかった場合
                    if best_match is None or self._compare_scores(score, best_score) > 0:
                        best_match = receipt
                        best_score = score

            # ベストマッチが見つかった場合
            if best_match and best_score:
                match = Match(
                    transaction=transaction,
                    receipt=best_match,
                    score=best_score,
                )
                matches.append(match)
                matched_transaction_ids.add(transaction.id)
                matched_receipt_files.add(best_match.source_file)
                logger.info(f"Matched: {match}")

        # 未マッチの取引・領収書
        unmatched_transactions = [
            tx for tx in transactions if tx.id not in matched_transaction_ids
        ]
        unmatched_receipts = [
            r for r in receipts if r.source_file not in matched_receipt_files
        ]

        logger.info(
            f"Matching complete: {len(matches)} matches, "
            f"{len(unmatched_transactions)} unmatched transactions, "
            f"{len(unmatched_receipts)} unmatched receipts"
        )

        return matches, unmatched_transactions, unmatched_receipts

    def _match_single(
        self,
        transaction: Transaction,
        receipt: ReceiptData,
    ) -> Optional[MatchScore]:
        """
        個別の取引と領収書をマッチング

        Args:
            transaction: 取引
            receipt: 領収書

        Returns:
            マッチングスコア、マッチ不可の場合はNone
        """
        # 1. 日付チェック（厳密一致）
        if transaction.date != receipt.date:
            logger.debug(
                f"Date mismatch: tx={transaction.date}, receipt={receipt.date}"
            )
            return None

        # 2. 金額チェック（通貨換算 + 許容誤差）
        try:
            amount_jpy = self._convert_to_jpy(
                amount=receipt.amount,
                currency=receipt.currency,
                date=receipt.date,
            )

            if amount_jpy is None:
                logger.warning(f"Failed to convert {receipt.currency} to JPY")
                return None

            # 金額差分（パーセント）
            if transaction.amount == 0:
                logger.warning(f"Transaction amount is zero: {transaction.id}")
                return None

            diff_pct = abs(amount_jpy - transaction.amount) / transaction.amount * 100

            # 許容誤差内かチェック
            amount_match = diff_pct <= self.tolerance_percent

            logger.debug(
                f"Amount check: tx=¥{transaction.amount:,.0f}, "
                f"receipt={receipt.amount} {receipt.currency} (¥{amount_jpy:,.0f}), "
                f"diff={diff_pct:.2f}%, match={amount_match}"
            )

            return MatchScore(
                date_match=True,
                amount_match=amount_match,
                amount_diff_pct=diff_pct,
                confidence=receipt.confidence,
            )

        except Exception as e:
            logger.error(f"Error during matching: {e}")
            return None

    def _convert_to_jpy(
        self,
        amount: float,
        currency: str,
        date: datetime.date,
    ) -> Optional[float]:
        """
        外貨をJPYに変換

        Args:
            amount: 金額
            currency: 通貨コード
            date: 取引日

        Returns:
            JPY金額、変換失敗時はNone
        """
        if currency == "JPY":
            return amount

        # 為替レート取得
        rate = self.fx_client.get_rate(currency, "JPY", date)

        if rate is None:
            logger.error(f"Failed to get FX rate for {currency}/JPY on {date}")
            return None

        jpy_amount = amount * rate
        logger.debug(f"Converted {amount} {currency} to ¥{jpy_amount:,.2f} (rate: {rate})")

        return jpy_amount

    def _compare_scores(self, score1: MatchScore, score2: MatchScore) -> int:
        """
        2つのスコアを比較（衝突解決用）

        Args:
            score1: スコア1
            score2: スコア2

        Returns:
            1: score1が優位、-1: score2が優位、0: 同等
        """
        # 金額差分が小さい方を優先
        if abs(score1.amount_diff_pct - score2.amount_diff_pct) > 0.1:
            return -1 if score1.amount_diff_pct < score2.amount_diff_pct else 1

        # 信頼度が高い方を優先
        if abs(score1.confidence - score2.confidence) > 0.05:
            return 1 if score1.confidence > score2.confidence else -1

        return 0
