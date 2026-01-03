#!/usr/bin/env python3
"""
フレーム合成ユーティリティ - ビジュアル要素をフレームへ合成するための関数群です。

図形/テキスト/絵文字の描画や、要素を合成してアニメーション用フレームを作るための機能を提供します。
"""

from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def create_blank_frame(
    width: int, height: int, color: tuple[int, int, int] = (255, 255, 255)
) -> Image.Image:
    """
    単色背景の空フレームを作成します。

    Args:
        width: フレーム幅
        height: フレーム高
        color: RGB色タプル（デフォルト: 白）

    Returns:
        PIL Image
    """
    return Image.new("RGB", (width, height), color)


def draw_circle(
    frame: Image.Image,
    center: tuple[int, int],
    radius: int,
    fill_color: Optional[tuple[int, int, int]] = None,
    outline_color: Optional[tuple[int, int, int]] = None,
    outline_width: int = 1,
) -> Image.Image:
    """
    フレーム上に円を描画します。

    Args:
        frame: 描画対象のPIL Image
        center: 中心座標(x, y)
        radius: 半径
        fill_color: 塗りつぶしRGB（Noneなら塗りなし）
        outline_color: 枠線RGB（Noneなら枠線なし）
        outline_width: 枠線幅（px）

    Returns:
        変更後のフレーム
    """
    draw = ImageDraw.Draw(frame)
    x, y = center
    bbox = [x - radius, y - radius, x + radius, y + radius]
    draw.ellipse(bbox, fill=fill_color, outline=outline_color, width=outline_width)
    return frame


def draw_text(
    frame: Image.Image,
    text: str,
    position: tuple[int, int],
    color: tuple[int, int, int] = (0, 0, 0),
    centered: bool = False,
) -> Image.Image:
    """
    フレーム上にテキストを描画します。

    Args:
        frame: 描画対象のPIL Image
        text: 描画するテキスト
        position: 座標(x, y)（centered=Trueでない限り左上基準）
        color: テキストRGB
        centered: Trueなら指定座標を中心に配置

    Returns:
        変更後のフレーム
    """
    draw = ImageDraw.Draw(frame)

    # Pillowのデフォルトフォントを使用します。
    # 絵文字用にフォントを変えたい場合は、ここに追加ロジックを入れてください。
    font = ImageFont.load_default()

    if centered:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = position[0] - text_width // 2
        y = position[1] - text_height // 2
        position = (x, y)

    draw.text(position, text, fill=color, font=font)
    return frame


def create_gradient_background(
    width: int,
    height: int,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
) -> Image.Image:
    """
    縦方向のグラデーション背景を作成します。

    Args:
        width: フレーム幅
        height: フレーム高
        top_color: 上側のRGB
        bottom_color: 下側のRGB

    Returns:
        グラデーション付きPIL Image
    """
    frame = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(frame)

    # 行ごとの色ステップを計算
    r1, g1, b1 = top_color
    r2, g2, b2 = bottom_color

    for y in range(height):
        # 色を補間
        ratio = y / height
        r = int(r1 * (1 - ratio) + r2 * ratio)
        g = int(g1 * (1 - ratio) + g2 * ratio)
        b = int(b1 * (1 - ratio) + b2 * ratio)

        # 水平線を描画
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return frame


def draw_star(
    frame: Image.Image,
    center: tuple[int, int],
    size: int,
    fill_color: tuple[int, int, int],
    outline_color: Optional[tuple[int, int, int]] = None,
    outline_width: int = 1,
) -> Image.Image:
    """
    5つ星（五芒星）を描画します。

    Args:
        frame: 描画対象のPIL Image
        center: 中心座標(x, y)
        size: 星のサイズ（外接円半径）
        fill_color: 塗りつぶしRGB
        outline_color: 枠線RGB（Noneなら枠線なし）
        outline_width: 枠線幅

    Returns:
        変更後のフレーム
    """
    import math

    draw = ImageDraw.Draw(frame)
    x, y = center

    # 星の頂点を計算
    points = []
    for i in range(10):
        angle = (i * 36 - 90) * math.pi / 180  # 1点あたり36度、上から開始
        radius = size if i % 2 == 0 else size * 0.4  # 外側/内側を交互に
        px = x + radius * math.cos(angle)
        py = y + radius * math.sin(angle)
        points.append((px, py))

    # 星を描画
    draw.polygon(points, fill=fill_color, outline=outline_color, width=outline_width)

    return frame
