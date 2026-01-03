import json
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText


# `fields.json`で定義されたテキスト注釈を追加してPDFに記入します。forms.mdを参照。


def transform_coordinates(bbox, image_width, image_height, pdf_width, pdf_height):
    """バウンディングボックスを画像座標からPDF座標へ変換する"""
    # 画像座標: 原点は左上、yは下方向に増加
    # PDF座標: 原点は左下、yは上方向に増加
    x_scale = pdf_width / image_width
    y_scale = pdf_height / image_height
    
    left = bbox[0] * x_scale
    right = bbox[2] * x_scale
    
    # PDF用にY座標を反転
    top = pdf_height - (bbox[1] * y_scale)
    bottom = pdf_height - (bbox[3] * y_scale)
    
    return left, bottom, right, top


def fill_pdf_form(input_pdf_path, fields_json_path, output_pdf_path):
    """fields.jsonのデータでPDFフォームを記入する"""
    
    # 入力の`fields.json`はforms.mdで説明されている形式です。
    with open(fields_json_path, "r") as f:
        fields_data = json.load(f)
    
    # PDFを開く
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    
    # 全ページをwriterへコピー
    writer.append(reader)
    
    # ページごとのPDF寸法を取得
    pdf_dimensions = {}
    for i, page in enumerate(reader.pages):
        mediabox = page.mediabox
        pdf_dimensions[i + 1] = [mediabox.width, mediabox.height]
    
    # 各フォームフィールドを処理
    annotations = []
    for field in fields_data["form_fields"]:
        page_num = field["page_number"]
        
        # ページ寸法を取得し、座標を変換
        page_info = next(p for p in fields_data["pages"] if p["page_number"] == page_num)
        image_width = page_info["image_width"]
        image_height = page_info["image_height"]
        pdf_width, pdf_height = pdf_dimensions[page_num]
        
        transformed_entry_box = transform_coordinates(
            field["entry_bounding_box"],
            image_width, image_height,
            pdf_width, pdf_height
        )
        
        # 空フィールドはスキップ
        if "entry_text" not in field or "text" not in field["entry_text"]:
            continue
        entry_text = field["entry_text"]
        text = entry_text["text"]
        if not text:
            continue
        
        font_name = entry_text.get("font", "Arial")
        font_size = str(entry_text.get("font_size", 14)) + "pt"
        font_color = entry_text.get("font_color", "000000")

        # フォントサイズ/色はビューアによって安定して反映されない場合があります：
        # https://github.com/py-pdf/pypdf/issues/2084
        annotation = FreeText(
            text=text,
            rect=transformed_entry_box,
            font=font_name,
            font_size=font_size,
            font_color=font_color,
            border_color=None,
            background_color=None,
        )
        annotations.append(annotation)
        # pypdfのpage_numberは0始まり
        writer.add_annotation(page_number=page_num - 1, annotation=annotation)
        
    # 記入済みPDFを保存
    with open(output_pdf_path, "wb") as output:
        writer.write(output)
    
    print(f"PDFフォームへの記入が完了し、{output_pdf_path} に保存しました")
    print(f"追加したテキスト注釈数: {len(annotations)}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("使い方: fill_pdf_form_with_annotations.py [入力PDF] [fields.json] [出力PDF]")
        sys.exit(1)
    input_pdf = sys.argv[1]
    fields_json = sys.argv[2]
    output_pdf = sys.argv[3]
    
    fill_pdf_form(input_pdf, fields_json, output_pdf)