"""
Word文書における追跡変更（tracked changes）を検証するバリデータです。
"""

import subprocess
import tempfile
import zipfile
from pathlib import Path


class RedliningValidator:
    """Word文書の追跡変更（tracked changes）を検証します。"""

    def __init__(self, unpacked_dir, original_docx, verbose=False):
        self.unpacked_dir = Path(unpacked_dir)
        self.original_docx = Path(original_docx)
        self.verbose = verbose
        self.namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        }

    def validate(self):
        """メイン検証。妥当ならTrue、そうでなければFalseを返します。"""
        # アンパック済みディレクトリが存在し、構造が正しいか確認
        modified_file = self.unpacked_dir / "word" / "document.xml"
        if not modified_file.exists():
            print(f"FAILED - 変更後のdocument.xmlが見つかりません: {modified_file}")
            return False

        # まず、Claudeによる追跡変更が存在するか確認（存在しないならredlining検証は不要）
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(modified_file)
            root = tree.getroot()

            # Claudeがauthorになっている w:del / w:ins を探す
            del_elements = root.findall(".//w:del", self.namespaces)
            ins_elements = root.findall(".//w:ins", self.namespaces)

            # Claudeの変更だけに絞り込む
            claude_del_elements = [
                elem
                for elem in del_elements
                if elem.get(f"{{{self.namespaces['w']}}}author") == "Claude"
            ]
            claude_ins_elements = [
                elem
                for elem in ins_elements
                if elem.get(f"{{{self.namespaces['w']}}}author") == "Claude"
            ]

            # Claudeの追跡変更が使われている場合のみredlining検証が必要
            if not claude_del_elements and not claude_ins_elements:
                if self.verbose:
                    print("PASSED - Claudeによる追跡変更が見つかりませんでした。")
                return True

        except Exception:
            # XMLをパースできない場合は、通常のフル検証に進む
            pass

        # 元のdocxを展開するため一時ディレクトリを作成
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 元docxを展開
            try:
                with zipfile.ZipFile(self.original_docx, "r") as zip_ref:
                    zip_ref.extractall(temp_path)
            except Exception as e:
                print(f"FAILED - 元docxの展開エラー: {e}")
                return False

            original_file = temp_path / "word" / "document.xml"
            if not original_file.exists():
                print(
                    f"FAILED - 元docx内に document.xml が見つかりません: {self.original_docx}"
                )
                return False

            # redlining検証のため、両方のXMLをxml.etree.ElementTreeでパース
            try:
                import xml.etree.ElementTree as ET

                modified_tree = ET.parse(modified_file)
                modified_root = modified_tree.getroot()
                original_tree = ET.parse(original_file)
                original_root = original_tree.getroot()
            except ET.ParseError as e:
                print(f"FAILED - XMLパースエラー: {e}")
                return False

            # 両ドキュメントからClaudeの追跡変更を除去
            self._remove_claude_tracked_changes(original_root)
            self._remove_claude_tracked_changes(modified_root)

            # テキスト内容を抽出して比較
            modified_text = self._extract_text_content(modified_root)
            original_text = self._extract_text_content(original_root)

            if modified_text != original_text:
                # 文字単位の差分を提示
                error_message = self._generate_detailed_diff(
                    original_text, modified_text
                )
                print(error_message)
                return False

            if self.verbose:
                print("PASSED - Claudeの変更はすべて追跡変更として正しく記録されています")
            return True

    def _generate_detailed_diff(self, original_text, modified_text):
        """gitのword diffを使って、詳細な差分（単語/文字レベル）を生成します。"""
        error_parts = [
            "FAILED - Claudeの追跡変更を除去した後のドキュメント本文が一致しません",
            "",
            "考えられる原因:",
            "  1. 他者の <w:ins> / <w:del> タグの内部テキストを直接変更した",
            "  2. 追跡変更を正しく使わずに編集した",
            "  3. 他者の挿入を削除する際、<w:ins> の内側に <w:del> をネストしなかった",
            "",
            "追跡変更済み（pre-redlined）ドキュメントでは次のパターンを使用してください:",
            "  - 他者の挿入（INSERTION）を拒否: 相手の <w:ins> の内側に <w:del> をネストする",
            "  - 他者の削除（DELETION）を復元: 相手の <w:del> の後ろに新しい <w:ins> を追加する",
            "",
        ]

        # gitのword diffを表示
        git_diff = self._get_git_word_diff(original_text, modified_text)
        if git_diff:
            error_parts.extend(["差分:", "============", git_diff])
        else:
            error_parts.append("word diffを生成できません（gitが利用できない可能性があります）")

        return "\n".join(error_parts)

    def _get_git_word_diff(self, original_text, modified_text):
        """gitでword diffを生成します（可能なら文字単位で精密に）。"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # 2つの一時ファイルを作成
                original_file = temp_path / "original.txt"
                modified_file = temp_path / "modified.txt"

                original_file.write_text(original_text, encoding="utf-8")
                modified_file.write_text(modified_text, encoding="utf-8")

                # まず文字単位diff（精密）を試す
                result = subprocess.run(
                    [
                        "git",
                        "diff",
                        "--word-diff=plain",
                        "--word-diff-regex=.",  # 文字単位diff
                        "-U0",  # コンテキスト0行（変更行のみ）
                        "--no-index",
                        str(original_file),
                        str(modified_file),
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.stdout.strip():
                    # 出力を整形（git diffのヘッダ行を除去）
                    lines = result.stdout.split("\n")
                    # ヘッダ行をスキップ（diff --git, index, +++, ---, @@）
                    content_lines = []
                    in_content = False
                    for line in lines:
                        if line.startswith("@@"):
                            in_content = True
                            continue
                        if in_content and line.strip():
                            content_lines.append(line)

                    if content_lines:
                        return "\n".join(content_lines)

                # 文字単位が冗長なら単語単位diffへフォールバック
                result = subprocess.run(
                    [
                        "git",
                        "diff",
                        "--word-diff=plain",
                        "-U0",  # コンテキスト0行
                        "--no-index",
                        str(original_file),
                        str(modified_file),
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.stdout.strip():
                    lines = result.stdout.split("\n")
                    content_lines = []
                    in_content = False
                    for line in lines:
                        if line.startswith("@@"):
                            in_content = True
                            continue
                        if in_content and line.strip():
                            content_lines.append(line)
                    return "\n".join(content_lines)

        except (subprocess.CalledProcessError, FileNotFoundError, Exception):
            # gitが無い等の理由で失敗した場合はNone（上位でフォールバック表示）
            pass

        return None

    def _remove_claude_tracked_changes(self, root):
        """XMLルートから、Claudeがauthorの追跡変更を除去します。"""
        ins_tag = f"{{{self.namespaces['w']}}}ins"
        del_tag = f"{{{self.namespaces['w']}}}del"
        author_attr = f"{{{self.namespaces['w']}}}author"

        # w:ins 要素を除去
        for parent in root.iter():
            to_remove = []
            for child in parent:
                if child.tag == ins_tag and child.get(author_attr) == "Claude":
                    to_remove.append(child)
            for elem in to_remove:
                parent.remove(elem)

        # Unwrap content in w:del elements where author is "Claude"
        deltext_tag = f"{{{self.namespaces['w']}}}delText"
        t_tag = f"{{{self.namespaces['w']}}}t"

        for parent in root.iter():
            to_process = []
            for child in parent:
                if child.tag == del_tag and child.get(author_attr) == "Claude":
                    to_process.append((child, list(parent).index(child)))

            # インデックスを維持するため逆順に処理
            for del_elem, del_index in reversed(to_process):
                # 移動前に w:delText を w:t に変換
                for elem in del_elem.iter():
                    if elem.tag == deltext_tag:
                        elem.tag = t_tag

                # Move all children of w:del to its parent before removing w:del
                for child in reversed(list(del_elem)):
                    parent.insert(del_index, child)
                parent.remove(del_elem)

    def _extract_text_content(self, root):
        """Word XMLからテキスト内容を抽出し、段落構造を保ちます。

        追跡変更の挿入が「テキストのない構造要素」だけを追加するケースでは、
        空段落が誤検知（false positive）の原因になり得るためスキップします。
        """
        p_tag = f"{{{self.namespaces['w']}}}p"
        t_tag = f"{{{self.namespaces['w']}}}t"

        paragraphs = []
        for p_elem in root.findall(f".//{p_tag}"):
            # この段落内のテキスト要素を収集
            text_parts = []
            for t_elem in p_elem.findall(f".//{t_tag}"):
                if t_elem.text:
                    text_parts.append(t_elem.text)
            paragraph_text = "".join(text_parts)
            # 空段落はスキップ（内容検証に影響しない）
            if paragraph_text:
                paragraphs.append(paragraph_text)

        return "\n".join(paragraphs)


if __name__ == "__main__":
    raise RuntimeError("このモジュールは直接実行しないでください。")
