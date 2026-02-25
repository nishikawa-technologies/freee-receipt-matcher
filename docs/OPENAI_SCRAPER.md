# OpenAI 領収書スクレイパ

OpenAI Platform の請求履歴から領収書PDFを自動取得するスクレイパ（Phase 2機能）。

## 概要

- **対象**: OpenAI Platform (https://platform.openai.com)
- **取得内容**: Stripe経由の請求書PDF（過去90日分など）
- **認証**: Google OAuth（Cookie保存で2回目以降は自動）
- **技術**: Playwright（ブラウザ自動化）

## 仕組み

1. OpenAI Platform の請求履歴ページにアクセス
2. 各請求の "View" ボタンをクリック
3. 新しいタブでStripeページが開く
4. Stripeページから領収書PDFのURLを取得
5. PDFをダウンロード

## セットアップ

### 1. Playwright インストール

```bash
# requirements.txt に playwright を追加済み
uv pip install playwright

# ブラウザバイナリをインストール
playwright install chromium
```

### 2. Cookie セットアップ（推奨）

**デフォルトブラウザで認証して Cookie を取得する方法（推奨）:**

```bash
uv run python scripts/setup_openai_cookies.py
```

**フロー:**
1. デフォルトブラウザで OpenAI が開く
2. Google アカウントでログイン
3. ブラウザの開発者ツールまたは拡張機能で Cookie を取得
4. ターミナルに Cookie JSON を貼り付け
5. `credentials/openai_cookies.json` に自動保存

**Cookie 取得方法（推奨: Chrome 拡張機能）:**

1. [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) をインストール
2. OpenAI にログイン
3. 拡張機能アイコンをクリック → 'Export' → 'JSON'
4. クリップボードにコピーされる
5. セットアップスクリプトに貼り付け

### 3. 代替: Chromium で直接認証

Cookie セットアップの代わりに Chromium で直接認証も可能:

```bash
uv run python scripts/test_openai_scraper.py
```

この場合、Chromium ブラウザが開き、手動ログインが必要です。

### 4. 2回目以降（自動ログイン）

Cookie保存後は自動ログイン可能:

```bash
# ヘッドレスモードで高速実行
uv run python scripts/test_openai_scraper.py --headless
```

## 使い方

### 基本実行

```bash
# 過去90日分の請求書を取得
uv run python scripts/test_openai_scraper.py
```

### オプション

```bash
# 過去30日分のみ取得
uv run python scripts/test_openai_scraper.py --days 30

# ヘッドレスモード（Cookie保存済みの場合）
uv run python scripts/test_openai_scraper.py --headless

# PDF保存先を指定
uv run python scripts/test_openai_scraper.py --output-dir ./invoices
```

## プログラムから使用

```python
from src.clients.connectors import OpenAIScraper

# スクレイパ初期化
scraper = OpenAIScraper(
    cookie_file="credentials/openai_cookies.json",
    headless=True,  # Cookie保存済みならヘッドレスOK
    use_google_auth=True,
)

# 過去90日分の請求書取得
invoices = scraper.fetch_invoices(days=90)

# PDFダウンロード（請求書情報にPDF URLが含まれる）
scraper.download_pdfs(invoices, output_dir="./temp")

# 結果確認
for invoice in invoices:
    print(f"{invoice.date} - ${invoice.amount} - {invoice.pdf_path}")
```

## run.py との統合（将来）

将来的には `run.py` に統合して、Gmail以外のソースからも領収書を取得可能にする予定:

```bash
# Gmail + OpenAI の両方から領収書取得
uv run python run.py --sources gmail,openai
```

## トラブルシューティング

### Playwright not installed

```bash
playwright install chromium
```

### Cookie が保存されない

初回実行時にブラウザで手動ログインした後、必ず**ターミナルで Enter キーを押す**必要があります。
これによりCookieが保存されます。

### "View" ボタンが見つからない

OpenAIのUIが変更された可能性があります。
`openai_scraper.py` の `_extract_invoices_from_stripe()` メソッドのセレクタを確認してください:

```python
view_buttons = page.get_by_role("button", name="View").all()
```

ブラウザの開発者ツールでボタンの実際のテキストや属性を確認して調整してください。

### Stripe ページで情報抽出に失敗

Stripeページの構造が変更された場合、`_extract_from_stripe_page()` メソッドのセレクタを更新:

```python
# 日付
date_text = page.locator('[data-testid="invoice-date"]').inner_text()

# 金額
amount_text = page.locator('[data-testid="invoice-amount"]').inner_text()

# 領収書リンク
receipt_link = page.get_by_role("link", name="Receipt")
```

開発者ツールで実際の構造を確認して調整してください。

## セキュリティ

- **Cookie ファイル**: `credentials/openai_cookies.json` は `.gitignore` 対象
- **Google OAuth**: セキュアな認証フロー（パスワード保存不要）
- **初回のみ手動**: Cookie保存後は自動ログイン

## 制限事項

- OpenAIのUI変更により動作しなくなる可能性あり（メンテナンスが必要）
- 大量リクエストはRate Limitに注意
- 2要素認証(2FA)有効時はCookie認証のみ対応

## 今後の拡張

Phase 2で他のSaaSコネクタも追加予定:

- `anthropic_scraper.py` - Anthropic Console
- `aws_scraper.py` - AWS Billing
- `azure_scraper.py` - Azure Portal
- `slack_scraper.py` - Slack 請求
