#!/usr/bin/env python3
"""
イージング関数 - アニメーションを滑らかにするための時間関数です。

自然な動き/タイミングのための各種イージング関数を提供します。
すべての関数は t（0.0〜1.0）を受け取り、イージング後の値（0.0〜1.0）を返します。
"""

import math


def linear(t: float) -> float:
    """線形補間（イージングなし）。"""
    return t


def ease_in_quad(t: float) -> float:
    """2次のイーズイン（ゆっくり始まり加速）。"""
    return t * t


def ease_out_quad(t: float) -> float:
    """2次のイーズアウト（速く始まり減速）。"""
    return t * (2 - t)


def ease_in_out_quad(t: float) -> float:
    """2次のイーズイン・アウト（始まりと終わりがゆっくり）。"""
    if t < 0.5:
        return 2 * t * t
    return -1 + (4 - 2 * t) * t


def ease_in_cubic(t: float) -> float:
    """3次のイーズイン（ゆっくり始まる）。"""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """3次のイーズアウト（速く始まる）。"""
    return (t - 1) * (t - 1) * (t - 1) + 1


def ease_in_out_cubic(t: float) -> float:
    """3次のイーズイン・アウト。"""
    if t < 0.5:
        return 4 * t * t * t
    return (t - 1) * (2 * t - 2) * (2 * t - 2) + 1


def ease_in_bounce(t: float) -> float:
    """バウンス（イーズイン：跳ねるように始まる）。"""
    return 1 - ease_out_bounce(1 - t)


def ease_out_bounce(t: float) -> float:
    """バウンス（イーズアウト：跳ねるように終わる）。"""
    if t < 1 / 2.75:
        return 7.5625 * t * t
    elif t < 2 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    elif t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    else:
        t -= 2.625 / 2.75
        return 7.5625 * t * t + 0.984375


def ease_in_out_bounce(t: float) -> float:
    """バウンス（イーズイン・アウト）。"""
    if t < 0.5:
        return ease_in_bounce(t * 2) * 0.5
    return ease_out_bounce(t * 2 - 1) * 0.5 + 0.5


def ease_in_elastic(t: float) -> float:
    """エラスティック（イーズイン：バネのような効果）。"""
    if t == 0 or t == 1:
        return t
    return -math.pow(2, 10 * (t - 1)) * math.sin((t - 1.1) * 5 * math.pi)


def ease_out_elastic(t: float) -> float:
    """エラスティック（イーズアウト：バネのような効果）。"""
    if t == 0 or t == 1:
        return t
    return math.pow(2, -10 * t) * math.sin((t - 0.1) * 5 * math.pi) + 1


def ease_in_out_elastic(t: float) -> float:
    """エラスティック（イーズイン・アウト）。"""
    if t == 0 or t == 1:
        return t
    t = t * 2 - 1
    if t < 0:
        return -0.5 * math.pow(2, 10 * t) * math.sin((t - 0.1) * 5 * math.pi)
    return math.pow(2, -10 * t) * math.sin((t - 0.1) * 5 * math.pi) * 0.5 + 1


# 便利な名前→関数のマッピング
EASING_FUNCTIONS = {
    "linear": linear,
    "ease_in": ease_in_quad,
    "ease_out": ease_out_quad,
    "ease_in_out": ease_in_out_quad,
    "bounce_in": ease_in_bounce,
    "bounce_out": ease_out_bounce,
    "bounce": ease_in_out_bounce,
    "elastic_in": ease_in_elastic,
    "elastic_out": ease_out_elastic,
    "elastic": ease_in_out_elastic,
}


def get_easing(name: str = "linear"):
    """名前からイージング関数を取得します。"""
    return EASING_FUNCTIONS.get(name, linear)


def interpolate(start: float, end: float, t: float, easing: str = "linear") -> float:
    """
    イージングを使って2値の間を補間します。

    Args:
        start: 開始値
        end: 終了値
        t: 進捗（0.0〜1.0）
        easing: イージング関数名

    Returns:
        補間値
    """
    ease_func = get_easing(easing)
    eased_t = ease_func(t)
    return start + (end - start) * eased_t


def ease_back_in(t: float) -> float:
    """バック（イーズイン：前進前にわずかに後ろへオーバーシュート）。"""
    c1 = 1.70158
    c3 = c1 + 1
    return c3 * t * t * t - c1 * t * t


def ease_back_out(t: float) -> float:
    """バック（イーズアウト：前にオーバーシュートしてから戻って収束）。"""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_back_in_out(t: float) -> float:
    """バック（イーズイン・アウト：両端でオーバーシュート）。"""
    c1 = 1.70158
    c2 = c1 * 1.525
    if t < 0.5:
        return (pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
    return (pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2


def apply_squash_stretch(
    base_scale: tuple[float, float], intensity: float, direction: str = "vertical"
) -> tuple[float, float]:
    """
    よりダイナミックなアニメーションのための、スクワッシュ&ストレッチのスケールを計算します。

    Args:
        base_scale: 基本スケール（width_scale, height_scale）
        intensity: 強度（0.0〜1.0）
        direction: 'vertical' / 'horizontal' / 'both'

    Returns:
        スクワッシュ/ストレッチ適用後の（width_scale, height_scale）
    """
    width_scale, height_scale = base_scale

    if direction == "vertical":
        # 縦に潰し、横に伸ばす（体積を保つ意図）
        height_scale *= 1 - intensity * 0.5
        width_scale *= 1 + intensity * 0.5
    elif direction == "horizontal":
        # 横に潰し、縦に伸ばす
        width_scale *= 1 - intensity * 0.5
        height_scale *= 1 + intensity * 0.5
    elif direction == "both":
        # 両方向に潰す
        width_scale *= 1 - intensity * 0.3
        height_scale *= 1 - intensity * 0.3

    return (width_scale, height_scale)


def calculate_arc_motion(
    start: tuple[float, float], end: tuple[float, float], height: float, t: float
) -> tuple[float, float]:
    """
    放物線アークに沿った位置を計算します（自然な移動経路）。

    Args:
        start: 開始位置(x, y)
        end: 終了位置(x, y)
        height: 中点でのアーク高さ（正=上方向）
        t: 進捗（0.0〜1.0）

    Returns:
        アーク上の位置(x, y)
    """
    x1, y1 = start
    x2, y2 = end

    # xは線形補間
    x = x1 + (x2 - x1) * t

    # yは放物線補間
    # y = start + progress * (end - start) + arc_offset
    # arc_offsetはt=0.5で最大
    arc_offset = 4 * height * t * (1 - t)
    y = y1 + (y2 - y1) * t - arc_offset

    return (x, y)


# 追加したイージング関数をマッピングへ登録
EASING_FUNCTIONS.update(
    {
        "back_in": ease_back_in,
        "back_out": ease_back_out,
        "back_in_out": ease_back_in_out,
        "anticipate": ease_back_in,  # 別名
        "overshoot": ease_back_out,  # 別名
    }
)
