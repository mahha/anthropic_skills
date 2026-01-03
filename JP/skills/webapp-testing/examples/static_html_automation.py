from playwright.sync_api import sync_playwright
import os

# 例: file:// URLを使ってローカルの静的HTMLファイルを自動操作する

html_file_path = os.path.abspath('path/to/your/file.html')
file_url = f'file://{html_file_path}'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})

    # ローカルHTMLファイルへ移動
    page.goto(file_url)

    # スクリーンショットを撮る
    page.screenshot(path='/mnt/user-data/outputs/static_page.png', full_page=True)

    # 要素を操作
    page.click('text=Click Me')
    page.fill('#name', 'John Doe')
    page.fill('#email', 'john@example.com')

    # フォーム送信
    page.click('button[type="submit"]')
    page.wait_for_timeout(500)

    # 最終スクリーンショットを撮る
    page.screenshot(path='/mnt/user-data/outputs/after_submit.png', full_page=True)

    browser.close()

print("静的HTMLの自動操作が完了しました！")