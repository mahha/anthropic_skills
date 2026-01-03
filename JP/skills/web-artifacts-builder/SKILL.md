---
name: web-artifacts-builder
description: モダンなフロントエンドWebテクノロジー（React、Tailwind CSS、shadcn/ui）を使用して、精巧なマルチコンポーネントclaude.ai HTML成果物を作成するためのツールスイート。状態管理、ルーティング、またはshadcn/uiコンポーネントを必要とする複雑な成果物に使用 - シンプルな単一ファイルHTML/JSX成果物には使用しないでください。
license: 完全な条件はLICENSE.txtに記載されています
---

# Web成果物ビルダー

強力なフロントエンドclaude.ai成果物を構築するには、以下の手順に従います：
1. `scripts/init-artifact.sh`を使用してフロントエンドリポジトリを初期化
2. 生成されたコードを編集して成果物を開発
3. `scripts/bundle-artifact.sh`を使用してすべてのコードを単一のHTMLファイルにバンドル
4. 成果物をユーザーに表示
5. （オプション）成果物をテスト

**スタック**: React 18 + TypeScript + Vite + Parcel（バンドリング）+ Tailwind CSS + shadcn/ui

## デザイン＆スタイルガイドライン

非常に重要：しばしば「AIスラップ」と呼ばれるものを避けるために、過度な中央揃えレイアウト、紫のグラデーション、統一された角丸、Interフォントの使用を避けてください。

## クイックスタート

### ステップ1：プロジェクトの初期化

新しいReactプロジェクトを作成するために初期化スクリプトを実行します：
```bash
bash scripts/init-artifact.sh <project-name>
cd <project-name>
```

これにより、以下が完全に設定されたプロジェクトが作成されます：
- ✅ React + TypeScript（Vite経由）
- ✅ shadcn/uiテーマシステム付きTailwind CSS 3.4.1
- ✅ パスエイリアス（`@/`）が設定済み
- ✅ 40以上のshadcn/uiコンポーネントが事前インストール済み
- ✅ すべてのRadix UI依存関係が含まれています
- ✅ Parcelがバンドリング用に設定済み（.parcelrc経由）
- ✅ Node 18+互換性（自動検出してViteバージョンを固定）

### ステップ2：成果物の開発

成果物を構築するには、生成されたファイルを編集します。ガイダンスについては、以下の**一般的な開発タスク**を参照してください。

### ステップ3：単一HTMLファイルにバンドル

Reactアプリを単一のHTML成果物にバンドルするには：
```bash
bash scripts/bundle-artifact.sh
```

これにより、`bundle.html`が作成されます - すべてのJavaScript、CSS、依存関係がインライン化された自己完結型の成果物です。このファイルは、Claude会話で成果物として直接共有できます。

**要件**: プロジェクトにはルートディレクトリに`index.html`が必要です。

**スクリプトが行うこと**：
- バンドリング依存関係をインストール（parcel、@parcel/config-default、parcel-resolver-tspaths、html-inline）
- パスエイリアスサポート付き`.parcelrc`設定を作成
- Parcelでビルド（ソースマップなし）
- html-inlineを使用してすべてのアセットを単一のHTMLにインライン化

### ステップ4：成果物をユーザーと共有

最後に、ユーザーが成果物として表示できるように、会話でバンドルされたHTMLファイルを共有します。

### ステップ5：成果物のテスト/視覚化（オプション）

注意：これは完全にオプションのステップです。必要または要求された場合のみ実行してください。

成果物をテスト/視覚化するには、利用可能なツール（他のスキルやPlaywrightやPuppeteerなどの組み込みツールを含む）を使用します。一般的に、成果物を事前にテストするのは避けてください。リクエストと完成した成果物が表示されるまでの間にレイテンシが追加されるためです。成果物を提示した後、要求された場合、または問題が発生した場合に後でテストします。

## リファレンス

- **shadcn/uiコンポーネント**: https://ui.shadcn.com/docs/components

