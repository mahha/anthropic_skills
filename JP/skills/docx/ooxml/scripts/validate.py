#!/usr/bin/env python3
"""
OfficeドキュメントのXMLを、XSDスキーマおよび追跡変更（tracked changes）に対して検証するコマンドラインツールです。

使い方:
    python validate.py <dir> --original <original_file>
"""

import argparse
import sys
from pathlib import Path

from validation import DOCXSchemaValidator, PPTXSchemaValidator, RedliningValidator


def main():
    parser = argparse.ArgumentParser(description="OfficeドキュメントXMLを検証します")
    parser.add_argument(
        "unpacked_dir",
        help="アンパック済みOfficeドキュメントのディレクトリパス",
    )
    parser.add_argument(
        "--original",
        required=True,
        help="元ファイルのパス（.docx/.pptx/.xlsx）",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="詳細出力を有効化",
    )
    args = parser.parse_args()

    # パスを検証
    unpacked_dir = Path(args.unpacked_dir)
    original_file = Path(args.original)
    file_extension = original_file.suffix.lower()
    assert unpacked_dir.is_dir(), f"Error: {unpacked_dir} is not a directory"
    assert original_file.is_file(), f"Error: {original_file} is not a file"
    assert file_extension in [".docx", ".pptx", ".xlsx"], (
        f"Error: {original_file} must be a .docx, .pptx, or .xlsx file"
    )

    # 検証を実行
    match file_extension:
        case ".docx":
            validators = [DOCXSchemaValidator, RedliningValidator]
        case ".pptx":
            validators = [PPTXSchemaValidator]
        case _:
            print(f"Error: Validation not supported for file type {file_extension}")
            sys.exit(1)

    # 各バリデータを実行
    success = True
    for V in validators:
        validator = V(unpacked_dir, original_file, verbose=args.verbose)
        if not validator.validate():
            success = False

    if success:
        print("すべての検証に合格しました！")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
