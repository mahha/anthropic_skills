from playwright.sync_api import sync_playwright

# 例: ブラウザ自動操作中にコンソールログを収集する

url = 'http://localhost:5173'  # 必要に応じてURLを置き換えてください

console_logs = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})

    # コンソールログ収集を設定
    def handle_console_message(msg):
        console_logs.append(f"[{msg.type}] {msg.text}")
        print(f"Console: [{msg.type}] {msg.text}")

    page.on("console", handle_console_message)

    # ページへ移動
    page.goto(url)
    page.wait_for_load_state('networkidle')

    # ページを操作（コンソールログが発生）
    page.click('text=Dashboard')
    page.wait_for_timeout(1000)

    browser.close()

# コンソールログをファイルへ保存
with open('/mnt/user-data/outputs/console.log', 'w') as f:
    f.write('\n'.join(console_logs))

print(f"\nCaptured {len(console_logs)} console messages")
print(f"Logs saved to: /mnt/user-data/outputs/console.log")