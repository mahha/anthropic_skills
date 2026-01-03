---
name: pptx
description: "プレゼンテーションの作成、編集、分析。Claudeがプレゼンテーション（.pptxファイル）で作業する必要がある場合：(1) 新しいプレゼンテーションを作成、(2) コンテンツを変更または編集、(3) レイアウトで作業、(4) コメントまたはスピーカーノートを追加、またはその他のプレゼンテーションタスク"
license: プロプライエタリ。完全な条件はLICENSE.txtに記載されています
---

# PPTX作成、編集、分析

## 概要

ユーザーが.pptxファイルの作成、編集、または内容の分析を依頼する場合があります。.pptxファイルは、基本的に読み取りまたは編集できるXMLファイルとその他のリソースを含むZIPアーカイブです。タスクごとに異なるツールとワークフローが利用可能です。

## コンテンツの読み取りと分析

### テキスト抽出

プレゼンテーションのテキスト内容を読むだけでよい場合、ドキュメントをマークダウンに変換します：

```bash
# ドキュメントをマークダウンに変換
python -m markitdown path-to-file.pptx
```

### 生XMLアクセス

コメント、スピーカーノート、スライドレイアウト、アニメーション、デザイン要素、複雑なフォーマットには生XMLアクセスが必要です。これらの機能のいずれかについて、プレゼンテーションをアンパックして、生XMLコンテンツを読み取る必要があります。

#### ファイルをアンパック

`python ooxml/scripts/unpack.py <office_file> <output_dir>`

**注意**: unpack.pyスクリプトは、プロジェクトルートからの相対パスで`skills/pptx/ooxml/scripts/unpack.py`にあります。このパスにスクリプトが存在しない場合、`find . -name "unpack.py"`を使用して場所を見つけてください。

#### 主要なファイル構造

* `ppt/presentation.xml` - メインのプレゼンテーションメタデータとスライド参照
* `ppt/slides/slide{N}.xml` - 個別スライド内容（slide1.xml、slide2.xmlなど）
* `ppt/notesSlides/notesSlide{N}.xml` - 各スライドのスピーカーノート
* `ppt/comments/modernComment_*.xml` - 特定スライドのコメント
* `ppt/slideLayouts/` - スライドのレイアウトテンプレート
* `ppt/slideMasters/` - マスタースライドテンプレート
* `ppt/theme/` - テーマとスタイル情報
* `ppt/media/` - 画像などのメディアファイル

#### タイポグラフィと色の抽出

**模倣するデザイン例が与えられた場合**: 以下の方法で、最初にプレゼンテーションのタイポグラフィと色を必ず分析します：
1. **テーマファイルを読む**: `ppt/theme/theme1.xml`で色（`<a:clrScheme>`）とフォント（`<a:fontScheme>`）を確認
2. **スライド内容をサンプル**: `ppt/slides/slide1.xml`で実際のフォント使用（`<a:rPr>`）と色を確認
3. **パターンを検索**: すべてのXMLファイルで色（`<a:solidFill>`、`<a:srgbClr>`）とフォント参照をgrepで検索

## テンプレートなしで新しいPowerPointプレゼンテーションを作成

ゼロから新しいPowerPointプレゼンテーションを作成する場合、**html2pptx**ワークフローを使用してHTMLスライドをPowerPointに変換し、正確な配置を実現します。

### デザイン原則

**重要**: いかなるプレゼンテーションも作成する前に、内容を分析し、適切なデザイン要素を選択します：
1. **題材を考慮**: このプレゼンテーションは何についてか？どのトーン、業界、ムードを示唆するか？
2. **ブランディングを確認**: ユーザーが会社/組織に言及した場合、そのブランドカラーとアイデンティティを考慮
3. **内容にパレットを合わせる**: 題材を反映する色を選択
4. **アプローチを明示**: コードを書く前に、デザイン選択を説明

**要件**:
- ✅ コードを書く前に、内容に基づくデザインアプローチを明示する
- ✅ Webセーフフォントのみ使用：Arial、Helvetica、Times New Roman、Georgia、Courier New、Verdana、Tahoma、Trebuchet MS、Impact
- ✅ サイズ、太さ、色で明確な視覚階層を作る
- ✅ 可読性を確保：強いコントラスト、適切な文字サイズ、きれいな整列
- ✅ 一貫性を保つ：スライド全体でパターン、余白、視覚言語を繰り返す

#### カラーパレットの選択

**創造的に色を選ぶ**:
- **デフォルトを超えて考える**: この特定のトピックに本当に合う色は？オートパイロットの選択を避ける
- **複数の角度を考慮**: トピック、業界、ムード、エネルギーレベル、ターゲットオーディエンス、ブランドアイデンティティ（言及があれば）
- **冒険する**: 予期しない組み合わせも試す（医療＝緑、金融＝ネイビーに固定しない）
- **パレットを構築**: 一緒に機能する3-5色を選ぶ（支配色 + 補助色 + アクセント）
- **コントラストを確保**: 背景上でテキストが明確に読める必要がある

**パレット例**（発想の起点。1つ選ぶ/調整する/自作する）:

1. **Classic Blue**: Deep navy (#1C2833), slate gray (#2E4053), silver (#AAB7B8), off-white (#F4F6F6)
2. **Teal & Coral**: Teal (#5EA8A7), deep teal (#277884), coral (#FE4447), white (#FFFFFF)
3. **Bold Red**: Red (#C0392B), bright red (#E74C3C), orange (#F39C12), yellow (#F1C40F), green (#2ECC71)
4. **Warm Blush**: Mauve (#A49393), blush (#EED6D3), rose (#E8B4B8), cream (#FAF7F2)
5. **Burgundy Luxury**: Burgundy (#5D1D2E), crimson (#951233), rust (#C15937), gold (#997929)
6. **Deep Purple & Emerald**: Purple (#B165FB), dark blue (#181B24), emerald (#40695B), white (#FFFFFF)
7. **Cream & Forest Green**: Cream (#FFE1C7), forest green (#40695B), white (#FCFCFC)
8. **Pink & Purple**: Pink (#F8275B), coral (#FF574A), rose (#FF737D), purple (#3D2F68)
9. **Lime & Plum**: Lime (#C5DE82), plum (#7C3A5F), coral (#FD8C6E), blue-gray (#98ACB5)
10. **Black & Gold**: Gold (#BF9A4A), black (#000000), cream (#F4F6F6)
11. **Sage & Terracotta**: Sage (#87A96B), terracotta (#E07A5F), cream (#F4F1DE), charcoal (#2C2C2C)
12. **Charcoal & Red**: Charcoal (#292929), red (#E33737), light gray (#CCCBCB)
13. **Vibrant Orange**: Orange (#F96D00), light gray (#F2F2F2), charcoal (#222831)
14. **Forest Green**: Black (#191A19), green (#4E9F3D), dark green (#1E5128), white (#FFFFFF)
15. **Retro Rainbow**: Purple (#722880), pink (#D72D51), orange (#EB5C18), amber (#F08800), gold (#DEB600)
16. **Vintage Earthy**: Mustard (#E3B448), sage (#CBD18F), forest green (#3A6B35), cream (#F4F1DE)
17. **Coastal Rose**: Old rose (#AD7670), beaver (#B49886), eggshell (#F3ECDC), ash gray (#BFD5BE)
18. **Orange & Turquoise**: Light orange (#FC993E), grayish turquoise (#667C6F), white (#FCFCFC)

#### 視覚的ディテールのオプション

**幾何学パターン**:
- 水平ではなく対角のセクション区切り
- 非対称のカラム幅（30/70、40/60、25/75）
- 見出しテキストを90°/270°回転
- 画像の円形/六角形フレーム
- コーナーの三角アクセント形状
- 奥行きを出す重なり

**ボーダー/フレーム処理**:
- 片側のみの太い単色ボーダー（10-20pt）
- 対比色の二重線ボーダー
- 全枠ではなくコーナーブラケット
- L字ボーダー（上+左、または下+右）
- 見出し下の下線アクセント（3-5pt厚）

**タイポグラフィ処理**:
- 極端なサイズコントラスト（72pt見出し vs 11pt本文）
- 文字間隔を広くした全大文字見出し
- 巨大な番号付きセクション表示
- データ/統計/技術内容にモノスペース（Courier New）
- 密な情報にコンデンスフォント（Arial Narrow）
- 強調用のアウトラインテキスト

**チャート/データのスタイリング**:
- 重要データのみアクセント色、他はモノクロ
- 縦棒ではなく横棒
- 棒グラフではなくドットプロット
- グリッド線は最小限、または無し
- 凡例ではなく要素上にデータラベル
- 主要指標は巨大な数字で表示

**レイアウトの工夫**:
- フルブリード画像 + テキストオーバーレイ
- ナビ/コンテキスト用のサイドバー列（幅20-30%）
- モジュラーグリッド（3×3、4×4）
- Zパターン/Fパターンの情報流れ
- 色付き形状上に浮かぶテキストボックス
- 雑誌風のマルチカラム

**背景処理**:
- スライドの40-60%を占める単色ブロック
- グラデーション塗り（垂直または対角のみ）
- 分割背景（2色、対角または垂直）
- 端から端までのカラーバンド
- ネガティブスペースをデザイン要素として扱う

### レイアウトのヒント

**チャートやテーブルを含むスライドを作成する場合：**
- **2カラムレイアウト（推奨）**: 全幅のヘッダーを置き、その下を2カラム（片方はテキスト/箇条書き、もう片方は強調コンテンツ）にする。バランスが良く、チャート/テーブルの可読性も上がります。flexboxで不均等な幅（例：40%/60%）を使用して、コンテンツ種類ごとに最適化します。
- **フルスライドレイアウト**: 強調コンテンツ（チャート/テーブル）をスライド全体に使い、最大のインパクトと可読性を得ます。
- **縦積みは絶対にしない**: 1カラムでテキストの下にチャート/テーブルを置かない（可読性とレイアウトが悪化します）。

### ワークフロー

1. **必須 - ファイル全体を読み取る**: [`html2pptx.md`](html2pptx.md)を最初から最後まで完全に読み取ります。**このファイルを読み取る際、範囲制限を設定しないでください。** 詳細な構文、重要なフォーマット規則、ベストプラクティスのために、ファイル全体を読み取ってから作業を開始します。\n+2. 各スライド用に適切なサイズ（例：16:9なら720pt × 405pt）のHTMLファイルを作成\n+   - すべてのテキストは`<p>`、`<h1>`-`<h6>`、`<ul>`、`<ol>`を使用\n+   - チャート/テーブルを追加する領域は`class=\"placeholder\"`を使用（可視化のため灰色背景でレンダリング）\n+   - **重要**: グラデーションとアイコンはSharpで先にPNGにラスタライズしてからHTMLで参照\n+   - **レイアウト**: チャート/テーブル/画像を含むスライドは、フルスライドまたは2カラムレイアウトを使用\n+3. [`html2pptx.js`](scripts/html2pptx.js)ライブラリを使ったJavaScriptファイルを作成して実行し、HTMLスライドをPowerPointに変換して保存\n+   - `html2pptx()`関数で各HTMLを処理\n+   - PptxGenJS APIでプレースホルダー領域にチャート/テーブルを追加\n+   - `pptx.writeFile()`で保存\n+4. **視覚的検証**: サムネイルを生成し、レイアウト問題を点検\n+   - サムネイルグリッド作成：`python scripts/thumbnail.py output.pptx workspace/thumbnails --cols 4`\n+   - サムネイル画像を読み取り、以下を注意深く確認：\n+     - **テキストの欠け**: ヘッダーバー、形状、スライド端で切れていないか\n+     - **テキストの重なり**: テキスト同士や形状と重なっていないか\n+     - **配置問題**: 端や他要素に近すぎないか\n+     - **コントラスト問題**: 背景と文字のコントラストが十分か\n+   - 問題があればHTMLのマージン/余白/色を調整し、再生成\n+   - すべてのスライドが視覚的に正しくなるまで繰り返す\n+\n+## 既存のPowerPointプレゼンテーションを編集\n+\n+既存のPowerPointプレゼンテーションのスライドを編集する場合、生のOffice Open XML（OOXML）形式で作業する必要があります。これは、.pptxファイルをアンパックし、XML内容を編集し、再パックすることを意味します。\n+\n+### ワークフロー\n+1. **必須 - ファイル全体を読み取る**: [`ooxml.md`](ooxml.md)（約500行）を最初から最後まで完全に読み取ります。**このファイルを読み取る際、範囲制限を設定しないでください。** OOXML構造と編集ワークフローの詳細なガイダンスのため、プレゼンテーション編集前にファイル全体を読み取ります。\n+2. プレゼンテーションをアンパック：`python ooxml/scripts/unpack.py <office_file> <output_dir>`\n+3. XMLファイルを編集（主に`ppt/slides/slide{N}.xml`など）\n+4. **重要**: 各編集直後に検証し、検証エラーを修正してから進む：`python ooxml/scripts/validate.py <dir> --original <file>`\n+5. 最終プレゼンテーションをパック：`python ooxml/scripts/pack.py <input_directory> <office_file>`\n+\n+## テンプレートを使用して新しいPowerPointプレゼンテーションを作成\n+\n+既存テンプレートのデザインに沿ったプレゼンテーションを作成する場合、テンプレートスライドを複製・並べ替えた後に、プレースホルダー内容を置換する必要があります。\n+\n+### ワークフロー\n+1. **テンプレートテキストを抽出し、視覚サムネイルグリッドを作成**：\n+   * テキスト抽出：`python -m markitdown template.pptx > template-content.md`\n+   * `template-content.md`を読む：テンプレート内容を理解するため、ファイル全体を読み取ります。**範囲制限を設定しないでください。**\n+   * サムネイルグリッド作成：`python scripts/thumbnail.py template.pptx`\n+   * 詳細は[#サムネイルグリッドの作成](#creating-thumbnail-grids)を参照\n+\n+2. **テンプレートを分析し、インベントリをファイルに保存**：\n+   * **視覚分析**: サムネイルグリッドでレイアウト、デザインパターン、構造を理解\n+   * `template-inventory.md`にテンプレートインベントリ分析を作成して保存：\n+     ```markdown\n+     # Template Inventory Analysis\n+     **Total Slides: [count]**\n+     **IMPORTANT: Slides are 0-indexed (first slide = 0, last slide = count-1)**\n+\n+     ## [Category Name]\n+     - Slide 0: [Layout code if available] - Description/purpose\n+     - Slide 1: [Layout code] - Description/purpose\n+     - Slide 2: [Layout code] - Description/purpose\n+     [... EVERY slide must be listed individually with its index ...]\n+     ```\n+   * **サムネイルグリッドの使用**: 以下を特定するためにサムネイルを参照：\n+     - レイアウトパターン（タイトル、本文、セクション区切り等）\n+     - 画像プレースホルダーの位置と数\n+     - スライドグループ間のデザイン一貫性\n+     - 視覚階層と構造\n+   * このインベントリファイルは次ステップで適切なテンプレートを選ぶために必須です\n+\n+3. **テンプレートインベントリに基づいてアウトラインを作成**：\n+   * ステップ2のテンプレートをレビュー\n+   * 最初のスライドに導入/タイトルテンプレートを選択（通常は最初の方のテンプレート）\n+   * 他のスライドは安全なテキスト中心レイアウトを選択\n+   * **重要：レイアウト構造を実コンテンツに一致させる**：\n+     - 1カラム：統一された物語/単一トピック\n+     - 2カラム：2つの明確に異なる項目/概念がある場合のみ\n+     - 3カラム：3つの明確に異なる項目/概念がある場合のみ\n+     - 画像+テキスト：実際に挿入する画像がある場合のみ\n+     - Quote：実際の引用（帰属付き）の場合のみ。強調目的で使わない\n+     - コンテンツよりプレースホルダーが多いレイアウトは使わない\n+     - 2項目なら3カラムに押し込まない\n+     - 4項目以上なら複数スライドに分割するかリスト形式を検討\n+   * レイアウト選択前に、実際のコンテンツ個数を数える\n+   * 選択したレイアウトの各プレースホルダーが意味ある内容で埋まることを確認\n+   * 各コンテンツセクションに対して**最適**なレイアウトを1つ選ぶ\n+   * 利用可能なデザインを活かしたコンテンツとテンプレート対応を`outline.md`に保存\n+   * テンプレートマッピング例：\n+      ```\n+      # Template slides to use (0-based indexing)\n+      # WARNING: Verify indices are within range! Template with 73 slides has indices 0-72\n+      # Mapping: slide numbers from outline -> template slide indices\n+      template_mapping = [\n+          0,   # Use slide 0 (Title/Cover)\n+          34,  # Use slide 34 (B1: Title and body)\n+          34,  # Use slide 34 again (duplicate for second B1)\n+          50,  # Use slide 50 (E1: Quote)\n+          54,  # Use slide 54 (F2: Closing + Text)\n+      ]\n+      ```\n+\n+4. **`rearrange.py`でスライドを複製/並べ替え/削除**：\n+   * `scripts/rearrange.py`で希望順にスライドを持つ新しいプレゼンテーションを作成：\n+     ```bash\n+     python scripts/rearrange.py template.pptx working.pptx 0,34,34,50,52\n+     ```\n+   * 重複スライドの複製、未使用スライドの削除、並べ替えを自動で処理\n+   * スライドインデックスは0始まり\n+   * 同じインデックスを複数回指定すると、そのスライドが複製されます\n+\n+5. **`inventory.py`で全テキストを抽出**：\n+   * **インベントリ抽出を実行**：\n+     ```bash\n+     python scripts/inventory.py working.pptx text-inventory.json\n+     ```\n+   * **text-inventory.jsonを読む**：全ての形状とプロパティを理解するため、ファイル全体を読み取ります。**範囲制限を設定しないでください。**\n+\n+6. **置換テキストを生成し、JSONに保存**\n+   * まずインベントリ内に存在する形状のみを参照\n+   * replace.pyは置換JSONがインベントリに存在するか検証します\n+   * 置換JSONに\"paragraphs\"が無い形状は自動でクリアされます\n+   * バレット段落では`alignment`を設定しない（`\"bullet\": true`なら自動で左寄せ）\n+   * 置換用JSONはテキスト文字列だけでなく段落プロパティも含める\n+   * バレット記号（•, -, *）はテキストに含めない（自動で付与される）\n+\n+7. **`replace.py`で置換を適用**\n+   ```bash\n+   python scripts/replace.py working.pptx replacement-text.json output.pptx\n+   ```\n+\n+## Creating Thumbnail Grids
\n+PowerPointスライドの視覚サムネイルグリッドを作成して、迅速に分析・参照するには：\n+\n+```bash\n+python scripts/thumbnail.py template.pptx [output_prefix]\n+```\n+\n+**機能**:\n+- 作成: `thumbnails.jpg`（大きなデッキの場合は`thumbnails-1.jpg`、`thumbnails-2.jpg`など）\n+- デフォルト: 5列、グリッドあたり最大30枚（5×6）\n+- カスタムプレフィックス: `python scripts/thumbnail.py template.pptx my-grid`\n+  - 注意: 特定ディレクトリに出力したい場合、プレフィックスにパスを含めます（例：`workspace/my-grid`）\n+- 列数を調整: `--cols 4`（範囲: 3-6、グリッドあたり枚数に影響）\n+- グリッド上限: 3列=12、4列=20、5列=30、6列=42\n+- スライドは0始まり\n+\n+**ユースケース**:\n+- テンプレート分析: レイアウトとデザインパターンを素早く理解\n+- 内容レビュー: デッキ全体の視覚概要\n+- ナビゲーション参照: 見た目でスライドを特定\n+- 品質チェック: すべてのスライドが適切にフォーマットされているか確認\n+\n+**例**:\n+```bash\n+# 基本\n+python scripts/thumbnail.py presentation.pptx\n+\n+# オプション併用: カスタム名 + 列数\n+python scripts/thumbnail.py template.pptx analysis --cols 4\n+```\n+\n+## スライドを画像に変換\n+\n+PowerPointスライドを視覚的に分析するには、2段階で画像に変換します：\n+\n+1. **PPTXをPDFに変換**:\n+   ```bash\n+   soffice --headless --convert-to pdf template.pptx\n+   ```\n+\n+2. **PDFページをJPEG画像に変換**:\n+   ```bash\n+   pdftoppm -jpeg -r 150 template.pdf slide\n+   ```\n+   これにより、`slide-1.jpg`、`slide-2.jpg`などが作成されます。\n+\n+オプション:\n+- `-r 150`: 解像度を150 DPIに設定（品質/サイズのバランス調整）\n+- `-jpeg`: JPEG形式（PNGが必要なら`-png`）\n+- `-f N`: 最初のページ（例：`-f 2`は2ページ目から）\n+- `-l N`: 最後のページ（例：`-l 5`は5ページ目で停止）\n+- `slide`: 出力プレフィックス\n+\n+範囲指定例:\n+```bash\n+pdftoppm -jpeg -r 150 -f 2 -l 5 template.pdf slide  # 2-5ページのみ変換\n+```\n+\n+## コードスタイルガイドライン\n+\n+**重要**: PPTX操作のコードを生成する場合：\n+- 簡潔なコードを記述\n+- 冗長な変数名と冗長な操作を避ける\n+- 不要なprint文を避ける\n+\n+## 依存関係\n+\n+必要な依存関係（既にインストールされている想定）：\n+\n+- **markitdown**: `pip install \"markitdown[pptx]\"`（プレゼンのテキスト抽出用）\n+- **pptxgenjs**: `npm install -g pptxgenjs`（html2pptxで作成するため）\n+- **playwright**: `npm install -g playwright`（html2pptxでHTMLレンダリングするため）\n+- **react-icons**: `npm install -g react-icons react react-dom`（アイコン用）\n+- **sharp**: `npm install -g sharp`（SVGラスタライズと画像処理）\n+- **LibreOffice**: `sudo apt-get install libreoffice`（PDF変換用）\n+- **Poppler**: `sudo apt-get install poppler-utils`（pdftoppmでPDFを画像に変換するため）\n+- **defusedxml**: `pip install defusedxml`（安全なXML解析用）\n+

