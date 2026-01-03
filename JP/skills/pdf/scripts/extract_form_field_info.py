import json
import sys

from pypdf import PdfReader


# PDF内の入力可能なフォームフィールドに関する情報を抽出し、
# Claudeがフィールドを埋めるために使うJSONを出力します。forms.mdを参照。


# PdfReaderの`get_fields`および`update_page_form_field_values`が用いる形式に合わせています。
def get_full_annotation_field_id(annotation):
    components = []
    while annotation:
        field_name = annotation.get('/T')
        if field_name:
            components.append(field_name)
        annotation = annotation.get('/Parent')
    return ".".join(reversed(components)) if components else None


def make_field_dict(field, field_id):
    field_dict = {"field_id": field_id}
    ft = field.get('/FT')
    if ft == "/Tx":
        field_dict["type"] = "text"
    elif ft == "/Btn":
        field_dict["type"] = "checkbox"  # radio groups handled separately
        states = field.get("/_States_", [])
        if len(states) == 2:
            # "/Off"は常に「未チェック値」になるようです（以下の仕様に示唆あり）
            # https://opensource.adobe.com/dc-acrobat-sdk-docs/standards/pdfstandards/pdf/PDF32000_2008.pdf#page=448
            # "/_States_"リスト内での位置は1番目/2番目いずれの場合もあります。
            if "/Off" in states:
                field_dict["checked_value"] = states[0] if states[0] != "/Off" else states[1]
                field_dict["unchecked_value"] = "/Off"
            else:
                print(f"チェックボックス`${field_id}`で想定外のstate値です。checked/uncheckedが正しくない可能性があります。チェックを入れる場合は結果を目視確認してください。")
                field_dict["checked_value"] = states[0]
                field_dict["unchecked_value"] = states[1]
    elif ft == "/Ch":
        field_dict["type"] = "choice"
        states = field.get("/_States_", [])
        field_dict["choice_options"] = [{
            "value": state[0],
            "text": state[1],
        } for state in states]
    else:
        field_dict["type"] = f"unknown ({ft})"
    return field_dict


# 入力可能なPDFフィールドのリストを返します：
# [
#   {
#     "field_id": "name",
#     "page": 1,
#     "type": ("text", "checkbox", "radio_group", or "choice")
#     // Per-type additional fields described in forms.md
#   },
# ]
def get_field_info(reader: PdfReader):
    fields = reader.get_fields()

    field_info_by_id = {}
    possible_radio_names = set()

    for field_id, field in fields.items():
        # 子要素を持つコンテナフィールドはスキップします。
        # ただし、ラジオボタン選択肢の親グループである可能性があるため例外扱いします。
        if field.get("/Kids"):
            if field.get("/FT") == "/Btn":
                possible_radio_names.add(field_id)
            continue
        field_info_by_id[field_id] = make_field_dict(field, field_id)

    # バウンディング矩形は、各ページオブジェクト内のアノテーションに格納されます。

    # ラジオボタンの選択肢は、各選択肢ごとに別アノテーションを持ちます。
    # ただし全選択肢は同じフィールド名を共有します。
    # See https://westhealth.github.io/exploring-fillable-forms-with-pdfrw.html
    radio_fields_by_id = {}

    for page_index, page in enumerate(reader.pages):
        annotations = page.get('/Annots', [])
        for ann in annotations:
            field_id = get_full_annotation_field_id(ann)
            if field_id in field_info_by_id:
                field_info_by_id[field_id]["page"] = page_index + 1
                field_info_by_id[field_id]["rect"] = ann.get('/Rect')
            elif field_id in possible_radio_names:
                try:
                    # ann['/AP']['/N'] should have two items. One of them is '/Off',
                    # the other is the active value.
                    on_values = [v for v in ann["/AP"]["/N"] if v != "/Off"]
                except KeyError:
                    continue
                if len(on_values) == 1:
                    rect = ann.get("/Rect")
                    if field_id not in radio_fields_by_id:
                        radio_fields_by_id[field_id] = {
                            "field_id": field_id,
                            "type": "radio_group",
                            "page": page_index + 1,
                            "radio_options": [],
                        }
                    # 注：少なくともmacOS 15.7では、Preview.appが選択済みラジオボタンを正しく表示しません。
                    # （値の先頭スラッシュを外すとPreviewでは表示されますが、Chrome/Firefox/Acrobat等で崩れます）
                    radio_fields_by_id[field_id]["radio_options"].append({
                        "value": on_values[0],
                        "rect": rect,
                    })

    # 一部PDFでは、フォーム定義があっても対応するアノテーションが無く、位置が特定できません。
    # その場合は現状これらのフィールドを無視します。
    fields_with_location = []
    for field_info in field_info_by_id.values():
        if "page" in field_info:
            fields_with_location.append(field_info)
        else:
            print(f"field_id={field_info.get('field_id')} の位置を特定できないため無視します")

    # ページ番号→Y位置（PDF座標系では上下が反転）→Xの順でソートします。
    def sort_key(f):
        if "radio_options" in f:
            rect = f["radio_options"][0]["rect"] or [0, 0, 0, 0]
        else:
            rect = f.get("rect") or [0, 0, 0, 0]
        adjusted_position = [-rect[1], rect[0]]
        return [f.get("page"), adjusted_position]
    
    sorted_fields = fields_with_location + list(radio_fields_by_id.values())
    sorted_fields.sort(key=sort_key)

    return sorted_fields


def write_field_info(pdf_path: str, json_output_path: str):
    reader = PdfReader(pdf_path)
    field_info = get_field_info(reader)
    with open(json_output_path, "w") as f:
        json.dump(field_info, f, indent=2)
    print(f"{len(field_info)}個のフィールドを {json_output_path} に書き出しました")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("使い方: extract_form_field_info.py [入力PDF] [出力JSON]")
        sys.exit(1)
    write_field_info(sys.argv[1], sys.argv[2])
