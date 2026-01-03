"""
ドキュメントファイル向けの共通検証ロジックを持つ、ベースバリデータです。

注: このファイルは大きいため、コメント/docstringの一部は原文（英語）を残しています。検証ロジック自体は変更していません。
"""

import re
from pathlib import Path

import lxml.etree


class BaseSchemaValidator:
    """ドキュメントファイル向けの共通検証ロジックを持つ、ベースバリデータです。"""

    # 'id'属性がファイル内で一意であるべき要素
    # 形式: element_name -> (attribute_name, scope)
    # scope: 'file'（ファイル内一意）または 'global'（全ファイルで一意）
    UNIQUE_ID_REQUIREMENTS = {
        # Word要素
        "comment": ("id", "file"),  # Comment IDs in comments.xml
        "commentrangestart": ("id", "file"),  # Must match comment IDs
        "commentrangeend": ("id", "file"),  # Must match comment IDs
        "bookmarkstart": ("id", "file"),  # Bookmark start IDs
        "bookmarkend": ("id", "file"),  # Bookmark end IDs
        # 注: ins/del（追跡変更）は同一リビジョンの一部としてIDを共有する場合があります
        # PowerPoint要素
        "sldid": ("id", "file"),  # Slide IDs in presentation.xml
        "sldmasterid": ("id", "global"),  # Slide master IDs must be globally unique
        "sldlayoutid": ("id", "global"),  # Slide layout IDs must be globally unique
        "cm": ("authorid", "file"),  # Comment author IDs
        # Excel要素
        "sheet": ("sheetid", "file"),  # Sheet IDs in workbook.xml
        "definedname": ("id", "file"),  # Named range IDs
        # 図形/Shape要素（全形式共通）
        "cxnsp": ("id", "file"),  # Connection shape IDs
        "sp": ("id", "file"),  # Shape IDs
        "pic": ("id", "file"),  # Picture IDs
        "grpsp": ("id", "file"),  # Group shape IDs
    }

    # 要素名→期待するリレーション種別のマッピング
    # サブクラスで形式別のマッピングに上書きします
    ELEMENT_RELATIONSHIP_TYPES = {}

    # Office文書タイプ共通のスキーママッピング
    SCHEMA_MAPPINGS = {
        # 文書タイプ別スキーマ
        "word": "ISO-IEC29500-4_2016/wml.xsd",  # Word documents
        "ppt": "ISO-IEC29500-4_2016/pml.xsd",  # PowerPoint presentations
        "xl": "ISO-IEC29500-4_2016/sml.xsd",  # Excel spreadsheets
        # 共通ファイル
        "[Content_Types].xml": "ecma/fouth-edition/opc-contentTypes.xsd",
        "app.xml": "ISO-IEC29500-4_2016/shared-documentPropertiesExtended.xsd",
        "core.xml": "ecma/fouth-edition/opc-coreProperties.xsd",
        "custom.xml": "ISO-IEC29500-4_2016/shared-documentPropertiesCustom.xsd",
        ".rels": "ecma/fouth-edition/opc-relationships.xsd",
        # Word固有ファイル
        "people.xml": "microsoft/wml-2012.xsd",
        "commentsIds.xml": "microsoft/wml-cid-2016.xsd",
        "commentsExtensible.xml": "microsoft/wml-cex-2018.xsd",
        "commentsExtended.xml": "microsoft/wml-2012.xsd",
        # チャート（全タイプ共通）
        "chart": "ISO-IEC29500-4_2016/dml-chart.xsd",
        # テーマ（全タイプ共通）
        "theme": "ISO-IEC29500-4_2016/dml-main.xsd",
        # 描画/メディアファイル
        "drawing": "ISO-IEC29500-4_2016/dml-main.xsd",
    }

    # 共通の名前空間定数
    MC_NAMESPACE = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"

    # バリデータ全体で使う共通OOXML名前空間
    PACKAGE_RELATIONSHIPS_NAMESPACE = (
        "http://schemas.openxmlformats.org/package/2006/relationships"
    )
    OFFICE_RELATIONSHIPS_NAMESPACE = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    CONTENT_TYPES_NAMESPACE = (
        "http://schemas.openxmlformats.org/package/2006/content-types"
    )

    # ignorable namespaces をクリーンアップする対象フォルダ
    MAIN_CONTENT_FOLDERS = {"word", "ppt", "xl"}

    # 許可するOOXML名前空間（全ドキュメントタイプのスーパーセット）
    OOXML_NAMESPACES = {
        "http://schemas.openxmlformats.org/officeDocument/2006/math",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "http://schemas.openxmlformats.org/schemaLibrary/2006/main",
        "http://schemas.openxmlformats.org/drawingml/2006/main",
        "http://schemas.openxmlformats.org/drawingml/2006/chart",
        "http://schemas.openxmlformats.org/drawingml/2006/chartDrawing",
        "http://schemas.openxmlformats.org/drawingml/2006/diagram",
        "http://schemas.openxmlformats.org/drawingml/2006/picture",
        "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
        "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
        "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "http://schemas.openxmlformats.org/presentationml/2006/main",
        "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "http://schemas.openxmlformats.org/officeDocument/2006/sharedTypes",
        "http://www.w3.org/XML/1998/namespace",
    }

    def __init__(self, unpacked_dir, original_file, verbose=False):
        self.unpacked_dir = Path(unpacked_dir).resolve()
        self.original_file = Path(original_file)
        self.verbose = verbose

        # スキーマディレクトリを設定
        self.schemas_dir = Path(__file__).parent.parent.parent / "schemas"

        # XMLと.relsファイルを収集
        patterns = ["*.xml", "*.rels"]
        self.xml_files = [
            f for pattern in patterns for f in self.unpacked_dir.rglob(pattern)
        ]

        if not self.xml_files:
            print(f"Warning: No XML files found in {self.unpacked_dir}")

    def validate(self):
        """全検証を実行し、すべて合格ならTrueを返します。"""
        raise NotImplementedError("サブクラスは validate メソッドを実装する必要があります")

    def validate_xml(self):
        """すべてのXMLファイルが整形式（well-formed）であることを検証します。"""
        errors = []

        for xml_file in self.xml_files:
            try:
                # XMLファイルのパースを試みる
                lxml.etree.parse(str(xml_file))
            except lxml.etree.XMLSyntaxError as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: "
                    f"Line {e.lineno}: {e.msg}"
                )
            except Exception as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: "
                    f"Unexpected error: {str(e)}"
                )

        if errors:
            print(f"FAILED - XMLの違反が{len(errors)}件見つかりました:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("PASSED - すべてのXMLは整形式です")
            return True

    def validate_namespaces(self):
        """Ignorable属性内の名前空間プレフィックスが宣言済みであることを検証します。"""
        errors = []

        for xml_file in self.xml_files:
            try:
                root = lxml.etree.parse(str(xml_file)).getroot()
                declared = set(root.nsmap.keys()) - {None}  # Exclude default namespace

                for attr_val in [
                    v for k, v in root.attrib.items() if k.endswith("Ignorable")
                ]:
                    undeclared = set(attr_val.split()) - declared
                    errors.extend(
                        f"  {xml_file.relative_to(self.unpacked_dir)}: "
                        f"Namespace '{ns}' in Ignorable but not declared"
                        for ns in undeclared
                    )
            except lxml.etree.XMLSyntaxError:
                continue

        if errors:
            print(f"FAILED - {len(errors)} namespace issues:")
            for error in errors:
                print(error)
            return False
        if self.verbose:
            print("PASSED - すべての名前空間プレフィックスは適切に宣言されています")
        return True

    def validate_unique_ids(self):
        """OOXML要件に従い、特定IDが一意であることを検証します。"""
        errors = []
        global_ids = {}  # Track globally unique IDs across all files

        for xml_file in self.xml_files:
            try:
                root = lxml.etree.parse(str(xml_file)).getroot()
                file_ids = {}  # Track IDs that must be unique within this file

                # ツリーからmc:AlternateContent要素をすべて除去
                mc_elements = root.xpath(
                    ".//mc:AlternateContent", namespaces={"mc": self.MC_NAMESPACE}
                )
                for elem in mc_elements:
                    elem.getparent().remove(elem)

                # クリーンアップ後のツリーでIDをチェック
                for elem in root.iter():
                    # 名前空間を除いた要素名を取得
                    tag = (
                        elem.tag.split("}")[-1].lower()
                        if "}" in elem.tag
                        else elem.tag.lower()
                    )

                    # この要素タイプにID一意性要件があるか確認
                    if tag in self.UNIQUE_ID_REQUIREMENTS:
                        attr_name, scope = self.UNIQUE_ID_REQUIREMENTS[tag]

                        # 指定属性を探す
                        id_value = None
                        for attr, value in elem.attrib.items():
                            attr_local = (
                                attr.split("}")[-1].lower()
                                if "}" in attr
                                else attr.lower()
                            )
                            if attr_local == attr_name:
                                id_value = value
                                break

                        if id_value is not None:
                            if scope == "global":
                                # グローバル一意性をチェック
                                if id_value in global_ids:
                                    prev_file, prev_line, prev_tag = global_ids[
                                        id_value
                                    ]
                                    errors.append(
                                        f"  {xml_file.relative_to(self.unpacked_dir)}: "
                                        f"Line {elem.sourceline}: Global ID '{id_value}' in <{tag}> "
                                        f"already used in {prev_file} at line {prev_line} in <{prev_tag}>"
                                    )
                                else:
                                    global_ids[id_value] = (
                                        xml_file.relative_to(self.unpacked_dir),
                                        elem.sourceline,
                                        tag,
                                    )
                            elif scope == "file":
                                # ファイル内一意性をチェック
                                key = (tag, attr_name)
                                if key not in file_ids:
                                    file_ids[key] = {}

                                if id_value in file_ids[key]:
                                    prev_line = file_ids[key][id_value]
                                    errors.append(
                                        f"  {xml_file.relative_to(self.unpacked_dir)}: "
                                        f"Line {elem.sourceline}: Duplicate {attr_name}='{id_value}' in <{tag}> "
                                        f"(first occurrence at line {prev_line})"
                                    )
                                else:
                                    file_ids[key][id_value] = elem.sourceline

            except (lxml.etree.XMLSyntaxError, Exception) as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: エラー: {e}"
                )

        if errors:
            print(f"FAILED - ID一意性の違反が{len(errors)}件見つかりました:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("PASSED - 必須のIDはすべて一意です")
            return True

    def validate_file_references(self):
        """すべての .rels が正しくファイル参照していること、かつ全ファイルが参照されていることを検証します。"""
        errors = []

        # .relsファイルを列挙
        rels_files = list(self.unpacked_dir.rglob("*.rels"))

        if not rels_files:
            if self.verbose:
                print("PASSED - .rels ファイルが見つかりませんでした")
            return True

        # アンパック済みディレクトリ内の全ファイルを列挙（参照ファイルは除外）
        all_files = []
        for file_path in self.unpacked_dir.rglob("*"):
            if (
                file_path.is_file()
                and file_path.name != "[Content_Types].xml"
                and not file_path.name.endswith(".rels")
            ):  # .rels から参照されないファイル群
                all_files.append(file_path.resolve())

        # いずれかの.relsから参照されているファイル集合を追跡
        all_referenced_files = set()

        if self.verbose:
            print(
                f".rels ファイル: {len(rels_files)}件 / 参照対象ファイル: {len(all_files)}件"
            )

        # 各.relsファイルをチェック
        for rels_file in rels_files:
            try:
                # relationshipsファイルをパース
                rels_root = lxml.etree.parse(str(rels_file)).getroot()

                # この.relsファイルの配置ディレクトリを取得
                rels_dir = rels_file.parent

                # すべてのrelationshipとtargetを抽出
                referenced_files = set()
                broken_refs = []

                for rel in rels_root.findall(
                    ".//ns:Relationship",
                    namespaces={"ns": self.PACKAGE_RELATIONSHIPS_NAMESPACE},
                ):
                    target = rel.get("Target")
                    if target and not target.startswith(
                        ("http", "mailto:")
                    ):  # 外部URLはスキップ
                        # .relsの位置からの相対パスとしてtargetを解決
                        if rels_file.name == ".rels":
                            # ルート.rels - targetはunpacked_dir基準
                            target_path = self.unpacked_dir / target
                        else:
                            # その他の.rels - targetは「親の親」基準
                            # 例: word/_rels/document.xml.rels -> word/ 基準
                            base_dir = rels_dir.parent
                            target_path = base_dir / target

                        # パスを正規化して存在確認
                        try:
                            target_path = target_path.resolve()
                            if target_path.exists() and target_path.is_file():
                                referenced_files.add(target_path)
                                all_referenced_files.add(target_path)
                            else:
                                broken_refs.append((target, rel.sourceline))
                        except (OSError, ValueError):
                            broken_refs.append((target, rel.sourceline))

                # 壊れた参照をレポート
                if broken_refs:
                    rel_path = rels_file.relative_to(self.unpacked_dir)
                    for broken_ref, line_num in broken_refs:
                        errors.append(
                            f"  {rel_path}: {line_num}行目: 参照切れ: {broken_ref}"
                        )

            except Exception as e:
                rel_path = rels_file.relative_to(self.unpacked_dir)
                errors.append(f"  {rel_path} のパースエラー: {e}")

        # 未参照ファイルをチェック（存在するがどこからも参照されていない）
        unreferenced_files = set(all_files) - all_referenced_files

        if unreferenced_files:
            for unref_file in sorted(unreferenced_files):
                unref_rel_path = unref_file.relative_to(self.unpacked_dir)
                errors.append(f"  未参照ファイル: {unref_rel_path}")

        if errors:
            print(f"FAILED - relationship検証エラーが{len(errors)}件見つかりました:")
            for error in errors:
                print(error)
            print(
                "CRITICAL: これらのエラーにより、文書が破損しているように見える可能性があります。"
                + "参照切れは必ず修正し、"
                + "未参照ファイルは参照を追加するか削除してください。"
            )
            return False
        else:
            if self.verbose:
                print(
                    "PASSED - すべての参照は有効で、必要なファイル参照も適切です"
                )
            return True

    def validate_all_relationship_ids(self):
        """XML内の r:id が対応する .rels に存在するIDを参照していることを検証します（必要ならtypeも検証）。"""
        import lxml.etree

        errors = []

        # r:id参照を含む可能性がある各XMLファイルを処理
        for xml_file in self.xml_files:
            # .relsファイル自体は除外
            if xml_file.suffix == ".rels":
                continue

            # 対応する.relsファイルを決定
            # dir/file.xml -> dir/_rels/file.xml.rels
            rels_dir = xml_file.parent / "_rels"
            rels_file = rels_dir / f"{xml_file.name}.rels"

            # 対応する.relsが無ければスキップ（問題ない場合がある）
            if not rels_file.exists():
                continue

            try:
                # .relsをパースして、有効なrelationship IDとtypeを取得
                rels_root = lxml.etree.parse(str(rels_file)).getroot()
                rid_to_type = {}

                for rel in rels_root.findall(
                    f".//{{{self.PACKAGE_RELATIONSHIPS_NAMESPACE}}}Relationship"
                ):
                    rid = rel.get("Id")
                    rel_type = rel.get("Type", "")
                    if rid:
                        # rId重複をチェック
                        if rid in rid_to_type:
                            rels_rel_path = rels_file.relative_to(self.unpacked_dir)
                            errors.append(
                                f"  {rels_rel_path}: Line {rel.sourceline}: "
                                f"relationship ID '{rid}' が重複しています（IDは一意である必要があります）"
                            )
                        # フルURLからtype名部分だけ抽出
                        type_name = (
                            rel_type.split("/")[-1] if "/" in rel_type else rel_type
                        )
                        rid_to_type[rid] = type_name

                # XMLをパースしてr:id参照を抽出
                xml_root = lxml.etree.parse(str(xml_file)).getroot()

                # r:id属性を持つ要素を列挙
                for elem in xml_root.iter():
                    # r:id属性（relationship ID）を取得
                    rid_attr = elem.get(f"{{{self.OFFICE_RELATIONSHIPS_NAMESPACE}}}id")
                    if rid_attr:
                        xml_rel_path = xml_file.relative_to(self.unpacked_dir)
                        elem_name = (
                            elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                        )

                        # IDが存在するか確認
                        if rid_attr not in rid_to_type:
                            errors.append(
                                f"  {xml_rel_path}: Line {elem.sourceline}: "
                                f"<{elem_name}> references non-existent relationship '{rid_attr}' "
                                f"(有効ID: {', '.join(sorted(rid_to_type.keys())[:5])}{'...' if len(rid_to_type) > 5 else ''})"
                            )
                        # この要素にtype期待値があるか確認
                        elif self.ELEMENT_RELATIONSHIP_TYPES:
                            expected_type = self._get_expected_relationship_type(
                                elem_name
                            )
                            if expected_type:
                                actual_type = rid_to_type[rid_attr]
                                # 実typeが期待typeと一致/包含するか確認
                                if expected_type not in actual_type.lower():
                                    errors.append(
                                        f"  {xml_rel_path}: Line {elem.sourceline}: "
                                        f"<{elem_name}> references '{rid_attr}' which points to '{actual_type}' "
                                        f"しかし期待されるrelationshipは '{expected_type}' です"
                                    )

            except Exception as e:
                xml_rel_path = xml_file.relative_to(self.unpacked_dir)
                errors.append(f"  {xml_rel_path} の処理エラー: {e}")

        if errors:
            print(f"FAILED - relationship ID参照エラーが{len(errors)}件見つかりました:")
            for error in errors:
                print(error)
            print("\nこれらのID不整合により、文書が破損しているように見える可能性があります。")
            return False
        else:
            if self.verbose:
                print("PASSED - すべてのrelationship ID参照は有効です")
            return True

    def _get_expected_relationship_type(self, element_name):
        """要素に対して期待されるrelationship typeを取得します。

        まず明示マッピングを参照し、無ければパターンから推測します。
        """
        # 要素名を小文字に正規化
        elem_lower = element_name.lower()

        # 明示的マッピングを優先
        if elem_lower in self.ELEMENT_RELATIONSHIP_TYPES:
            return self.ELEMENT_RELATIONSHIP_TYPES[elem_lower]

        # よくあるパターンを推測
        # パターン1: "Id"で終わる要素は、プレフィックス種別のrelationshipを期待することが多い
        if elem_lower.endswith("id") and len(elem_lower) > 2:
            # 例: "sldId" -> "sld", "sldMasterId" -> "sldMaster"
            prefix = elem_lower[:-2]  # "id" を除去
            # "sldMasterId"のような複合か確認
            if prefix.endswith("master"):
                return prefix.lower()
            elif prefix.endswith("layout"):
                return prefix.lower()
            else:
                # 単純ケース: "sldId" -> "slide"
                # よくある変換
                if prefix == "sld":
                    return "slide"
                return prefix.lower()

        # パターン2: "Reference"で終わる要素は、プレフィックス種別のrelationshipを期待することが多い
        if elem_lower.endswith("reference") and len(elem_lower) > 9:
            prefix = elem_lower[:-9]  # "reference" を除去
            return prefix.lower()

        return None

    def validate_content_types(self):
        """[Content_Types].xmlに、必要なコンテンツが正しく宣言されていることを検証します。"""
        errors = []

        # [Content_Types].xml を探す
        content_types_file = self.unpacked_dir / "[Content_Types].xml"
        if not content_types_file.exists():
            print("FAILED - [Content_Types].xml file not found")
            return False

        try:
            # パースし、宣言済みPartと拡張子を収集
            root = lxml.etree.parse(str(content_types_file)).getroot()
            declared_parts = set()
            declared_extensions = set()

            # Override宣言（個別ファイル）を取得
            for override in root.findall(
                f".//{{{self.CONTENT_TYPES_NAMESPACE}}}Override"
            ):
                part_name = override.get("PartName")
                if part_name is not None:
                    declared_parts.add(part_name.lstrip("/"))

            # Default宣言（拡張子単位）を取得
            for default in root.findall(
                f".//{{{self.CONTENT_TYPES_NAMESPACE}}}Default"
            ):
                extension = default.get("Extension")
                if extension is not None:
                    declared_extensions.add(extension.lower())

            # content type宣言が必要なルート要素
            declarable_roots = {
                "sld",
                "sldLayout",
                "sldMaster",
                "presentation",  # PowerPoint
                "document",  # Word
                "workbook",
                "worksheet",  # Excel
                "theme",  # Common
            }

            # 宣言されているべき一般的なメディア拡張子
            media_extensions = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "bmp": "image/bmp",
                "tiff": "image/tiff",
                "wmf": "image/x-wmf",
                "emf": "image/x-emf",
            }

            # アンパック済みディレクトリ内の全ファイルを列挙
            all_files = list(self.unpacked_dir.rglob("*"))
            all_files = [f for f in all_files if f.is_file()]

            # すべてのXMLファイルについてOverride宣言をチェック
            for xml_file in self.xml_files:
                path_str = str(xml_file.relative_to(self.unpacked_dir)).replace(
                    "\\", "/"
                )

                # 非コンテンツファイルは除外
                if any(
                    skip in path_str
                    for skip in [".rels", "[Content_Types]", "docProps/", "_rels/"]
                ):
                    continue

                try:
                    root_tag = lxml.etree.parse(str(xml_file)).getroot().tag
                    root_name = root_tag.split("}")[-1] if "}" in root_tag else root_tag

                    if root_name in declarable_roots and path_str not in declared_parts:
                        errors.append(
                            f"  {path_str}: ルート<{root_name}>を持つファイルが [Content_Types].xml に宣言されていません"
                        )

                except Exception:
                    continue  # パース不能なファイルはスキップ

            # XML以外のファイルについてDefault拡張子宣言をチェック
            for file_path in all_files:
                # XML/メタデータは除外（上でチェック済み）
                if file_path.suffix.lower() in {".xml", ".rels"}:
                    continue
                if file_path.name == "[Content_Types].xml":
                    continue
                if "_rels" in file_path.parts or "docProps" in file_path.parts:
                    continue

                extension = file_path.suffix.lstrip(".").lower()
                if extension and extension not in declared_extensions:
                    # 宣言が必要な既知のメディア拡張子か確認
                    if extension in media_extensions:
                        relative_path = file_path.relative_to(self.unpacked_dir)
                        errors.append(
                            f"  {relative_path}: 拡張子 '{extension}' のファイルが [Content_Types].xml に宣言されていません"
                            f"（追加候補: <Default Extension=\"{extension}\" ContentType=\"{media_extensions[extension]}\"/>）"
                        )

        except Exception as e:
            errors.append(f"  [Content_Types].xml のパースエラー: {e}")

        if errors:
            print(f"FAILED - content type宣言のエラーが{len(errors)}件あります:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print(
                    "PASSED - すべてのコンテンツは [Content_Types].xml に適切に宣言されています"
                )
            return True

    def validate_file_against_xsd(self, xml_file, verbose=False):
        """単一XMLファイルをXSDスキーマで検証し、元ファイルと比較します。

        Args:
            xml_file: 検証するXMLファイルのパス
            verbose: 詳細出力を有効化

        Returns:
            tuple: (is_valid, new_errors_set)。is_validは True/False/None（スキップ）です
        """
        # symlink等を考慮して両パスをresolve
        xml_file = Path(xml_file).resolve()
        unpacked_dir = self.unpacked_dir.resolve()

        # 現在ファイルを検証
        is_valid, current_errors = self._validate_single_file_xsd(
            xml_file, unpacked_dir
        )

        if is_valid is None:
            return None, set()  # スキップ
        elif is_valid:
            return True, set()  # 合格（エラーなし）

        # 元ファイル側のエラーを取得
        original_errors = self._get_original_file_errors(xml_file)

        # 元と比較（ここでは両者ともsetが保証される）
        assert current_errors is not None
        new_errors = current_errors - original_errors

        if new_errors:
            if verbose:
                relative_path = xml_file.relative_to(unpacked_dir)
                print(f"FAILED - {relative_path}: {len(new_errors)} new error(s)")
                for error in list(new_errors)[:3]:
                    truncated = error[:250] + "..." if len(error) > 250 else error
                    print(f"  - {truncated}")
            return False, new_errors
        else:
            # すべて元から存在するエラー
            if verbose:
                print(
                    f"PASSED - 新規エラーはありません（元は{len(current_errors)}件のエラーあり）"
                )
            return True, set()

    def validate_against_xsd(self):
        """XSDスキーマでXMLを検証し、元ファイルと比較して新規エラーのみ表示します。"""
        new_errors = []
        original_error_count = 0
        valid_count = 0
        skipped_count = 0

        for xml_file in self.xml_files:
            relative_path = str(xml_file.relative_to(self.unpacked_dir))
            is_valid, new_file_errors = self.validate_file_against_xsd(
                xml_file, verbose=False
            )

            if is_valid is None:
                skipped_count += 1
                continue
            elif is_valid and not new_file_errors:
                valid_count += 1
                continue
            elif is_valid:
            # エラーはあるが元から存在するもののみ
                original_error_count += 1
                valid_count += 1
                continue

            # 新規エラーあり
            new_errors.append(f"  {relative_path}: {len(new_file_errors)} new error(s)")
            for error in list(new_file_errors)[:3]:  # 先頭3件だけ表示
                new_errors.append(
                    f"    - {error[:250]}..." if len(error) > 250 else f"    - {error}"
                )

        # サマリを表示
        if self.verbose:
            print(f"検証対象: {len(self.xml_files)}ファイル")
            print(f"  - 合格: {valid_count}")
            print(f"  - スキップ（スキーマなし）: {skipped_count}")
            if original_error_count:
                print(f"  - 元からのエラーあり（無視）: {original_error_count}")
            print(
                f"  - 新規エラーあり: {len(new_errors) > 0 and len([e for e in new_errors if not e.startswith('    ')]) or 0}"
            )

        if new_errors:
            print("\nFAILED - 新規の検証エラーが見つかりました:")
            for error in new_errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("\nPASSED - 新規のXSD検証エラーはありません")
            return True

    def _get_schema_path(self, xml_file):
        """XMLファイルに対応するスキーマパスを決定します。"""
        # ファイル名の完全一致をチェック
        if xml_file.name in self.SCHEMA_MAPPINGS:
            return self.schemas_dir / self.SCHEMA_MAPPINGS[xml_file.name]

        # .rels ファイルをチェック
        if xml_file.suffix == ".rels":
            return self.schemas_dir / self.SCHEMA_MAPPINGS[".rels"]

        # chartファイルをチェック
        if "charts/" in str(xml_file) and xml_file.name.startswith("chart"):
            return self.schemas_dir / self.SCHEMA_MAPPINGS["chart"]

        # themeファイルをチェック
        if "theme/" in str(xml_file) and xml_file.name.startswith("theme"):
            return self.schemas_dir / self.SCHEMA_MAPPINGS["theme"]

        # main contentフォルダ配下なら、フォルダ名に応じたスキーマを使う
        if xml_file.parent.name in self.MAIN_CONTENT_FOLDERS:
            return self.schemas_dir / self.SCHEMA_MAPPINGS[xml_file.parent.name]

        return None

    def _clean_ignorable_namespaces(self, xml_doc):
        """許可された名前空間以外の属性/要素を除去します。"""
        # クリーンなコピーを作成
        xml_string = lxml.etree.tostring(xml_doc, encoding="unicode")
        xml_copy = lxml.etree.fromstring(xml_string)

        # 許可されていない名前空間の属性を除去
        for elem in xml_copy.iter():
            attrs_to_remove = []

            for attr in elem.attrib:
                # 許可外の名前空間の属性か確認
                if "{" in attr:
                    ns = attr.split("}")[0][1:]
                    if ns not in self.OOXML_NAMESPACES:
                        attrs_to_remove.append(attr)

            # 収集した属性を除去
            for attr in attrs_to_remove:
                del elem.attrib[attr]

        # 許可されていない名前空間の要素を除去
        self._remove_ignorable_elements(xml_copy)

        return lxml.etree.ElementTree(xml_copy)

    def _remove_ignorable_elements(self, root):
        """許可された名前空間以外の要素を再帰的に除去します。"""
        elements_to_remove = []

        # 除去対象の要素を探す
        for elem in list(root):
            # 要素ノード以外（コメント/処理命令など）はスキップ
            if not hasattr(elem, "tag") or callable(elem.tag):
                continue

            tag_str = str(elem.tag)
            if tag_str.startswith("{"):
                ns = tag_str.split("}")[0][1:]
                if ns not in self.OOXML_NAMESPACES:
                    elements_to_remove.append(elem)
                    continue

            # 子要素を再帰的にクリーンアップ
            self._remove_ignorable_elements(elem)

        # 収集した要素を除去
        for elem in elements_to_remove:
            root.remove(elem)

    def _preprocess_for_mc_ignorable(self, xml_doc):
        """mc:Ignorable 属性を適切に扱うための前処理を行います。"""
        # 検証前に mc:Ignorable 属性を除去
        root = xml_doc.getroot()

        # ルートから mc:Ignorable 属性を除去
        if f"{{{self.MC_NAMESPACE}}}Ignorable" in root.attrib:
            del root.attrib[f"{{{self.MC_NAMESPACE}}}Ignorable"]

        return xml_doc

    def _validate_single_file_xsd(self, xml_file, base_path):
        """単一XMLファイルをXSDスキーマで検証します（戻り値: (is_valid, errors_set)）。"""
        schema_path = self._get_schema_path(xml_file)
        if not schema_path:
            return None, None  # 対応スキーマがないためスキップ

        try:
            # スキーマをロード
            with open(schema_path, "rb") as xsd_file:
                parser = lxml.etree.XMLParser()
                xsd_doc = lxml.etree.parse(
                    xsd_file, parser=parser, base_url=str(schema_path)
                )
                schema = lxml.etree.XMLSchema(xsd_doc)

            # XMLをロードして前処理
            with open(xml_file, "r") as f:
                xml_doc = lxml.etree.parse(f)

            xml_doc, _ = self._remove_template_tags_from_text_nodes(xml_doc)
            xml_doc = self._preprocess_for_mc_ignorable(xml_doc)

            # 必要に応じて ignorable namespaces をクリーンアップ
            relative_path = xml_file.relative_to(base_path)
            if (
                relative_path.parts
                and relative_path.parts[0] in self.MAIN_CONTENT_FOLDERS
            ):
                xml_doc = self._clean_ignorable_namespaces(xml_doc)

            # 検証
            if schema.validate(xml_doc):
                return True, set()
            else:
                errors = set()
                for error in schema.error_log:
                    # 正規化したエラーメッセージを保存（比較のため行番号は含めない）
                    errors.add(error.message)
                return False, errors

        except Exception as e:
            return False, {str(e)}

    def _get_original_file_errors(self, xml_file):
        """元ドキュメント内の対応ファイルから、XSD検証エラーを取得します。

        引数:
            xml_file: unpacked_dir内の対象XMLファイルパス

        戻り値:
            元ファイルのエラーメッセージ集合（set）
        """
        import tempfile
        import zipfile

        # symlink等を考慮して両パスをresolve（例: macOSの /var と /private/var）
        xml_file = Path(xml_file).resolve()
        unpacked_dir = self.unpacked_dir.resolve()
        relative_path = xml_file.relative_to(unpacked_dir)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # 元ファイルを展開
            with zipfile.ZipFile(self.original_file, "r") as zip_ref:
                zip_ref.extractall(temp_path)

            # 元側の対応ファイルを特定
            original_xml_file = temp_path / relative_path

            if not original_xml_file.exists():
                # 元に存在しないファイルなので、元由来のエラーはなし
                return set()

            # 元側の該当ファイルを検証
            is_valid, errors = self._validate_single_file_xsd(
                original_xml_file, temp_path
            )
            return errors if errors else set()

    def _remove_template_tags_from_text_nodes(self, xml_doc):
        """XMLテキストノードからテンプレタグを除去し、警告を収集します。

        テンプレタグは `{{ ... }}` 形式で、内容差し替え用のプレースホルダです。
        XML構造は維持したまま、XSD検証の前にテキストから除去します。

        戻り値:
            tuple: (クリーンアップ済みxml_doc, 警告リスト)
        """
        warnings = []
        template_pattern = re.compile(r"\{\{[^}]*\}\}")

        # 元ドキュメントを破壊しないようコピーを作る
        xml_string = lxml.etree.tostring(xml_doc, encoding="unicode")
        xml_copy = lxml.etree.fromstring(xml_string)

        def process_text_content(text, content_type):
            if not text:
                return text
            matches = list(template_pattern.finditer(text))
            if matches:
                for match in matches:
                    warnings.append(
                        f"{content_type} にテンプレタグが見つかりました: {match.group()}"
                    )
                return template_pattern.sub("", text)
            return text

        # ドキュメント内のテキストノードを処理
        for elem in xml_copy.iter():
            # Skip processing if this is a w:t element
            if not hasattr(elem, "tag") or callable(elem.tag):
                continue
            tag_str = str(elem.tag)
            if tag_str.endswith("}t") or tag_str == "t":
                continue

            elem.text = process_text_content(elem.text, "本文")
            elem.tail = process_text_content(elem.tail, "末尾テキスト")

        return lxml.etree.ElementTree(xml_copy), warnings


if __name__ == "__main__":
    raise RuntimeError("このモジュールは直接実行しないでください。")
