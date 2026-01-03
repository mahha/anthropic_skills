#!/usr/bin/env python3
"""
バリデータ - GIFがSlackの要件を満たすかをチェックします。

これらのバリデータは、GIFがSlackのサイズ/寸法制約を満たすことを確認するのに役立ちます。
"""

from pathlib import Path


def validate_gif(
    gif_path: str | Path, is_emoji: bool = True, verbose: bool = True
) -> tuple[bool, dict]:
    """
    Slack向けにGIFを検証します（寸法、サイズ、フレーム数）。

    Args:
        gif_path: GIFファイルのパス
        is_emoji: 絵文字用ならTrue（128x128推奨）、メッセージ用GIFならFalse
        verbose: 検証詳細を表示する

    Returns:
        (合格: bool, 結果: 詳細dict) のタプル
    """
    from PIL import Image

    gif_path = Path(gif_path)

    if not gif_path.exists():
        return False, {"error": f"File not found: {gif_path}"}

    # ファイルサイズを取得
    size_bytes = gif_path.stat().st_size
    size_kb = size_bytes / 1024
    size_mb = size_kb / 1024

    # 寸法とフレーム情報を取得
    try:
        with Image.open(gif_path) as img:
            width, height = img.size

            # フレーム数を数える
            frame_count = 0
            try:
                while True:
                    img.seek(frame_count)
                    frame_count += 1
            except EOFError:
                pass

            # 再生時間を取得
            try:
                duration_ms = img.info.get("duration", 100)
                total_duration = (duration_ms * frame_count) / 1000
                fps = frame_count / total_duration if total_duration > 0 else 0
            except:
                total_duration = None
                fps = None

    except Exception as e:
        return False, {"error": f"Failed to read GIF: {e}"}

    # 寸法を検証
    if is_emoji:
        optimal = width == height == 128
        acceptable = width == height and 64 <= width <= 128
        dim_pass = acceptable
    else:
        aspect_ratio = (
            max(width, height) / min(width, height)
            if min(width, height) > 0
            else float("inf")
        )
        dim_pass = aspect_ratio <= 2.0 and 320 <= min(width, height) <= 640

    results = {
        "file": str(gif_path),
        "passes": dim_pass,
        "width": width,
        "height": height,
        "size_kb": size_kb,
        "size_mb": size_mb,
        "frame_count": frame_count,
        "duration_seconds": total_duration,
        "fps": fps,
        "is_emoji": is_emoji,
        "optimal": optimal if is_emoji else None,
    }

    # verboseなら表示
    if verbose:
        print(f"\n{gif_path.name} を検証中:")
        print(
            f"  Dimensions: {width}x{height}"
            + (
                f"（{'最適' if optimal else '許容'}）"
                if is_emoji and acceptable
                else ""
            )
        )
        print(
            f"  Size: {size_kb:.1f} KB"
            + (f" ({size_mb:.2f} MB)" if size_mb >= 1.0 else "")
        )
        print(
            f"  Frames: {frame_count}"
            + (f" @ {fps:.1f} fps ({total_duration:.1f}s)" if fps else "")
        )

        if not dim_pass:
            print(f"  注: {'絵文字は128x128が推奨です' if is_emoji else 'Slack向けとしては一般的でない寸法です'}")

        if size_mb > 5.0:
            print("  注: ファイルサイズが大きいです。フレーム数/色数を減らすことを検討してください")

    return dim_pass, results


def is_slack_ready(
    gif_path: str | Path, is_emoji: bool = True, verbose: bool = True
) -> bool:
    """
    GIFがSlack向けに問題ないかを素早くチェックします。

    Args:
        gif_path: GIFファイルのパス
        is_emoji: 絵文字用GIFならTrue、メッセージ用GIFならFalse
        verbose: フィードバックを表示する

    Returns:
        寸法が許容範囲ならTrue
    """
    passes, _ = validate_gif(gif_path, is_emoji, verbose)
    return passes
