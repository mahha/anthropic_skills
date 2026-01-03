import json
import sys

from PIL import Image, ImageDraw


# ClaudeがPDF内のテキスト注釈をどこに追加するかを決める際に作成するバウンディングボックス情報をもとに、
# 矩形を描画した「検証用」画像を作成します。forms.mdを参照。


def create_validation_image(page_number, fields_json_path, input_path, output_path):
    # 入力ファイルは、forms.mdで説明されている`fields.json`形式である必要があります。
    with open(fields_json_path, 'r') as f:
        data = json.load(f)

        img = Image.open(input_path)
        draw = ImageDraw.Draw(img)
        num_boxes = 0
        
        for field in data["form_fields"]:
            if field["page_number"] == page_number:
                entry_box = field['entry_bounding_box']
                label_box = field['label_bounding_box']
                # 入力欄バウンディングボックスに赤枠、ラベルに青枠を描画します。
                draw.rectangle(entry_box, outline='red', width=2)
                draw.rectangle(label_box, outline='blue', width=2)
                num_boxes += 2
        
        img.save(output_path)
        print(f"{output_path} に検証画像を作成しました（バウンディングボックス数: {num_boxes}）")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("使い方: create_validation_image.py [ページ番号] [fields.json] [入力画像パス] [出力画像パス]")
        sys.exit(1)
    page_number = int(sys.argv[1])
    fields_json_path = sys.argv[2]
    input_image_path = sys.argv[3]
    output_image_path = sys.argv[4]
    create_validation_image(page_number, fields_json_path, input_image_path, output_image_path)
