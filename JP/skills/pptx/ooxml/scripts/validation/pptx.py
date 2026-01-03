"""
PowerPointプレゼンのXMLファイルを、XSDスキーマに対して検証するバリデータです。
"""

import re

from .base import BaseSchemaValidator


class PPTXSchemaValidator(BaseSchemaValidator):
    """PowerPointプレゼンのXMLファイルをXSDスキーマに対して検証します。"""

    # PowerPointプレゼンの名前空間
    PRESENTATIONML_NAMESPACE = (
        "http://schemas.openxmlformats.org/presentationml/2006/main"
    )

    # PowerPoint固有の「要素→リレーション種別」マッピング
    ELEMENT_RELATIONSHIP_TYPES = {
        "sldid": "slide",
        "sldmasterid": "slidemaster",
        "notesmasterid": "notesmaster",
        "sldlayoutid": "slidelayout",
        "themeid": "theme",
        "tablestyleid": "tablestyles",
    }

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

        # テスト3: UUID形式IDの検証
        if not self.validate_uuid_ids():
            all_valid = False

        # テスト4: リレーションとファイル参照の検証
        if not self.validate_file_references():
            all_valid = False

        # テスト5: スライドレイアウトIDの検証
        if not self.validate_slide_layout_ids():
            all_valid = False

        # テスト6: content type宣言
        if not self.validate_content_types():
            all_valid = False

        # テスト7: XSDスキーマ検証
        if not self.validate_against_xsd():
            all_valid = False

        # テスト8: ノートスライド参照の検証
        if not self.validate_notes_slide_references():
            all_valid = False

        # テスト9: リレーションID参照の検証
        if not self.validate_all_relationship_ids():
            all_valid = False

        # テスト10: 重複スライドレイアウト参照の検証
        if not self.validate_no_duplicate_slide_layouts():
            all_valid = False

        return all_valid

    def validate_uuid_ids(self):
        """UUIDに見えるID属性が、16進文字のみで構成されることを検証します。"""
        import lxml.etree

        errors = []
        # UUIDパターン: 8-4-4-4-12 の16進（ブレース/ハイフンは任意）
        uuid_pattern = re.compile(
            r"^[\{\(]?[0-9A-Fa-f]{8}-?[0-9A-Fa-f]{4}-?[0-9A-Fa-f]{4}-?[0-9A-Fa-f]{4}-?[0-9A-Fa-f]{12}[\}\)]?$"
        )

        for xml_file in self.xml_files:
            try:
                root = lxml.etree.parse(str(xml_file)).getroot()

                # 全要素のID系属性をチェック
                for elem in root.iter():
                    for attr, value in elem.attrib.items():
                        # ID属性かどうか
                        attr_name = attr.split("}")[-1].lower()
                        if attr_name == "id" or attr_name.endswith("id"):
                            # UUIDっぽい値か（長さ/構造）
                            if self._looks_like_uuid(value):
                                # 16進文字が適切な位置に入っているか検証
                                if not uuid_pattern.match(value):
                                    errors.append(
                                        f"  {xml_file.relative_to(self.unpacked_dir)}: "
                                        f"Line {elem.sourceline}: ID '{value}' はUUIDのように見えますが、無効な16進文字が含まれています"
                                    )

            except (lxml.etree.XMLSyntaxError, Exception) as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: Error: {e}"
                )

        if errors:
            print(f"FAILED - UUID形式IDの検証エラーが{len(errors)}件あります:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("PASSED - UUID形式に見えるIDはすべて有効な16進値でした")
            return True

    def _looks_like_uuid(self, value):
        """値がUUIDの一般的な構造を持つかを判定します。"""
        # 代表的な区切りを除去
        clean_value = value.strip("{}()").replace("-", "")
        # 32文字の「16進っぽい」値か（無効文字を含む可能性はある）
        return len(clean_value) == 32 and all(c.isalnum() for c in clean_value)

    def validate_slide_layout_ids(self):
        """スライドマスター内のsldLayoutIdが、有効なスライドレイアウトを参照しているか検証します。"""
        import lxml.etree

        errors = []

        # スライドマスターファイルを列挙
        slide_masters = list(self.unpacked_dir.glob("ppt/slideMasters/*.xml"))

        if not slide_masters:
            if self.verbose:
                print("PASSED - スライドマスターが見つかりませんでした")
            return True

        for slide_master in slide_masters:
            try:
                # スライドマスターをパース
                root = lxml.etree.parse(str(slide_master)).getroot()

                # 対応する_relsファイルを探す
                rels_file = slide_master.parent / "_rels" / f"{slide_master.name}.rels"

                if not rels_file.exists():
                    errors.append(
                        f"  {slide_master.relative_to(self.unpacked_dir)}: "
                        f"relationshipsファイルがありません: {rels_file.relative_to(self.unpacked_dir)}"
                    )
                    continue

                # relationshipsファイルをパース
                rels_root = lxml.etree.parse(str(rels_file)).getroot()

                # スライドレイアウトを指す有効なrelationship ID集合を作る
                valid_layout_rids = set()
                for rel in rels_root.findall(
                    f".//{{{self.PACKAGE_RELATIONSHIPS_NAMESPACE}}}Relationship"
                ):
                    rel_type = rel.get("Type", "")
                    if "slideLayout" in rel_type:
                        valid_layout_rids.add(rel.get("Id"))

                # スライドマスター内のsldLayoutIdを列挙
                for sld_layout_id in root.findall(
                    f".//{{{self.PRESENTATIONML_NAMESPACE}}}sldLayoutId"
                ):
                    r_id = sld_layout_id.get(
                        f"{{{self.OFFICE_RELATIONSHIPS_NAMESPACE}}}id"
                    )
                    layout_id = sld_layout_id.get("id")

                    if r_id and r_id not in valid_layout_rids:
                        errors.append(
                            f"  {slide_master.relative_to(self.unpacked_dir)}: "
                            f"Line {sld_layout_id.sourceline}: sldLayoutId with id='{layout_id}' "
                            f"r:id='{r_id}' を参照していますが、slideLayoutのrelationshipsに存在しません"
                        )

            except (lxml.etree.XMLSyntaxError, Exception) as e:
                errors.append(
                    f"  {slide_master.relative_to(self.unpacked_dir)}: Error: {e}"
                )

        if errors:
            print(f"FAILED - スライドレイアウトIDの検証エラーが{len(errors)}件あります:")
            for error in errors:
                print(error)
            print(
                "無効な参照を削除するか、relationshipsファイルに不足しているスライドレイアウトを追加してください。"
            )
            return False
        else:
            if self.verbose:
                print("PASSED - すべてのスライドレイアウトIDが有効なレイアウトを参照しています")
            return True

    def validate_no_duplicate_slide_layouts(self):
        """各スライドがslideLayout参照をちょうど1つ持つことを検証します。"""
        import lxml.etree

        errors = []
        slide_rels_files = list(self.unpacked_dir.glob("ppt/slides/_rels/*.xml.rels"))

        for rels_file in slide_rels_files:
            try:
                root = lxml.etree.parse(str(rels_file)).getroot()

                # slideLayoutのrelationshipsを抽出
                layout_rels = [
                    rel
                    for rel in root.findall(
                        f".//{{{self.PACKAGE_RELATIONSHIPS_NAMESPACE}}}Relationship"
                    )
                    if "slideLayout" in rel.get("Type", "")
                ]

                if len(layout_rels) > 1:
                    errors.append(
                        f"  {rels_file.relative_to(self.unpacked_dir)}: has {len(layout_rels)} slideLayout references"
                    )

            except Exception as e:
                errors.append(
                    f"  {rels_file.relative_to(self.unpacked_dir)}: Error: {e}"
                )

        if errors:
            print("FAILED - slideLayout参照が重複しているスライドが見つかりました:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("PASSED - すべてのスライドが slideLayout 参照をちょうど1つ持っています")
            return True

    def validate_notes_slide_references(self):
        """各notesSlideファイルが、1つのスライドからのみ参照されていることを検証します。"""
        import lxml.etree

        errors = []
        notes_slide_references = {}  # Track which slides reference each notesSlide

        # スライドのrelationshipsファイルを列挙
        slide_rels_files = list(self.unpacked_dir.glob("ppt/slides/_rels/*.xml.rels"))

        if not slide_rels_files:
            if self.verbose:
                print("PASSED - スライドのrelationshipsファイルが見つかりませんでした")
            return True

        for rels_file in slide_rels_files:
            try:
                # relationshipsファイルをパース
                root = lxml.etree.parse(str(rels_file)).getroot()

                # notesSlideのrelationshipsを抽出
                for rel in root.findall(
                    f".//{{{self.PACKAGE_RELATIONSHIPS_NAMESPACE}}}Relationship"
                ):
                    rel_type = rel.get("Type", "")
                    if "notesSlide" in rel_type:
                        target = rel.get("Target", "")
                        if target:
                            # 相対パスを考慮してtargetパスを正規化
                            normalized_target = target.replace("../", "")

                            # このnotesSlideを参照しているスライドを追跡
                            slide_name = rels_file.stem.replace(
                                ".xml", ""
                            )  # e.g., "slide1"

                            if normalized_target not in notes_slide_references:
                                notes_slide_references[normalized_target] = []
                            notes_slide_references[normalized_target].append(
                                (slide_name, rels_file)
                            )

            except (lxml.etree.XMLSyntaxError, Exception) as e:
                errors.append(
                    f"  {rels_file.relative_to(self.unpacked_dir)}: Error: {e}"
                )

        # 重複参照がないか確認
        for target, references in notes_slide_references.items():
            if len(references) > 1:
                slide_names = [ref[0] for ref in references]
                errors.append(
                    f"  Notes slide '{target}' is referenced by multiple slides: {', '.join(slide_names)}"
                )
                for slide_name, rels_file in references:
                    errors.append(f"    - {rels_file.relative_to(self.unpacked_dir)}")

        if errors:
            print(
                f"FAILED - notes slide参照の検証エラーが{len([e for e in errors if not e.startswith('    ')])}件あります:"
            )
            for error in errors:
                print(error)
            print("各スライドは、必要に応じて個別のスライドファイルを持つ場合があります。")
            return False
        else:
            if self.verbose:
                print("PASSED - すべてのnotes slide参照は一意です")
            return True


if __name__ == "__main__":
    raise RuntimeError("このモジュールは直接実行しないでください。")
