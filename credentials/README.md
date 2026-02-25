# credentials/ ディレクトリ

このディレクトリには**機密情報のみ**を配置します。

## 配置するファイル

### 1. freee.yaml
```yaml
access_token: "YOUR_FREEE_ACCESS_TOKEN"
company_id: 123456
```

### 2. claude_api_key.txt
```
sk-ant-xxxxx
```

### 3. gmail_credentials.json
Google Cloud Console からダウンロードした OAuth2 credentials

### 4. gmail_token.json
初回認証時に自動生成されます（自動生成）

---

**⚠️ このディレクトリの内容は絶対にGitにコミットしないでください！**

`.gitignore` で `credentials/` 全体が除外されています。
