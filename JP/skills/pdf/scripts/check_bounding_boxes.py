from dataclasses import dataclass
import json
import sys


# ClaudeがPDF解析時に作成する`fields.json`について、
# バウンディングボックスが重なっていないことをチェックするスクリプトです。forms.mdを参照。


@dataclass
class RectAndField:
    rect: list[float]
    rect_type: str
    field: dict


# Claudeが読み取れるようにstdoutへ出力するメッセージのリストを返します。
def get_bounding_box_messages(fields_json_stream) -> list[str]:
    messages = []
    fields = json.load(fields_json_stream)
    messages.append(f"Read {len(fields['form_fields'])} fields")

    def rects_intersect(r1, r2):
        disjoint_horizontal = r1[0] >= r2[2] or r1[2] <= r2[0]
        disjoint_vertical = r1[1] >= r2[3] or r1[3] <= r2[1]
        return not (disjoint_horizontal or disjoint_vertical)

    rects_and_fields = []
    for f in fields["form_fields"]:
        rects_and_fields.append(RectAndField(f["label_bounding_box"], "label", f))
        rects_and_fields.append(RectAndField(f["entry_bounding_box"], "entry", f))

    has_error = False
    for i, ri in enumerate(rects_and_fields):
        # 計算量はO(N^2)。問題になる場合は最適化できます。
        for j in range(i + 1, len(rects_and_fields)):
            rj = rects_and_fields[j]
            if ri.field["page_number"] == rj.field["page_number"] and rects_intersect(ri.rect, rj.rect):
                has_error = True
                if ri.field is rj.field:
                    messages.append(f"FAILURE: intersection between label and entry bounding boxes for `{ri.field['description']}` ({ri.rect}, {rj.rect})")
                else:
                    messages.append(f"FAILURE: intersection between {ri.rect_type} bounding box for `{ri.field['description']}` ({ri.rect}) and {rj.rect_type} bounding box for `{rj.field['description']}` ({rj.rect})")
                if len(messages) >= 20:
                    messages.append("以降のチェックを中断します。バウンディングボックスを修正して再実行してください。")
                    return messages
        if ri.rect_type == "entry":
            if "entry_text" in ri.field:
                font_size = ri.field["entry_text"].get("font_size", 14)
                entry_height = ri.rect[3] - ri.rect[1]
                if entry_height < font_size:
                    has_error = True
                    messages.append(
                        f"FAILURE: `{ri.field['description']}` の入力バウンディングボックスの高さ（{entry_height}）が、"
                        f"テキスト内容に対して不足しています（フォントサイズ: {font_size}）。"
                        "ボックスの高さを増やすか、フォントサイズを下げてください。"
                    )
                    if len(messages) >= 20:
                        messages.append("以降のチェックを中断します。バウンディングボックスを修正して再実行してください。")
                        return messages

    if not has_error:
        messages.append("SUCCESS: すべてのバウンディングボックスは有効です")
    return messages

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使い方: check_bounding_boxes.py [fields.json]")
        sys.exit(1)
    # 入力ファイルは、forms.mdで説明されている`fields.json`形式である必要があります。
    with open(sys.argv[1]) as f:
        messages = get_bounding_box_messages(f)
    for msg in messages:
        print(msg)
