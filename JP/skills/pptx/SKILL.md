---
name: pptx
description: "プレゼンテーションの作成・編集・分析。Claude がプレゼン資料（.pptx）で (1) 新規作成、(2) 内容の修正、(3) レイアウトの調整、(4) コメント/スピーカーノートの操作、その他のプレゼン関連タスクを行う場合に使用します。"
license: プロプライエタリ。完全な条件は LICENSE.txt に記載されています
---

# PPTX の作成・編集・分析

## 概要

ユーザーは .pptx ファイルの作成、編集、または内容の分析を依頼することがあります。.pptx は本質的に XML ファイルや画像などのリソースを含む ZIP アーカイブです。目的に応じて、異なるツールとワークフローを使い分けます。

## コンテンツの読み取りと分析

### テキスト抽出

プレゼンの「テキスト内容だけ」を素早く読みたい場合は、Markdown に変換します。

```bash
# Convert document to markdown
python -m markitdown path-to-file.pptx
```

### 生 XML へのアクセス

コメント、スピーカーノート、スライドレイアウト、アニメーション、デザイン要素、複雑な書式などは、生 XML を直接読む必要があります。これらを扱う場合、まず .pptx を展開して XML を確認します。

#### ファイルの展開（unpack）

`python ooxml/scripts/unpack.py <office_file> <output_dir>`

**注意**: `unpack.py` はプロジェクトルートからの相対パスで `skills/pptx/ooxml/scripts/unpack.py` にあります。もし存在しない場合は、`find . -name "unpack.py"` で場所を特定してください。

#### 主要なファイル構造

* `ppt/presentation.xml` - プレゼン全体のメタデータとスライド参照
* `ppt/slides/slide{N}.xml` - 各スライドの内容（slide1.xml, slide2.xml, ...）
* `ppt/notesSlides/notesSlide{N}.xml` - 各スライドのスピーカーノート
* `ppt/comments/modernComment_*.xml` - 特定スライドに紐づくコメント
* `ppt/slideLayouts/` - スライドレイアウトテンプレート
* `ppt/slideMasters/` - マスタースライドテンプレート
* `ppt/theme/` - テーマとスタイル情報
* `ppt/media/` - 画像などのメディア

#### タイポグラフィと色の抽出

**模倣するデザイン例が与えられている場合**: 次の順番で、タイポグラフィと配色を必ず先に分析します。

1. **テーマファイルを読む**: `ppt/theme/theme1.xml` の色（`<a:clrScheme>`）とフォント（`<a:fontScheme>`）を確認
2. **実スライドをサンプル**: `ppt/slides/slide1.xml` の実際のフォント指定（`<a:rPr>`）と色を確認
3. **パターン検索**: すべての XML を対象に、色（`<a:solidFill>`, `<a:srgbClr>`）やフォント参照を grep で検索

## テンプレートなしで新しい PowerPoint プレゼンを作成

ゼロから新規作成する場合は、**html2pptx** ワークフローを使って HTML スライドを PowerPoint に変換し、正確な配置を実現します。

### デザイン原則

**重要**: 作成前に内容を分析し、適切なデザイン要素を選びます。

1. **題材を考える**: 何のプレゼンか？トーン、業界、ムードは？
2. **ブランディングを確認**: 会社/組織に言及があれば、ブランドカラーやアイデンティティを考慮
3. **パレットを内容に合わせる**: 題材を反映する色を選ぶ
4. **アプローチを言語化**: コードを書く前に、デザイン選択の理由を説明

**要件**:
- ✅ コードを書く前に、内容に基づくデザイン方針を明示する
- ✅ Web セーフフォントのみ使用: Arial, Helvetica, Times New Roman, Georgia, Courier New, Verdana, Tahoma, Trebuchet MS, Impact
- ✅ サイズ/太さ/色で明確な階層を作る
- ✅ 可読性の確保: 強いコントラスト、適切な文字サイズ、整列
- ✅ 一貫性: パターン・余白・視覚言語を全スライドで揃える

#### カラーパレットの選び方

**色を創造的に選ぶ**:
- **デフォルトから脱する**: トピックに本当に合う色は何か？「いつもの色」を避ける
- **複数視点で考える**: トピック/業界/ムード/エネルギー/ターゲット/ブランド（あれば）
- **意外性も試す**: 医療=緑、金融=紺、の固定観念に縛られない
- **3〜5色で構成**: 主役 + 支える色 + アクセントを設計する
- **コントラスト必須**: 背景と文字のコントラストで可読性を確保

**パレット例**（発想の起点。選ぶ/調整する/自作する）:

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

#### 視覚ディテールの選択肢

**幾何学パターン**:
- 水平ではなく対角の区切り
- 非対称カラム（30/70, 40/60, 25/75）
- 見出しを 90°/270° 回転
- 画像を円形/六角形で切り抜く
- コーナーに三角アクセント
- 形状を重ねて奥行きを作る

**枠線・フレーム**:
- 片側だけ太い単色ボーダー（10〜20pt）
- 対比色の二重線
- 全枠ではなくコーナーブラケット
- L 字のフレーム（上+左 / 下+右）
- 見出し下に太い下線アクセント（3〜5pt）

**タイポグラフィ**:
- 極端なサイズ差（72pt 見出し vs 11pt 本文）
- 文字間隔を広くした全大文字見出し
- 巨大な番号でセクションを表現
- データ/統計/技術は等幅（Courier New）
- 情報密度が高い時は Arial Narrow
- アウトライン文字で強調

**チャート/データ**:
- モノクロ + 重要だけアクセント色
- 縦棒より横棒
- 棒よりドットプロット
- グリッド線は最小限（または無し）
- 凡例ではなく要素上にデータラベル
- 重要 KPI を巨大な数字で

**レイアウト**:
- フルブリード画像 + テキストオーバーレイ
- ナビ/コンテキスト用サイドバー（20〜30%）
- モジュラーグリッド（3×3, 4×4）
- Z/F パターンの流れ
- 形状の上に浮かぶテキストボックス
- 雑誌風マルチカラム

**背景**:
- 40〜60% を占める単色ブロック
- グラデーション（垂直/対角のみ）
- 2色分割（対角/垂直）
- 端から端までのカラーバンド
- ネガティブスペースをデザイン要素として使う

### レイアウトのヒント

**チャートやテーブルを含むスライドの注意**:
- **2カラム（推奨）**: 上部に全幅ヘッダー、下を 2 カラム（片方にテキスト/箇条書き、もう片方に強調コンテンツ）。バランスが良く、可読性が上がります。幅は 40%/60% のように不均等にすると効果的です。
- **フルスライド**: チャート/テーブルを全面に使い、最大の可読性とインパクトを得る
- **縦積み禁止**: 1 カラムで「テキストの下にチャート/テーブル」を置くと読みづらく、レイアウト崩れを起こしやすい

### ワークフロー

1. **必須 - ファイル全体を読む**: [`html2pptx.md`](html2pptx.md) を最初から最後まで完全に読みます。**このファイルを読むときは範囲指定を絶対にしないでください。**
2. 各スライド用に、適切なサイズ（例: 16:9 なら 720pt × 405pt）の HTML ファイルを作成
   - すべてのテキストは `<p>`, `<h1>`-`<h6>`, `<ul>`, `<ol>` を使用
   - チャート/テーブルを追加する領域には `class="placeholder"` を使う（見えるよう灰色背景でレンダリング）
   - **重要**: グラデーションとアイコンは Sharp で先に PNG にラスタライズしてから HTML で参照
   - **レイアウト**: チャート/テーブル/画像があるスライドは、フルスライドまたは 2 カラムを使う
3. [`html2pptx.js`](scripts/html2pptx.js) を使う JS を作成し実行して、HTML スライドを PowerPoint に変換・保存
   - `html2pptx()` で各 HTML を処理
   - PptxGenJS API でプレースホルダー領域にチャート/テーブルを追加
   - `pptx.writeFile()` で保存
4. **視覚検証**: サムネイルを生成してレイアウト崩れを点検
   - サムネイルグリッド: `python scripts/thumbnail.py output.pptx workspace/thumbnails --cols 4`
   - **テキスト欠け** / **重なり** / **余白不足** / **コントラスト不足** を確認し、必要なら HTML を調整して再生成

## 既存の PowerPoint プレゼンを編集

既存の .pptx を編集する場合は、生の Office Open XML（OOXML）を扱います。つまり、.pptx を展開し、XML を編集し、再パックします。

### ワークフロー

1. **必須 - ファイル全体を読む**: [`ooxml.md`](ooxml.md)（約500行）を最初から最後まで完全に読みます。**このファイルを読むときは範囲指定を絶対にしないでください。**
2. 展開: `python ooxml/scripts/unpack.py <office_file> <output_dir>`
3. XML を編集（主に `ppt/slides/slide{N}.xml` など）
4. **重要**: 編集のたびにすぐ検証し、エラーを解消してから進む: `python ooxml/scripts/validate.py <dir> --original <file>`
5. 再パック: `python ooxml/scripts/pack.py <input_directory> <office_file>`

## テンプレートを使って新しい PowerPoint プレゼンを作成

既存テンプレートのデザインに合わせる場合は、テンプレートスライドを複製・並べ替えた上で、プレースホルダーの内容を置換します。

### ワークフロー

1. **テンプレートのテキスト抽出とサムネイル作成**:
   * テキスト抽出: `python -m markitdown template.pptx > template-content.md`
   * `template-content.md` を読む（**範囲指定なし**）
   * サムネイル: `python scripts/thumbnail.py template.pptx`
   * 詳細は [サムネイルグリッドの作成](#creating-thumbnail-grids) を参照

2. **テンプレート分析を行い、インベントリを保存**:
   * サムネイルを見てレイアウトパターンやプレースホルダー構造を把握
   * `template-inventory.md` に、全スライドの一覧を必ず保存（スライドは 0 始まり）

```markdown
# Template Inventory Analysis
**Total Slides: [count]**
**IMPORTANT: Slides are 0-indexed (first slide = 0, last slide = count-1)**

## [Category Name]
- Slide 0: [Layout code if available] - Description/purpose
- Slide 1: [Layout code] - Description/purpose
- Slide 2: [Layout code] - Description/purpose
[... EVERY slide must be listed individually with its index ...]
```

3. **テンプレートインベントリに基づいてアウトラインを作成**:
   * 導入/タイトルは序盤のテンプレートから選ぶ
   * 他は安全なテキスト中心レイアウトを選ぶ
   * **重要: レイアウトのプレースホルダー数と、実コンテンツ数を必ず一致させる**

テンプレートマッピング例:

```
# Template slides to use (0-based indexing)
# WARNING: Verify indices are within range! Template with 73 slides has indices 0-72
# Mapping: slide numbers from outline -> template slide indices
template_mapping = [
    0,   # Use slide 0 (Title/Cover)
    34,  # Use slide 34 (B1: Title and body)
    34,  # Use slide 34 again (duplicate for second B1)
    50,  # Use slide 50 (E1: Quote)
    54,  # Use slide 54 (F2: Closing + Text)
]
```

4. **`rearrange.py` で複製/並べ替え/削除**:

```bash
python scripts/rearrange.py template.pptx working.pptx 0,34,34,50,52
```

5. **`inventory.py` で全テキスト形状のインベントリを抽出**:

```bash
python scripts/inventory.py working.pptx text-inventory.json
```

   * `text-inventory.json` を読む（**範囲指定なし**）

6. **置換テキストを JSON にまとめる**:
   * インベントリに存在するスライド/形状のみ参照
   * 置換 JSON に `paragraphs` がない形状は自動でクリアされる点に注意
   * バレットは `bullet: true` で付与されるため、テキストに `•` などを含めない
   * 置換ファイルを `replacement-text.json` として保存

7. **`replace.py` で置換を適用**:

```bash
python scripts/replace.py working.pptx replacement-text.json output.pptx
```

<a id="creating-thumbnail-grids"></a>
## サムネイルグリッドの作成

PowerPoint スライドの視覚サムネイルグリッドを作成して、素早く分析・参照するには：

```bash
python scripts/thumbnail.py template.pptx [output_prefix]
```

**機能**:
- 作成: `thumbnails.jpg`（大きいデッキは `thumbnails-1.jpg`, `thumbnails-2.jpg`...）
- デフォルト: 5列、最大 30 枚/グリッド（5×6）
- カスタム接頭辞: `python scripts/thumbnail.py template.pptx my-grid`
  - 出力先を指定したい場合は `workspace/my-grid` のようにパスを含める
- 列数: `--cols 4`（3〜6。グリッドあたり枚数に影響）
- 上限: 3列=12、4列=20、5列=30、6列=42
- スライドは 0 始まり

**例**:

```bash
# Basic usage
python scripts/thumbnail.py presentation.pptx

# Combine options: custom name, columns
python scripts/thumbnail.py template.pptx analysis --cols 4
```

## スライドを画像に変換

PowerPoint スライドを視覚的に分析するには、2段階で画像に変換します。

1. **PPTX → PDF**:

```bash
soffice --headless --convert-to pdf template.pptx
```

2. **PDF → JPEG**:

```bash
pdftoppm -jpeg -r 150 template.pdf slide
```

オプション:
- `-r 150`: 150 DPI（品質/サイズのバランス）
- `-jpeg`: JPEG（PNG が必要なら `-png`）
- `-f N`: 開始ページ
- `-l N`: 終了ページ

## コードスタイルガイドライン

**重要**: PPTX 操作のコード生成では、
- 簡潔に書く
- 冗長な変数名/重複処理を避ける
- 不要な print を避ける

## 依存関係

必要な依存関係（インストール済み想定）：

- **markitdown**: `uv pip install "markitdown[pptx]"`（プレゼンのテキスト抽出）
- **pptxgenjs**: `npm install -g pptxgenjs`（html2pptx）
- **playwright**: `npm install -g playwright`（html2pptx の HTML レンダリング）
- **react-icons**: `npm install -g react-icons react react-dom`（アイコン）
- **sharp**: `npm install -g sharp`（SVG ラスタライズ/画像処理）
- **LibreOffice**: `sudo apt-get install libreoffice`（PDF 変換）
- **Poppler**: `sudo apt-get install poppler-utils`（pdftoppm）
- **defusedxml**: `uv pip install defusedxml`（安全な XML 解析）


