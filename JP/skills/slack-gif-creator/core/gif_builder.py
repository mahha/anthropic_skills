#!/usr/bin/env python3
"""
GIFビルダー - Slack向けに最適化されたGIFを作成するための中核モジュールです。

プログラム生成したフレームからGIFを作るためのメインインターフェースを提供し、
Slackの要件に合わせた自動最適化を行います。
"""

from pathlib import Path
from typing import Optional

import imageio.v3 as imageio
import numpy as np
from PIL import Image


class GIFBuilder:
    """フレームから最適化済みGIFを作成するビルダー。"""

    def __init__(self, width: int = 480, height: int = 480, fps: int = 15):
        """
        GIFビルダーを初期化します。

        Args:
            width: フレーム幅（px）
            height: フレーム高（px）
            fps: フレーム/秒
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.frames: list[np.ndarray] = []

    def add_frame(self, frame: np.ndarray | Image.Image):
        """
        GIFにフレームを追加します。

        Args:
            frame: numpy配列またはPIL Imageのフレーム（RGBに変換されます）
        """
        if isinstance(frame, Image.Image):
            frame = np.array(frame.convert("RGB"))

        # フレームサイズを合わせる
        if frame.shape[:2] != (self.height, self.width):
            pil_frame = Image.fromarray(frame)
            pil_frame = pil_frame.resize(
                (self.width, self.height), Image.Resampling.LANCZOS
            )
            frame = np.array(pil_frame)

        self.frames.append(frame)

    def add_frames(self, frames: list[np.ndarray | Image.Image]):
        """複数フレームをまとめて追加します。"""
        for frame in frames:
            self.add_frame(frame)

    def optimize_colors(
        self, num_colors: int = 128, use_global_palette: bool = True
    ) -> list[np.ndarray]:
        """
        量子化により全フレームの色数を削減します。

        Args:
            num_colors: 目標の色数（8〜256）
            use_global_palette: 全フレームで単一パレットを使う（圧縮率が上がりやすい）

        Returns:
            色最適化後フレームのリスト
        """
        optimized = []

        if use_global_palette and len(self.frames) > 1:
            # 全フレームからグローバルパレットを作成
            # パレット生成のためにフレームをサンプリング
            sample_size = min(5, len(self.frames))
            sample_indices = [
                int(i * len(self.frames) / sample_size) for i in range(sample_size)
            ]
            sample_frames = [self.frames[i] for i in sample_indices]

            # パレット生成のため、サンプルフレームを1枚の画像相当に結合
            # 各フレームをフラット化して全ピクセルをスタック
            all_pixels = np.vstack(
                [f.reshape(-1, 3) for f in sample_frames]
            )  # (total_pixels, 3)

            # ピクセルデータから適切な形状のRGB画像を作る
            # 全ピクセルから概ね正方形に近い画像を構成
            total_pixels = len(all_pixels)
            width = min(512, int(np.sqrt(total_pixels)))  # 妥当な幅（最大512）
            height = (total_pixels + width - 1) // width  # 切り上げ除算

            # 必要ならパディングして矩形を埋める
            pixels_needed = width * height
            if pixels_needed > total_pixels:
                padding = np.zeros((pixels_needed - total_pixels, 3), dtype=np.uint8)
                all_pixels = np.vstack([all_pixels, padding])

            # RGB画像フォーマット(H, W, 3)にリシェイプ
            img_array = (
                all_pixels[:pixels_needed].reshape(height, width, 3).astype(np.uint8)
            )
            combined_img = Image.fromarray(img_array, mode="RGB")

            # グローバルパレットを生成
            global_palette = combined_img.quantize(colors=num_colors, method=2)

            # 全フレームにグローバルパレットを適用
            for frame in self.frames:
                pil_frame = Image.fromarray(frame)
                quantized = pil_frame.quantize(palette=global_palette, dither=1)
                optimized.append(np.array(quantized.convert("RGB")))
        else:
            # フレームごとに量子化
            for frame in self.frames:
                pil_frame = Image.fromarray(frame)
                quantized = pil_frame.quantize(colors=num_colors, method=2, dither=1)
                optimized.append(np.array(quantized.convert("RGB")))

        return optimized

    def deduplicate_frames(self, threshold: float = 0.9995) -> int:
        """
        連続する重複（またはほぼ重複）のフレームを除去します。

        Args:
            threshold: 類似度しきい値（0.0〜1.0）。高いほど厳しい（0.9995=ほぼ同一）。
                      微妙な動きを残すなら0.9995+、強めに削るなら0.98程度。

        Returns:
            削除したフレーム数
        """
        if len(self.frames) < 2:
            return 0

        deduplicated = [self.frames[0]]
        removed_count = 0

        for i in range(1, len(self.frames)):
            # 直前フレームと比較
            prev_frame = np.array(deduplicated[-1], dtype=np.float32)
            curr_frame = np.array(self.frames[i], dtype=np.float32)

            # 類似度を計算（正規化）
            diff = np.abs(prev_frame - curr_frame)
            similarity = 1.0 - (np.mean(diff) / 255.0)

            # 十分に違う場合だけ残す
            # しきい値が高い（0.9995+）ほど「ほぼ同一」だけ除去
            if similarity < threshold:
                deduplicated.append(self.frames[i])
            else:
                removed_count += 1

        self.frames = deduplicated
        return removed_count

    def save(
        self,
        output_path: str | Path,
        num_colors: int = 128,
        optimize_for_emoji: bool = False,
        remove_duplicates: bool = False,
    ) -> dict:
        """
        フレームをSlack向けに最適化したGIFとして保存します。

        Args:
            output_path: GIFの保存先
            num_colors: 使用する色数（少ないほどファイルは小さくなりやすい）
            optimize_for_emoji: Trueなら絵文字向け最適化（128x128、色数削減）
            remove_duplicates: Trueなら連続重複フレームを削除（任意）

        Returns:
            ファイル情報（path/size/dimensions/frame_count等）を含むdict
        """
        if not self.frames:
            raise ValueError("No frames to save. Add frames with add_frame() first.")

        output_path = Path(output_path)

        # 重複フレームを削除してサイズを削減
        if remove_duplicates:
            removed = self.deduplicate_frames(threshold=0.9995)
            if removed > 0:
                print(
                    f"  ほぼ同一のフレームを{removed}枚削除しました（微妙な動きは保持）"
                )

        # 絵文字向け最適化（必要な場合）
        if optimize_for_emoji:
            if self.width > 128 or self.height > 128:
                print(
                    f"  絵文字用に {self.width}x{self.height} から 128x128 にリサイズします"
                )
                self.width = 128
                self.height = 128
                # 全フレームをリサイズ
                resized_frames = []
                for frame in self.frames:
                    pil_frame = Image.fromarray(frame)
                    pil_frame = pil_frame.resize((128, 128), Image.Resampling.LANCZOS)
                    resized_frames.append(np.array(pil_frame))
                self.frames = resized_frames
            num_colors = min(num_colors, 48)  # 絵文字向けに色数をより強く制限

            # 絵文字向けにフレーム数も強めに削減
            if len(self.frames) > 12:
                print(
                    f"  絵文字向けにフレーム数を {len(self.frames)} から約12枚へ削減します"
                )
                # 約12枚になるよう間引く
                keep_every = max(1, len(self.frames) // 12)
                self.frames = [
                    self.frames[i] for i in range(0, len(self.frames), keep_every)
                ]

        # グローバルパレットで色数最適化
        optimized_frames = self.optimize_colors(num_colors, use_global_palette=True)

        # フレーム時間（ms）を計算
        frame_duration = 1000 / self.fps

        # GIFを保存
        imageio.imwrite(
            output_path,
            optimized_frames,
            duration=frame_duration,
            loop=0,  # 無限ループ
        )

        # ファイル情報を取得
        file_size_kb = output_path.stat().st_size / 1024
        file_size_mb = file_size_kb / 1024

        info = {
            "path": str(output_path),
            "size_kb": file_size_kb,
            "size_mb": file_size_mb,
            "dimensions": f"{self.width}x{self.height}",
            "frame_count": len(optimized_frames),
            "fps": self.fps,
            "duration_seconds": len(optimized_frames) / self.fps,
            "colors": num_colors,
        }

        # 情報を表示
        print("\n✓ GIFの作成が完了しました！")
        print(f"  Path: {output_path}")
        print(f"  Size: {file_size_kb:.1f} KB ({file_size_mb:.2f} MB)")
        print(f"  Dimensions: {self.width}x{self.height}")
        print(f"  Frames: {len(optimized_frames)} @ {self.fps} fps")
        print(f"  Duration: {info['duration_seconds']:.1f}s")
        print(f"  Colors: {num_colors}")

        # サイズに関する注記
        if optimize_for_emoji:
            print("  絵文字向けに最適化済み（128x128、色数削減）")
        if file_size_mb > 1.0:
            print(f"\n  注: ファイルサイズが大きいです（{file_size_kb:.1f} KB）")
            print("  対策: フレーム数/寸法/色数を減らすことを検討してください")

        return info

    def clear(self):
        """全フレームをクリアします（複数GIFを作るときに便利）。"""
        self.frames = []
