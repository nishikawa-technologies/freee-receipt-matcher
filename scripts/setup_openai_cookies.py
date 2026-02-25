#!/usr/bin/env python3
"""
OpenAI Cookie セットアップスクリプト

デフォルトブラウザでログインして、Cookieを手動で取得します。

使い方:
    1. このスクリプトを実行
    2. デフォルトブラウザでOpenAIが開く
    3. Googleアカウントでログイン
    4. ブラウザの開発者ツールでCookieをコピー
    5. ターミナルに貼り付け
    6. credentials/openai_cookies.json に保存
"""

import webbrowser
import json
import sys
from pathlib import Path

OPENAI_LOGIN_URL = "https://platform.openai.com/login"
COOKIE_FILE = "credentials/openai_cookies.json"


def main():
    print("=" * 80)
    print("OpenAI Cookie セットアップ")
    print("=" * 80)
    print()
    print("手順:")
    print("1. デフォルトブラウザで OpenAI が開きます")
    print("2. Google アカウントでログイン")
    print("3. ログイン後、以下の手順で Cookie を取得:")
    print()
    print("   【Chrome/Edge の場合】")
    print("   a. F12 キーで開発者ツールを開く")
    print("   b. 'Application' タブをクリック")
    print("   c. 左メニューから 'Cookies' → 'https://platform.openai.com' を選択")
    print("   d. 重要なCookie（__Secure-next-auth.session-token など）をメモ")
    print()
    print("   【または簡易版】")
    print("   a. Chrome拡張 'EditThisCookie' または 'Cookie-Editor' をインストール")
    print("   b. 拡張機能でCookieをJSON形式でエクスポート")
    print()
    print("=" * 80)
    input("\nEnter キーを押してブラウザを開く...")

    # デフォルトブラウザで開く
    print(f"\nブラウザを開いています: {OPENAI_LOGIN_URL}")
    webbrowser.open(OPENAI_LOGIN_URL)

    print()
    print("=" * 80)
    print("Cookie の取得方法（詳細）")
    print("=" * 80)
    print()
    print("【方法1: 開発者ツール（手動）】")
    print("1. ログイン完了後、F12 で開発者ツールを開く")
    print("2. Console タブに移動")
    print("3. 以下のコードを貼り付けて Enter:")
    print()
    print("   copy(JSON.stringify(document.cookie.split('; ').map(c => {")
    print("     const [name, value] = c.split('=');")
    print("     return {name, value, domain: '.openai.com', path: '/'};")
    print("   })))")
    print()
    print("4. クリップボードにCookieがコピーされます")
    print()
    print("【方法2: 拡張機能（推奨）】")
    print("1. Chrome Web Store で 'Cookie-Editor' を検索してインストール")
    print("2. OpenAI にログイン後、拡張機能アイコンをクリック")
    print("3. 'Export' → 'JSON' をクリック")
    print("4. クリップボードにコピーされます")
    print()
    print("=" * 80)
    print()

    # Cookie JSON を入力
    print("取得した Cookie JSON をここに貼り付けてください:")
    print("（複数行の場合は最後に空行を入力して Ctrl+D で終了）")
    print()

    try:
        # 複数行入力を受け付ける
        lines = []
        while True:
            try:
                line = input()
                if not line and lines:  # 空行で終了
                    break
                lines.append(line)
            except EOFError:
                break

        cookie_json = '\n'.join(lines)

        # JSON として検証
        cookies = json.loads(cookie_json)

        if not isinstance(cookies, list):
            print("\n❌ エラー: Cookie は配列形式である必要があります")
            sys.exit(1)

        # 必須フィールドチェック
        for cookie in cookies:
            if not isinstance(cookie, dict):
                print("\n❌ エラー: 各 Cookie はオブジェクトである必要があります")
                sys.exit(1)
            if 'name' not in cookie or 'value' not in cookie:
                print("\n❌ エラー: Cookie には 'name' と 'value' が必要です")
                sys.exit(1)

        # domain を設定（もしなければ）
        for cookie in cookies:
            if 'domain' not in cookie:
                cookie['domain'] = '.openai.com'
            if 'path' not in cookie:
                cookie['path'] = '/'

        # ファイルに保存
        cookie_path = Path(COOKIE_FILE)
        cookie_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cookie_path, 'w') as f:
            json.dump(cookies, f, indent=2)

        print()
        print("=" * 80)
        print("✓ Cookie を保存しました")
        print("=" * 80)
        print(f"ファイル: {COOKIE_FILE}")
        print(f"Cookie 数: {len(cookies)}")
        print()
        print("これで OpenAI スクレイパが使用可能になりました:")
        print()
        print("  uv run python scripts/test_openai_scraper.py --headless")
        print()

    except json.JSONDecodeError as e:
        print(f"\n❌ JSON パースエラー: {e}")
        print("\n有効な JSON 形式で入力してください")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n中断されました")
        sys.exit(1)


if __name__ == "__main__":
    main()
