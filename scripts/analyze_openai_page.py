#!/usr/bin/env python3
"""
OpenAI 請求履歴ページの DOM を解析

実際のページ構造を確認してセレクタを特定する
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.sync_api import sync_playwright

BILLING_URL = "https://platform.openai.com/settings/organization/billing/history"
COOKIE_FILE = "credentials/openai_cookies.json"


def main():
    print("=" * 80)
    print("OpenAI 請求履歴ページ DOM 解析")
    print("=" * 80)
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        # Cookie 読み込み
        with open(COOKIE_FILE, 'r') as f:
            cookies = json.load(f)
            context.add_cookies(cookies)

        page = context.new_page()

        print(f"Navigating to {BILLING_URL}...")
        page.goto(BILLING_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        print(f"Current URL: {page.url}")
        print()

        # ページタイトル
        print(f"Page title: {page.title()}")
        print()

        # HTML を保存
        html_content = page.content()
        html_file = "temp/openai_billing_page.html"
        Path(html_file).parent.mkdir(parents=True, exist_ok=True)
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✓ HTML saved to {html_file}")

        # スクリーンショット
        screenshot_file = "temp/openai_billing_page.png"
        page.screenshot(path=screenshot_file, full_page=True)
        print(f"✓ Screenshot saved to {screenshot_file}")
        print()

        # リンクを探す
        print("=" * 80)
        print("全リンクの解析")
        print("=" * 80)
        print()

        all_links = page.locator('a').all()
        print(f"Total links found: {len(all_links)}")
        print()

        # invoice.stripe.com へのリンク
        stripe_links = [link for link in all_links if link.get_attribute('href') and 'invoice.stripe.com' in link.get_attribute('href')]
        print(f"Stripe invoice links: {len(stripe_links)}")

        if stripe_links:
            print()
            print("Stripe invoice links:")
            for i, link in enumerate(stripe_links[:5], 1):  # 最初の5件
                href = link.get_attribute('href')
                text = link.inner_text().strip() if link.inner_text() else "(no text)"
                print(f"  [{i}] {text}")
                print(f"      URL: {href}")
        print()

        # "View" を含むリンク/ボタン
        print("=" * 80)
        print("'View' を含む要素")
        print("=" * 80)
        print()

        view_elements = page.locator('text=View').all()
        print(f"Elements with 'View' text: {len(view_elements)}")

        if view_elements:
            for i, elem in enumerate(view_elements[:5], 1):
                tag_name = elem.evaluate('el => el.tagName')
                text = elem.inner_text().strip()
                print(f"  [{i}] <{tag_name}> {text}")

                # href があれば表示
                href = elem.get_attribute('href')
                if href:
                    print(f"      href: {href}")
        print()

        # テーブルがあるか確認
        print("=" * 80)
        print("テーブル構造")
        print("=" * 80)
        print()

        tables = page.locator('table').all()
        print(f"Tables found: {len(tables)}")

        if tables:
            for i, table in enumerate(tables, 1):
                rows = table.locator('tr').all()
                print(f"\nTable {i}: {len(rows)} rows")

                # 最初の数行を表示
                for j, row in enumerate(rows[:3], 1):
                    cells = row.locator('td, th').all()
                    cell_texts = [cell.inner_text().strip() for cell in cells]
                    print(f"  Row {j}: {cell_texts}")
        print()

        # div や section で請求履歴を表示している可能性
        print("=" * 80)
        print("請求履歴らしい要素")
        print("=" * 80)
        print()

        # 金額パターンを探す（$XX.XX）
        amount_elements = page.locator('text=/\\$[0-9]+\\.[0-9]{2}/').all()
        print(f"Amount elements ($XX.XX pattern): {len(amount_elements)}")

        if amount_elements:
            print("\nFirst 5 amounts:")
            for i, elem in enumerate(amount_elements[:5], 1):
                text = elem.inner_text().strip()
                # 親要素の情報も取得
                parent_text = elem.locator('..').inner_text().strip()
                print(f"  [{i}] {text}")
                print(f"      Context: {parent_text[:100]}...")
        print()

        # 日付パターンを探す
        date_patterns = [
            'text=/Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec/',
            'text=/\\d{1,2}\\/\\d{1,2}\\/\\d{4}/',
            'text=/\\d{4}-\\d{2}-\\d{2}/',
        ]

        print("Date-like elements:")
        for pattern in date_patterns:
            elements = page.locator(pattern).all()
            if elements:
                print(f"\n  Pattern '{pattern}': {len(elements)} found")
                for elem in elements[:3]:
                    print(f"    - {elem.inner_text().strip()}")

        browser.close()

    print()
    print("=" * 80)
    print("解析完了")
    print("=" * 80)
    print(f"\nHTML ファイルを確認してください: {html_file}")
    print(f"スクリーンショット: {screenshot_file}")


if __name__ == "__main__":
    main()
