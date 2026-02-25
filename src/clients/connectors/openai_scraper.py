#!/usr/bin/env python3
"""
OpenAI 領収書スクレイパ

OpenAI Platform の請求履歴から領収書PDFを取得。
Playwright でブラウザ自動化、認証済みセッションを利用。
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


@dataclass
class OpenAIInvoice:
    """OpenAI 請求書情報"""
    invoice_id: str
    date: datetime
    amount: float
    currency: str
    pdf_url: Optional[str] = None
    pdf_path: Optional[str] = None


class OpenAIScraper:
    """
    OpenAI Platform から領収書を取得するスクレイパ

    使い方:
        scraper = OpenAIScraper(
            email="your@email.com",
            password="your_password",  # またはCookie使用
            headless=True
        )
        invoices = scraper.fetch_invoices(days=90)
        scraper.download_pdfs(invoices, output_dir="./temp")
    """

    BILLING_URL = "https://platform.openai.com/settings/organization/billing"
    BILLING_HISTORY_URL = "https://platform.openai.com/settings/organization/billing/history"
    LOGIN_URL = "https://platform.openai.com/login"

    def __init__(
        self,
        cookie_file: Optional[str] = None,
        headless: bool = True,
        browser_type: str = "chromium",  # chromium, firefox, webkit
        use_google_auth: bool = True,
    ):
        """
        Args:
            cookie_file: 認証済みCookieファイルパス
            headless: ヘッドレスモード
            browser_type: ブラウザタイプ
            use_google_auth: Google認証を使用（デフォルト: True）
        """
        self.cookie_file = cookie_file
        self.headless = headless
        self.browser_type = browser_type
        self.use_google_auth = use_google_auth

    def fetch_invoices(self, days: int = 90) -> List[OpenAIInvoice]:
        """
        過去N日分の請求書を取得

        Args:
            days: 取得日数（デフォルト90日）

        Returns:
            請求書リスト
        """
        logger.info(f"Fetching OpenAI invoices for the past {days} days")

        with sync_playwright() as p:
            browser = self._launch_browser(p)

            # ボット検出回避のための設定
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
            )

            # Cookie認証
            if self.cookie_file and os.path.exists(self.cookie_file):
                logger.info(f"Loading cookies from {self.cookie_file}")
                context.add_cookies(self._load_cookies())

            page = context.new_page()

            try:
                # ログイン or Cookie認証
                logger.info("Checking authentication status...")
                is_auth = self._is_authenticated(page)
                logger.info(f"Already authenticated: {is_auth}")

                if not is_auth:
                    # Cookie が無効な場合は削除
                    if self.cookie_file and os.path.exists(self.cookie_file):
                        logger.warning(f"Cookie が無効です。削除します: {self.cookie_file}")
                        os.remove(self.cookie_file)

                    # ヘッドレスモードの場合はブラウザを再起動
                    if self.headless:
                        logger.info("再認証が必要なため、ブラウザを再起動します...")
                        context.close()
                        browser.close()

                        # 非ヘッドレスで再起動
                        self.headless = False
                        browser = self._launch_browser(p)
                        context = browser.new_context()
                        page = context.new_page()

                    if self.use_google_auth:
                        logger.info("=" * 80)
                        logger.info("Google認証が必要です")
                        logger.info("=" * 80)
                        logger.info("ブラウザで OpenAI にログインしてください")
                        logger.info("'Continue with Google' をクリックして Google アカウントでログイン")
                        logger.info("ログイン完了したらこのターミナルに戻って Enter キーを押してください")
                        logger.info("=" * 80)

                        # ログインページに移動
                        page.goto(self.LOGIN_URL, wait_until="networkidle")

                        input("\nログイン完了したら Enter キーを押す >>> ")

                        # 認証成功を確認
                        if not self._is_authenticated(page):
                            raise ValueError("ログインに失敗しました。もう一度お試しください。")

                        logger.info("✓ ログイン成功")
                    else:
                        raise ValueError("Not authenticated. Use cookie_file or manual login")

                # 請求履歴ページに直接遷移
                logger.info(f"Navigating to billing history: {self.BILLING_HISTORY_URL}")
                page.goto(self.BILLING_HISTORY_URL, wait_until="domcontentloaded", timeout=60000)

                # ページの完全な読み込みを待つ
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)  # テーブルの読み込み待機
                logger.info(f"Billing history page loaded: {page.url}")

                # 請求書を抽出（Stripe経由）
                invoices = self._extract_invoices_from_stripe(page, context, days)

                # Cookie保存（次回用）
                if self.cookie_file:
                    self._save_cookies(context)

                logger.info(f"Found {len(invoices)} invoices")
                return invoices

            finally:
                context.close()
                browser.close()

    def download_pdfs(self, invoices: List[OpenAIInvoice], output_dir: str = "./temp") -> List[OpenAIInvoice]:
        """
        請求書PDFをダウンロード（Stripeページの「領収書をダウンロード」ボタンをクリック）

        Args:
            invoices: 請求書リスト
            output_dir: 保存先ディレクトリ

        Returns:
            PDFパス付き請求書リスト
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading {len(invoices)} PDFs to {output_dir}")

        with sync_playwright() as p:
            browser = self._launch_browser(p)

            # ボット検出回避設定
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                accept_downloads=True,  # ダウンロードを許可
            )

            if self.cookie_file and os.path.exists(self.cookie_file):
                context.add_cookies(self._load_cookies())

            page = context.new_page()

            try:
                for i, invoice in enumerate(invoices, 1):
                    if not invoice.pdf_url:
                        logger.warning(f"No PDF URL for invoice {invoice.invoice_id}")
                        continue

                    logger.info(f"[{i}/{len(invoices)}] Processing invoice {invoice.invoice_id}")

                    try:
                        # Stripeページに移動
                        logger.info(f"Navigating to Stripe invoice page: {invoice.pdf_url}")
                        page.goto(invoice.pdf_url, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(2000)

                        # 領収書ダウンロードボタンを探す
                        download_button = page.locator('[data-testid="download-invoice-receipt-pdf-button"]')

                        if download_button.count() == 0:
                            # data-testidがない場合、テキストで探す
                            download_button = page.locator('button:has-text("領収書をダウンロード"), button:has-text("Download receipt")')

                        if download_button.count() == 0:
                            logger.warning(f"Download button not found for invoice {invoice.invoice_id}")
                            continue

                        # ダウンロード処理
                        pdf_filename = f"openai_{invoice.date.strftime('%Y%m%d')}_{invoice.invoice_id.replace('#', '').replace(' ', '_')}.pdf"
                        pdf_path = output_path / pdf_filename

                        logger.info(f"Clicking download button for {pdf_filename}")

                        # ダウンロードを待機してボタンクリック
                        with page.expect_download(timeout=60000) as download_info:
                            download_button.first.click()

                        download = download_info.value

                        # ダウンロードしたファイルを保存
                        download.save_as(str(pdf_path))
                        invoice.pdf_path = str(pdf_path)

                        logger.info(f"✓ Saved PDF to {pdf_path}")

                    except Exception as e:
                        logger.error(f"Error downloading {invoice.invoice_id}: {e}", exc_info=True)
                        continue

                logger.info(f"Downloaded {len([i for i in invoices if i.pdf_path])} / {len(invoices)} PDFs")
                return invoices

            finally:
                context.close()
                browser.close()

    def _launch_browser(self, playwright) -> Browser:
        """ブラウザ起動"""
        logger.info(f"Launching browser: {self.browser_type}, headless={self.headless}")
        browser_launcher = getattr(playwright, self.browser_type)
        browser = browser_launcher.launch(headless=self.headless)
        logger.info(f"Browser launched successfully")
        return browser

    def _is_authenticated(self, page: Page) -> bool:
        """認証済みかチェック"""
        logger.info(f"Navigating to {self.BILLING_HISTORY_URL} to check authentication...")
        try:
            page.goto(self.BILLING_HISTORY_URL, wait_until="domcontentloaded", timeout=60000)

            # ページが読み込まれるまで待機
            page.wait_for_timeout(3000)

            current_url = page.url
            logger.info(f"Current URL: {current_url}")

            # 1. URL が login にリダイレクトされた
            if "login" in current_url.lower():
                logger.info("Redirected to login page")
                return False

            # 2. 請求履歴テーブルが存在するか（ログイン済みの証拠）
            table_exists = page.locator('table.billing-history-table').count() > 0
            if table_exists:
                logger.info("Billing history table found - authenticated")
                return True

            # 3. Settings サイドバーが存在するか
            settings_sidebar = page.locator('text=Settings').count() > 0
            if settings_sidebar:
                logger.info("Settings sidebar found - authenticated")
                return True

            # 4. ユーザーアバターが表示されているか
            user_avatar = page.locator('button[aria-haspopup="menu"]').count() > 0
            if user_avatar:
                logger.info("User avatar menu found - authenticated")
                return True

            # どれも見つからない = 未認証
            logger.info("No authenticated content found")
            return False

        except Exception as e:
            logger.error(f"Error checking authentication: {e}")
            return False

    def _login_google(self, page: Page):
        """
        Google認証でログイン

        Note: Google認証は手動操作が必要。
        ヘッドレスOFFで実行し、初回のみ手動ログインしてCookie保存。
        """
        logger.info("Google認証を開始します")
        page.goto(self.LOGIN_URL, wait_until="networkidle")

        # "Continue with Google" ボタンをクリック
        try:
            google_button = page.get_by_role("button", name="Continue with Google")
            if google_button.is_visible():
                google_button.click()
                logger.info("Google認証ボタンをクリックしました")
        except Exception as e:
            logger.warning(f"Google認証ボタンが見つかりません: {e}")
            logger.info("手動でログインしてください")

    def _extract_invoices_from_stripe(self, page: Page, context, days: int) -> List[OpenAIInvoice]:
        """
        OpenAI請求履歴ページのテーブルからStripe請求書リンクを抽出し、
        各Stripeページから領収書情報を取得

        フロー:
        1. 請求履歴テーブルからStripe invoice URLを抽出
        2. 各URLを新しいタブで開く
        3. Stripeページから日付・金額・PDF URLを取得
        """
        invoices = []
        cutoff_date = datetime.now() - timedelta(days=days)

        logger.info("請求履歴テーブルからStripe請求書リンクを抽出中...")

        # デバッグ用スクリーンショット
        screenshot_path = "temp/openai_billing_page.png"
        try:
            os.makedirs("temp", exist_ok=True)
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot saved to {screenshot_path}")
        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e}")

        # Stripe 請求書リンクを探す（テーブル内のリンク）
        logger.info("Searching for Stripe invoice links in billing history table...")

        # invoice.stripe.com へのリンクを探す
        stripe_links = page.locator('a[href*="invoice.stripe.com"]').all()

        logger.info(f"Found {len(stripe_links)} Stripe invoice links")

        if len(stripe_links) == 0:
            logger.warning("No Stripe invoice links found in the table")
            # テーブルの存在確認
            table_count = page.locator('table.billing-history-table').count()
            logger.info(f"Billing history table count: {table_count}")
            return invoices

        for i, link in enumerate(stripe_links):
            try:
                logger.info(f"Processing invoice {i+1}/{len(stripe_links)}")

                # リンクのURLを取得
                stripe_url = link.get_attribute("href")
                if not stripe_url:
                    logger.warning(f"Link {i+1} has no href attribute")
                    continue

                logger.info(f"Stripe URL: {stripe_url}")

                # 新しいタブでStripeページを開く
                stripe_page = context.new_page()
                stripe_page.goto(stripe_url, wait_until="domcontentloaded", timeout=60000)
                stripe_page.wait_for_timeout(2000)

                logger.info(f"Stripe page loaded: {stripe_page.url}")

                # Stripeページから情報を抽出
                invoice = self._extract_from_stripe_page(stripe_page, cutoff_date)

                if invoice:
                    invoices.append(invoice)
                    logger.info(f"Extracted: {invoice.date.strftime('%Y-%m-%d')} - ${invoice.amount}")

                # Stripeページを閉じる
                stripe_page.close()

            except Exception as e:
                logger.error(f"Failed to process invoice {i+1}: {e}")
                continue

        return invoices

    def _extract_from_stripe_page(self, page: Page, cutoff_date: datetime) -> Optional[OpenAIInvoice]:
        """
        Stripeページから請求書情報を抽出し、領収書PDFをダウンロード

        Args:
            page: Stripeページ
            cutoff_date: カットオフ日付

        Returns:
            請求書情報（期間外ならNone）
        """
        try:
            # ページ読み込み待機
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

            # デバッグ用スクリーンショット
            screenshot_path = f"temp/stripe_invoice_{int(datetime.now().timestamp())}.png"
            try:
                os.makedirs("temp", exist_ok=True)
                page.screenshot(path=screenshot_path)
                logger.info(f"Stripe page screenshot saved to {screenshot_path}")
            except Exception as e:
                logger.warning(f"Failed to save screenshot: {e}")

            # 日付を抽出（Stripeの日本語ページ対応）
            date_text = None
            import re

            # 方法1: テーブル内の「支払い日」を探す
            rows = page.locator('tr.LabeledTableRow').all()
            for row in rows:
                cells = row.locator('td').all()
                if len(cells) >= 2:
                    label = cells[0].inner_text().strip()
                    value = cells[1].inner_text().strip()
                    if '支払い日' in label or 'Date' in label:
                        date_text = value
                        logger.info(f"Found date from table: {date_text}")
                        break

            # 方法2: ページ全体から日付パターンを探す
            if not date_text:
                page_text = page.inner_text()
                # "2026年2月25日" 形式（日本語）
                match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', page_text)
                if match:
                    year, month, day = match.groups()
                    date_text = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    logger.info(f"Found Japanese date: {date_text}")
                else:
                    # "January 15, 2026" 形式（英語）
                    match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})', page_text)
                    if match:
                        date_text = match.group(0)
                        logger.info(f"Found English date: {date_text}")

            if not date_text:
                logger.warning("Could not find invoice date on Stripe page")
                return None

            # 日付パース（複数フォーマット対応）
            invoice_date = None
            for fmt in ["%Y-%m-%d", "%Y年%m月%d日", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"]:
                try:
                    invoice_date = datetime.strptime(date_text.strip(), fmt)
                    logger.info(f"Parsed date: {invoice_date} using format {fmt}")
                    break
                except:
                    continue

            if not invoice_date:
                logger.warning(f"Could not parse date: {date_text}")
                return None

            if invoice_date < cutoff_date:
                logger.debug(f"Invoice date {invoice_date} is outside range")
                return None

            # 金額を抽出（data-testid使用）
            amount_text = None

            # 方法1: data-testid="invoice-amount-post-payment"
            amount_elem = page.locator('[data-testid="invoice-amount-post-payment"]')
            if amount_elem.count() > 0:
                amount_text = amount_elem.locator('.CurrencyAmount').inner_text()
                logger.info(f"Found amount via data-testid: {amount_text}")

            # 方法2: ページ全体から金額パターンを探す
            if not amount_text:
                page_text = page.inner_text()
                # $1,234.56 形式
                matches = re.findall(r'\$[0-9,]+\.[0-9]{2}', page_text)
                if matches:
                    # 最初の金額を使用（通常、最初が合計金額）
                    amount_text = matches[0]
                    logger.info(f"Found amount from page text: {amount_text}")

            if not amount_text:
                logger.warning("Could not find invoice amount on Stripe page")
                return None

            amount_str = amount_text.replace("$", "").replace(",", "").strip()
            amount = float(amount_str)

            # 請求書番号を抽出
            invoice_number = None
            for row in rows:
                cells = row.locator('td').all()
                if len(cells) >= 2:
                    label = cells[0].inner_text().strip()
                    value = cells[1].inner_text().strip()
                    if '請求書番号' in label or 'Invoice' in label:
                        invoice_number = value
                        logger.info(f"Found invoice number: {invoice_number}")
                        break

            if not invoice_number:
                invoice_number = f"openai_{invoice_date.strftime('%Y%m%d')}_{int(amount*100)}"

            # 領収書PDFのURL（ボタンから取得）
            pdf_url = page.url  # デフォルトは現在のページURL

            return OpenAIInvoice(
                invoice_id=invoice_number,
                date=invoice_date,
                amount=amount,
                currency="USD",
                pdf_url=pdf_url,
            )

        except Exception as e:
            logger.error(f"Failed to extract from Stripe page: {e}", exc_info=True)
            return None

    def _load_cookies(self) -> List[dict]:
        """Cookieファイルから読み込み"""
        import json
        with open(self.cookie_file, "r") as f:
            return json.load(f)

    def _save_cookies(self, context):
        """Cookieを保存"""
        import json
        cookies = context.cookies()
        with open(self.cookie_file, "w") as f:
            json.dump(cookies, f, indent=2)
        logger.info(f"Saved cookies to {self.cookie_file}")


if __name__ == "__main__":
    # テスト実行例
    import sys

    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("OpenAI スクレイパ - 直接実行")
    print("=" * 80)
    print("推奨: scripts/test_openai_scraper.py を使用してください")
    print("=" * 80)

    scraper = OpenAIScraper(
        cookie_file="credentials/openai_cookies.json",
        headless=False,  # ヘッドレスOFFでデバッグ
        use_google_auth=True,
    )

    # 過去90日分の請求書取得
    invoices = scraper.fetch_invoices(days=90)

    print(f"\nFound {len(invoices)} invoices:")
    for inv in invoices:
        print(f"  {inv.date.strftime('%Y-%m-%d')} - ${inv.amount:.2f} ({inv.invoice_id})")

    # PDFダウンロード
    if invoices:
        scraper.download_pdfs(invoices, output_dir="./temp")
        print(f"\nDownloaded {len([i for i in invoices if i.pdf_path])} PDFs")
