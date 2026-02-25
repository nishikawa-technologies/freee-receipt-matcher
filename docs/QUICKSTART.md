# クイックスタートガイド

freee-receipt-matcher を5分で始める手順。

## 1. 依存関係インストール

```bash
# poppler インストール（PDF処理用）
brew install poppler

# uv インストール
curl -LsSf https://astral.sh/uv/install.sh | sh

# Python パッケージは uv が自動的にインストール
```

## 2. 認証情報の準備

**すべての機密情報は `credentials/` ディレクトリに集約します。**

### 2-1. freee APIトークン

1. https://developer.freee.co.jp/ にアクセス
2. 「アプリケーション」→「新しいアプリケーション」
3. アクセストークンを発行
4. `credentials/freee.yaml` を作成:

```bash
cd credentials
cp freee.yaml.example freee.yaml
```

`credentials/freee.yaml` を編集:

```yaml
access_token: "取得したアクセストークン"
company_id: 123456  # freeeの設定 > 事業所設定で確認
```

### 2-2. Gmail API認証

1. https://console.cloud.google.com/ にアクセス
2. 新規プロジェクト作成
3. 「APIとサービス」→「ライブラリ」→「Gmail API」を検索して有効化
4. 「認証情報」→「認証情報を作成」→「OAuth クライアント ID」
5. アプリケーションの種類: **デスクトップアプリ**
6. `credentials.json` をダウンロード
7. `credentials/gmail_credentials.json` に配置:

```bash
mv ~/Downloads/credentials.json credentials/gmail_credentials.json
```

### 2-3. Claude APIキー

1. https://console.anthropic.com/ にアクセス
2. 「API Keys」でキーを作成
3. `credentials/claude_api_key.txt` を作成:

```bash
cd credentials
cp claude_api_key.txt.example claude_api_key.txt
```

`credentials/claude_api_key.txt` を編集（1行のみ）:

```
sk-ant-xxxxx_YOUR_ACTUAL_KEY
```

**または** 環境変数を使用する場合:

```bash
export CLAUDE_API_KEY=sk-ant-xxxxx
```

> ファイル優先で、環境変数はフォールバックとして使用されます。

## 3. 設定ファイル作成

```bash
cp config.yaml.example config.yaml
```

**`config.yaml` には機密情報は含まれません**（すべて `credentials/` に分離）。

デフォルト設定で動作しますが、必要に応じて調整:

```yaml
matching:
  tolerance_percent: 3.0   # 金額許容誤差（%）
  date_range_days: 90      # デフォルト検索範囲
  min_confidence: 0.7      # 最低信頼度

logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
```

## 4. セットアップ検証

```bash
uv run python validate_setup.py
```

すべて ✓ が表示されればOK。✗ がある場合は指示に従って修正してください。

## 5. 初回実行（Dry Run）

```bash
# まずはマッチング結果を確認（freeeに添付しない）
uv run python run.py --dry-run --date-from 2026-02-01 --date-to 2026-02-25
```

### 初回Gmail認証

実行するとブラウザが開きます:

1. Googleアカウントを選択
2. 「このアプリはGoogleで確認されていません」→「詳細」→「（アプリ名）に移動」
3. 「許可」をクリック
4. ターミナルに戻ると処理が続行

`credentials/gmail_token.json` が自動生成されます。

## 6. 結果確認

ログに以下のような結果が表示されます:

```
[INFO] Matching 15 transactions with 23 receipts
[INFO] Matched: Transaction T123 to receipt_1.pdf (amount_diff: 0.5%)
...
[INFO] MATCHING RESULTS
[INFO] Matched: 12
[INFO] Unmatched transactions: 3
[INFO] Unmatched receipts: 11
```

## 7. 本番実行

問題なければ `--dry-run` を外して実行:

```bash
uv run python run.py --date-from 2026-02-01 --date-to 2026-02-25
```

freeeの「自動で経理」画面で領収書が添付されているか確認してください。

## credentials/ ディレクトリの構成

完成すると以下のようになります:

```
credentials/
├── freee.yaml                    # あなたが作成
├── claude_api_key.txt            # あなたが作成
├── gmail_credentials.json        # Google Cloudからダウンロード
├── gmail_token.json              # 初回実行時に自動生成
├── freee.yaml.example            # サンプル
├── claude_api_key.txt.example    # サンプル
└── README.md                     # 説明
```

## トラブルシューティング

### `Failed to load freee credentials`

`credentials/freee.yaml` が存在しない、またはYAML形式が不正:

```bash
cd credentials
cp freee.yaml.example freee.yaml
# 編集して access_token と company_id を設定
```

### `Claude API key not found`

以下のいずれかを実行:

```bash
# 方法1: ファイルで設定（推奨）
echo "sk-ant-xxxxx" > credentials/claude_api_key.txt

# 方法2: 環境変数で設定
export CLAUDE_API_KEY=sk-ant-xxxxx
```

### `gmail_credentials.json not found`

ファイルパスを確認:

```bash
ls -l credentials/gmail_credentials.json
```

存在しない場合はGoogle Cloud Consoleからダウンロードして配置。

### `poppler not found`

```bash
brew install poppler
```

## 日常的な使い方

設定完了後は、定期的に実行するだけ:

```bash
# 過去90日分を処理（デフォルト）
uv run python run.py

# または特定期間
uv run python run.py --date-from 2026-02-01 --date-to 2026-02-28
```

## セキュリティ

- `credentials/` ディレクトリ全体が `.gitignore` 対象
- `config.yaml` も `.gitignore` 対象
- **絶対に `credentials/` の内容をコミットしないでください**

## 次のステップ

- ログを確認して精度をチェック: `tail -f logs/freee-matcher.log`
- 許容誤差を調整: `config.yaml` の `tolerance_percent`
- 定期実行を設定: cron または GitHub Actions
