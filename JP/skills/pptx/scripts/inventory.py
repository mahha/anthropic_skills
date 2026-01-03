#!/usr/bin/env python3
"""
PowerPointプレゼンから、構造化されたテキスト内容を抽出します。

注: このファイルは大きいため、コメント/docstringの一部は原文（英語）を残しています。処理ロジックは変更していません。

主な機能:
- PowerPointのshapeから全テキストを抽出
- 段落の書式（配置、箇条書き、フォント、行間など）を保持
- ネストしたGroupShapeを再帰的に処理し、正しい絶対位置を計算
- スライド上の見た目位置でshapeをソート
- スライド番号や非コンテンツのプレースホルダを除外
- JSONとして扱いやすい構造で出力

クラス:
    ParagraphData: 書式付きテキスト段落
    ShapeData: 位置情報とテキスト内容を持つshape

主な関数:
    extract_text_inventory: プレゼンから全テキストを抽出
    save_inventory: 抽出データをJSONに保存

使い方:
    python inventory.py input.pptx output.json
"""

import argparse
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.shapes.base import BaseShape

# 型エイリアス（シグネチャを読みやすくする）
JsonValue = Union[str, int, float, bool, None]
ParagraphDict = Dict[str, JsonValue]
ShapeDict = Dict[
    str, Union[str, float, bool, List[ParagraphDict], List[str], Dict[str, Any], None]
]
InventoryData = Dict[
    str, Dict[str, "ShapeData"]
]  # スライドID -> {shape ID -> ShapeData}
InventoryDict = Dict[str, Dict[str, ShapeDict]]  # JSONシリアライズ可能なインベントリ


def main():
    """コマンドライン実行時のエントリポイント。"""
    parser = argparse.ArgumentParser(
        description="GroupShapeを正しく扱いながら、PowerPointからテキストインベントリを抽出します。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python inventory.py presentation.pptx inventory.json
    グループ化されたshapeについても、正しい絶対位置でテキストインベントリを抽出します

  python inventory.py presentation.pptx inventory.json --issues-only
    overflow/overlapの問題があるテキストshapeのみを抽出します

出力JSONには次が含まれます:
  - スライド/shape単位に整理された全テキスト内容
  - グループ内shapeの正しい絶対位置
  - 見た目の位置とサイズ（インチ）
  - 段落プロパティと書式
  - 問題検出: テキストoverflowとshapeの重なり
        """,
    )

    parser.add_argument("input", help="入力PowerPointファイル（.pptx）")
    parser.add_argument("output", help="出力JSONファイル（インベントリ）")
    parser.add_argument(
        "--issues-only",
        action="store_true",
        help="overflow/overlapの問題があるテキストshapeのみを含めます",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"エラー: 入力ファイルが見つかりません: {args.input}")
        sys.exit(1)

    if not input_path.suffix.lower() == ".pptx":
        print("エラー: 入力はPowerPointファイル（.pptx）である必要があります")
        sys.exit(1)

    try:
        print(f"テキストインベントリを抽出します: {args.input}")
        if args.issues_only:
            print(
                "issues-only: 問題（overflow/overlap）のあるテキストshapeのみに絞り込みます"
            )
        inventory = extract_text_inventory(input_path, issues_only=args.issues_only)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_inventory(inventory, output_path)

        print(f"出力を保存しました: {args.output}")

        # 統計を表示
        total_slides = len(inventory)
        total_shapes = sum(len(shapes) for shapes in inventory.values())
        if args.issues_only:
            if total_shapes > 0:
                print(
                    f"{total_slides}枚のスライドで、問題のあるテキスト要素を{total_shapes}件検出しました"
                )
            else:
                print("問題は見つかりませんでした")
        else:
            print(
                f"{total_slides}枚のスライドで、テキスト要素を{total_shapes}件検出しました"
            )

    except Exception as e:
        print(f"プレゼンの処理中にエラーが発生しました: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


@dataclass
class ShapeWithPosition:
    """スライド上の絶対位置を持つshapeです。"""

    shape: BaseShape
    absolute_left: int  # EMU単位
    absolute_top: int  # EMU単位


class ParagraphData:
    """PowerPointの段落から抽出した段落プロパティのデータ構造です。"""

    def __init__(self, paragraph: Any):
        """PowerPointの段落オブジェクトから初期化します。

        Args:
            paragraph: PowerPointの段落オブジェクト
        """
        self.text: str = paragraph.text.strip()
        self.bullet: bool = False
        self.level: Optional[int] = None
        self.alignment: Optional[str] = None
        self.space_before: Optional[float] = None
        self.space_after: Optional[float] = None
        self.font_name: Optional[str] = None
        self.font_size: Optional[float] = None
        self.bold: Optional[bool] = None
        self.italic: Optional[bool] = None
        self.underline: Optional[bool] = None
        self.color: Optional[str] = None
        self.theme_color: Optional[str] = None
        self.line_spacing: Optional[float] = None

        # 箇条書き（bullet）書式を確認
        if (
            hasattr(paragraph, "_p")
            and paragraph._p is not None
            and paragraph._p.pPr is not None
        ):
            pPr = paragraph._p.pPr
            ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
            if (
                pPr.find(f"{ns}buChar") is not None
                or pPr.find(f"{ns}buAutoNum") is not None
            ):
                self.bullet = True
                if hasattr(paragraph, "level"):
                    self.level = paragraph.level

        # LEFT（デフォルト）以外なら配置（alignment）を追加
        if hasattr(paragraph, "alignment") and paragraph.alignment is not None:
            alignment_map = {
                PP_ALIGN.CENTER: "CENTER",
                PP_ALIGN.RIGHT: "RIGHT",
                PP_ALIGN.JUSTIFY: "JUSTIFY",
            }
            if paragraph.alignment in alignment_map:
                self.alignment = alignment_map[paragraph.alignment]

        # 設定されていればspacingプロパティを追加
        if hasattr(paragraph, "space_before") and paragraph.space_before:
            self.space_before = paragraph.space_before.pt
        if hasattr(paragraph, "space_after") and paragraph.space_after:
            self.space_after = paragraph.space_after.pt

        # 最初のrunからフォント属性を抽出
        if paragraph.runs:
            first_run = paragraph.runs[0]
            if hasattr(first_run, "font"):
                font = first_run.font
                if font.name:
                    self.font_name = font.name
                if font.size:
                    self.font_size = font.size.pt
                if font.bold is not None:
                    self.bold = font.bold
                if font.italic is not None:
                    self.italic = font.italic
                if font.underline is not None:
                    self.underline = font.underline

                # 色を処理（RGBとテーマカラーの両方）
                try:
                    # まずRGBカラーを試す
                    if font.color.rgb:
                        self.color = str(font.color.rgb)
                except (AttributeError, TypeError):
                    # テーマカラーへフォールバック
                    try:
                        if font.color.theme_color:
                            self.theme_color = font.color.theme_color.name
                    except (AttributeError, TypeError):
                        pass

        # 設定されていれば行間（line spacing）を追加
        if hasattr(paragraph, "line_spacing") and paragraph.line_spacing is not None:
            if hasattr(paragraph.line_spacing, "pt"):
                self.line_spacing = round(paragraph.line_spacing.pt, 2)
            else:
                # 倍率（multiplier）→ポイントへ換算
                font_size = self.font_size if self.font_size else 12.0
                self.line_spacing = round(paragraph.line_spacing * font_size, 2)

    def to_dict(self) -> ParagraphDict:
        """None値を除外して、JSONシリアライズ用のdictへ変換します。"""
        result: ParagraphDict = {"text": self.text}

        # 値がある場合のみオプション項目を追加
        if self.bullet:
            result["bullet"] = self.bullet
        if self.level is not None:
            result["level"] = self.level
        if self.alignment:
            result["alignment"] = self.alignment
        if self.space_before is not None:
            result["space_before"] = self.space_before
        if self.space_after is not None:
            result["space_after"] = self.space_after
        if self.font_name:
            result["font_name"] = self.font_name
        if self.font_size is not None:
            result["font_size"] = self.font_size
        if self.bold is not None:
            result["bold"] = self.bold
        if self.italic is not None:
            result["italic"] = self.italic
        if self.underline is not None:
            result["underline"] = self.underline
        if self.color:
            result["color"] = self.color
        if self.theme_color:
            result["theme_color"] = self.theme_color
        if self.line_spacing is not None:
            result["line_spacing"] = self.line_spacing

        return result


class ShapeData:
    """PowerPointのshapeから抽出したshapeプロパティのデータ構造です。"""

    @staticmethod
    def emu_to_inches(emu: int) -> float:
        """EMU（PowerPoint内部単位）をインチに変換します。"""
        return emu / 914400.0

    @staticmethod
    def inches_to_pixels(inches: float, dpi: int = 96) -> int:
        """指定DPIで、インチをピクセルに変換します。"""
        return int(inches * dpi)

    @staticmethod
    def get_font_path(font_name: str) -> Optional[str]:
        """フォント名からフォントファイルのパスを取得します。

        Args:
            font_name: フォント名（例: 'Arial', 'Calibri'）

        Returns:
            フォントファイルのパス。見つからない場合はNone。
        """
        system = platform.system()

        # 試行する一般的なフォントファイル名のバリエーション
        font_variations = [
            font_name,
            font_name.lower(),
            font_name.replace(" ", ""),
            font_name.replace(" ", "-"),
        ]

        # OSごとにフォントディレクトリと拡張子を定義
        if system == "Darwin":  # macOS
            font_dirs = [
                "/System/Library/Fonts/",
                "/Library/Fonts/",
                "~/Library/Fonts/",
            ]
            extensions = [".ttf", ".otf", ".ttc", ".dfont"]
        else:  # Linux
            font_dirs = [
                "/usr/share/fonts/truetype/",
                "/usr/local/share/fonts/",
                "~/.fonts/",
            ]
            extensions = [".ttf", ".otf"]

        # フォントファイル探索を実行
        from pathlib import Path

        for font_dir in font_dirs:
            font_dir_path = Path(font_dir).expanduser()
            if not font_dir_path.exists():
                continue

            # まず完全一致を試す
            for variant in font_variations:
                for ext in extensions:
                    font_path = font_dir_path / f"{variant}{ext}"
                    if font_path.exists():
                        return str(font_path)

            # 次に曖昧一致（フォント名を含むファイル）を試す
            try:
                for file_path in font_dir_path.iterdir():
                    if file_path.is_file():
                        file_name_lower = file_path.name.lower()
                        font_name_lower = font_name.lower().replace(" ", "")
                        if font_name_lower in file_name_lower and any(
                            file_name_lower.endswith(ext) for ext in extensions
                        ):
                            return str(file_path)
            except (OSError, PermissionError):
                continue

        return None

    @staticmethod
    def get_slide_dimensions(slide: Any) -> tuple[Optional[int], Optional[int]]:
        """スライドオブジェクトからスライド寸法を取得します。

        Args:
            slide: スライドオブジェクト

        Returns:
            (width_emu, height_emu)。取得できない場合は (None, None)。
        """
        try:
            prs = slide.part.package.presentation_part.presentation
            return prs.slide_width, prs.slide_height
        except (AttributeError, TypeError):
            return None, None

    @staticmethod
    def get_default_font_size(shape: BaseShape, slide_layout: Any) -> Optional[float]:
        """プレースホルダshapeのデフォルトフォントサイズをスライドレイアウトから抽出します。

        Args:
            shape: プレースホルダshape
            slide_layout: プレースホルダ定義を含むスライドレイアウト

        Returns:
            デフォルトのフォントサイズ（ポイント）。見つからない場合はNone。
        """
        try:
            if not hasattr(shape, "placeholder_format"):
                return None

            shape_type = shape.placeholder_format.type  # type: ignore
            for layout_placeholder in slide_layout.placeholders:
                if layout_placeholder.placeholder_format.type == shape_type:
                    # sz（size）属性を持つ最初のdefRPr要素を探す
                    for elem in layout_placeholder.element.iter():
                        if "defRPr" in elem.tag and (sz := elem.get("sz")):
                            return float(sz) / 100.0  # EMU（PowerPoint内部単位）→ポイント
                    break
        except Exception:
            pass
        return None

    def __init__(
        self,
        shape: BaseShape,
        absolute_left: Optional[int] = None,
        absolute_top: Optional[int] = None,
        slide: Optional[Any] = None,
    ):
        """PowerPointのshapeオブジェクトから初期化します。

        Args:
            shape: PowerPointのshapeオブジェクト（事前に検証済みであること）
            absolute_left: 左位置（EMU。グループ内shape用の絶対位置）
            absolute_top: 上位置（EMU。グループ内shape用の絶対位置）
            slide: 寸法/レイアウト情報取得用のスライドオブジェクト（任意）
        """
        self.shape = shape  # 元shapeへの参照を保持
        self.shape_id: str = ""  # ソート後に設定

        # スライドオブジェクトから寸法を取得
        self.slide_width_emu, self.slide_height_emu = (
            self.get_slide_dimensions(slide) if slide else (None, None)
        )

        # 該当する場合はプレースホルダ種別を取得
        self.placeholder_type: Optional[str] = None
        self.default_font_size: Optional[float] = None
        if hasattr(shape, "is_placeholder") and shape.is_placeholder:  # type: ignore
            if shape.placeholder_format and shape.placeholder_format.type:  # type: ignore
                self.placeholder_type = (
                    str(shape.placeholder_format.type).split(".")[-1].split(" ")[0]  # type: ignore
                )

                # レイアウトからデフォルトフォントサイズを取得
                if slide and hasattr(slide, "slide_layout"):
                    self.default_font_size = self.get_default_font_size(
                        shape, slide.slide_layout
                    )

        # 位置情報を取得
        # 絶対位置が渡されていればそれを使う（グループ内shape用）。なければshape自身の位置を使う
        left_emu = (
            absolute_left
            if absolute_left is not None
            else (shape.left if hasattr(shape, "left") else 0)
        )
        top_emu = (
            absolute_top
            if absolute_top is not None
            else (shape.top if hasattr(shape, "top") else 0)
        )

        self.left: float = round(self.emu_to_inches(left_emu), 2)  # type: ignore
        self.top: float = round(self.emu_to_inches(top_emu), 2)  # type: ignore
        self.width: float = round(
            self.emu_to_inches(shape.width if hasattr(shape, "width") else 0),
            2,  # type: ignore
        )
        self.height: float = round(
            self.emu_to_inches(shape.height if hasattr(shape, "height") else 0),
            2,  # type: ignore
        )

        # overflow計算用にEMU座標を保存
        self.left_emu = left_emu
        self.top_emu = top_emu
        self.width_emu = shape.width if hasattr(shape, "width") else 0
        self.height_emu = shape.height if hasattr(shape, "height") else 0

        # overflow状態を計算
        self.frame_overflow_bottom: Optional[float] = None
        self.slide_overflow_right: Optional[float] = None
        self.slide_overflow_bottom: Optional[float] = None
        self.overlapping_shapes: Dict[
            str, float
        ] = {}  # shape_id -> 重なり面積（平方インチ）
        self.warnings: List[str] = []
        self._estimate_frame_overflow()
        self._calculate_slide_overflow()
        self._detect_bullet_issues()

    @property
    def paragraphs(self) -> List[ParagraphData]:
        """shapeのtext frameから段落を算出します。"""
        if not self.shape or not hasattr(self.shape, "text_frame"):
            return []

        paragraphs = []
        for paragraph in self.shape.text_frame.paragraphs:  # type: ignore
            if paragraph.text.strip():
                paragraphs.append(ParagraphData(paragraph))
        return paragraphs

    def _get_default_font_size(self) -> int:
        """テーマのテキストスタイルからデフォルトフォントサイズを取得し、無ければ控えめなデフォルトを使います。"""
        try:
            if not (
                hasattr(self.shape, "part") and hasattr(self.shape.part, "slide_layout")
            ):
                return 14

            slide_master = self.shape.part.slide_layout.slide_master  # type: ignore
            if not hasattr(slide_master, "element"):
                return 14

            # プレースホルダ種別からテーマスタイルを決定
            style_name = "bodyStyle"  # Default
            if self.placeholder_type and "TITLE" in self.placeholder_type:
                style_name = "titleStyle"

            # テーマスタイルからフォントサイズを探す
            for child in slide_master.element.iter():
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == style_name:
                    for elem in child.iter():
                        if "sz" in elem.attrib:
                            return int(elem.attrib["sz"]) // 100
        except Exception:
            pass

        return 14  # Conservative default for body text

    def _get_usable_dimensions(self, text_frame) -> Tuple[int, int]:
        """マージンを考慮した後の、使用可能な幅/高さ（px）を取得します。"""
        # PowerPointのデフォルトマージン（インチ）
        margins = {"top": 0.05, "bottom": 0.05, "left": 0.1, "right": 0.1}

        # 実マージンが設定されていればそれを優先
        if hasattr(text_frame, "margin_top") and text_frame.margin_top:
            margins["top"] = self.emu_to_inches(text_frame.margin_top)
        if hasattr(text_frame, "margin_bottom") and text_frame.margin_bottom:
            margins["bottom"] = self.emu_to_inches(text_frame.margin_bottom)
        if hasattr(text_frame, "margin_left") and text_frame.margin_left:
            margins["left"] = self.emu_to_inches(text_frame.margin_left)
        if hasattr(text_frame, "margin_right") and text_frame.margin_right:
            margins["right"] = self.emu_to_inches(text_frame.margin_right)

        # 使用可能領域を計算
        usable_width = self.width - margins["left"] - margins["right"]
        usable_height = self.height - margins["top"] - margins["bottom"]

        # ピクセルへ変換
        return (
            self.inches_to_pixels(usable_width),
            self.inches_to_pixels(usable_height),
        )

    def _wrap_text_line(self, line: str, max_width_px: int, draw, font) -> List[str]:
        """1行のテキストがmax_width_pxに収まるよう折り返します。"""
        if not line:
            return [""]

        # 幅計算を効率化するためtextlengthを使用
        if draw.textlength(line, font=font) <= max_width_px:
            return [line]

        # 折り返しが必要：単語に分割
        wrapped = []
        words = line.split(" ")
        current_line = ""

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if draw.textlength(test_line, font=font) <= max_width_px:
                current_line = test_line
            else:
                if current_line:
                    wrapped.append(current_line)
                current_line = word

        if current_line:
            wrapped.append(current_line)

        return wrapped

    def _estimate_frame_overflow(self) -> None:
        """PILのテキスト計測を使って、テキストがshape境界から溢れているかを推定します。"""
        if not self.shape or not hasattr(self.shape, "text_frame"):
            return

        text_frame = self.shape.text_frame  # type: ignore
        if not text_frame or not text_frame.paragraphs:
            return

        # マージン考慮後の使用可能寸法を取得
        usable_width_px, usable_height_px = self._get_usable_dimensions(text_frame)
        if usable_width_px <= 0 or usable_height_px <= 0:
            return

        # テキスト計測用にPILを準備
        dummy_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy_img)

        # プレースホルダのデフォルトフォントサイズを取得（無ければ控えめに推定）
        default_font_size = self._get_default_font_size()

        # 全段落の合計高さを計算
        total_height_px = 0

        for para_idx, paragraph in enumerate(text_frame.paragraphs):
            if not paragraph.text.strip():
                continue

            para_data = ParagraphData(paragraph)

            # この段落用のフォントを読み込む
            font_name = para_data.font_name or "Arial"
            font_size = int(para_data.font_size or default_font_size)

            font = None
            font_path = self.get_font_path(font_name)
            if font_path:
                try:
                    font = ImageFont.truetype(font_path, size=font_size)
                except Exception:
                    font = ImageFont.load_default()
            else:
                font = ImageFont.load_default()

            # この段落の全行を折り返す
            all_wrapped_lines = []
            for line in paragraph.text.split("\n"):
                wrapped = self._wrap_text_line(line, usable_width_px, draw, font)
                all_wrapped_lines.extend(wrapped)

            if all_wrapped_lines:
                # 行高さを計算
                if para_data.line_spacing:
                    # 明示的にカスタム行間が設定されている
                    line_height_px = para_data.line_spacing * 96 / 72
                else:
                    # PowerPointデフォルトの単一行間（フォントサイズの1.0倍）
                    line_height_px = font_size * 96 / 72

                # space_beforeを加算（最初の段落を除く）
                if para_idx > 0 and para_data.space_before:
                    total_height_px += para_data.space_before * 96 / 72

                # 段落テキストの高さを加算
                total_height_px += len(all_wrapped_lines) * line_height_px

                # space_afterを加算
                if para_data.space_after:
                    total_height_px += para_data.space_after * 96 / 72

        # overflowをチェック（<= 0.05\" の軽微なものは無視）
        if total_height_px > usable_height_px:
            overflow_px = total_height_px - usable_height_px
            overflow_inches = round(overflow_px / 96.0, 2)
            if overflow_inches > 0.05:  # Only report significant overflows
                self.frame_overflow_bottom = overflow_inches

    def _calculate_slide_overflow(self) -> None:
        """shapeがスライド境界からはみ出しているかを算出します。"""
        if self.slide_width_emu is None or self.slide_height_emu is None:
            return

        # 右方向のoverflowをチェック（<= 0.01\" の軽微なものは無視）
        right_edge_emu = self.left_emu + self.width_emu
        if right_edge_emu > self.slide_width_emu:
            overflow_emu = right_edge_emu - self.slide_width_emu
            overflow_inches = round(self.emu_to_inches(overflow_emu), 2)
            if overflow_inches > 0.01:  # Only report significant overflows
                self.slide_overflow_right = overflow_inches

        # 下方向のoverflowをチェック（<= 0.01\" の軽微なものは無視）
        bottom_edge_emu = self.top_emu + self.height_emu
        if bottom_edge_emu > self.slide_height_emu:
            overflow_emu = bottom_edge_emu - self.slide_height_emu
            overflow_inches = round(self.emu_to_inches(overflow_emu), 2)
            if overflow_inches > 0.01:  # Only report significant overflows
                self.slide_overflow_bottom = overflow_inches

    def _detect_bullet_issues(self) -> None:
        """段落内の箇条書き（bullet）書式の問題を検出します。"""
        if not self.shape or not hasattr(self.shape, "text_frame"):
            return

        text_frame = self.shape.text_frame  # type: ignore
        if not text_frame or not text_frame.paragraphs:
            return

        # 手動箇条書きの可能性がある一般的な記号
        bullet_symbols = ["•", "●", "○"]

        for paragraph in text_frame.paragraphs:
            text = paragraph.text.strip()
            # 手動箇条書き記号の有無をチェック
            if text and any(text.startswith(symbol + " ") for symbol in bullet_symbols):
                self.warnings.append(
                    "manual_bullet_symbol: use proper bullet formatting"
                )
                break

    @property
    def has_any_issues(self) -> bool:
        """shapeに問題（overflow/overlap/warnings）があるかを判定します。"""
        return (
            self.frame_overflow_bottom is not None
            or self.slide_overflow_right is not None
            or self.slide_overflow_bottom is not None
            or len(self.overlapping_shapes) > 0
            or len(self.warnings) > 0
        )

    def to_dict(self) -> ShapeDict:
        """JSONシリアライズ用のdictへ変換します。"""
        result: ShapeDict = {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }

        # 存在する場合のみオプション項目を追加
        if self.placeholder_type:
            result["placeholder_type"] = self.placeholder_type

        if self.default_font_size:
            result["default_font_size"] = self.default_font_size

        # overflowがある場合のみoverflow情報を追加
        overflow_data = {}

        # frame overflowがあれば追加
        if self.frame_overflow_bottom is not None:
            overflow_data["frame"] = {"overflow_bottom": self.frame_overflow_bottom}

        # slide overflowがあれば追加
        slide_overflow = {}
        if self.slide_overflow_right is not None:
            slide_overflow["overflow_right"] = self.slide_overflow_right
        if self.slide_overflow_bottom is not None:
            slide_overflow["overflow_bottom"] = self.slide_overflow_bottom
        if slide_overflow:
            overflow_data["slide"] = slide_overflow

        # overflowがある場合のみoverflowフィールドを追加
        if overflow_data:
            result["overflow"] = overflow_data

        # 重なりがあるshapeがあればoverlapフィールドを追加
        if self.overlapping_shapes:
            result["overlap"] = {"overlapping_shapes": self.overlapping_shapes}

        # warningsがあればwarningsフィールドを追加
        if self.warnings:
            result["warnings"] = self.warnings

        # placeholder_typeの後ろにparagraphsを追加
        result["paragraphs"] = [para.to_dict() for para in self.paragraphs]

        return result


def is_valid_shape(shape: BaseShape) -> bool:
    """shapeが意味のあるテキスト内容を含むかを判定します。"""
    # テキストフレームがあり、内容があることが必須
    if not hasattr(shape, "text_frame") or not shape.text_frame:  # type: ignore
        return False

    text = shape.text_frame.text.strip()  # type: ignore
    if not text:
        return False

    # スライド番号や数値フッターを除外
    if hasattr(shape, "is_placeholder") and shape.is_placeholder:  # type: ignore
        if shape.placeholder_format and shape.placeholder_format.type:  # type: ignore
            placeholder_type = (
                str(shape.placeholder_format.type).split(".")[-1].split(" ")[0]  # type: ignore
            )
            if placeholder_type == "SLIDE_NUMBER":
                return False
            if placeholder_type == "FOOTER" and text.isdigit():
                return False

    return True


def collect_shapes_with_absolute_positions(
    shape: BaseShape, parent_left: int = 0, parent_top: int = 0
) -> List[ShapeWithPosition]:
    """有効なテキストを持つshapeを再帰的に収集し、絶対位置も計算します。

    グループ内のshapeの座標はグループ基準の相対値です。
    この関数は、親グループのオフセットを累積してスライド上の絶対位置を算出します。

    Args:
        shape: 処理対象のshape
        parent_left: 親グループからの累積leftオフセット（EMU）
        parent_top: 親グループからの累積topオフセット（EMU）

    Returns:
        絶対位置を持つShapeWithPositionのリスト
    """
    if hasattr(shape, "shapes"):  # GroupShape
        result = []
        # このグループの位置を取得
        group_left = shape.left if hasattr(shape, "left") else 0
        group_top = shape.top if hasattr(shape, "top") else 0

        # このグループの絶対位置を計算
        abs_group_left = parent_left + group_left
        abs_group_top = parent_top + group_top

        # オフセットを累積しながら子要素を処理
        for child in shape.shapes:  # type: ignore
            result.extend(
                collect_shapes_with_absolute_positions(
                    child, abs_group_left, abs_group_top
                )
            )
        return result

    # 通常shape：有効なテキストがあるか確認
    if is_valid_shape(shape):
        # 絶対位置を計算
        shape_left = shape.left if hasattr(shape, "left") else 0
        shape_top = shape.top if hasattr(shape, "top") else 0

        return [
            ShapeWithPosition(
                shape=shape,
                absolute_left=parent_left + shape_left,
                absolute_top=parent_top + shape_top,
            )
        ]

    return []


def sort_shapes_by_position(shapes: List[ShapeData]) -> List[ShapeData]:
    """見た目の位置（上→下、左→右）でshapeをソートします。

    縦方向に0.5インチ以内のshapeは同一行とみなします。
    """
    if not shapes:
        return shapes

    # まず上方向（top）でソート
    shapes = sorted(shapes, key=lambda s: (s.top, s.left))

    # shapeを行単位でグループ化（縦方向0.5インチ以内を同一行とみなす）
    result = []
    row = [shapes[0]]
    row_top = shapes[0].top

    for shape in shapes[1:]:
        if abs(shape.top - row_top) <= 0.5:
            row.append(shape)
        else:
            # 現在行をleftでソートして結果へ追加
            result.extend(sorted(row, key=lambda s: s.left))
            row = [shape]
            row_top = shape.top

    # 最後の行を追加
    result.extend(sorted(row, key=lambda s: s.left))
    return result


def calculate_overlap(
    rect1: Tuple[float, float, float, float],
    rect2: Tuple[float, float, float, float],
    tolerance: float = 0.05,
) -> Tuple[bool, float]:
    """2つの矩形がどの程度重なっているかを算出します。

    Args:
        rect1: 1つ目の矩形（left, top, width, height）。単位はインチ
        rect2: 2つ目の矩形（left, top, width, height）。単位はインチ
        tolerance: 重なり判定の最小幅（インチ）。既定は0.05インチ

    Returns:
        (overlaps, overlap_area) を返します。
        - overlaps: toleranceより大きく重なっていればTrue
        - overlap_area: 重なり面積（平方インチ）
    """
    left1, top1, w1, h1 = rect1
    left2, top2, w2, h2 = rect2

    # 重なり寸法を計算
    overlap_width = min(left1 + w1, left2 + w2) - max(left1, left2)
    overlap_height = min(top1 + h1, top2 + h2) - max(top1, top2)

    # 意味のある重なりか確認（許容値より大きいか）
    if overlap_width > tolerance and overlap_height > tolerance:
        # 重なり面積（平方インチ）を計算
        overlap_area = overlap_width * overlap_height
        return True, round(overlap_area, 2)

    return False, 0


def detect_overlaps(shapes: List[ShapeData]) -> None:
    """重なっているshapeを検出し、overlapping_shapes辞書を更新します。

    各ShapeDataには事前にshape_idが設定されている必要があります。
    shapesはin-placeで更新され、重なり面積（平方インチ）つきでshape IDが追加されます。

    Args:
        shapes: shape_idが設定済みのShapeDataリスト
    """
    n = len(shapes)

    # shapeの各ペアを比較
    for i in range(n):
        for j in range(i + 1, n):
            shape1 = shapes[i]
            shape2 = shapes[j]

            # shape IDが設定されていることを保証
            assert shape1.shape_id, f"インデックス{i}のshapeにshape_idがありません"
            assert shape2.shape_id, f"インデックス{j}のshapeにshape_idがありません"

            rect1 = (shape1.left, shape1.top, shape1.width, shape1.height)
            rect2 = (shape2.left, shape2.top, shape2.width, shape2.height)

            overlaps, overlap_area = calculate_overlap(rect1, rect2)

            if overlaps:
                # 重なり面積（平方インチ）付きでshape IDを追加
                shape1.overlapping_shapes[shape2.shape_id] = overlap_area
                shape2.overlapping_shapes[shape1.shape_id] = overlap_area


def extract_text_inventory(
    pptx_path: Path, prs: Optional[Any] = None, issues_only: bool = False
) -> InventoryData:
    """PowerPointプレゼンの全スライドからテキスト内容を抽出します。

    Args:
        pptx_path: PowerPointファイルのパス
        prs: 使用するPresentationオブジェクト（任意）。未指定の場合はpptx_pathから読み込みます
        issues_only: Trueの場合、overflow/overlapの問題があるshapeのみ含めます

    Returns:
        入れ子辞書: {slide-N: {shape-N: ShapeData}}

        shapeは見た目の位置（上→下、左→右）でソートされます。
        ShapeDataはshape情報一式を保持し、`to_dict()` でJSON用の辞書に変換できます。
    """
    if prs is None:
        prs = Presentation(str(pptx_path))
    inventory: InventoryData = {}

    for slide_idx, slide in enumerate(prs.slides):
        # 絶対位置付きで、このスライドの有効shapeを収集
        shapes_with_positions = []
        for shape in slide.shapes:  # type: ignore
            shapes_with_positions.extend(collect_shapes_with_absolute_positions(shape))

        if not shapes_with_positions:
            continue

        # 絶対位置とスライド参照付きでShapeDataへ変換
        shape_data_list = [
            ShapeData(
                swp.shape,
                swp.absolute_left,
                swp.absolute_top,
                slide,
            )
            for swp in shapes_with_positions
        ]

        # 見た目順にソートし、安定したIDを一括で付与
        sorted_shapes = sort_shapes_by_position(shape_data_list)
        for idx, shape_data in enumerate(sorted_shapes):
            shape_data.shape_id = f"shape-{idx}"

        # 安定IDを使って重なりを検出
        if len(sorted_shapes) > 1:
            detect_overlaps(sorted_shapes)

        # issues_only指定がある場合のみ、問題（overflow/overlap）を持つshapeに絞る（重なり検出の後）
        if issues_only:
            sorted_shapes = [sd for sd in sorted_shapes if sd.has_any_issues]

        if not sorted_shapes:
            continue

        # 安定したshape IDを使ってスライドインベントリを作成
        inventory[f"slide-{slide_idx}"] = {
            shape_data.shape_id: shape_data for shape_data in sorted_shapes
        }

    return inventory


def get_inventory_as_dict(pptx_path: Path, issues_only: bool = False) -> InventoryDict:
    """テキストインベントリを抽出し、JSONシリアライズ可能な辞書として返します。

    `extract_text_inventory` の簡易ラッパーです。`ShapeData` オブジェクトではなく
    辞書を返すため、テストやJSONへの直接シリアライズに便利です。

    Args:
        pptx_path: PowerPointファイルのパス
        issues_only: Trueの場合、overflow/overlapの問題があるshapeのみ含めます

    Returns:
        JSON用にシリアライズされた全データの入れ子辞書
    """
    inventory = extract_text_inventory(pptx_path, issues_only=issues_only)

    # ShapeDataオブジェクトを辞書へ変換
    dict_inventory: InventoryDict = {}
    for slide_key, shapes in inventory.items():
        dict_inventory[slide_key] = {
            shape_key: shape_data.to_dict() for shape_key, shape_data in shapes.items()
        }

    return dict_inventory


def save_inventory(inventory: InventoryData, output_path: Path) -> None:
    """インベントリを適切な整形でJSONファイルに保存します。

    JSONシリアライズのため、ShapeDataオブジェクトを辞書へ変換します。
    """
    # ShapeDataオブジェクトを辞書へ変換
    json_inventory: InventoryDict = {}
    for slide_key, shapes in inventory.items():
        json_inventory[slide_key] = {
            shape_key: shape_data.to_dict() for shape_key, shape_data in shapes.items()
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(json_inventory, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
