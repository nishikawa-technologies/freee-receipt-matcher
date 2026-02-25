# セキュリティガイド

freee-receipt-matcherの機密情報管理について。

## 設計思想

**すべての機密情報を `credentials/` ディレクトリに集約し、Git管理から完全に除外する。**

## ファイル構成

### Git管理対象（安全）

```
config.yaml.example          # 設定サンプル（機密情報なし）
credentials/.gitkeep         # ディレクトリ維持用
credentials/README.md        # 説明
credentials/*.example        # サンプルファイル
```

### Git管理対象外（機密情報）

```
credentials/freee.yaml              # freee API トークン・会社ID
credentials/claude_api_key.txt      # Claude API キー
credentials/gmail_credentials.json  # Gmail OAuth2 認証情報
credentials/gmail_token.json        # Gmail アクセストークン（自動生成）
config.yaml                         # 設定ファイル（パスのみ、念のため除外）
```

## .gitignore 構造

```gitignore
# credentials/ 内のすべてを除外
credentials/*

# 例外: サンプル・ドキュメントのみ含める
!credentials/*.example
!credentials/README.md
!credentials/.gitkeep

# config.yamlも除外（念のため）
config.yaml
```

## セットアップフロー

### 1. リポジトリクローン

```bash
git clone https://github.com/yourusername/freee-receipt-matcher.git
cd freee-receipt-matcher
```

### 2. 機密情報の配置

```bash
# freee認証情報
cd credentials
cp freee.yaml.example freee.yaml
# 編集して実際のトークンを設定

# Claude APIキー
cp claude_api_key.txt.example claude_api_key.txt
# 編集して実際のキーを設定

# Gmail OAuth2認証情報
# Google Cloud Consoleからダウンロードして配置
mv ~/Downloads/credentials.json gmail_credentials.json
```

### 3. 検証

```bash
cd ..
uv run python validate_setup.py
```

## コミット前チェックリスト

コミット前に以下を必ず確認:

```bash
# 1. git statusで credentials/ 内の機密情報が含まれていないか確認
git status

# 期待される出力（credentials/は?? credentials/のみ）:
# ?? .gitignore
# ?? config.yaml.example
# ?? credentials/     ← これのみOK
# ?? ...

# 2. git addのdry-runで追加されるファイルを確認
git add -n credentials/

# 期待される出力:
# add 'credentials/.gitkeep'
# add 'credentials/README.md'
# add 'credentials/*.example'
# ← .yaml, .json, .txt（サンプル以外）は含まれないこと

# 3. 問題なければコミット
git add .
git commit -m "..."
```

## 緊急対応：機密情報をコミットしてしまった場合

### リモートにpush前

```bash
# 直前のコミットを取り消し
git reset --soft HEAD~1

# または特定ファイルのみstaging解除
git restore --staged credentials/freee.yaml
```

### リモートにpush済み

**絶対にやるべきこと:**

1. **即座にトークンを無効化**
   - freee: Developer Consoleでトークン削除・再発行
   - Claude: Anthropic Consoleでキー削除・再発行
   - Gmail: Google Cloud Consoleで認証情報削除・再作成

2. **Git履歴から削除**（完全削除は困難）
   ```bash
   # リポジトリを削除して作り直すのが最も確実
   ```

3. **監視**
   - 不正利用がないか監視
   - freee: APIアクセスログ確認
   - Claude: 使用量ダッシュボード確認

## ベストプラクティス

### DO（推奨）

- ✅ 機密情報はすべて `credentials/` に配置
- ✅ コミット前に `git status` と `git add -n` で確認
- ✅ 定期的にトークンをローテーション
- ✅ `validate_setup.py` でセットアップ検証
- ✅ `.gitignore` を絶対に編集しない（機密情報除外を緩めない）

### DON'T（禁止）

- ❌ config.yamlに機密情報を直接記載
- ❌ ソースコードにトークンをハードコード
- ❌ credentials/ を `.gitignore` から削除
- ❌ トークンをSlack/Discord等にコピペ
- ❌ スクリーンショットにトークンを含める

## 環境変数の使用（オプション）

ファイルの代わりに環境変数も使用可能（ただしファイル優先）:

```bash
# ~/.zshrc または ~/.bashrc
export CLAUDE_API_KEY=sk-ant-xxxxx

# config.yamlで api_key_env を有効化
llm:
  api_key_env: "CLAUDE_API_KEY"
```

**注意**: 環境変数もシェル履歴に残るため、設定ファイル推奨。

## まとめ

- **原則**: `credentials/` = 機密情報のみ
- **確認**: コミット前に必ず `git status` と `git add -n`
- **緊急時**: トークンの即座無効化
