# scripts/ ディレクトリ

開発・デバッグ用のユーティリティスクリプト集。

## デバッグ用スクリプト

### check_duplicate_transaction.py
特定日付の取引の重複を確認するスクリプト。

```bash
uv run python scripts/check_duplicate_transaction.py
```

### check_duplicates.py
最近添付した取引の領収書重複を確認。

```bash
uv run python scripts/check_duplicates.py
```

### check_go_emails.py
Gmail API でGO領収書メールを検索して添付ファイル数を確認。

```bash
uv run python scripts/check_go_emails.py
```

### verify_data_preservation.py
領収書添付前後でデータが保持されているか検証。

```bash
uv run python scripts/verify_data_preservation.py
```

## テストスクリプト

### debug_matching.py
マッチングロジックの詳細デバッグ。

### inspect_deal.py
特定の取引詳細を表示。

### test_attach_*.py
領収書添付APIの動作テスト（複数バージョン）。

### test_check_deal_fields.py
取引フィールドの確認テスト。

### test_deals_api.py
freee Deals APIの動作確認。

### test_fx_api.py
為替レートAPI取得テスト。

## 使い方

これらのスクリプトは開発・デバッグ目的で使用します。
本番運用では `run.py` を使用してください。

**注意**: これらのスクリプトは実際のAPI（freee, Gmail等）を呼び出すため、
実行すると実データに影響する可能性があります。
