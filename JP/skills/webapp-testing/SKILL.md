---
name: webapp-testing
description: Playwrightを使用してローカルWebアプリケーションと対話し、テストするためのツールキット。フロントエンド機能の検証、UI動作のデバッグ、ブラウザスクリーンショットのキャプチャ、ブラウザログの表示をサポートします。
license: 完全な条件はLICENSE.txtに記載されています
---

# Webアプリケーションテスト

ローカルWebアプリケーションをテストするには、ネイティブPython Playwrightスクリプトを作成します。

**利用可能なヘルパースクリプト**：
- `scripts/with_server.py` - サーバーライフサイクルを管理（複数のサーバーをサポート）

**スクリプトは常に最初に`--help`を実行して**使用方法を確認してください。カスタマイズされたソリューションが絶対に必要であることが判明するまで、ソースを読み取らないでください。これらのスクリプトは非常に大きく、コンテキストウィンドウを汚染する可能性があります。これらは、コンテキストウィンドウに取り込むのではなく、ブラックボックススクリプトとして直接呼び出されるように存在します。

## 意思決定ツリー：アプローチの選択

```
ユーザータスク → 静的HTMLですか？
    ├─ はい → セレクタを識別するためにHTMLファイルを直接読み取る
    │         ├─ 成功 → セレクタを使用してPlaywrightスクリプトを作成
    │         └─ 失敗/不完全 → 動的として処理（以下を参照）
    │
    └─ いいえ（動的Webアプリ） → サーバーは既に実行中ですか？
        ├─ いいえ → 実行: python scripts/with_server.py --help
        │       その後、ヘルパーを使用して簡略化されたPlaywrightスクリプトを作成
        │
        └─ はい → 偵察-その後-アクション：
            1. ナビゲートしてnetworkidleを待つ
            2. スクリーンショットを撮るかDOMを検査
            3. レンダリングされた状態からセレクタを識別
            4. 発見されたセレクタでアクションを実行
```

## 例：with_server.pyの使用

サーバーを起動するには、まず`--help`を実行してから、ヘルパーを使用します：

**単一サーバー：**
```bash
python scripts/with_server.py --server "npm run dev" --port 5173 -- python your_automation.py
```

**複数サーバー（例：バックエンド + フロントエンド）：**
```bash
python scripts/with_server.py \
  --server "cd backend && python server.py" --port 3000 \
  --server "cd frontend && npm run dev" --port 5173 \
  -- python your_automation.py
```

自動化スクリプトを作成するには、Playwrightロジックのみを含めます（サーバーは自動的に管理されます）：
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True) # 常にchromiumをヘッドレスモードで起動
    page = browser.new_page()
    page.goto('http://localhost:5173') # サーバーは既に実行中で準備完了
    page.wait_for_load_state('networkidle') # 重要：JSの実行を待つ
    # ... あなたの自動化ロジック
    browser.close()
```

## 偵察-その後-アクションパターン

1. **レンダリングされたDOMを検査**：
   ```python
   page.screenshot(path='/tmp/inspect.png', full_page=True)
   content = page.content()
   page.locator('button').all()
   ```

2. **検査結果からセレクタを識別**

3. **発見されたセレクタを使用してアクションを実行**

## よくある落とし穴

❌ **動的アプリでnetworkidleを待つ前にDOMを検査しないでください**
✅ **検査前に`page.wait_for_load_state('networkidle')`を待ちます**

## ベストプラクティス

- **バンドルされたスクリプトをブラックボックスとして使用** - タスクを達成するには、`scripts/`で利用可能なスクリプトのいずれかが役立つかどうかを検討します。これらのスクリプトは、コンテキストウィンドウを汚染することなく、一般的で複雑なワークフローを確実に処理します。`--help`を使用して使用方法を確認し、直接呼び出します。
- 同期スクリプトには`sync_playwright()`を使用
- 完了したら常にブラウザを閉じる
- 説明的なセレクタを使用：`text=`、`role=`、CSSセレクタ、またはID
- 適切な待機を追加：`page.wait_for_selector()`または`page.wait_for_timeout()`

## リファレンスファイル

- **examples/** - 一般的なパターンを示す例：
  - `element_discovery.py` - ページ上のボタン、リンク、入力の検出
  - `static_html_automation.py` - ローカルHTML用のfile:// URLの使用
  - `console_logging.py` - 自動化中にコンソールログをキャプチャ

