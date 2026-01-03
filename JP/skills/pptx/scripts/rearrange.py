#!/usr/bin/env python3
"""
指定したインデックス列に基づいて、PowerPointのスライド順を組み替えます。

使い方:
    python rearrange.py template.pptx output.pptx 0,34,34,50,52

template.pptx から指定順にスライドを取り出して output.pptx を作成します。
スライドは重複指定できます（例: 34を2回など）。
"""

import argparse
import shutil
import sys
from copy import deepcopy
from pathlib import Path

import six
from pptx import Presentation


def main():
    parser = argparse.ArgumentParser(
        description="指定したインデックス列に基づいてPowerPointスライドを組み替えます。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python rearrange.py template.pptx output.pptx 0,34,34,50,52
    template.pptx の 0, 34（2回）, 50, 52 を使って output.pptx を作成します

  python rearrange.py template.pptx output.pptx 5,3,1,2,4
    指定順に並べ替えた output.pptx を作成します

注: スライド番号は0始まりです（最初=0、次=1…）
        """,
    )

    parser.add_argument("template", help="テンプレートPPTXのパス")
    parser.add_argument("output", help="出力PPTXのパス")
    parser.add_argument(
        "sequence", help="スライド番号のカンマ区切り列（0始まり）"
    )

    args = parser.parse_args()

    # スライド番号列をパース
    try:
        slide_sequence = [int(x.strip()) for x in args.sequence.split(",")]
    except ValueError:
        print(
            "エラー: sequence形式が不正です。カンマ区切り整数にしてください（例: 0,34,34,50,52）"
        )
        sys.exit(1)

    # テンプレートの存在確認
    template_path = Path(args.template)
    if not template_path.exists():
        print(f"エラー: テンプレートファイルが見つかりません: {args.template}")
        sys.exit(1)

    # 必要なら出力ディレクトリを作成
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        rearrange_presentation(template_path, output_path, slide_sequence)
    except ValueError as e:
        print(f"エラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"プレゼン処理中のエラー: {e}")
        sys.exit(1)


def duplicate_slide(pres, index):
    """プレゼン内のスライドを複製します。"""
    source = pres.slides[index]

    # レイアウトを引き継いで体裁を保つ
    new_slide = pres.slides.add_slide(source.slide_layout)

    # 元スライドの画像/メディアのリレーションを収集
    image_rels = {}
    for rel_id, rel in six.iteritems(source.part.rels):
        if "image" in rel.reltype or "media" in rel.reltype:
            image_rels[rel_id] = rel

    # 重要: プレースホルダ形状をクリアして重複を避ける
    for shape in new_slide.shapes:
        sp = shape.element
        sp.getparent().remove(sp)

    # 元スライドの全shapeをコピー
    for shape in source.shapes:
        el = shape.element
        new_el = deepcopy(el)
        new_slide.shapes._spTree.insert_element_before(new_el, "p:extLst")

        # 画像shape対応: blip参照（埋め込みrId）を更新する必要がある
        # pic以外のコンテキストにもあるため、全blip要素を探す
        # namesapces指定なしで要素自身のxpathを使う
        blips = new_el.xpath(".//a:blip[@r:embed]")
        for blip in blips:
            old_rId = blip.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            )
            if old_rId in image_rels:
                # 宛先スライド側にこの画像の新しいリレーションを作る
                old_rel = image_rels[old_rId]
                # get_or_addは既存rIdを返すか、追加して新rIdを返す
                new_rId = new_slide.part.rels.get_or_add(
                    old_rel.reltype, old_rel._target
                )
                # blipのembed参照を新しいリレーションIDへ更新
                blip.set(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed",
                    new_rId,
                )

    # 他所で参照される可能性のある追加の画像/メディアリレーションもコピー
    for rel_id, rel in image_rels.items():
        try:
            new_slide.part.rels.get_or_add(rel.reltype, rel._target)
        except Exception:
            pass  # 既に存在する可能性あり

    return new_slide


def delete_slide(pres, index):
    """プレゼンからスライドを削除します。"""
    rId = pres.slides._sldIdLst[index].rId
    pres.part.drop_rel(rId)
    del pres.slides._sldIdLst[index]


def reorder_slides(pres, slide_index, target_index):
    """スライドを別の位置へ移動します。"""
    slides = pres.slides._sldIdLst

    # 現在位置から要素を取り除く
    slide_element = slides[slide_index]
    slides.remove(slide_element)

    # 目的位置へ挿入
    slides.insert(target_index, slide_element)


def rearrange_presentation(template_path, output_path, slide_sequence):
    """
    テンプレートから指定順にスライドを取り出し、新しいプレゼンを作成します。

    Args:
        template_path: テンプレートPPTXのパス
        output_path: 出力PPTXのパス
        slide_sequence: 取り込むスライド番号（0始まり）のリスト
    """
    # 寸法とテーマを保つためテンプレートをコピー
    if template_path != output_path:
        shutil.copy2(template_path, output_path)
        prs = Presentation(output_path)
    else:
        prs = Presentation(template_path)

    total_slides = len(prs.slides)

    # インデックス検証
    for idx in slide_sequence:
        if idx < 0 or idx >= total_slides:
            raise ValueError(f"Slide index {idx} out of range (0-{total_slides - 1})")

    # 元スライドと複製スライドの対応を追跡
    slide_map = []  # List of actual slide indices for final presentation
    duplicated = {}  # Track duplicates: original_idx -> [duplicate_indices]

    # Step 1: 重複指定されたスライドを複製
    print(f"テンプレートから {len(slide_sequence)} 枚のスライドを処理します...")
    for i, template_idx in enumerate(slide_sequence):
        if template_idx in duplicated and duplicated[template_idx]:
            # Already duplicated this slide, use the duplicate
            slide_map.append(duplicated[template_idx].pop(0))
            print(f"  [{i}] スライド{template_idx}の複製を使用します")
        elif slide_sequence.count(template_idx) > 1 and template_idx not in duplicated:
            # First occurrence of a repeated slide - create duplicates
            slide_map.append(template_idx)
            duplicates = []
            count = slide_sequence.count(template_idx) - 1
            print(f"  [{i}] 元スライド{template_idx}を使用し、複製を{count}枚作成します")
            for _ in range(count):
                duplicate_slide(prs, template_idx)
                duplicates.append(len(prs.slides) - 1)
            duplicated[template_idx] = duplicates
        else:
            # Unique slide or first occurrence already handled, use original
            slide_map.append(template_idx)
            print(f"  [{i}] 元スライド{template_idx}を使用します")

    # Step 2: 不要スライドを削除（後ろから）
    slides_to_keep = set(slide_map)
    print(f"\n未使用スライドを {len(prs.slides) - len(slides_to_keep)} 枚削除します...")
    for i in range(len(prs.slides) - 1, -1, -1):
        if i not in slides_to_keep:
            delete_slide(prs, i)
            # 削除に伴いslide_mapのインデックスを更新
            slide_map = [idx - 1 if idx > i else idx for idx in slide_map]

    # Step 3: 最終的な順序に並べ替え
    print(f"{len(slide_map)} 枚のスライドを最終シーケンスへ並べ替えます...")
    for target_pos in range(len(slide_map)):
        # target_posに置くべきスライドを探す
        current_pos = slide_map[target_pos]
        if current_pos != target_pos:
            reorder_slides(prs, current_pos, target_pos)
            # 移動により他スライドの位置もずれるためslide_mapを更新
            for i in range(len(slide_map)):
                if slide_map[i] > current_pos and slide_map[i] <= target_pos:
                    slide_map[i] -= 1
                elif slide_map[i] < current_pos and slide_map[i] >= target_pos:
                    slide_map[i] += 1
            slide_map[target_pos] = target_pos

    # 保存
    prs.save(output_path)
    print(f"\n並べ替えたプレゼンを保存しました: {output_path}")
    print(f"最終スライド枚数: {len(prs.slides)}")


if __name__ == "__main__":
    main()
