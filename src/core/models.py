"""
ドメインモデル
取引、領収書、マッチング結果などのデータ構造
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """freee取引データ"""

    id: str
    date: datetime.date
    amount: float  # JPY
    description: str
    merchant_name: Optional[str]
    status: str
    has_receipt: bool = False  # 領収書添付済みかどうか

    def __str__(self):
        return (
            f"Transaction(id={self.id}, date={self.date}, "
            f"amount=¥{self.amount:,.0f}, merchant={self.merchant_name})"
        )


@dataclass
class ReceiptData:
    """領収書抽出データ"""

    merchant_name: str
    date: datetime.date
    amount: float
    currency: str  # "JPY", "USD", etc.
    confidence: float  # 0.0-1.0
    raw_text: str  # デバッグ用
    source_file: str

    def __str__(self):
        return (
            f"Receipt(merchant={self.merchant_name}, date={self.date}, "
            f"amount={self.amount} {self.currency}, confidence={self.confidence:.2f})"
        )


@dataclass
class MatchScore:
    """マッチングスコア"""

    date_match: bool
    amount_match: bool
    amount_diff_pct: float  # 金額差分（パーセント）
    confidence: float  # 領収書の信頼度

    @property
    def is_valid(self) -> bool:
        """有効なマッチかどうか"""
        return self.date_match and self.amount_match


@dataclass
class Match:
    """取引と領収書のマッチング結果"""

    transaction: Transaction
    receipt: ReceiptData
    score: MatchScore

    def __str__(self):
        return (
            f"Match(tx={self.transaction.id}, receipt={self.receipt.source_file}, "
            f"diff={self.score.amount_diff_pct:.2f}%, conf={self.score.confidence:.2f})"
        )


@dataclass
class Message:
    """Gmailメッセージデータ"""

    id: str
    date: datetime
    subject: str
    sender: str

    def __str__(self):
        return f"Message(id={self.id}, date={self.date}, subject={self.subject[:50]}...)"


@dataclass
class Attachment:
    """メール添付ファイルデータ"""

    filename: str
    data: bytes
    message_id: str

    def __str__(self):
        size_kb = len(self.data) / 1024
        return f"Attachment(filename={self.filename}, size={size_kb:.1f}KB)"
