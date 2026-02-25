#!/usr/bin/env python3
"""
セットアップ検証スクリプト
必要な設定・認証情報が揃っているか確認
"""

import os
import sys
from pathlib import Path

import yaml

# カラー出力
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def check(condition, message):
    """チェック結果を表示"""
    if condition:
        print(f"{GREEN}✓{RESET} {message}")
        return True
    else:
        print(f"{RED}✗{RESET} {message}")
        return False


def warn(message):
    """警告を表示"""
    print(f"{YELLOW}⚠{RESET} {message}")


def main():
    print("=" * 60)
    print("freee-receipt-matcher セットアップ検証")
    print("=" * 60)
    print()

    all_ok = True

    # 1. Python バージョン
    print("1. Python バージョン")
    python_version = sys.version_info
    ok = check(
        python_version >= (3, 9),
        f"Python {python_version.major}.{python_version.minor} (要: 3.9以上)",
    )
    all_ok = all_ok and ok
    print()

    # 2. 依存パッケージ
    print("2. 依存パッケージ")

    packages = [
        "requests",
        "yaml",
        "anthropic",
        "pdf2image",
        "PIL",
        "google.auth",
        "googleapiclient",
    ]

    for pkg in packages:
        try:
            __import__(pkg)
            check(True, f"{pkg} インストール済み")
        except ImportError:
            check(False, f"{pkg} 未インストール → pip install -r requirements.txt")
            all_ok = False
    print()

    # 3. poppler
    print("3. システム依存")
    import shutil

    poppler = shutil.which("pdfinfo") or shutil.which("pdftoppm")
    ok = check(poppler, "poppler インストール済み")
    if not ok:
        print("   → brew install poppler (macOS)")
        print("   → sudo apt-get install poppler-utils (Ubuntu)")
        all_ok = False
    print()

    # 4. 設定ファイル
    print("4. 設定ファイル")
    config_exists = Path("config.yaml").exists()
    ok = check(config_exists, "config.yaml 存在")

    if not ok:
        print("   → cp config.yaml.example config.yaml")
        all_ok = False
    print()

    # 5. credentials/ ディレクトリ
    print("5. credentials/ ディレクトリ")

    # freee認証情報
    freee_yaml = Path("credentials/freee.yaml")
    ok = check(freee_yaml.exists(), "freee.yaml 配置済み")
    if not ok:
        print("   → cd credentials && cp freee.yaml.example freee.yaml")
        print("   → credentials/freee.yaml を編集してトークンを設定")
        all_ok = False
    else:
        # freee.yamlの中身をチェック
        try:
            with open(freee_yaml) as f:
                freee_data = yaml.safe_load(f)
                token = freee_data.get("access_token")
                company = freee_data.get("company_id")

                if token and "YOUR_FREEE" not in token:
                    check(True, "  freee access_token 設定済み")
                else:
                    check(False, "  freee access_token 未設定")
                    all_ok = False

                if company and company != 0:
                    check(True, "  freee company_id 設定済み")
                else:
                    check(False, "  freee company_id 未設定")
                    all_ok = False
        except Exception as e:
            check(False, f"  freee.yaml読み込みエラー: {e}")
            all_ok = False

    # Gmail認証情報
    gmail_creds = Path("credentials/gmail_credentials.json")
    ok = check(gmail_creds.exists(), "gmail_credentials.json 配置済み")
    if not ok:
        print("   → Google Cloud Console で OAuth2 credentials.json をダウンロード")
        print("   → credentials/gmail_credentials.json に配置")
        all_ok = False

    gmail_token = Path("credentials/gmail_token.json")
    if gmail_token.exists():
        check(True, "gmail_token.json 存在（認証済み）")
    else:
        warn("gmail_token.json 未作成（初回実行時に認証が必要）")

    # Claude APIキー
    claude_file = Path("credentials/claude_api_key.txt")
    claude_env = os.environ.get("CLAUDE_API_KEY")

    if claude_file.exists():
        try:
            with open(claude_file) as f:
                key = f.read().strip()
                if key and not key.startswith("sk-ant-xxxxx"):
                    check(True, "claude_api_key.txt 設定済み")
                else:
                    check(False, "claude_api_key.txt に実際のキーを設定")
                    all_ok = False
        except Exception as e:
            check(False, f"claude_api_key.txt 読み込みエラー: {e}")
            all_ok = False
    elif claude_env:
        check(True, "CLAUDE_API_KEY 環境変数設定済み")
    else:
        check(False, "Claude APIキー未設定")
        print("   → echo 'sk-ant-xxxxx' > credentials/claude_api_key.txt")
        print("   → または export CLAUDE_API_KEY=sk-ant-xxxxx")
        all_ok = False

    print()

    # 6. ディレクトリ
    print("6. 作業ディレクトリ")
    for dir_name in ["cache", "temp", "logs", "credentials"]:
        dir_path = Path(dir_name)
        check(dir_path.exists() and dir_path.is_dir(), f"{dir_name}/ 存在")
    print()

    # サマリー
    print("=" * 60)
    if all_ok:
        print(f"{GREEN}✓ セットアップ完了！{RESET}")
        print()
        print("次のコマンドで実行できます:")
        print()
        print("  python run.py --dry-run --date-from 2026-02-01 --date-to 2026-02-25")
        print()
    else:
        print(f"{RED}✗ セットアップ未完了{RESET}")
        print()
        print("上記の ✗ 項目を修正してください。")
        print("詳細は QUICKSTART.md を参照してください。")
        print()
    print("=" * 60)

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
