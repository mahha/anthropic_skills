---
name: slack-gif-creator
description: Slack用に最適化されたアニメーションGIFを作成するための知識とユーティリティ。制約、検証ツール、アニメーションコンセプトを提供します。ユーザーが「Slack用にXがYをするGIFを作って」などのSlack用アニメーションGIFを要求したときに使用します。
license: 完全な条件はLICENSE.txtに記載されています
---

# Slack GIFクリエイター

Slack用に最適化されたアニメーションGIFを作成するためのユーティリティと知識を提供するツールキット。

## Slack要件

**寸法：**
- 絵文字GIF: 128x128（推奨）
- メッセージGIF: 480x480

**パラメータ：**
- FPS: 10-30（低いほどファイルサイズが小さい）
- 色数: 48-128（少ないほどファイルサイズが小さい）
- 継続時間: 絵文字GIFは3秒未満に保つ

## コアワークフロー

```python
from core.gif_builder import GIFBuilder
from PIL import Image, ImageDraw

# 1. ビルダーを作成
builder = GIFBuilder(width=128, height=128, fps=10)

# 2. フレームを生成
for i in range(12):
    frame = Image.new('RGB', (128, 128), (240, 248, 255))
    draw = ImageDraw.Draw(frame)

    # PILプリミティブを使用してアニメーションを描画
    # （円、多角形、線など）

    builder.add_frame(frame)

# 3. 最適化して保存
builder.save('output.gif', num_colors=48, optimize_for_emoji=True)
```

## グラフィックの描画

### ユーザーがアップロードした画像の操作
ユーザーが画像をアップロードした場合、以下を検討します：
- **直接使用**（例：「これをアニメーション化」、「これをフレームに分割」）
- **インスピレーションとして使用**（例：「これのようなものを作る」）

PILを使用して画像を読み込み、操作します：
```python
from PIL import Image

uploaded = Image.open('file.png')
# 直接使用するか、色/スタイルの参考としてのみ使用
```

### ゼロから描画
ゼロからグラフィックを描画する場合、PIL ImageDrawプリミティブを使用します：

```python
from PIL import ImageDraw

draw = ImageDraw.Draw(frame)

# 円/楕円
draw.ellipse([x1, y1, x2, y2], fill=(r, g, b), outline=(r, g, b), width=3)

# 星、三角形、任意の多角形
points = [(x1, y1), (x2, y2), (x3, y3), ...]
draw.polygon(points, fill=(r, g, b), outline=(r, g, b), width=3)

# 線
draw.line([(x1, y1), (x2, y2)], fill=(r, g, b), width=5)

# 矩形
draw.rectangle([x1, y1, x2, y2], fill=(r, g, b), outline=(r, g, b), width=3)
```

**使用しないでください：** 絵文字フォント（プラットフォーム間で信頼性が低い）や、このスキルに事前パッケージ化されたグラフィックが存在すると仮定しないでください。

### グラフィックを良く見せる方法

グラフィックは基本的ではなく、洗練され、創造的である必要があります。方法は次のとおりです：

**太い線を使用** - アウトラインと線には常に`width=2`以上を設定します。細い線（width=1）は粗く、アマチュアに見えます。

**視覚的な深みを追加**：
- 背景にグラデーションを使用（`create_gradient_background`）
- 複雑さのために複数のシェイプを重ねる（例：内側に小さな星がある星）

**シェイプをより興味深くする**：
- 単なる平らな円を描かない - ハイライト、リング、パターンを追加
- 星にはグローを付ける（後ろに大きく、半透明のバージョンを描く）
- 複数のシェイプを組み合わせる（星 + スパークル、円 + リング）

**色に注意**：
- 鮮やかで補色の色を使用
- コントラストを追加（明るいシェイプに暗いアウトライン、暗いシェイプに明るいアウトライン）
- 全体的な構成を考慮

**複雑なシェイプ**（ハート、雪の結晶など）の場合：
- 多角形と楕円の組み合わせを使用
- 対称性のためにポイントを慎重に計算
- 詳細を追加（ハートにはハイライトカーブ、雪の結晶には複雑な枝）

創造的で詳細に！良いSlack GIFは洗練されて見えるべきで、プレースホルダーグラフィックのように見えるべきではありません。

## 利用可能なユーティリティ

### GIFBuilder (`core.gif_builder`)
フレームを組み立て、Slack用に最適化します：
```python
builder = GIFBuilder(width=128, height=128, fps=10)
builder.add_frame(frame)  # PIL Imageを追加
builder.add_frames(frames)  # フレームのリストを追加
builder.save('out.gif', num_colors=48, optimize_for_emoji=True, remove_duplicates=True)
```

### Validators (`core.validators`)
GIFがSlack要件を満たしているかチェック：
```python
from core.validators import validate_gif, is_slack_ready

# 詳細な検証
passes, info = validate_gif('my.gif', is_emoji=True, verbose=True)

# クイックチェック
if is_slack_ready('my.gif'):
    print("準備完了！")
```

### イージング関数 (`core.easing`)
線形ではなく滑らかな動き：
```python
from core.easing import interpolate

# 0.0から1.0への進行
t = i / (num_frames - 1)

# イージングを適用
y = interpolate(start=0, end=400, t=t, easing='ease_out')

# 利用可能: linear, ease_in, ease_out, ease_in_out,
#           bounce_out, elastic_out, back_out
```

### フレームヘルパー (`core.frame_composer`)
一般的なニーズのための便利な関数：
```python
from core.frame_composer import (
    create_blank_frame,         # 単色背景
    create_gradient_background,  # 垂直グラデーション
    draw_circle,                # 円のヘルパー
    draw_text,                  # シンプルなテキストレンダリング
    draw_star                   # 5点の星
)
```

## アニメーションコンセプト

### シェイク/振動
オブジェクトの位置をオフセットして振動：
- フレームインデックスで`math.sin()`または`math.cos()`を使用
- 自然な感じのために小さなランダムな変動を追加
- x位置および/またはy位置に適用

### パルス/心拍
オブジェクトのサイズをリズミカルにスケール：
- 滑らかなパルスに`math.sin(t * frequency * 2 * math.pi)`を使用
- 心拍の場合：2回のクイックパルス、その後一時停止（サイン波を調整）
- ベースサイズの0.8から1.2の間でスケール

### バウンス
オブジェクトが落下して跳ね返る：
- 着地に`interpolate()`と`easing='bounce_out'`を使用
- 落下に`easing='ease_in'`を使用（加速）
- 各フレームでy速度を増やすことで重力を適用

### スピン/回転
中心を中心にオブジェクトを回転：
- PIL: `image.rotate(angle, resample=Image.BICUBIC)`
- ウォブル：線形ではなくサイン波で角度を使用

### フェードイン/アウト
徐々に表示または非表示：
- RGBA画像を作成し、アルファチャンネルを調整
- または`Image.blend(image1, image2, alpha)`を使用
- フェードイン：アルファを0から1へ
- フェードアウト：アルファを1から0へ

### スライド
オブジェクトを画面外から位置へ移動：
- 開始位置：フレーム境界外
- 終了位置：ターゲット位置
- 滑らかな停止に`interpolate()`と`easing='ease_out'`を使用
- オーバーシュート：`easing='back_out'`を使用

### ズーム
ズーム効果のためにスケールと位置：
- ズームイン：0.1から2.0にスケール、中央をクロップ
- ズームアウト：2.0から1.0にスケール
- ドラマのためにモーションブラーを追加（PILフィルター）

### 爆発/パーティクルバースト
外側に放射するパーティクルを作成：
- ランダムな角度と速度でパーティクルを生成
- 各パーティクルを更新：`x += vx`, `y += vy`
- 重力を追加：`vy += gravity_constant`
- 時間の経過とともにパーティクルをフェードアウト（アルファを減らす）

## 最適化戦略

ファイルサイズを小さくするように求められた場合のみ、以下の方法のいくつかを実装します：

1. **フレーム数を減らす** - FPSを下げる（20の代わりに10）または継続時間を短くする
2. **色数を減らす** - `num_colors=128`の代わりに`num_colors=48`
3. **寸法を小さくする** - 480x480の代わりに128x128
4. **重複を削除** - `save()`で`remove_duplicates=True`
5. **絵文字モード** - `optimize_for_emoji=True`が自動最適化

```python
# 絵文字の最大最適化
builder.save(
    'emoji.gif',
    num_colors=48,
    optimize_for_emoji=True,
    remove_duplicates=True
)
```

## 哲学

このスキルは以下を提供します：
- **知識**: Slackの要件とアニメーションコンセプト
- **ユーティリティ**: GIFBuilder、バリデーター、イージング関数
- **柔軟性**: PILプリミティブを使用してアニメーションロジックを作成

提供しません：
- 厳格なアニメーションテンプレートまたは事前作成された関数
- 絵文字フォントレンダリング（プラットフォーム間で信頼性が低い）
- スキルに組み込まれた事前パッケージ化されたグラフィックのライブラリ

**ユーザーアップロードに関する注意**: このスキルには事前構築されたグラフィックは含まれていませんが、ユーザーが画像をアップロードした場合、PILを使用して読み込み、操作します - リクエストに基づいて、直接使用するか、単にインスピレーションとして使用するかを解釈します。

創造的になりましょう！コンセプトを組み合わせ（バウンス + 回転、パルス + スライドなど）、PILの全機能を使用します。

## 依存関係

```bash
pip install pillow imageio numpy
```

