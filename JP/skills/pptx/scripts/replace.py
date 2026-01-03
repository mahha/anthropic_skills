#!/usr/bin/env python3
"""PowerPointプレゼンにテキスト置換を適用します。

使い方:
    python replace.py <input.pptx> <replacements.json> <output.pptx>

replacements.json は inventory.py が出力する構造に従う必要があります。
inventory.py が特定したテキストshapeは、replacements内でそのshapeに "paragraphs" を指定しない限り、
テキストがクリアされます。
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from inventory import InventoryData, extract_text_inventory
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.text import PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Pt


def clear_paragraph_bullets(paragraph):
    """段落の箇条書き（bullet）設定をクリアします。"""
    pPr = paragraph._element.get_or_add_pPr()

    # 既存のbullet要素を削除
    for child in list(pPr):
        if (
            child.tag.endswith("buChar")
            or child.tag.endswith("buNone")
            or child.tag.endswith("buAutoNum")
            or child.tag.endswith("buFont")
        ):
            pPr.remove(child)

    return pPr


def apply_paragraph_properties(paragraph, para_data: Dict[str, Any]):
    """段落へ書式設定を適用します。"""
    # テキストは取得するが、ここではまだ段落へ直接セットしない
    text = para_data.get("text", "")

    # 段落プロパティを取得/作成
    pPr = clear_paragraph_bullets(paragraph)

    # 箇条書き（bullet）を処理
    if para_data.get("bullet", False):
        level = para_data.get("level", 0)
        paragraph.level = level

        # フォントサイズに比例したインデントを計算
        font_size = para_data.get("font_size", 18.0)
        level_indent_emu = int((font_size * (1.6 + level * 1.6)) * 12700)
        hanging_indent_emu = int(-font_size * 0.8 * 12700)

        # インデントを設定
        pPr.attrib["marL"] = str(level_indent_emu)
        pPr.attrib["indent"] = str(hanging_indent_emu)

        # 箇条書き記号を追加
        buChar = OxmlElement("a:buChar")
        buChar.set("char", "•")
        pPr.append(buChar)

        # bullet時は、未指定なら左寄せをデフォルトにする
        if "alignment" not in para_data:
            paragraph.alignment = PP_ALIGN.LEFT
    else:
        # 非bulletテキストではインデントを削除
        pPr.attrib["marL"] = "0"
        pPr.attrib["indent"] = "0"

        # buNone要素を追加
        buNone = OxmlElement("a:buNone")
        pPr.insert(0, buNone)

    # 配置（alignment）を適用
    if "alignment" in para_data:
        alignment_map = {
            "LEFT": PP_ALIGN.LEFT,
            "CENTER": PP_ALIGN.CENTER,
            "RIGHT": PP_ALIGN.RIGHT,
            "JUSTIFY": PP_ALIGN.JUSTIFY,
        }
        if para_data["alignment"] in alignment_map:
            paragraph.alignment = alignment_map[para_data["alignment"]]

    # 行間/段落間隔（spacing）を適用
    if "space_before" in para_data:
        paragraph.space_before = Pt(para_data["space_before"])
    if "space_after" in para_data:
        paragraph.space_after = Pt(para_data["space_after"])
    if "line_spacing" in para_data:
        paragraph.line_spacing = Pt(para_data["line_spacing"])

    # run単位の書式を適用
    if not paragraph.runs:
        run = paragraph.add_run()
        run.text = text
    else:
        run = paragraph.runs[0]
        run.text = text

    # フォント属性を適用
    apply_font_properties(run, para_data)


def apply_font_properties(run, para_data: Dict[str, Any]):
    """テキストrunにフォント属性を適用します。"""
    if "bold" in para_data:
        run.font.bold = para_data["bold"]
    if "italic" in para_data:
        run.font.italic = para_data["italic"]
    if "underline" in para_data:
        run.font.underline = para_data["underline"]
    if "font_size" in para_data:
        run.font.size = Pt(para_data["font_size"])
    if "font_name" in para_data:
        run.font.name = para_data["font_name"]

    # 色を適用（RGB優先、無ければtheme_colorへフォールバック）
    if "color" in para_data:
        color_hex = para_data["color"].lstrip("#")
        if len(color_hex) == 6:
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)
            run.font.color.rgb = RGBColor(r, g, b)
    elif "theme_color" in para_data:
        # 名前からテーマカラーを取得（例: "DARK_1", "ACCENT_1"）
        theme_name = para_data["theme_color"]
        try:
            run.font.color.theme_color = getattr(MSO_THEME_COLOR, theme_name)
        except AttributeError:
            print(f"  WARNING: Unknown theme color name '{theme_name}'")


def detect_frame_overflow(inventory: InventoryData) -> Dict[str, Dict[str, float]]:
    """shape内のテキスト溢れを検出します（テキストがshape境界を超える場合）。

    Returns dict of slide_key -> shape_key -> overflow_inches.
    Only includes shapes that have text overflow.
    """
    overflow_map = {}

    for slide_key, shapes_dict in inventory.items():
        for shape_key, shape_data in shapes_dict.items():
            # フレーム溢れをチェック（テキストがshape境界を超える場合）
            if shape_data.frame_overflow_bottom is not None:
                if slide_key not in overflow_map:
                    overflow_map[slide_key] = {}
                overflow_map[slide_key][shape_key] = shape_data.frame_overflow_bottom

    return overflow_map


def validate_replacements(inventory: InventoryData, replacements: Dict) -> List[str]:
    """replacements内のshapeが、inventoryにすべて存在することを検証します。

    Returns list of error messages.
    """
    errors = []

    for slide_key, shapes_data in replacements.items():
        if not slide_key.startswith("slide-"):
            continue

        # スライドが存在するか確認
        if slide_key not in inventory:
            errors.append(f"Slide '{slide_key}' not found in inventory")
            continue

        # 各shapeを確認
        for shape_key in shapes_data.keys():
            if shape_key not in inventory[slide_key]:
                # replacements未定義のshapeを探し、内容プレビューを表示
                unused_with_content = []
                for k in inventory[slide_key].keys():
                    if k not in shapes_data:
                        shape_data = inventory[slide_key][k]
                        # 段落テキストをプレビューとして取得
                        paragraphs = shape_data.paragraphs
                        if paragraphs and paragraphs[0].text:
                            first_text = paragraphs[0].text[:50]
                            if len(paragraphs[0].text) > 50:
                                first_text += "..."
                            unused_with_content.append(f"{k} ('{first_text}')")
                        else:
                            unused_with_content.append(k)

                errors.append(
                    f"Shape '{shape_key}' not found on '{slide_key}'. "
                    f"Shapes without replacements: {', '.join(sorted(unused_with_content)) if unused_with_content else 'none'}"
                )

    return errors


def check_duplicate_keys(pairs):
    """JSON読み込み時に重複キーがないかチェックします。"""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate key found in JSON: '{key}'")
        result[key] = value
    return result


def apply_replacements(pptx_file: str, json_file: str, output_file: str):
    """JSONの指定に従ってPowerPointプレゼンへテキスト置換を適用します。"""

    # プレゼンを読み込む
    prs = Presentation(pptx_file)

    # 全テキストshapeのinventoryを取得（ShapeDataを返す）
    # 同一Presentationインスタンスを使うためprsを渡す
    inventory = extract_text_inventory(Path(pptx_file), prs)

    # 元プレゼンでテキスト溢れを検出
    original_overflow = detect_frame_overflow(inventory)

    # 重複キー検出付きで置換データを読み込む
    with open(json_file, "r") as f:
        replacements = json.load(f, object_pairs_hook=check_duplicate_keys)

    # 置換データを検証
    errors = validate_replacements(inventory, replacements)
    if errors:
        print("ERROR: Invalid shapes in replacement JSON:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease check the inventory and update your replacement JSON.")
        print(
            "You can regenerate the inventory with: python inventory.py <input.pptx> <output.json>"
        )
        raise ValueError(f"Found {len(errors)} validation error(s)")

    # 統計を記録
    shapes_processed = 0
    shapes_cleared = 0
    shapes_replaced = 0

    # inventoryの各スライドを処理
    for slide_key, shapes_dict in inventory.items():
        if not slide_key.startswith("slide-"):
            continue

        slide_index = int(slide_key.split("-")[1])

        if slide_index >= len(prs.slides):
            print(f"Warning: Slide {slide_index} not found")
            continue

        # inventoryの各shapeを処理
        for shape_key, shape_data in shapes_dict.items():
            shapes_processed += 1

            # ShapeDataから直接shapeを取得
            shape = shape_data.shape
            if not shape:
                print(f"Warning: {shape_key} has no shape reference")
                continue

            # ShapeDataは__init__でtext_frameを検証済み
            text_frame = shape.text_frame  # type: ignore

            text_frame.clear()  # type: ignore
            shapes_cleared += 1

            # 置換段落の有無を確認
            replacement_shape_data = replacements.get(slide_key, {}).get(shape_key, {})
            if "paragraphs" not in replacement_shape_data:
                continue

            shapes_replaced += 1

            # 置換段落を追加
            for i, para_data in enumerate(replacement_shape_data["paragraphs"]):
                if i == 0:
                    p = text_frame.paragraphs[0]  # type: ignore
                else:
                    p = text_frame.add_paragraph()  # type: ignore

                apply_paragraph_properties(p, para_data)

    # 置換後の問題をチェック
    # inventory取得中にプレゼンが改変されるのを避けるため、一時ファイルへ保存して再読み込みする
    # （extract_text_inventoryがfont.colorへアクセスすると、空の<a:solidFill/>要素が追加される）
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        prs.save(str(tmp_path))

    try:
        updated_inventory = extract_text_inventory(tmp_path)
        updated_overflow = detect_frame_overflow(updated_inventory)
    finally:
        tmp_path.unlink()  # 一時ファイルを削除

    # テキスト溢れが悪化していないか確認
    overflow_errors = []
    for slide_key, shape_overflows in updated_overflow.items():
        for shape_key, new_overflow in shape_overflows.items():
            # 元のoverflowを取得（元々無ければ0）
            original = original_overflow.get(slide_key, {}).get(shape_key, 0.0)

            # overflowが増えたらエラー
            if new_overflow > original + 0.01:  # 丸め誤差の小さな許容
                increase = new_overflow - original
                overflow_errors.append(
                    f'{slide_key}/{shape_key}: overflow worsened by {increase:.2f}" '
                    f'(was {original:.2f}", now {new_overflow:.2f}")'
                )

    # 更新したshapeから警告を収集
    warnings = []
    for slide_key, shapes_dict in updated_inventory.items():
        for shape_key, shape_data in shapes_dict.items():
            if shape_data.warnings:
                for warning in shape_data.warnings:
                    warnings.append(f"{slide_key}/{shape_key}: {warning}")

    # 問題があれば失敗扱い
    if overflow_errors or warnings:
        print("\nERROR: Issues detected in replacement output:")
        if overflow_errors:
            print("\nText overflow worsened:")
            for error in overflow_errors:
                print(f"  - {error}")
        if warnings:
            print("\nFormatting warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        print("\nPlease fix these issues before saving.")
        raise ValueError(
            f"Found {len(overflow_errors)} overflow error(s) and {len(warnings)} warning(s)"
        )

    # プレゼンを保存
    prs.save(output_file)

    # 結果を表示
    print(f"Saved updated presentation to: {output_file}")
    print(f"Processed {len(prs.slides)} slides")
    print(f"  - Shapes processed: {shapes_processed}")
    print(f"  - Shapes cleared: {shapes_cleared}")
    print(f"  - Shapes replaced: {shapes_replaced}")


def main():
    """コマンドライン実行時のエントリポイント。"""
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    input_pptx = Path(sys.argv[1])
    replacements_json = Path(sys.argv[2])
    output_pptx = Path(sys.argv[3])

    if not input_pptx.exists():
        print(f"Error: Input file '{input_pptx}' not found")
        sys.exit(1)

    if not replacements_json.exists():
        print(f"Error: Replacements JSON file '{replacements_json}' not found")
        sys.exit(1)

    try:
        apply_replacements(str(input_pptx), str(replacements_json), str(output_pptx))
    except Exception as e:
        print(f"Error applying replacements: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
