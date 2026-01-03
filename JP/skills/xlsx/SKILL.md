---
name: xlsx
description: "数式、フォーマット、データ分析、視覚化をサポートする包括的なスプレッドシート作成、編集、分析。Claudeがスプレッドシート（.xlsx、.xlsm、.csv、.tsvなど）を操作する必要がある場合：(1) 数式とフォーマットを含む新しいスプレッドシートを作成、(2) データを読み取りまたは分析、(3) 数式を保持しながら既存のスプレッドシートを変更、(4) スプレッドシートでのデータ分析と視覚化、または(5) 数式を再計算"
license: プロプライエタリ。完全な条件はLICENSE.txtに記載されています
---

# 出力の要件

## すべてのExcelファイル

### ゼロ数式エラー
- すべてのExcelモデルは、ゼロの数式エラー（#REF!、#DIV/0!、#VALUE!、#N/A、#NAME?）で提供される必要があります

### 既存のテンプレートを保持（テンプレートを更新する場合）
- ファイルを変更する際、既存のフォーマット、スタイル、規則を研究し、正確に一致させます
- 確立されたパターンを持つファイルに標準化されたフォーマットを課さないでください
- 既存のテンプレート規則は常にこれらのガイドラインを上書きします

## 財務モデル

### カラーコーディング標準
ユーザーまたは既存のテンプレートで特に指定されない限り

#### 業界標準のカラー規則
- **青いテキスト（RGB: 0,0,255）**: ハードコードされた入力、およびシナリオ用にユーザーが変更する数値
- **黒いテキスト（RGB: 0,0,0）**: すべての数式と計算
- **緑のテキスト（RGB: 0,128,0）**: 同じブック内の他のワークシートから取得するリンク
- **赤いテキスト（RGB: 255,0,0）**: 他のファイルへの外部リンク
- **黄色の背景（RGB: 255,255,0）**: 注意が必要な主要な仮定、または更新が必要なセル

### 数値フォーマット標準

#### 必須フォーマット規則
- **年**: テキスト文字列としてフォーマット（例：「2024」、not「2,024」）
- **通貨**: $#,##0フォーマットを使用；ヘッダーに常に単位を指定（「Revenue ($mm)」）
- **ゼロ**: 数値フォーマットを使用してすべてのゼロを「-」にする（パーセンテージを含む、例：「$#,##0;($#,##0);-」）
- **パーセンテージ**: デフォルトで0.0%フォーマット（小数点1桁）
- **倍数**: 評価倍数（EV/EBITDA、P/E）には0.0xフォーマット
- **負の数**: マイナス-123ではなく括弧(123)を使用

### 数式構築規則

#### 仮定の配置
- すべての仮定（成長率、マージン、倍数など）を別の仮定セルに配置します
- 数式でハードコードされた値の代わりにセル参照を使用します
- 例：=B5*1.05の代わりに=B5*(1+$B$6)を使用

#### 数式エラー防止
- すべてのセル参照が正しいことを確認します
- 範囲のオフバイワンエラーをチェックします
- すべての予測期間で一貫した数式を確保します
- エッジケース（ゼロ値、負の数）でテストします
- 意図しない循環参照がないことを確認します

#### ハードコードのドキュメント要件
- コメントまたはセルの横（テーブルの終わりの場合）。フォーマット：「Source: [System/Document], [Date], [Specific Reference], [URL if applicable]」
- 例：
  - "Source: Company 10-K, FY2024, Page 45, Revenue Note, [SEC EDGAR URL]"
  - "Source: Company 10-Q, Q2 2025, Exhibit 99.1, [SEC EDGAR URL]"
  - "Source: Bloomberg Terminal, 8/15/2025, AAPL US Equity"
  - "Source: FactSet, 8/20/2025, Consensus Estimates Screen"

# XLSX作成、編集、分析

## 概要

ユーザーが.xlsxファイルの作成、編集、または内容の分析を依頼する場合があります。タスクごとに異なるツールとワークフローが利用可能です。

## 重要な要件

**数式再計算にはLibreOfficeが必要**: `recalc.py`スクリプトを使用して数式値を再計算するために、LibreOfficeがインストールされていると想定できます。スクリプトは初回実行時にLibreOfficeを自動的に設定します

## データの読み取りと分析

### pandasによるデータ分析
データ分析、視覚化、基本操作には、強力なデータ操作機能を提供する**pandas**を使用します：

```python
import pandas as pd

# Excelを読み取る
df = pd.read_excel('file.xlsx')  # デフォルト: 最初のシート
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # すべてのシートを辞書として

# 分析
df.head()      # データをプレビュー
df.info()      # 列情報
df.describe()  # 統計

# Excelに書き込む
df.to_excel('output.xlsx', index=False)
```

## Excelファイルワークフロー

## 重要：ハードコードされた値ではなく数式を使用

**Pythonで値を計算してハードコードするのではなく、常にExcel数式を使用してください。** これにより、スプレッドシートが動的で更新可能なままになります。

### ❌ 間違い - 計算値をハードコード
```python
# 悪い例: Pythonで計算して結果をハードコード
total = df['Sales'].sum()
sheet['B10'] = total  # 5000をハードコード

# 悪い例: Pythonで成長率を計算
growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # 0.15をハードコード

# 悪い例: Pythonで平均を計算
avg = sum(values) / len(values)
sheet['D20'] = avg  # 42.5をハードコード
```

### ✅ 正しい - Excel数式を使用
```python
# 良い例: Excelに合計を計算させる
sheet['B10'] = '=SUM(B2:B9)'

# 良い例: Excel数式として成長率
sheet['C5'] = '=(C4-C2)/C2'

# 良い例: Excel関数を使用して平均
sheet['D20'] = '=AVERAGE(D2:D19)'
```

これはすべての計算に適用されます - 合計、パーセンテージ、比率、差など。スプレッドシートは、ソースデータが変更されたときに再計算できる必要があります。

## 一般的なワークフロー
1. **ツールを選択**: データにはpandas、数式/フォーマットにはopenpyxl
2. **作成/読み込み**: 新しいブックを作成するか、既存のファイルを読み込みます
3. **変更**: データ、数式、フォーマットを追加/編集します
4. **保存**: ファイルに書き込みます
5. **数式を再計算（数式を使用している場合は必須）**: recalc.pyスクリプトを使用します
   ```bash
   python recalc.py output.xlsx
   ```
6. **エラーを確認して修正**: 
   - スクリプトはエラー詳細を含むJSONを返します
   - `status`が`errors_found`の場合、`error_summary`で特定のエラータイプと場所を確認します
   - 識別されたエラーを修正し、再度再計算します
   - 修正する一般的なエラー：
     - `#REF!`: 無効なセル参照
     - `#DIV/0!`: ゼロ除算
     - `#VALUE!`: 数式のデータ型が間違っている
     - `#NAME?`: 認識されない数式名

### 新しいExcelファイルを作成

```python
# 数式とフォーマットにopenpyxlを使用
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# データを追加
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# 数式を追加
sheet['B2'] = '=SUM(A1:A10)'

# フォーマット
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# 列幅
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

### 既存のExcelファイルを編集

```python
# 数式とフォーマットを保持するためにopenpyxlを使用
from openpyxl import load_workbook

# 既存のファイルを読み込む
wb = load_workbook('existing.xlsx')
sheet = wb.active  # または特定のシートにはwb['SheetName']

# 複数のシートを操作
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"シート: {sheet_name}")

# セルを変更
sheet['A1'] = 'New Value'
sheet.insert_rows(2)  # 位置2に行を挿入
sheet.delete_cols(3)  # 列3を削除

# 新しいシートを追加
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

## 数式を再計算

openpyxlで作成または変更されたExcelファイルには、文字列として数式が含まれますが、計算値は含まれません。提供された`recalc.py`スクリプトを使用して数式を再計算します：

```bash
python recalc.py <excel_file> [timeout_seconds]
```

例：
```bash
python recalc.py output.xlsx 30
```

スクリプトは：
- 初回実行時にLibreOfficeマクロを自動的に設定します
- すべてのシートのすべての数式を再計算します
- Excelエラー（#REF!、#DIV/0!など）についてすべてのセルをスキャンします
- 詳細なエラー場所とカウントを含むJSONを返します
- LinuxとmacOSの両方で動作します

## 数式検証チェックリスト

数式が正しく機能することを確認するためのクイックチェック：

### 必須検証
- [ ] **2-3個のサンプル参照をテスト**: 完全なモデルを構築する前に、正しい値を取得することを確認します
- [ ] **列マッピング**: Excel列が一致することを確認します（例：列64 = BL、not BK）
- [ ] **行オフセット**: Excel行は1ベースであることを覚えておきます（DataFrame行5 = Excel行6）

### よくある落とし穴
- [ ] **NaN処理**: `pd.notna()`でnull値をチェックします
- [ ] **右端の列**: FYデータはしばしば列50+にあります
- [ ] **複数の一致**: 最初だけでなく、すべての出現を検索します
- [ ] **ゼロ除算**: 数式で`/`を使用する前に分母をチェックします（#DIV/0!）
- [ ] **間違った参照**: すべてのセル参照が意図したセルを指していることを確認します（#REF!）
- [ ] **シート間参照**: シートをリンクするには正しいフォーマット（Sheet1!A1）を使用します

### 数式テスト戦略
- [ ] **小さく始める**: 広く適用する前に2-3個のセルで数式をテストします
- [ ] **依存関係を確認**: 数式で参照されるすべてのセルが存在することを確認します
- [ ] **エッジケースをテスト**: ゼロ、負の数、非常に大きな値を含めます

### recalc.py出力の解釈
スクリプトはエラー詳細を含むJSONを返します：
```json
{
  "status": "success",           // または "errors_found"
  "total_errors": 0,              // エラー総数
  "total_formulas": 42,           // ファイル内の数式数
  "error_summary": {              // エラーが見つかった場合のみ存在
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  }
}
```

## ベストプラクティス

### ライブラリの選択
- **pandas**: データ分析、一括操作、シンプルなデータエクスポートに最適
- **openpyxl**: 複雑なフォーマット、数式、Excel固有の機能に最適

### openpyxlでの作業
- セルインデックスは1ベースです（row=1, column=1はセルA1を指します）
- 計算値を読み取るには`data_only=True`を使用：`load_workbook('file.xlsx', data_only=True)`
- **警告**: `data_only=True`で開いて保存すると、数式が値に置き換えられ、永続的に失われます
- 大きなファイルの場合：読み取りには`read_only=True`、書き込みには`write_only=True`を使用します
- 数式は保持されますが評価されません - 値を更新するにはrecalc.pyを使用します

### pandasでの作業
- 推論の問題を避けるためにデータ型を指定：`pd.read_excel('file.xlsx', dtype={'id': str})`
- 大きなファイルの場合、特定の列を読み取ります：`pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- 日付を適切に処理：`pd.read_excel('file.xlsx', parse_dates=['date_column'])`

## コードスタイルガイドライン
**重要**: Excel操作のPythonコードを生成する場合：
- 不要なコメントなしで最小限で簡潔なPythonコードを記述します
- 冗長な変数名と冗長な操作を避けます
- 不要なprint文を避けます

**Excelファイル自体について**：
- 複雑な数式や重要な仮定を含むセルにコメントを追加します
- ハードコードされた値のデータソースを文書化します
- 主要な計算とモデルセクションのメモを含めます

