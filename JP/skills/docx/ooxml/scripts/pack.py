#!/usr/bin/env python3
"""
XMLの整形（pretty print）を戻した上で、ディレクトリを.docx/.pptx/.xlsxにパックするツールです。

使用例:
    python pack.py <input_directory> <office_file> [--force]
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import defusedxml.minidom
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="ディレクトリをOfficeファイルにパックします")
    parser.add_argument("input_directory", help="アンパック済みOfficeドキュメントのディレクトリ")
    parser.add_argument("output_file", help="出力Officeファイル（.docx/.pptx/.xlsx）")
    parser.add_argument("--force", action="store_true", help="検証をスキップ")
    args = parser.parse_args()

    try:
        success = pack_document(
            args.input_directory, args.output_file, validate=not args.force
        )

        # 検証をスキップした場合は警告を表示
        if args.force:
            print("Warning: Skipped validation, file may be corrupt", file=sys.stderr)
        # 検証に失敗した場合はエラー終了
        elif not success:
            print("Contents would produce a corrupt file.", file=sys.stderr)
            print("Please validate XML before repacking.", file=sys.stderr)
            print("Use --force to skip validation and pack anyway.", file=sys.stderr)
            sys.exit(1)

    except ValueError as e:
        sys.exit(f"Error: {e}")


def pack_document(input_dir, output_file, validate=False):
    """ディレクトリをOfficeファイル（.docx/.pptx/.xlsx）にパックします。

    Args:
        input_dir: アンパック済みOfficeドキュメントのディレクトリパス
        output_file: 出力Officeファイルのパス
        validate: Trueの場合、sofficeで検証します（デフォルト: False）

    Returns:
        bool: 成功ならTrue、検証失敗ならFalse
    """
    input_dir = Path(input_dir)
    output_file = Path(output_file)

    if not input_dir.is_dir():
        raise ValueError(f"{input_dir} is not a directory")
    if output_file.suffix.lower() not in {".docx", ".pptx", ".xlsx"}:
        raise ValueError(f"{output_file} must be a .docx, .pptx, or .xlsx file")

    # 元ディレクトリを変更しないよう一時ディレクトリで作業
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_content_dir = Path(temp_dir) / "content"
        shutil.copytree(input_dir, temp_content_dir)

        # pretty printで入った不要な空白を除去するためXMLを処理
        for pattern in ["*.xml", "*.rels"]:
            for xml_file in temp_content_dir.rglob(pattern):
                condense_xml(xml_file)

        # 最終的なOfficeファイルをzipアーカイブとして作成
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in temp_content_dir.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(temp_content_dir))

        # 必要なら検証
        if validate:
            if not validate_document(output_file):
                output_file.unlink()  # Delete the corrupt file
                return False

    return True


def validate_document(doc_path):
    """sofficeでHTML変換してドキュメントを検証します。"""
    # 拡張子に応じて適切な変換フィルタを選択
    match doc_path.suffix.lower():
        case ".docx":
            filter_name = "html:HTML"
        case ".pptx":
            filter_name = "html:impress_html_Export"
        case ".xlsx":
            filter_name = "html:HTML (StarCalc)"

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            result = subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    filter_name,
                    "--outdir",
                    temp_dir,
                    str(doc_path),
                ],
                capture_output=True,
                timeout=10,
                text=True,
            )
            if not (Path(temp_dir) / f"{doc_path.stem}.html").exists():
                error_msg = result.stderr.strip() or "Document validation failed"
                print(f"検証エラー: {error_msg}", file=sys.stderr)
                return False
            return True
        except FileNotFoundError:
            print("警告: sofficeが見つかりません。検証をスキップします。", file=sys.stderr)
            return True
        except subprocess.TimeoutExpired:
            print("検証エラー: 変換がタイムアウトしました", file=sys.stderr)
            return False
        except Exception as e:
            print(f"検証エラー: {e}", file=sys.stderr)
            return False


def condense_xml(xml_file):
    """不要な空白を除去し、コメントノードを削除します。"""
    with open(xml_file, "r", encoding="utf-8") as f:
        dom = defusedxml.minidom.parse(f)

    # 要素ごとに空白テキストノードとコメントノードを除去
    for element in dom.getElementsByTagName("*"):
        # w:t要素はスキップ（内容文字列を壊さないため）
        if element.tagName.endswith(":t"):
            continue

        # 空白のみのテキストノードとコメントノードを削除
        for child in list(element.childNodes):
            if (
                child.nodeType == child.TEXT_NODE
                and child.nodeValue
                and child.nodeValue.strip() == ""
            ) or child.nodeType == child.COMMENT_NODE:
                element.removeChild(child)

    # 圧縮したXMLを書き戻す
    with open(xml_file, "wb") as f:
        f.write(dom.toxml(encoding="UTF-8"))


if __name__ == "__main__":
    main()
