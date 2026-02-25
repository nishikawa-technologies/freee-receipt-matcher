# freee-receipt-matcher

freeeの「自動で経理」に残っている未処理取引と、Gmailに届いている領収書PDFを自動でマッチングして添付するツール。

**日付×金額による高精度マッチング。freeeユーザーの面倒な領収書管理を自動化します。**

## 特徴

- **日付×金額による高精度マッチング**: 取引先名の表記揺れに左右されない確実なマッチング
- **LLM活用**: Claude Vision APIで領収書PDFから情報を自動抽出
- **外貨対応**: USD建ての請求書も市場レートでJPY換算して照合
- **高速処理**: 並列OCR処理とキャッシュにより高速化（36個のPDFを約1分で処理）
- **複数PDF対応**: 1件のメールに多数のPDFが添付されていても自動で全て処理
- **データ保持**: 取引先情報、税区分、勘定科目などを完全に保持
- **シンプル**: `uv run python run.py` 一発で動作
- **安全**: `--dry-run` モードでプレビュー可能

## 前提条件

- Python 3.9以上
- poppler（PDF処理用）
  - macOS: `brew install poppler`
  - Ubuntu: `sudo apt-get install poppler-utils`

## インストール

```bash
# リポジトリクローン
git clone https://github.com/yourusername/freee-receipt-matcher.git
cd freee-receipt-matcher

# uvのインストール（未インストールの場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 依存関係は自動的にインストールされます
```

## 初期設定

**機密情報はすべて `credentials/` ディレクトリに集約する設計です。**

### 1. 認証情報の準備

#### freee APIトークン

1. [freee Developer Console](https://developer.freee.co.jp/) でアクセストークンを発行
2. `credentials/freee.yaml` を作成:

```bash
cd credentials
cp freee.yaml.example freee.yaml
# 編集して access_token と company_id を設定
```

#### Gmail API認証

1. [Google Cloud Console](https://console.cloud.google.com/) でOAuth 2.0クライアントIDを作成
2. `credentials.json` をダウンロード
3. `credentials/gmail_credentials.json` に配置

#### Claude APIキー

1. [Anthropic Console](https://console.anthropic.com/) でAPIキーを取得
2. `credentials/claude_api_key.txt` に保存:

```bash
echo "sk-ant-xxxxx" > credentials/claude_api_key.txt
```

### 2. 設定ファイル作成

```bash
cp config.yaml.example config.yaml
```

デフォルト設定で動作しますが、必要に応じて調整可能:

```yaml
matching:
  tolerance_percent: 3.0   # 金額許容誤差（%）
  date_range_days: 90      # 検索日数
  min_confidence: 0.7      # 最低信頼度

logging:
  level: "INFO"
```

### 3. セットアップ検証

```bash
uv run python validate_setup.py
```

詳細は [QUICKSTART.md](docs/QUICKSTART.md) を参照してください。

## 使い方

### 基本実行（過去90日分）

```bash
uv run python run.py
```

### 日付範囲を指定

```bash
uv run python run.py --date-from 2026-02-01 --date-to 2026-02-25
```

### Dry Run（添付せずに結果のみ確認）

```bash
uv run python run.py --dry-run
```

### 設定ファイル指定

```bash
uv run python run.py --config /path/to/config.yaml
```

## 処理フロー

1. **freee APIから未処理取引を取得**
   - 指定期間内の未処理取引を取得

2. **Gmailから領収書メールを検索**
   - PDF添付ファイルを持つメールを検索

3. **LLMで情報抽出**
   - Claude Vision APIで各PDFから以下を抽出:
     - 取引先名
     - 日付
     - 金額
     - 通貨

4. **日付×金額でマッチング**
   - 日付が完全一致
   - 金額が許容誤差内（デフォルト±3%）
   - USD建ては市場レートでJPY換算

5. **freeeに添付**
   - マッチした領収書を対応する取引に自動添付

## プロジェクト構造

```
freee-receipt-matcher/
├── run.py              # メインエントリポイント
├── validate_setup.py   # セットアップ検証
├── src/
│   ├── clients/        # 外部APIクライアント
│   │   ├── freee_client.py
│   │   ├── gmail_client.py
│   │   ├── fx_rate_client.py
│   │   └── receipt_extractor.py
│   └── core/           # ビジネスロジック
│       ├── models.py   # ドメインモデル
│       └── matcher.py  # マッチングエンジン
├── docs/               # ドキュメント
│   ├── QUICKSTART.md
│   ├── PROJECT_STRUCTURE.md
│   └── SECURITY.md
├── scripts/            # デバッグ・テストスクリプト
├── credentials/        # 機密情報（.gitignore対象）
│   ├── freee.yaml
│   ├── claude_api_key.txt
│   └── gmail_credentials.json
├── config.yaml         # 設定ファイル
└── LICENSE             # MIT License
```

**設計思想**: 機密情報は `credentials/` に集約、設定は `config.yaml`。軽量DDDアーキテクチャ。

詳細は [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) を参照。

## ログ

実行ログは `logs/freee-matcher.log` に保存されます。

```bash
# リアルタイムでログ監視
tail -f logs/freee-matcher.log
```

## トラブルシューティング

### Gmail認証エラー

初回実行時にブラウザが開き、Googleアカウントへのアクセスを求められます。許可すると `credentials/gmail_token.json` が生成されます。

### freee API 401エラー

アクセストークンが無効です。freee Developer Consoleで新しいトークンを発行してください。

### poppler not foundエラー

PDFライブラリがインストールされていません:

```bash
# macOS
brew install poppler

# Ubuntu
sudo apt-get install poppler-utils
```

### 為替レート取得失敗

`exchangerate.host` APIが利用できない場合、近似日付のレートで自動リトライされます。

## 仕組み

### 日付×金額マッチングの有効性

- **大半のサービスは月1回請求** → 日付×金額がユニーク
- **OpenAI/Anthropicのリチャージ** → 散発的だが金額がユニーク
- **取引先名の表記揺れを回避** → freee側の登録名に依存しない

### 外貨換算の許容幅

- カード会社レートと市場レートの乖離を吸収
- デフォルト±3%（設定で変更可能）

## 既知の制限事項

### freee請求書から作成した取引への添付不可

freeeの「請求書」機能から作成された取引には、APIで領収書を添付できません（freeeのAPI仕様）。
該当する取引は手動で添付してください。

### 重複取引

freeeの「自動で経理」で同じクレジットカード明細が重複して登録されている場合があります。
これはfreee側のマスタデータの問題で、本ツールは重複を作成しません。
freee Web UIで重複取引を削除してください。

## ライセンス

MIT License

## 貢献

Issue、Pull Requestを歓迎します！

## Phase 2: Webスクレイピング対応（実装中）

Gmail以外のソースからも領収書を取得できるようになりました:

### OpenAI スクレイパ（実装済み）

OpenAI Platform の請求履歴からStripe経由で領収書PDFを自動取得。

```bash
# 1. Playwright インストール
uv run python -m playwright install chromium

# 2. Cookie セットアップ（推奨: デフォルトブラウザ使用）
uv run python scripts/setup_openai_cookies.py

# 3. 領収書取得（ヘッドレス）
uv run python scripts/test_openai_scraper.py --headless
```

詳細は [docs/OPENAI_SCRAPER.md](docs/OPENAI_SCRAPER.md) を参照。

### 今後の拡張予定

- 主要SaaSコネクタ（Anthropic, AWS, Azure, Slack等）
- `run.py` との統合（`--sources gmail,openai`）
- Web UI（FastAPI + React）
- `pip install` 対応

---

**困っている人が多い日本のfreeeユーザー向けのOSS。ぜひ使ってみてください！**
