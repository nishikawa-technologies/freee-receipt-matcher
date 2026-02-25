# freee-receipt-matcher — プロジェクト設計メモ

Claude Code がこのファイルを読んで会話コンテキストを引き継ぐためのドキュメント。
蓮との連携ブリッジとして機能する。

---

## プロジェクト概要

freee の「自動で経理」に残っている未処理取引をマスタとして、
Gmail に届いている対応する領収書を自動で探し出し、添付するツール。

**困っている人が多い日本の freee ユーザー向けの OSS。**

---

## ライセンス

MIT

---

## 技術スタック

- Python（バックエンド）
- 将来的に FastAPI + React (TypeScript) で Web UI 化の可能性あり

---

## コアのマッチングロジック

**主キー：日付 × 金額**（取引先名は補助的な確認用）

1. freee API から未処理取引を取得（取引日・金額・取引先名）
2. Gmail API で同期間の領収書メールを検索
3. 添付 PDF または HTML 本文を OCR → LLM (Claude API) で以下を抽出：
   - 取引先名
   - 日付
   - 金額（通貨含む）
4. 日付 × 金額でマッチング
5. USD 建ての場合は取引日の市場レートで JPY 換算して照合（±2〜3% の許容幅）
6. マッチした領収書を freee の対応取引に添付

### 補足

- 大半のサービスは月1回請求なので日付×金額での誤マッチはほぼ起きない
- OpenAI / Anthropic 等のリチャージ型（散発的請求）も金額がユニークなため特定可能
- freee 側の取引先名の表記揺れは気にしない（日付×金額で確定させる）
- USD→JPY はカード会社レートと市場レートの乖離があるため許容幅必須

---

## フェーズ設計

### Phase 1（MVP・今やること）

**目標：じんさん自身が使えるレベルで動くこと**

- Gmail の添付 PDF 領収書のみ対応
- 認証は credentials.json ベタ置きで OK（OAuth フロー不要）
- CLI で `python run.py` 一発で動く
- アーキテクチャの美しさは後回し

```
freee-receipt-matcher/
├── run.py               # エントリポイント
├── freee_client.py      # freee API ラッパー
├── gmail_client.py      # Gmail API ラッパー
├── ocr_ner.py           # LLM による情報抽出
├── matcher.py           # マッチングエンジン
├── fx_rate.py           # 為替レート取得
├── config.yaml          # 設定ファイル（認証情報パス等）
└── credentials/         # .gitignore 対象
    ├── freee_token.json
    └── gmail_credentials.json
```

### Phase 2（拡張）

- Web スクレイピング対応（認証付き）
- Playwright + 既存ブラウザセッション活用（mineo/eo 等）
- プラグインアーキテクチャで各サービスのコネクタを追加
- よく使われる SaaS（AWS, Azure, Slack, Notion, Adobe, Zoom 等）対応
- コミュニティによるコネクタ追加を想定

### Phase 3（将来）

- OAuth フローの整備（ツール作者がアプリ登録 → ユーザーは認可するだけ）
- `pip install freee-receipt-matcher` でインストール可能に
- Web UI（FastAPI + React）

---

## 認証方針（Phase 1）

- **freee**: freee Developer Console でアクセストークン発行、config.yaml に記載
- **Gmail**: Google Cloud Console で OAuth2 credentials.json 発行、ローカルに配置
- **LLM**: Claude API キー（or OpenAI）、環境変数で管理

---

## 為替レート

- USD/JPY の過去レートは外部 API から取得
- 候補: `exchangerate.host` または `open.er-api.com`（無料枠あり）
- 許容幅: ±3%（カード会社レートと市場レートの乖離を吸収）

---

## 開発方針

- まず動くものを作る（完璧主義に陥らない）
- じんさんの実際のユースケースで動いたら Phase 2 へ
- コミット前に credentials/ が含まれていないか必ず確認

---

## 蓮との連携について

このファイルは REN 上でのじんさんとれんの設計議論を Claude Code に引き継ぐためのブリッジ。
設計の変更・決定事項があれば REN 側でこのファイルを更新する。
