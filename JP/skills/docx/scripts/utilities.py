#!/usr/bin/env python3
"""
OOXMLドキュメント編集用ユーティリティです。

本モジュールは、XMLファイルを操作するための`XMLEditor`を提供します。
行番号ベースのノード検索やDOM操作をサポートし、パース時に各要素へ元の行/列位置を自動で付与します。

使用例:
    editor = XMLEditor("document.xml")

    # 行番号または範囲でノードを検索
    elem = editor.get_node(tag="w:r", line_number=519)
    elem = editor.get_node(tag="w:p", line_number=range(100, 200))

    # テキスト内容でノードを検索
    elem = editor.get_node(tag="w:p", contains="specific text")

    # 属性でノードを検索
    elem = editor.get_node(tag="w:r", attrs={"w:id": "target"})

    # フィルタを組み合わせる
    elem = editor.get_node(tag="w:p", line_number=range(1, 50), contains="text")

    # 置換・挿入・加工
    new_elem = editor.replace_node(elem, "<w:r><w:t>new text</w:t></w:r>")
    editor.insert_after(new_elem, "<w:r><w:t>more</w:t></w:r>")

    # 変更を保存
    editor.save()
"""

import html
from pathlib import Path
from typing import Optional, Union

import defusedxml.minidom
import defusedxml.sax


class XMLEditor:
    """
    行番号ベースのノード検索に対応した、OOXMLのXMLファイル操作エディタです。

    XMLをパースし、各要素の元の行/列位置を追跡します。
    これにより、元ファイル上の行番号でノードを見つけられるため、Readツールの出力と突き合わせる用途に便利です。

    Attributes:
        xml_path: 編集対象XMLファイルのパス
        encoding: 検出したエンコーディング（'ascii' または 'utf-8'）
        dom: 要素にparse_position属性が付いたパース済みDOM
    """

    def __init__(self, xml_path):
        """
        XMLファイルパスを受け取り、行番号追跡付きでパースして初期化します。

        引数:
            xml_path: 編集するXMLファイルのパス（strまたはPath）

        例外:
            ValueError: XMLファイルが存在しない場合
        """
        self.xml_path = Path(xml_path)
        if not self.xml_path.exists():
            raise ValueError(f"XML file not found: {xml_path}")

        with open(self.xml_path, "rb") as f:
            header = f.read(200).decode("utf-8", errors="ignore")
        self.encoding = "ascii" if 'encoding="ascii"' in header else "utf-8"

        parser = _create_line_tracking_parser()
        self.dom = defusedxml.minidom.parse(str(self.xml_path), parser)

    def get_node(
        self,
        tag: str,
        attrs: Optional[dict[str, str]] = None,
        line_number: Optional[Union[int, range]] = None,
        contains: Optional[str] = None,
    ):
        """
        タグ名と条件でDOM要素を取得します。

        元ファイル上の行番号や、属性値の一致などで要素を検索します。
        一致は「ちょうど1件」である必要があります。

        引数:
            tag: XMLタグ名（例: "w:del", "w:ins", "w:r"）
            attrs: 一致させる属性辞書（例: {"w:id": "1"}）
            line_number: 元XMLの行番号(int)または行範囲(range)（1始まり）
            contains: 要素内のテキストノードに含まれるべき文字列。
                      エンティティ表記（&#8220;）とUnicode文字（\u201c）の双方に対応します。

        戻り値:
            defusedxml.minidom.Element: 一致したDOM要素

        例外:
            ValueError: 見つからない、または複数一致した場合

        例:
            elem = editor.get_node(tag="w:r", line_number=519)
            elem = editor.get_node(tag="w:r", line_number=range(100, 200))
            elem = editor.get_node(tag="w:del", attrs={"w:id": "1"})
            elem = editor.get_node(tag="w:p", attrs={"w14:paraId": "12345678"})
            elem = editor.get_node(tag="w:commentRangeStart", attrs={"w:id": "0"})
            elem = editor.get_node(tag="w:p", contains="specific text")
            elem = editor.get_node(tag="w:t", contains="&#8220;Agreement")  # エンティティ表記
            elem = editor.get_node(tag="w:t", contains="\u201cAgreement")   # Unicode文字
        """
        matches = []
        for elem in self.dom.getElementsByTagName(tag):
            # line_numberフィルタ
            if line_number is not None:
                parse_pos = getattr(elem, "parse_position", (None,))
                elem_line = parse_pos[0]

                # 単一行番号と範囲の両方を扱う
                if isinstance(line_number, range):
                    if elem_line not in line_number:
                        continue
                else:
                    if elem_line != line_number:
                        continue

            # attrsフィルタ
            if attrs is not None:
                if not all(
                    elem.getAttribute(attr_name) == attr_value
                    for attr_name, attr_value in attrs.items()
                ):
                    continue

            # containsフィルタ
            if contains is not None:
                elem_text = self._get_element_text(elem)
                # 検索文字列を正規化: HTMLエンティティをUnicodeへ変換
                # これにより "&#8220;Rowan" と "“Rowan" の両方で検索できます
                normalized_contains = html.unescape(contains)
                if normalized_contains not in elem_text:
                    continue

            # すべてのフィルタを満たしたら一致
            matches.append(elem)

        if not matches:
            # 分かりやすいエラーメッセージを組み立てる
            filters = []
            if line_number is not None:
                line_str = (
                    f"lines {line_number.start}-{line_number.stop - 1}"
                    if isinstance(line_number, range)
                    else f"line {line_number}"
                )
                filters.append(f"at {line_str}")
            if attrs is not None:
                filters.append(f"with attributes {attrs}")
            if contains is not None:
                filters.append(f"containing '{contains}'")

            filter_desc = " ".join(filters) if filters else ""
            base_msg = f"Node not found: <{tag}> {filter_desc}".strip()

            # 使ったフィルタに応じてヒントを追加
            if contains:
                hint = "テキストが複数要素に分割されているか、表現が異なる可能性があります。"
            elif line_number:
                hint = "ドキュメントが変更されている場合、行番号が変わっている可能性があります。"
            elif attrs:
                hint = "属性値が正しいか確認してください。"
            else:
                hint = "フィルタ（attrs/line_number/contains）を追加してみてください。"

            raise ValueError(f"{base_msg}. {hint}")
        if len(matches) > 1:
            raise ValueError(
                f"Multiple nodes found: <{tag}>. "
                f"絞り込みのためにフィルタ（attrs/line_number/contains）を追加してください。"
            )
        return matches[0]

    def _get_element_text(self, elem):
        """
        要素からテキスト内容を再帰的に抽出します。

        空白のみ（スペース/タブ/改行）のテキストノードはスキップします。
        これらは通常、ドキュメント内容ではなくXML整形を表します。

        引数:
            elem: テキスト抽出対象のdefusedxml.minidom.Element

        戻り値:
            str: 要素内の非空白テキストを連結した文字列
        """
        text_parts = []
        for node in elem.childNodes:
            if node.nodeType == node.TEXT_NODE:
                # 空白のみのテキストノード（XML整形）をスキップ
                if node.data.strip():
                    text_parts.append(node.data)
            elif node.nodeType == node.ELEMENT_NODE:
                text_parts.append(self._get_element_text(node))
        return "".join(text_parts)

    def replace_node(self, elem, new_content):
        """
        DOM要素を新しいXML内容で置換します。

        引数:
            elem: 置換対象のdefusedxml.minidom.Element
            new_content: 置換後に挿入するXML文字列

        戻り値:
            List[defusedxml.minidom.Node]: 挿入されたノード一覧

        例:
            new_nodes = editor.replace_node(old_elem, "<w:r><w:t>text</w:t></w:r>")
        """
        parent = elem.parentNode
        nodes = self._parse_fragment(new_content)
        for node in nodes:
            parent.insertBefore(node, elem)
        parent.removeChild(elem)
        return nodes

    def insert_after(self, elem, xml_content):
        """
        DOM要素の後ろにXML内容を挿入します。

        引数:
            elem: 挿入基準となるdefusedxml.minidom.Element
            xml_content: 挿入するXML文字列

        戻り値:
            List[defusedxml.minidom.Node]: 挿入されたノード一覧

        例:
            new_nodes = editor.insert_after(elem, "<w:r><w:t>text</w:t></w:r>")
        """
        parent = elem.parentNode
        next_sibling = elem.nextSibling
        nodes = self._parse_fragment(xml_content)
        for node in nodes:
            if next_sibling:
                parent.insertBefore(node, next_sibling)
            else:
                parent.appendChild(node)
        return nodes

    def insert_before(self, elem, xml_content):
        """
        DOM要素の前にXML内容を挿入します。

        引数:
            elem: 挿入基準となるdefusedxml.minidom.Element
            xml_content: 挿入するXML文字列

        戻り値:
            List[defusedxml.minidom.Node]: 挿入されたノード一覧

        例:
            new_nodes = editor.insert_before(elem, "<w:r><w:t>text</w:t></w:r>")
        """
        parent = elem.parentNode
        nodes = self._parse_fragment(xml_content)
        for node in nodes:
            parent.insertBefore(node, elem)
        return nodes

    def append_to(self, elem, xml_content):
        """
        Append XML content as a child of a DOM element.

        引数:
            elem: defusedxml.minidom.Element to append to
            xml_content: String containing XML to append

        戻り値:
            List[defusedxml.minidom.Node]: All inserted nodes

        例:
            new_nodes = editor.append_to(elem, "<w:r><w:t>text</w:t></w:r>")
        """
        nodes = self._parse_fragment(xml_content)
        for node in nodes:
            elem.appendChild(node)
        return nodes

    def get_next_rid(self):
        """relationshipsファイルで次に利用可能なrIdを取得します。"""
        max_id = 0
        for rel_elem in self.dom.getElementsByTagName("Relationship"):
            rel_id = rel_elem.getAttribute("Id")
            if rel_id.startswith("rId"):
                try:
                    max_id = max(max_id, int(rel_id[3:]))
                except ValueError:
                    pass
        return f"rId{max_id + 1}"

    def save(self):
        """
        Save the edited XML back to the file.

        Serializes the DOM tree and writes it back to the original file path,
        preserving the original encoding (ascii or utf-8).
        """
        content = self.dom.toxml(encoding=self.encoding)
        self.xml_path.write_bytes(content)

    def _parse_fragment(self, xml_content):
        """
        Parse XML fragment and return list of imported nodes.

        引数:
            xml_content: String containing XML fragment

        戻り値:
            List of defusedxml.minidom.Node objects imported into this document

        例外:
            AssertionError: If fragment contains no element nodes
        """
        # ルート要素から名前空間宣言を抽出
        root_elem = self.dom.documentElement
        namespaces = []
        if root_elem and root_elem.attributes:
            for i in range(root_elem.attributes.length):
                attr = root_elem.attributes.item(i)
                if attr.name.startswith("xmlns"):  # type: ignore
                    namespaces.append(f'{attr.name}="{attr.value}"')  # type: ignore

        ns_decl = " ".join(namespaces)
        wrapper = f"<root {ns_decl}>{xml_content}</root>"
        fragment_doc = defusedxml.minidom.parseString(wrapper)
        nodes = [
            self.dom.importNode(child, deep=True)
            for child in fragment_doc.documentElement.childNodes  # type: ignore
        ]
        elements = [n for n in nodes if n.nodeType == n.ELEMENT_NODE]
        assert elements, "Fragment must contain at least one element"
        return nodes


def _create_line_tracking_parser():
    """
    Create a SAX parser that tracks line and column numbers for each element.

    Monkey patches the SAX content handler to store the current line and column
    position from the underlying expat parser onto each element as a parse_position
    attribute (line, column) tuple.

    戻り値:
        defusedxml.sax.xmlreader.XMLReader: Configured SAX parser
    """

    def set_content_handler(dom_handler):
        def startElementNS(name, tagName, attrs):
            orig_start_cb(name, tagName, attrs)
            cur_elem = dom_handler.elementStack[-1]
            cur_elem.parse_position = (
                parser._parser.CurrentLineNumber,  # type: ignore
                parser._parser.CurrentColumnNumber,  # type: ignore
            )

        orig_start_cb = dom_handler.startElementNS
        dom_handler.startElementNS = startElementNS
        orig_set_content_handler(dom_handler)

    parser = defusedxml.sax.make_parser()
    orig_set_content_handler = parser.setContentHandler
    parser.setContentHandler = set_content_handler  # type: ignore
    return parser
