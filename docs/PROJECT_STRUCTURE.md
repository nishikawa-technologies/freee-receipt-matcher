# プロジェクト構造

```
freee-receipt-matcher/
├── run.py                      # メインエントリポイント
├── validate_setup.py           # セットアップ検証スクリプト
│
├── src/                        # ソースコードディレクトリ
│   ├── __init__.py
│   │
│   ├── clients/                # 外部APIクライアント（Infrastructure層）
│   │   ├── __init__.py
│   │   ├── freee_client.py     # freee API
│   │   ├── gmail_client.py     # Gmail API
│   │   ├── fx_rate_client.py   # 為替レート取得
│   │   └── receipt_extractor.py # Claude Vision OCR
│   │
│   └── core/                   # ビジネスロジック（Domain/Core層）
│       ├── __init__.py
│       ├── models.py           # ドメインモデル
│       └── matcher.py          # マッチングエンジン
│
├── requirements.txt            # Python依存パッケージ
├── config.yaml.example         # 設定ファイルサンプル
├── config.yaml                 # 実際の設定ファイル（.gitignore対象）
│
├── README.md                   # プロジェクト概要・使い方
├── QUICKSTART.md               # クイックスタートガイド
├── SECURITY.md                 # セキュリティガイド
├── CLAUDE.md                   # プロジェクト設計メモ（Claude用）
├── PROJECT_STRUCTURE.md        # このファイル
│
├── .gitignore                  # Git除外設定
│
├── credentials/                # 機密情報（.gitignore対象）
│   ├── README.md               # credentials説明
│   ├── .gitkeep
│   ├── freee.yaml.example      # freee認証サンプル
│   ├── freee.yaml              # freee認証情報（機密）
│   ├── claude_api_key.txt.example
│   ├── claude_api_key.txt      # Claude APIキー（機密）
│   ├── gmail_credentials.json  # Gmail OAuth2（機密）
│   └── gmail_token.json        # Gmail トークン（自動生成・機密）
│
├── cache/                      # キャッシュディレクトリ
│   ├── fx_rates.json           # 為替レート永続キャッシュ
│   └── receipt_cache/          # 領収書OCR結果キャッシュ（MD5ハッシュベース）
│
├── temp/                       # 一時ファイル
│   └── (PDFダウンロード用)
│
└── logs/                       # ログ出力
    └── freee-matcher.log       # 実行ログ
```

## レイヤー構造（軽量DDD）

### src/clients/ - Infrastructure層

外部システムとの通信を担当。APIクライアント、データ取得など。

- **freee_client.py**: freee API（取引取得、領収書アップロード・添付）
- **gmail_client.py**: Gmail API（メール検索、添付ファイル取得）
- **fx_rate_client.py**: exchangerate.host API（為替レート取得・キャッシュ）
- **receipt_extractor.py**: Claude Vision API（PDF→構造化データ抽出）

### src/core/ - Domain/Core層

ビジネスロジックとドメインモデル。外部依存なし（clients層に依存）。

- **models.py**: ドメインモデル（Transaction, ReceiptData, Match等）
- **matcher.py**: マッチングエンジン（日付×金額ロジック）

### ルートディレクトリ

- **run.py**: エントリポイント（Application層的な役割）
- **validate_setup.py**: セットアップ検証ツール

## モジュール詳細

### src/core/models.py

すべてのドメインモデルを集約:

```python
@dataclass
class Transaction:        # freee取引データ
@dataclass
class ReceiptData:        # 領収書抽出データ
@dataclass
class Match:              # マッチング結果
@dataclass
class MatchScore:         # マッチングスコア
@dataclass
class Message:            # Gmailメッセージ
@dataclass
class Attachment:         # メール添付ファイル
```

### src/core/matcher.py

コアビジネスロジック:

```python
class ReceiptMatcher:
    def match(transactions, receipts)
        # 日付×金額マッチングアルゴリズム
```

### src/clients/

各クライアントのAPI呼び出しロジック:

```python
# freee_client.py
class FreeeClient:
    def get_walletables()
    def upload_receipt()
    def attach_receipt_to_transaction()

# gmail_client.py
class GmailClient:
    def search_messages()
    def get_attachments()

# fx_rate_client.py
class FXRateClient:
    def get_rate()

# receipt_extractor.py
class ReceiptExtractor:
    def extract_from_pdf()
    def extract_from_image()
```

### run.py

全体のワークフロー統括:

```python
def main():
    1. 設定読み込み（config.yaml + credentials/）
    2. クライアント初期化
    3. freeeから取引取得
    4. Gmailから領収書取得
    5. OCR/LLMで情報抽出
    6. マッチング実行
    7. freeeに添付
    8. サマリー表示
```

## データフロー

```
freee API → Transaction[]
                ↓
Gmail API → Message[] → Attachment[] → PDF[]
                                        ↓
Claude Vision API → ReceiptData[]
                                        ↓
                Matcher (日付×金額)
                        ↓
                Match[] (取引 ⟷ 領収書)
                        ↓
        freee API (upload & attach)
```

## 設定ファイル構造

### config.yaml（設定のみ、機密情報なし）

```yaml
freee:
  credentials_file: "credentials/freee.yaml"

gmail:
  credentials_path: "credentials/gmail_credentials.json"
  token_path: "credentials/gmail_token.json"

llm:
  provider: "anthropic"
  model: "claude-4-6-sonnet"
  credentials_file: "credentials/claude_api_key.txt"

fx_rates:
  provider: "exchangerate.host"
  cache_dir: "./cache"

matching:
  tolerance_percent: 3.0
  date_range_days: 90
  min_confidence: 0.7

logging:
  level: "INFO"
  file: "logs/freee-matcher.log"

temp_dir: "./temp"
```

### credentials/（機密情報のみ、.gitignore対象）

```yaml
# credentials/freee.yaml
access_token: "xxx"
company_id: 123456
```

```
# credentials/claude_api_key.txt
sk-ant-xxxxx
```

## インポート構造

```python
# run.py
from src.clients import FreeeClient, GmailClient, FXRateClient, ReceiptExtractor
from src.core import ReceiptMatcher

# src/clients/freee_client.py
from ..core.models import Transaction

# src/clients/gmail_client.py
from ..core.models import Message, Attachment

# src/clients/receipt_extractor.py
from ..core.models import ReceiptData

# src/core/matcher.py
from .models import Transaction, ReceiptData, Match, MatchScore
from ..clients.fx_rate_client import FXRateClient
```

## パフォーマンス最適化

### 並列処理

- **ThreadPoolExecutor**: 5ワーカーで並列OCR処理
- 36個のPDFを約1分で処理可能

### キャッシング

- **FXレートキャッシュ**: 過去レートは不変なので永続的にキャッシュ
- **領収書OCRキャッシュ**: MD5ハッシュベースで同一PDFの再処理を回避
- キャッシュヒット時はAPI呼び出しを省略

### ページネーション

- freee API: limit=100、offset-based pagination で大量取引も取得可能

## 依存関係

### パッケージマネージャ

- **uv**: 高速なPythonパッケージマネージャ（推奨）
- 従来の `pip install` も使用可能

### Python パッケージ

- `requests`: HTTP API呼び出し
- `pyyaml`: 設定ファイル読み込み
- `anthropic`: Claude API SDK
- `pdf2image`: PDF → 画像変換
- `Pillow`: 画像処理
- `google-api-python-client`: Gmail API
- `google-auth-*`: OAuth2認証

### システム依存

- `poppler-utils`: PDF処理（pdf2image用）
  - macOS: `brew install poppler`
  - Ubuntu: `apt-get install poppler-utils`

## セキュリティ

### .gitignore 対象

- `credentials/*`: 全ての認証情報（*.exampleは除外）
- `cache/`: キャッシュデータ
- `temp/`: ダウンロードしたPDF
- `logs/`: 実行ログ（個人情報含む可能性）
- `config.yaml`: 設定ファイル（念のため除外）

### 環境変数

- `CLAUDE_API_KEY`: Claudeトークン（credentials/ファイル優先、環境変数はフォールバック）

## 拡張ポイント

### Phase 2 拡張（プラグイン化）

```
src/
├── clients/
│   └── connectors/      # サービス別コネクタ
│       ├── aws.py
│       ├── azure.py
│       ├── slack.py
│       └── notion.py
```

### Web UI (Phase 3)

```
backend/
  └── api/
      └── fastapi_app.py

frontend/
  ├── src/
  │   ├── components/
  │   └── App.tsx
  └── package.json
```

## 開発ワークフロー

1. **機能追加**
   - Domain変更 → `src/core/models.py`
   - API追加 → `src/clients/`
   - ロジック変更 → `src/core/matcher.py`
   - 統合 → `run.py`

2. **テスト**
   - `--dry-run` で動作確認
   - 実データで検証

3. **コミット**
   - `.gitignore` 確認
   - `credentials/` が含まれていないか必須チェック
