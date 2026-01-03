#!/usr/bin/env python3
"""
スキル初期化ツール - テンプレートから新しいスキルを作成します

使い方:
    init_skill.py <skill-name> --path <path>

例:
    init_skill.py my-new-skill --path skills/public
    init_skill.py my-api-helper --path skills/private
    init_skill.py custom-skill --path /custom/location
"""

import sys
from pathlib import Path


SKILL_TEMPLATE = """---
name: {skill_name}
description: [TODO: このスキルが何をし、いつ使うべきかを分かりやすく説明してください。具体的な利用シナリオ/対象ファイル/発生するタスクなど「使うタイミング」も含めます。]
---

# {skill_title}

## Overview

[TODO: このスキルで何ができるかを1〜2文で説明]

## Structuring This Skill

[TODO: このスキルの目的に最も合う構成を選んでください。よくあるパターン:

**1. Workflow-Based** (best for sequential processes)
- Works well when there are clear step-by-step procedures
- Example: DOCX skill with "Workflow Decision Tree" → "Reading" → "Creating" → "Editing"
- Structure: ## Overview → ## Workflow Decision Tree → ## Step 1 → ## Step 2...

**2. Task-Based** (best for tool collections)
- Works well when the skill offers different operations/capabilities
- Example: PDF skill with "Quick Start" → "Merge PDFs" → "Split PDFs" → "Extract Text"
- Structure: ## Overview → ## Quick Start → ## Task Category 1 → ## Task Category 2...

**3. Reference/Guidelines** (best for standards or specifications)
- Works well for brand guidelines, coding standards, or requirements
- Example: Brand styling with "Brand Guidelines" → "Colors" → "Typography" → "Features"
- Structure: ## Overview → ## Guidelines → ## Specifications → ## Usage...

**4. Capabilities-Based** (best for integrated systems)
- Works well when the skill provides multiple interrelated features
- Example: Product Management with "Core Capabilities" → numbered capability list
- Structure: ## Overview → ## Core Capabilities → ### 1. Feature → ### 2. Feature...

パターンは必要に応じて組み合わせ可能です。多くのスキルは複数パターンを併用します（例: タスク型で開始し、複雑な操作にはワークフローを追加）。

完了したら、この「Structuring This Skill」セクション全体を削除してください（これはガイド用です）。]

## [TODO: 選択した構成に基づいて、最初のメインセクションに置き換えてください]

[TODO: ここに内容を追加してください。既存スキルの例:
- 技術スキル向けのコード例
- 複雑なワークフロー向けの意思決定ツリー
- 現実的なユーザー依頼を想定した具体例
- 必要に応じて scripts/templates/references への参照]

## Resources

このスキルには、同梱リソースの整理方法を示すサンプルディレクトリが含まれます:

### scripts/
特定の操作を行うために、直接実行できるコード（Python/Bash等）です。

**他のスキルの例:**
- PDF skill: `fill_fillable_fields.py`, `extract_form_field_info.py` - utilities for PDF manipulation
- DOCX skill: `document.py`, `utilities.py` - Python modules for document processing

**用途:** Pythonスクリプト、シェルスクリプト、または自動化/データ処理/特定操作を行う実行可能コード。

**注:** scripts はコンテキストに読み込まずに実行される場合がありますが、パッチ適用や環境調整のためにClaudeが読むことはできます。

### references/
Claudeの作業手順や思考のために、コンテキストへ読み込むことを想定したドキュメント/参照資料です。

**他のスキルの例:**
- Product management: `communication.md`, `context_building.md` - detailed workflow guides
- BigQuery: API reference documentation and query examples
- Finance: Schema documentation, company policies

**用途:** 詳細ドキュメント、APIリファレンス、DBスキーマ、包括的ガイドなど、Claudeが作業中に参照すべき情報。

### assets/
コンテキストに読み込む目的ではなく、Claudeが生成する成果物の中で利用するファイルです。

**他のスキルの例:**
- Brand styling: PowerPoint template files (.pptx), logo files
- Frontend builder: HTML/React boilerplate project directories
- Typography: Font files (.ttf, .woff2)

**用途:** テンプレート、ボイラープレート、ドキュメントテンプレ、画像、アイコン、フォントなど、最終成果物にコピー/利用するファイル。

---

**不要なディレクトリは削除して構いません。** すべてのスキルが3種類すべてのリソースを必要とするわけではありません。
"""

EXAMPLE_SCRIPT = '''#!/usr/bin/env python3
"""
Example helper script for {skill_name}

これは直接実行できるサンプル（プレースホルダ）スクリプトです。
必要に応じて実装を追加するか、不要なら削除してください。

他のスキルにある実在スクリプト例:
- pdf/scripts/fill_fillable_fields.py - PDFフォームのフィールドを入力
- pdf/scripts/convert_pdf_to_images.py - PDFページを画像に変換
"""

def main():
    print("{skill_name} のサンプルスクリプトです")
    # TODO: Add actual script logic here
    # 例: データ処理、ファイル変換、API呼び出し等

if __name__ == "__main__":
    main()
'''

EXAMPLE_REFERENCE = """# Reference Documentation for {skill_title}

これは詳細なリファレンスドキュメント用のプレースホルダです。
必要に応じて実際の参照内容に置き換えるか、不要なら削除してください。

他のスキルにある実在のリファレンス例:
- product-management/references/communication.md - Comprehensive guide for status updates
- product-management/references/context_building.md - Deep-dive on gathering context
- bigquery/references/ - API references and query examples

## When Reference Docs Are Useful

リファレンス docs が向いているケース:
- Comprehensive API documentation
- Detailed workflow guides
- Complex multi-step processes
- Information too lengthy for main SKILL.md
- Content that's only needed for specific use cases

## Structure Suggestions

### APIリファレンス例
- Overview
- Authentication
- Endpoints with examples
- Error codes
- Rate limits

### ワークフローガイド例
- Prerequisites
- Step-by-step instructions
- Common patterns
- Troubleshooting
- Best practices
"""

EXAMPLE_ASSET = """# Example Asset File

これは、アセットファイルを置く場所を示すプレースホルダです。
必要に応じて実際のアセット（テンプレート/画像/フォント等）に置き換えるか、不要なら削除してください。

アセットファイルは **コンテキストに読み込む目的ではなく**、Claudeが生成する成果物の中で利用する想定です。

他のスキルにあるアセット例:
- Brand guidelines: logo.png, slides_template.pptx
- Frontend builder: hello-world/ directory with HTML/React boilerplate
- Typography: custom-font.ttf, font-family.woff2
- Data: sample_data.csv, test_dataset.json

## Common Asset Types

- Templates: .pptx, .docx, boilerplate directories
- Images: .png, .jpg, .svg, .gif
- Fonts: .ttf, .otf, .woff, .woff2
- Boilerplate code: Project directories, starter files
- Icons: .ico, .svg
- Data files: .csv, .json, .xml, .yaml

注: これはテキストのプレースホルダです。実際のアセットは任意のファイル形式で構いません。
"""


def title_case_skill_name(skill_name):
    """ハイフン区切りのスキル名を表示用のTitle Caseに変換します。"""
    return ' '.join(word.capitalize() for word in skill_name.split('-'))


def init_skill(skill_name, path):
    """
    テンプレートSKILL.md付きで新しいスキルディレクトリを初期化します。

    Args:
        skill_name: スキル名
        path: スキルディレクトリを作成する場所

    Returns:
        作成したスキルディレクトリのパス。エラー時はNone
    """
    # スキルディレクトリのパスを決定
    skill_dir = Path(path).resolve() / skill_name

    # 既にディレクトリが存在しないか確認
    if skill_dir.exists():
        print(f"❌ Error: Skill directory already exists: {skill_dir}")
        return None

    # スキルディレクトリを作成
    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
        print(f"✅ Created skill directory: {skill_dir}")
    except Exception as e:
        print(f"❌ Error creating directory: {e}")
        return None

    # テンプレートからSKILL.mdを作成
    skill_title = title_case_skill_name(skill_name)
    skill_content = SKILL_TEMPLATE.format(
        skill_name=skill_name,
        skill_title=skill_title
    )

    skill_md_path = skill_dir / 'SKILL.md'
    try:
        skill_md_path.write_text(skill_content)
        print("✅ SKILL.md を作成しました")
    except Exception as e:
        print(f"❌ SKILL.md の作成エラー: {e}")
        return None

    # サンプルファイル付きでリソースディレクトリを作成
    try:
        # scripts/ ディレクトリを作成し、サンプルスクリプトを配置
        scripts_dir = skill_dir / 'scripts'
        scripts_dir.mkdir(exist_ok=True)
        example_script = scripts_dir / 'example.py'
        example_script.write_text(EXAMPLE_SCRIPT.format(skill_name=skill_name))
        example_script.chmod(0o755)
        print("✅ scripts/example.py を作成しました")

        # references/ ディレクトリを作成し、サンプル参照ドキュメントを配置
        references_dir = skill_dir / 'references'
        references_dir.mkdir(exist_ok=True)
        example_reference = references_dir / 'api_reference.md'
        example_reference.write_text(EXAMPLE_REFERENCE.format(skill_title=skill_title))
        print("✅ references/api_reference.md を作成しました")

        # assets/ ディレクトリを作成し、サンプル資産（プレースホルダ）を配置
        assets_dir = skill_dir / 'assets'
        assets_dir.mkdir(exist_ok=True)
        example_asset = assets_dir / 'example_asset.txt'
        example_asset.write_text(EXAMPLE_ASSET)
        print("✅ assets/example_asset.txt を作成しました")
    except Exception as e:
        print(f"❌ リソースディレクトリ作成エラー: {e}")
        return None

    # 次のステップを表示
    print(f"\n✅ スキル '{skill_name}' を {skill_dir} に初期化しました")
    print("\n次のステップ:")
    print("1. SKILL.md を編集してTODO項目を埋め、descriptionを更新する")
    print("2. scripts/・references/・assets/ 内のサンプルをカスタマイズする（不要なら削除）")
    print("3. 準備ができたらバリデータを実行して構造を確認する")

    return skill_dir


def main():
    if len(sys.argv) < 4 or sys.argv[2] != '--path':
        print("使い方: init_skill.py <skill-name> --path <path>")
        print("\nスキル名の要件:")
        print("  - hyphen-case識別子（例: 'data-analyzer'）")
        print("  - 小文字/数字/ハイフンのみ")
        print("  - 最大40文字")
        print("  - ディレクトリ名と完全一致すること")
        print("\n例:")
        print("  init_skill.py my-new-skill --path skills/public")
        print("  init_skill.py my-api-helper --path skills/private")
        print("  init_skill.py custom-skill --path /custom/location")
        sys.exit(1)

    skill_name = sys.argv[1]
    path = sys.argv[3]

    print(f"🚀 Initializing skill: {skill_name}")
    print(f"   Location: {path}")
    print()

    result = init_skill(skill_name, path)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
