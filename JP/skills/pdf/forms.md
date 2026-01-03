**重要：これらのステップは必ず順番に完了してください。コードを書く前に先へ進まないでください。**

PDFフォームに記入する必要がある場合、まずPDFに入力可能なフォームフィールドがあるか確認します。このファイルのディレクトリで次のスクリプトを実行します：
 `python scripts/check_fillable_fields <file.pdf>`  
結果に応じて「入力可能フィールド」または「入力不可能フィールド」へ進み、指示に従ってください。

# 入力可能フィールド

PDFに入力可能なフォームフィールドがある場合：
- このファイルのディレクトリで次のスクリプトを実行します：`python scripts/extract_form_field_info.py <input.pdf> <field_info.json>`。以下の形式でフィールド一覧を持つJSONファイルが作成されます：
```
[
  {
    "field_id": (フィールドの一意ID),
    "page": (ページ番号、1始まり),
    "rect": ([left, bottom, right, top] PDF座標でのバウンディングボックス。y=0はページ下端),
    "type": ("text", "checkbox", "radio_group", または "choice"),
  },
  // チェックボックスは "checked_value" と "unchecked_value" を持つ：
  {
    "field_id": (フィールドの一意ID),
    "page": (ページ番号、1始まり),
    "type": "checkbox",
    "checked_value": (チェックを入れるにはこの値をセット),
    "unchecked_value": (チェックを外すにはこの値をセット),
  },
  // ラジオグループは選択肢の "radio_options" リストを持つ。
  {
    "field_id": (フィールドの一意ID),
    "page": (ページ番号、1始まり),
    "type": "radio_group",
    "radio_options": [
      {
        "value": (この選択肢を選ぶにはこの値をセット),
        "rect": (この選択肢のラジオボタンのバウンディングボックス)
      },
      // 他のラジオ選択肢
    ]
  },
  // 複数選択フィールドは "choice_options" リストを持つ：
  {
    "field_id": (フィールドの一意ID),
    "page": (ページ番号、1始まり),
    "type": "choice",
    "choice_options": [
      {
        "value": (この選択肢を選ぶにはこの値をセット),
        "text": (表示されるテキスト)
      },
      // 他の選択肢
    ],
  }
]
```
- 次のスクリプトでPDFをPNGに変換します（このファイルのディレクトリで実行）：  
`python scripts/convert_pdf_to_images.py <file.pdf> <output_directory>`  
その後、画像を分析して各フォームフィールドの目的を判断します（PDF座標のバウンディングボックスを画像座標に変換すること）。
- 各フィールドに入力する値を、次の形式で`field_values.json`として作成します：
```
[
  {
    "field_id": "last_name", // `extract_form_field_info.py`のfield_idと一致する必要があります
    "description": "ユーザーの姓",
    "page": 1, // field_info.jsonの "page" と一致する必要があります
    "value": "Simpson"
  },
  {
    "field_id": "Checkbox12",
    "description": "ユーザーが18歳以上の場合にチェックすべきチェックボックス",
    "page": 1,
    "value": "/On" // チェックボックスは "checked_value" を使用。ラジオグループは "radio_options" の "value" を使用。
  },
  // more fields
]
```
- このファイルのディレクトリで`fill_fillable_fields.py`を実行し、記入済みPDFを作成します：  
`python scripts/fill_fillable_fields.py <input pdf> <field_values.json> <output pdf>`  
このスクリプトは、指定したフィールドIDと値が正しいか検証します。エラーが出たら該当フィールドを修正し、再試行してください。

# 入力不可能フィールド

PDFに入力可能なフォームフィールドがない場合、視覚的に「どこにデータを入れるべきか」を判断してテキスト注釈を作成する必要があります。以下のステップに**厳密に**従ってください。フォームを正確に完成させるため、**すべてのステップを必ず実行**します。各ステップの詳細は以下です。
- PDFをPNG画像に変換し、フィールドのバウンディングボックスを決める
- フィールド情報と、バウンディングボックスを可視化する検証画像を含むJSONファイルを作成する
- バウンディングボックスを検証する
- バウンディングボックスを使ってフォームに記入する

## ステップ1：視覚分析（必須）

- PDFをPNG画像に変換します。このファイルのディレクトリで次を実行：  
`python scripts/convert_pdf_to_images.py <file.pdf> <output_directory>`  
スクリプトは、PDFの各ページについて1枚のPNG画像を作成します。
- 各PNG画像を注意深く見て、全フォームフィールドと入力領域を特定します。テキストを入力するフィールドごとに、ラベル用と入力領域用の両方のバウンディングボックスを決めます。ラベルと入力領域のボックスは**交差してはいけません**。入力ボックスは、データを入力すべき領域だけを含む必要があります。通常ラベルの横/上/下にあります。入力ボックスは、文字が収まる十分な高さと幅が必要です。

フォーム構造の例：

*箱の中にラベル*
```
┌────────────────────────┐
│ Name:                  │
└────────────────────────┘
```
入力領域は「Name」ラベルの右側で、箱の端まで伸ばします。

*線の前にラベル*
```
Email: _______________________
```
入力領域は線の上で、線の全幅を含めます。

*線の下にラベル*
```
_________________________
Name
```
入力領域は線の上で、線の全幅を含めます。署名や日付で一般的です。

*線の上にラベル*
```
Please enter any special requests:
________________________________________________
```
入力領域はラベル下端から線までに広げ、線の全幅を含めます。

*チェックボックス*
```
Are you a US citizen? Yes □  No □
```
チェックボックスの場合：
- 小さな四角（□）を探します。これが実際にターゲットにするチェックボックスです（ラベルの左右どちらの場合もあります）
- ラベルテキスト（「Yes」「No」）と、クリック可能な四角を区別します
- 入力バウンディングボックスはテキストではなく**四角だけ**を覆う必要があります

### ステップ2：fields.jsonと検証画像を作成（必須）

- 次の形式でフォームフィールドとバウンディングボックス情報を持つ`fields.json`を作成します：
```
{
  "pages": [
    {
      "page_number": 1,
      "image_width": (1ページ目画像の幅px),
      "image_height": (1ページ目画像の高さpx),
    },
    {
      "page_number": 2,
      "image_width": (2ページ目画像の幅px),
      "image_height": (2ページ目画像の高さpx),
    }
    // additional pages
  ],
  "form_fields": [
    // テキストフィールド例
    {
      "page_number": 1,
      "description": "ここにユーザーの姓を入力する",
      // バウンディングボックスは [left, top, right, bottom]。ラベルと入力領域は重ならない。
      "field_label": "Last name",
      "label_bounding_box": [30, 125, 95, 142],
      "entry_bounding_box": [100, 125, 280, 142],
      "entry_text": {
        "text": "Johnson", // entry_bounding_box位置に注釈として追加される
        "font_size": 14, // 任意。デフォルト14
        "font_color": "000000", // 任意。RRGGBB。デフォルト000000（黒）
      }
    },
    // チェックボックス例：入力ボックスはテキストではなく四角を狙う
    {
      "page_number": 2,
      "description": "ユーザーが18歳以上ならチェックするチェックボックス",
      "entry_bounding_box": [140, 525, 155, 540],  // チェックボックスの小四角
      "field_label": "Yes",
      "label_bounding_box": [100, 525, 132, 540],  // 「Yes」テキスト
      // チェックを入れるには "X" を使う
      "entry_text": {
        "text": "X",
      }
    }
    // additional form field entries
  ]
}
```

各ページについて、このファイルのディレクトリで次のスクリプトを実行して検証画像を作成します：  
`python scripts/create_validation_image.py <page_number> <path_to_fields.json> <input_image_path> <output_image_path>`

検証画像では、入力領域が赤枠、ラベルテキストが青枠で表示されます。

### ステップ3：バウンディングボックスを検証（必須）

#### 自動交差チェック

- `check_bounding_boxes.py`で、ボックス同士が交差していないこと、入力ボックスの高さが十分なことを検証します（このファイルのディレクトリで実行）：  
`python scripts/check_bounding_boxes.py <JSON file>`

エラーがある場合、該当フィールドを再分析し、バウンディングボックスを調整して、エラーがなくなるまで繰り返します。青（ラベル）はテキストを含み、赤（入力）はテキストを含まないことを忘れないでください。

#### 画像の目視検査

**重要：検証画像を目視確認せずに先へ進まないでください**
- 赤枠は入力領域のみを覆う
- 赤枠は文字を含まない
- 青枠はラベル文字を含む
- チェックボックスの場合：
  - 赤枠はチェックボックスの四角の中心にある
  - 青枠はチェックボックスのラベル文字を覆う

枠が不適切に見える場合、fields.jsonを修正し、検証画像を再生成して再検証します。枠が完全に正確になるまで繰り返します。

### ステップ4：PDFに注釈を追加

fields.jsonの情報を使い、次のスクリプトで記入済みPDFを作成します（このファイルのディレクトリで実行）：  
`python scripts/fill_pdf_form_with_annotations.py <input_pdf_path> <path_to_fields.json> <output_pdf_path>`


