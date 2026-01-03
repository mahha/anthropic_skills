#!/usr/bin/env python3
"""
PowerPointの各スライドから、サムネイルのグリッド画像を作成します。

列数（最大6）を指定してサムネイルをグリッド状に配置します。
1グリッドに含める最大枚数は cols×(cols+1) です。スライド数が多い場合は、
番号付きの複数グリッドファイルを自動生成します。

作成したファイル名はすべて標準出力に表示されます。

出力:
- 1グリッド: {prefix}.jpg（1枚に収まる場合）
- 複数グリッド: {prefix}-1.jpg, {prefix}-2.jpg, ...

列数ごとの上限:
- 3列: 最大12枚（3×4）
- 4列: 最大20枚（4×5）
- 5列: 最大30枚（5×6）[デフォルト]
- 6列: 最大42枚（6×7）

使い方:
    python thumbnail.py input.pptx [output_prefix] [--cols N] [--outline-placeholders]

例:
    python thumbnail.py presentation.pptx
    # 作成: thumbnails.jpg（デフォルトprefix）
    # 出力例:
    #   1個のグリッドを作成:
    #     - thumbnails.jpg

    python thumbnail.py large-deck.pptx grid --cols 4
    # 作成: grid-1.jpg, grid-2.jpg, grid-3.jpg
    # 出力例:
    #   3個のグリッドを作成:
    #     - grid-1.jpg
    #     - grid-2.jpg
    #     - grid-3.jpg

    python thumbnail.py template.pptx analysis --outline-placeholders
    # テキストプレースホルダを赤枠で囲んだサムネイルグリッドを作成します
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from inventory import extract_text_inventory
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation

# 定数
THUMBNAIL_WIDTH = 300  # サムネイル幅（px）
CONVERSION_DPI = 100  # PDF→画像変換のDPI
MAX_COLS = 6  # 最大列数
DEFAULT_COLS = 5  # デフォルト列数
JPEG_QUALITY = 95  # JPEG品質

# グリッドレイアウト定数
GRID_PADDING = 20  # サムネイル間の余白
BORDER_WIDTH = 2  # サムネイル枠線幅
FONT_SIZE_RATIO = 0.12  # サムネイル幅に対するフォントサイズ比
LABEL_PADDING_RATIO = 0.4  # フォントサイズに対するラベル余白比


def main():
    parser = argparse.ArgumentParser(
        description="PowerPointスライドからサムネイルグリッドを作成します。"
    )
    parser.add_argument("input", help="入力PowerPointファイル（.pptx）")
    parser.add_argument(
        "output_prefix",
        nargs="?",
        default="thumbnails",
        help="出力ファイルのprefix（デフォルト: thumbnails。prefix.jpg または prefix-N.jpg を作成）",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=DEFAULT_COLS,
        help=f"列数（デフォルト: {DEFAULT_COLS}, 最大: {MAX_COLS}）",
    )
    parser.add_argument(
        "--outline-placeholders",
        action="store_true",
        help="テキストプレースホルダを色付きの枠で囲む",
    )

    args = parser.parse_args()

    # 列数を検証
    cols = min(args.cols, MAX_COLS)
    if args.cols > MAX_COLS:
        print(f"警告: 列数は{MAX_COLS}までです（指定: {args.cols}）")

    # 入力を検証
    input_path = Path(args.input)
    if not input_path.exists() or input_path.suffix.lower() != ".pptx":
        print(f"エラー: 不正なPowerPointファイルです: {args.input}")
        sys.exit(1)

    # 出力パスを構築（常にJPG）
    output_path = Path(f"{args.output_prefix}.jpg")

    print(f"処理中: {args.input}")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # 枠線表示が有効ならプレースホルダ領域を取得
            placeholder_regions = None
            slide_dimensions = None
            if args.outline_placeholders:
                print("プレースホルダ領域を抽出中...")
                placeholder_regions, slide_dimensions = get_placeholder_regions(
                    input_path
                )
                if placeholder_regions:
                    print(f"{len(placeholder_regions)}枚のスライドでプレースホルダを検出しました")

            # スライドを画像へ変換
            slide_images = convert_to_images(input_path, Path(temp_dir), CONVERSION_DPI)
            if not slide_images:
                print("エラー: スライドが見つかりません")
                sys.exit(1)

            print(f"スライド数: {len(slide_images)}")

            # グリッドを作成（1グリッド最大 cols×(cols+1) 枚）
            grid_files = create_grids(
                slide_images,
                cols,
                THUMBNAIL_WIDTH,
                output_path,
                placeholder_regions,
                slide_dimensions,
            )

            # 保存したファイルを表示
            print(f"{len(grid_files)}個のグリッドを作成しました:")
            for grid_file in grid_files:
                print(f"  - {grid_file}")

    except Exception as e:
        print(f"エラー: {e}")
        sys.exit(1)


def create_hidden_slide_placeholder(size):
    """非表示スライド用のプレースホルダ画像を作成します。"""
    img = Image.new("RGB", size, color="#F0F0F0")
    draw = ImageDraw.Draw(img)
    line_width = max(5, min(size) // 100)
    draw.line([(0, 0), size], fill="#CCCCCC", width=line_width)
    draw.line([(size[0], 0), (0, size[1])], fill="#CCCCCC", width=line_width)
    return img


def get_placeholder_regions(pptx_path):
    """プレゼン内のテキスト領域をすべて抽出します。

    (placeholder_regions, slide_dimensions) を返します。
    placeholder_regionsはスライド番号→テキスト領域リストのdictです。
    各領域は 'left'/'top'/'width'/'height'（インチ）を持ちます。
    slide_dimensionsは (width_inches, height_inches) です。
    """
    prs = Presentation(str(pptx_path))
    inventory = extract_text_inventory(pptx_path, prs)
    placeholder_regions = {}

    # 実際のスライド寸法をインチで取得（EMU→インチ変換）
    slide_width_inches = (prs.slide_width or 9144000) / 914400.0
    slide_height_inches = (prs.slide_height or 5143500) / 914400.0

    for slide_key, shapes in inventory.items():
        # "slide-N" 形式からスライド番号を抽出
        slide_idx = int(slide_key.split("-")[1])
        regions = []

        for shape_key, shape_data in shapes.items():
            # inventoryはテキストを持つshapeのみなので、すべてハイライト対象
            regions.append(
                {
                    "left": shape_data.left,
                    "top": shape_data.top,
                    "width": shape_data.width,
                    "height": shape_data.height,
                }
            )

        if regions:
            placeholder_regions[slide_idx] = regions

    return placeholder_regions, (slide_width_inches, slide_height_inches)


def convert_to_images(pptx_path, temp_dir, dpi):
    """PDF経由でPowerPointを画像へ変換します（非表示スライドも扱います）。"""
    # 非表示スライドを検出
    print("プレゼンを解析中...")
    prs = Presentation(str(pptx_path))
    total_slides = len(prs.slides)

    # 非表示スライドを抽出（表示用に1始まり）
    hidden_slides = {
        idx + 1
        for idx, slide in enumerate(prs.slides)
        if slide.element.get("show") == "0"
    }

    print(f"総スライド数: {total_slides}")
    if hidden_slides:
        print(f"非表示スライド: {sorted(hidden_slides)}")

    pdf_path = temp_dir / f"{pptx_path.stem}.pdf"

    # PDFへ変換
    print("PDFへ変換中...")
    result = subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temp_dir),
            str(pptx_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError("PDF conversion failed")

    # PDFを画像へ変換
    print(f"{dpi} DPIで画像へ変換中...")
    result = subprocess.run(
        ["pdftoppm", "-jpeg", "-r", str(dpi), str(pdf_path), str(temp_dir / "slide")],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Image conversion failed")

    visible_images = sorted(temp_dir.glob("slide-*.jpg"))

    # 非表示スライド用プレースホルダを含む全リストを作成
    all_images = []
    visible_idx = 0

    # 最初の表示スライドからプレースホルダ寸法を取得
    if visible_images:
        with Image.open(visible_images[0]) as img:
            placeholder_size = img.size
    else:
        placeholder_size = (1920, 1080)

    for slide_num in range(1, total_slides + 1):
        if slide_num in hidden_slides:
            # 非表示スライド用のプレースホルダ画像を作成
            placeholder_path = temp_dir / f"hidden-{slide_num:03d}.jpg"
            placeholder_img = create_hidden_slide_placeholder(placeholder_size)
            placeholder_img.save(placeholder_path, "JPEG")
            all_images.append(placeholder_path)
        else:
            # 表示スライドの実画像を使用
            if visible_idx < len(visible_images):
                all_images.append(visible_images[visible_idx])
                visible_idx += 1

    return all_images


def create_grids(
    image_paths,
    cols,
    width,
    output_path,
    placeholder_regions=None,
    slide_dimensions=None,
):
    """スライド画像から複数のサムネイルグリッドを作成します（1グリッド最大 cols×(cols+1) 枚）。"""
    # 1グリッド最大枚数は cols×(cols+1)（見た目の比率が良い）
    max_images_per_grid = cols * (cols + 1)
    grid_files = []

    print(
        f"Creating grids with {cols} columns (max {max_images_per_grid} images per grid)"
    )

    # 画像をチャンクに分割
    for chunk_idx, start_idx in enumerate(
        range(0, len(image_paths), max_images_per_grid)
    ):
        end_idx = min(start_idx + max_images_per_grid, len(image_paths))
        chunk_images = image_paths[start_idx:end_idx]

        # このチャンクのグリッドを作成
        grid = create_grid(
            chunk_images, cols, width, start_idx, placeholder_regions, slide_dimensions
        )

        # 出力ファイル名を生成
        if len(image_paths) <= max_images_per_grid:
            # 単一グリッド: サフィックス無しの基本ファイル名を使う
            grid_filename = output_path
        else:
            # 複数グリッド: 拡張子の前に -番号 を付ける
            stem = output_path.stem
            suffix = output_path.suffix
            grid_filename = output_path.parent / f"{stem}-{chunk_idx + 1}{suffix}"

        # グリッドを保存
        grid_filename.parent.mkdir(parents=True, exist_ok=True)
        grid.save(str(grid_filename), quality=JPEG_QUALITY)
        grid_files.append(str(grid_filename))

    return grid_files


def create_grid(
    image_paths,
    cols,
    width,
    start_slide_num=0,
    placeholder_regions=None,
    slide_dimensions=None,
):
    """スライド画像からサムネイルグリッドを作成します（プレースホルダ枠線表示は任意）。"""
    font_size = int(width * FONT_SIZE_RATIO)
    label_padding = int(font_size * LABEL_PADDING_RATIO)

    # 寸法を取得
    with Image.open(image_paths[0]) as img:
        aspect = img.height / img.width
    height = int(width * aspect)

    # グリッドサイズを計算
    rows = (len(image_paths) + cols - 1) // cols
    grid_w = cols * width + (cols + 1) * GRID_PADDING
    grid_h = rows * (height + font_size + label_padding * 2) + (rows + 1) * GRID_PADDING

    # グリッド画像を作成
    grid = Image.new("RGB", (grid_w, grid_h), "white")
    draw = ImageDraw.Draw(grid)

    # サムネイル幅に基づくサイズでフォントを読み込む
    try:
        # Pillowのデフォルトフォントをサイズ指定で使用
        font = ImageFont.load_default(size=font_size)
    except Exception:
        # サイズ指定が未対応なら、基本のデフォルトフォントにフォールバック
        font = ImageFont.load_default()

    # サムネイルを配置
    for i, img_path in enumerate(image_paths):
        row, col = i // cols, i % cols
        x = col * width + (col + 1) * GRID_PADDING
        y_base = (
            row * (height + font_size + label_padding * 2) + (row + 1) * GRID_PADDING
        )

        # 実際のスライド番号のラベルを追加
        label = f"{start_slide_num + i}"
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(
            (x + (width - text_w) // 2, y_base + label_padding),
            label,
            fill="black",
            font=font,
        )

        # ラベル下にサムネイルを配置（比率に応じた余白）
        y_thumbnail = y_base + label_padding + font_size + label_padding

        with Image.open(img_path) as img:
            # サムネイル化前の元寸法を取得
            orig_w, orig_h = img.size

            # 有効ならプレースホルダ枠線を描画
            if placeholder_regions and (start_slide_num + i) in placeholder_regions:
                # 透明合成のためRGBAへ変換
                if img.mode != "RGBA":
                    img = img.convert("RGBA")

                # このスライドの領域情報を取得
                regions = placeholder_regions[start_slide_num + i]

                # 実スライド寸法からスケール係数を計算
                if slide_dimensions:
                    slide_width_inches, slide_height_inches = slide_dimensions
                else:
                    # フォールバック: CONVERSION_DPI時の画像サイズから推定
                    slide_width_inches = orig_w / CONVERSION_DPI
                    slide_height_inches = orig_h / CONVERSION_DPI

                x_scale = orig_w / slide_width_inches
                y_scale = orig_h / slide_height_inches

                # ハイライト用オーバーレイを作成
                overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
                overlay_draw = ImageDraw.Draw(overlay)

                # 各プレースホルダ領域をハイライト
                for region in regions:
                    # 元画像のピクセル座標へ変換（インチ→px）
                    px_left = int(region["left"] * x_scale)
                    px_top = int(region["top"] * y_scale)
                    px_width = int(region["width"] * x_scale)
                    px_height = int(region["height"] * y_scale)

                    # 赤い太線で枠を描画（塗りではなく枠線）
                    stroke_width = max(
                        5, min(orig_w, orig_h) // 150
                    )  # 比率に応じて太めのstroke幅
                    overlay_draw.rectangle(
                        [(px_left, px_top), (px_left + px_width, px_top + px_height)],
                        outline=(255, 0, 0, 255),  # 明るい赤（完全不透明）
                        width=stroke_width,
                    )

                # アルファブレンドでオーバーレイを合成
                img = Image.alpha_composite(img, overlay)
                # JPEG保存のためRGBへ戻す
                img = img.convert("RGB")

            img.thumbnail((width, height), Image.Resampling.LANCZOS)
            w, h = img.size
            tx = x + (width - w) // 2
            ty = y_thumbnail + (height - h) // 2
            grid.paste(img, (tx, ty))

            # 枠線を追加
            if BORDER_WIDTH > 0:
                draw.rectangle(
                    [
                        (tx - BORDER_WIDTH, ty - BORDER_WIDTH),
                        (tx + w + BORDER_WIDTH - 1, ty + h + BORDER_WIDTH - 1),
                    ],
                    outline="gray",
                    width=BORDER_WIDTH,
                )

    return grid


if __name__ == "__main__":
    main()
