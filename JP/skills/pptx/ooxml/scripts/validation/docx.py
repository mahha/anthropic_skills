"""
Word文書のXMLファイルを、XSDスキーマに対して検証するバリデータです。
"""

import re
import tempfile
import zipfile

import lxml.etree

from .base import BaseSchemaValidator


class DOCXSchemaValidator(BaseSchemaValidator):
    """Word文書のXMLファイルをXSDスキーマに対して検証します。"""

    # Word固有の名前空間
    WORD_2006_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    # Word固有の「要素→リレーション種別」マッピング
    # まず空で開始し、必要に応じてケースを追加します
    ELEMENT_RELATIONSHIP_TYPES = {}

    def validate(self):
        """全検証を実行し、すべて合格ならTrueを返します。"""
        # テスト0: XMLの整形式（well-formedness）
        if not self.validate_xml():
            return False

        # テスト1: 名前空間宣言
        all_valid = True
        if not self.validate_namespaces():
            all_valid = False

        # テスト2: IDの一意性
        if not self.validate_unique_ids():
            all_valid = False

        # テスト3: リレーションとファイル参照の検証
        if not self.validate_file_references():
            all_valid = False

        # テスト4: content type宣言
        if not self.validate_content_types():
            all_valid = False

        # テスト5: XSDスキーマ検証
        if not self.validate_against_xsd():
            all_valid = False

        # テスト6: 空白保持（whitespace preservation）
        if not self.validate_whitespace_preservation():
            all_valid = False

        # テスト7: 削除（deletion）検証
        if not self.validate_deletions():
            all_valid = False

        # テスト8: 挿入（insertion）検証
        if not self.validate_insertions():
            all_valid = False

        # テスト9: リレーションID参照の検証
        if not self.validate_all_relationship_ids():
            all_valid = False

        # 段落数を数えて比較
        self.compare_paragraph_counts()

        return all_valid

    def validate_whitespace_preservation(self):
        """
        空白を含むw:t要素が xml:space='preserve' を持つことを検証します。
        """
        errors = []

        for xml_file in self.xml_files:
            # document.xml のみチェック
            if xml_file.name != "document.xml":
                continue

            try:
                root = lxml.etree.parse(str(xml_file)).getroot()

                # すべての w:t 要素を列挙
                for elem in root.iter(f"{{{self.WORD_2006_NAMESPACE}}}t"):
                    if elem.text:
                        text = elem.text
                        # テキストが空白で始まる/終わるか
                        if re.match(r"^\s.*", text) or re.match(r".*\s$", text):
                            # xml:space="preserve" があるか
                            xml_space_attr = f"{{{self.XML_NAMESPACE}}}space"
                            if (
                                xml_space_attr not in elem.attrib
                                or elem.attrib[xml_space_attr] != "preserve"
                            ):
                                # テキストのプレビューを表示
                                text_preview = (
                                    repr(text)[:50] + "..."
                                    if len(repr(text)) > 50
                                    else repr(text)
                                )
                                errors.append(
                                    f"  {xml_file.relative_to(self.unpacked_dir)}: "
                                    f"Line {elem.sourceline}: 空白を含むw:t要素に xml:space='preserve' がありません: {text_preview}"
                                )

            except (lxml.etree.XMLSyntaxError, Exception) as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: Error: {e}"
                )

        if errors:
            print(f"FAILED - 空白保持（whitespace preservation）の違反が{len(errors)}件あります:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("PASSED - すべての空白は適切に保持されています")
            return True

    def validate_deletions(self):
        """
        w:t要素が w:del 要素の内側に存在しないことを検証します。
        なぜかXSD検証では検出できないため、手動でチェックします。
        """
        errors = []

        for xml_file in self.xml_files:
            # document.xml のみチェック
            if xml_file.name != "document.xml":
                continue

            try:
                root = lxml.etree.parse(str(xml_file)).getroot()

                # w:del の子孫にある w:t 要素を探す
                namespaces = {"w": self.WORD_2006_NAMESPACE}
                xpath_expression = ".//w:del//w:t"
                problematic_t_elements = root.xpath(
                    xpath_expression, namespaces=namespaces
                )
                for t_elem in problematic_t_elements:
                    if t_elem.text:
                        # テキストのプレビューを表示
                        text_preview = (
                            repr(t_elem.text)[:50] + "..."
                            if len(repr(t_elem.text)) > 50
                            else repr(t_elem.text)
                        )
                        errors.append(
                            f"  {xml_file.relative_to(self.unpacked_dir)}: "
                            f"Line {t_elem.sourceline}: <w:del> 内に <w:t> が見つかりました: {text_preview}"
                        )

            except (lxml.etree.XMLSyntaxError, Exception) as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: Error: {e}"
                )

        if errors:
            print(f"FAILED - 削除（deletion）検証の違反が{len(errors)}件あります:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("PASSED - <w:del> 内に <w:t> は見つかりませんでした")
            return True

    def count_paragraphs_in_unpacked(self):
        """アンパック済みドキュメント内の段落数を数えます。"""
        count = 0

        for xml_file in self.xml_files:
            # document.xml のみチェック
            if xml_file.name != "document.xml":
                continue

            try:
                root = lxml.etree.parse(str(xml_file)).getroot()
                # すべての w:p 要素を数える
                paragraphs = root.findall(f".//{{{self.WORD_2006_NAMESPACE}}}p")
                count = len(paragraphs)
            except Exception as e:
                print(f"アンパック済みドキュメントの段落数カウント中のエラー: {e}")

        return count

    def count_paragraphs_in_original(self):
        """元のdocxファイル内の段落数を数えます。"""
        count = 0

        try:
            # 元ファイルを展開するため一時ディレクトリを作成
            with tempfile.TemporaryDirectory() as temp_dir:
                # 元docxを展開
                with zipfile.ZipFile(self.original_file, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)

                # document.xml をパース
                doc_xml_path = temp_dir + "/word/document.xml"
                root = lxml.etree.parse(doc_xml_path).getroot()

                # すべての w:p 要素を数える
                paragraphs = root.findall(f".//{{{self.WORD_2006_NAMESPACE}}}p")
                count = len(paragraphs)

        except Exception as e:
            print(f"元ドキュメントの段落数カウント中のエラー: {e}")

        return count

    def validate_insertions(self):
        """
        w:delText要素が w:ins 要素の内側に存在しないことを検証します。
        w:delText は、w:ins 内にあっても w:del にネストされている場合のみ許可されます。
        """
        errors = []

        for xml_file in self.xml_files:
            if xml_file.name != "document.xml":
                continue

            try:
                root = lxml.etree.parse(str(xml_file)).getroot()
                namespaces = {"w": self.WORD_2006_NAMESPACE}

                # Find w:delText in w:ins that are NOT within w:del
                invalid_elements = root.xpath(
                    ".//w:ins//w:delText[not(ancestor::w:del)]",
                    namespaces=namespaces
                )

                for elem in invalid_elements:
                    text_preview = (
                        repr(elem.text or "")[:50] + "..."
                        if len(repr(elem.text or "")) > 50
                        else repr(elem.text or "")
                    )
                    errors.append(
                        f"  {xml_file.relative_to(self.unpacked_dir)}: "
                        f"Line {elem.sourceline}: <w:delText> within <w:ins>: {text_preview}"
                    )

            except (lxml.etree.XMLSyntaxError, Exception) as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: Error: {e}"
                )

        if errors:
            print(f"FAILED - 挿入（insertion）検証の違反が{len(errors)}件あります:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("PASSED - w:ins 内に w:delText 要素は見つかりませんでした")
            return True

    def compare_paragraph_counts(self):
        """元ドキュメントと新ドキュメントの段落数を比較します。"""
        original_count = self.count_paragraphs_in_original()
        new_count = self.count_paragraphs_in_unpacked()

        diff = new_count - original_count
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"\n段落数: {original_count} → {new_count} ({diff_str})")


if __name__ == "__main__":
    raise RuntimeError("このモジュールは直接実行しないでください。")
