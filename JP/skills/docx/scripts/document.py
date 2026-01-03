#!/usr/bin/env python3
"""
Word文書を扱うためのライブラリ（コメント、追跡変更、編集）です。

注: このファイルは大きいため、コメント/docstringの一部は原文（英語）を残しています。処理ロジックは変更していません。

使い方:
    from skills.docx.scripts.document import Document

    # 初期化
    doc = Document('workspace/unpacked')
    doc = Document('workspace/unpacked', author="John Doe", initials="JD")

    # ノード検索
    node = doc[\"word/document.xml\"].get_node(tag=\"w:del\", attrs={\"w:id\": \"1\"})
    node = doc[\"word/document.xml\"].get_node(tag=\"w:p\", line_number=10)

    # コメント追加
    doc.add_comment(start=node, end=node, text=\"Comment text\")
    doc.reply_to_comment(parent_comment_id=0, text=\"Reply text\")

    # 追跡変更の提案
    doc[\"word/document.xml\"].suggest_deletion(node)  # Delete content
    doc[\"word/document.xml\"].revert_insertion(ins_node)  # Reject insertion
    doc[\"word/document.xml\"].revert_deletion(del_node)  # Reject deletion

    # 保存
    doc.save()
"""

import html
import random
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from defusedxml import minidom
from ooxml.scripts.pack import pack_document
from ooxml.scripts.validation.docx import DOCXSchemaValidator
from ooxml.scripts.validation.redlining import RedliningValidator

from .utilities import XMLEditor

# テンプレートファイルのパス
TEMPLATE_DIR = Path(__file__).parent / "templates"


class DocxXMLEditor(XMLEditor):
    """新しい要素にRSID/author/date等を自動付与するXMLEditorです。

    新規コンテンツ挿入時、対応する要素に属性を自動追加します:
    - w:rsidR, w:rsidRDefault, w:rsidP（w:p / w:r 要素向け）
    - w:author と w:date（w:ins / w:del / w:comment 要素向け）
    - w:id（w:ins / w:del 要素向け）

    属性:
        dom (defusedxml.minidom.Document): 直接操作用のDOMドキュメント
    """

    def __init__(
        self, xml_path, rsid: str, author: str = "Claude", initials: str = "C"
    ):
        """必須のRSIDと、任意のauthorで初期化します。

        引数:
            xml_path: 編集対象のXMLファイルパス
            rsid: 新規要素へ自動付与するRSID
            author: 追跡変更/コメント用の著者名（既定: "Claude"）
            initials: 著者イニシャル（既定: "C"）
        """
        super().__init__(xml_path)
        self.rsid = rsid
        self.author = author
        self.initials = initials

    def _get_next_change_id(self):
        """追跡変更要素を走査して、次に利用可能な変更IDを取得します。"""
        max_id = -1
        for tag in ("w:ins", "w:del"):
            elements = self.dom.getElementsByTagName(tag)
            for elem in elements:
                change_id = elem.getAttribute("w:id")
                if change_id:
                    try:
                        max_id = max(max_id, int(change_id))
                    except ValueError:
                        pass
        return max_id + 1

    def _ensure_w16du_namespace(self):
        """ルート要素にw16du名前空間が宣言されていることを保証します。"""
        root = self.dom.documentElement
        if not root.hasAttribute("xmlns:w16du"):  # type: ignore
            root.setAttribute(  # type: ignore
                "xmlns:w16du",
                "http://schemas.microsoft.com/office/word/2023/wordml/word16du",
            )

    def _ensure_w16cex_namespace(self):
        """ルート要素にw16cex名前空間が宣言されていることを保証します。"""
        root = self.dom.documentElement
        if not root.hasAttribute("xmlns:w16cex"):  # type: ignore
            root.setAttribute(  # type: ignore
                "xmlns:w16cex",
                "http://schemas.microsoft.com/office/word/2018/wordml/cex",
            )

    def _ensure_w14_namespace(self):
        """ルート要素にw14名前空間が宣言されていることを保証します。"""
        root = self.dom.documentElement
        if not root.hasAttribute("xmlns:w14"):  # type: ignore
            root.setAttribute(  # type: ignore
                "xmlns:w14",
                "http://schemas.microsoft.com/office/word/2010/wordml",
            )

    def _inject_attributes_to_nodes(self, nodes):
        """必要に応じて、DOMノードへRSID/author/date属性を注入（付与）します。

        対応する要素に対して、必要な属性を自動付与します:
        - w:r: w:rsidR（w:del内の場合はw:rsidDel）
        - w:p: w:rsidR / w:rsidRDefault / w:rsidP / w14:paraId / w14:textId
        - w:t: 前後に空白がある場合は xml:space="preserve"
        - w:ins / w:del: w:id / w:author / w:date / w16du:dateUtc
        - w:comment: w:author / w:date / w:initials
        - w16cex:commentExtensible: w16cex:dateUtc

        引数:
            nodes: 処理対象のDOMノードリスト
        """
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        def is_inside_deletion(elem):
            """要素がw:del要素の内側にあるかを判定します。"""
            parent = elem.parentNode
            while parent:
                if parent.nodeType == parent.ELEMENT_NODE and parent.tagName == "w:del":
                    return True
                parent = parent.parentNode
            return False

        def add_rsid_to_p(elem):
            if not elem.hasAttribute("w:rsidR"):
                elem.setAttribute("w:rsidR", self.rsid)
            if not elem.hasAttribute("w:rsidRDefault"):
                elem.setAttribute("w:rsidRDefault", self.rsid)
            if not elem.hasAttribute("w:rsidP"):
                elem.setAttribute("w:rsidP", self.rsid)
            # w14:paraId と w14:textId が無ければ追加
            if not elem.hasAttribute("w14:paraId"):
                self._ensure_w14_namespace()
                elem.setAttribute("w14:paraId", _generate_hex_id())
            if not elem.hasAttribute("w14:textId"):
                self._ensure_w14_namespace()
                elem.setAttribute("w14:textId", _generate_hex_id())

        def add_rsid_to_r(elem):
            # <w:del> 内の <w:r> には w:rsidDel、それ以外は w:rsidR を使う
            if is_inside_deletion(elem):
                if not elem.hasAttribute("w:rsidDel"):
                    elem.setAttribute("w:rsidDel", self.rsid)
            else:
                if not elem.hasAttribute("w:rsidR"):
                    elem.setAttribute("w:rsidR", self.rsid)

        def add_tracked_change_attrs(elem):
            # w:id が無ければ自動採番
            if not elem.hasAttribute("w:id"):
                elem.setAttribute("w:id", str(self._get_next_change_id()))
            if not elem.hasAttribute("w:author"):
                elem.setAttribute("w:author", self.author)
            if not elem.hasAttribute("w:date"):
                elem.setAttribute("w:date", timestamp)
            # 追跡変更用に w16du:dateUtc を追加（UTCタイムスタンプ生成のため w:date と同値）
            if elem.tagName in ("w:ins", "w:del") and not elem.hasAttribute(
                "w16du:dateUtc"
            ):
                self._ensure_w16du_namespace()
                elem.setAttribute("w16du:dateUtc", timestamp)

        def add_comment_attrs(elem):
            if not elem.hasAttribute("w:author"):
                elem.setAttribute("w:author", self.author)
            if not elem.hasAttribute("w:date"):
                elem.setAttribute("w:date", timestamp)
            if not elem.hasAttribute("w:initials"):
                elem.setAttribute("w:initials", self.initials)

        def add_comment_extensible_date(elem):
            # comment extensible要素用に w16cex:dateUtc を追加
            if not elem.hasAttribute("w16cex:dateUtc"):
                self._ensure_w16cex_namespace()
                elem.setAttribute("w16cex:dateUtc", timestamp)

        def add_xml_space_to_t(elem):
            # 先頭/末尾に空白がある w:t には xml:space=\"preserve\" を付与
            if (
                elem.firstChild
                and elem.firstChild.nodeType == elem.firstChild.TEXT_NODE
            ):
                text = elem.firstChild.data
                if text and (text[0].isspace() or text[-1].isspace()):
                    if not elem.hasAttribute("xml:space"):
                        elem.setAttribute("xml:space", "preserve")

        for node in nodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue

            # ノード自身を処理
            if node.tagName == "w:p":
                add_rsid_to_p(node)
            elif node.tagName == "w:r":
                add_rsid_to_r(node)
            elif node.tagName == "w:t":
                add_xml_space_to_t(node)
            elif node.tagName in ("w:ins", "w:del"):
                add_tracked_change_attrs(node)
            elif node.tagName == "w:comment":
                add_comment_attrs(node)
            elif node.tagName == "w16cex:commentExtensible":
                add_comment_extensible_date(node)

            # 子孫を処理（getElementsByTagNameは要素自身を返さない）
            for elem in node.getElementsByTagName("w:p"):
                add_rsid_to_p(elem)
            for elem in node.getElementsByTagName("w:r"):
                add_rsid_to_r(elem)
            for elem in node.getElementsByTagName("w:t"):
                add_xml_space_to_t(elem)
            for tag in ("w:ins", "w:del"):
                for elem in node.getElementsByTagName(tag):
                    add_tracked_change_attrs(elem)
            for elem in node.getElementsByTagName("w:comment"):
                add_comment_attrs(elem)
            for elem in node.getElementsByTagName("w16cex:commentExtensible"):
                add_comment_extensible_date(elem)

    def replace_node(self, elem, new_content):
        """自動属性付与付きでノードを置換します。"""
        nodes = super().replace_node(elem, new_content)
        self._inject_attributes_to_nodes(nodes)
        return nodes

    def insert_after(self, elem, xml_content):
        """自動属性付与付きで、要素の後ろに挿入します。"""
        nodes = super().insert_after(elem, xml_content)
        self._inject_attributes_to_nodes(nodes)
        return nodes

    def insert_before(self, elem, xml_content):
        """自動属性付与付きで、要素の前に挿入します。"""
        nodes = super().insert_before(elem, xml_content)
        self._inject_attributes_to_nodes(nodes)
        return nodes

    def append_to(self, elem, xml_content):
        """自動属性付与付きで、要素へappendします。"""
        nodes = super().append_to(elem, xml_content)
        self._inject_attributes_to_nodes(nodes)
        return nodes

    def revert_insertion(self, elem):
        """挿入（w:ins）を拒否するため、その内容を削除（w:del）として包みます。

        w:ins配下のすべてのrunをw:delで包み、w:tをw:delTextへ変換します。
        単一のw:ins要素、または複数のw:insを含むコンテナ要素のどちらも処理できます。

        引数:
            elem: 処理対象の要素（w:ins / w:p / w:body など）

        戻り値:
            list: 処理した要素を含むリスト

        例外:
            ValueError: 対象要素にw:ins要素が含まれない場合

        例:
            # 単一の挿入を拒否
            ins = doc["word/document.xml"].get_node(tag="w:ins", attrs={"w:id": "5"})
            doc["word/document.xml"].revert_insertion(ins)

            # 段落内の挿入をまとめて拒否
            para = doc["word/document.xml"].get_node(tag="w:p", line_number=42)
            doc["word/document.xml"].revert_insertion(para)
        """
        # 挿入（w:ins）を収集
        ins_elements = []
        if elem.tagName == "w:ins":
            ins_elements.append(elem)
        else:
            ins_elements.extend(elem.getElementsByTagName("w:ins"))

        # 拒否対象の挿入が存在することを検証
        if not ins_elements:
            raise ValueError(
                f"revert_insertion には w:ins 要素が必要です。"
                f"指定された要素 <{elem.tagName}> には挿入（w:ins）が含まれません。"
            )

        # すべての挿入を処理：子要素をw:delで包む
        for ins_elem in ins_elements:
            runs = list(ins_elem.getElementsByTagName("w:r"))
            if not runs:
                continue

            # 削除ラッパーを作成
            del_wrapper = self.dom.createElement("w:del")

            # 各runを処理
            for run in runs:
                # w:t → w:delText、w:rsidR → w:rsidDel に変換
                if run.hasAttribute("w:rsidR"):
                    run.setAttribute("w:rsidDel", run.getAttribute("w:rsidR"))
                    run.removeAttribute("w:rsidR")
                elif not run.hasAttribute("w:rsidDel"):
                    run.setAttribute("w:rsidDel", self.rsid)

                for t_elem in list(run.getElementsByTagName("w:t")):
                    del_text = self.dom.createElement("w:delText")
                    # エンティティ対応のため、子ノードをすべてコピー（firstChildだけでなく）
                    while t_elem.firstChild:
                        del_text.appendChild(t_elem.firstChild)
                    for i in range(t_elem.attributes.length):
                        attr = t_elem.attributes.item(i)
                        del_text.setAttribute(attr.name, attr.value)
                    t_elem.parentNode.replaceChild(del_text, t_elem)

            # insの子要素をすべてdelラッパーへ移動
            while ins_elem.firstChild:
                del_wrapper.appendChild(ins_elem.firstChild)

            # delラッパーをins配下へ戻す
            ins_elem.appendChild(del_wrapper)

            # 削除ラッパーへ属性を注入（付与）
            self._inject_attributes_to_nodes([del_wrapper])

        return [elem]

    def revert_deletion(self, elem):
        """削除（w:del）を拒否するため、削除された内容を再挿入します。

        各w:delの直後にw:ins要素を作成し、削除内容をコピーして
        w:delTextをw:tへ戻します。
        単一のw:del要素、または複数のw:delを含むコンテナ要素のどちらも処理できます。

        引数:
            elem: 処理対象の要素（w:del / w:p / w:body など）

        戻り値:
            list: elemがw:delなら [elem, new_ins]。それ以外は [elem]。

        例外:
            ValueError: 対象要素にw:del要素が含まれない場合

        例:
            # 単一の削除を拒否（戻り値: [w:del, w:ins]）
            del_elem = doc["word/document.xml"].get_node(tag="w:del", attrs={"w:id": "3"})
            nodes = doc["word/document.xml"].revert_deletion(del_elem)

            # 段落内の削除をまとめて拒否（戻り値: [para]）
            para = doc["word/document.xml"].get_node(tag="w:p", line_number=42)
            nodes = doc["word/document.xml"].revert_deletion(para)
        """
        # DOM変更の前に、削除（w:del）を先に収集
        del_elements = []
        is_single_del = elem.tagName == "w:del"

        if is_single_del:
            del_elements.append(elem)
        else:
            del_elements.extend(elem.getElementsByTagName("w:del"))

        # 拒否対象の削除が存在することを検証
        if not del_elements:
            raise ValueError(
                f"revert_deletion には w:del 要素が必要です。"
                f"指定された要素 <{elem.tagName}> には削除（w:del）が含まれません。"
            )

        # 生成した挿入を追跡（elemが単一のw:delの場合のみ有効）
        created_insertion = None

        # すべての削除を処理：削除内容をコピーした挿入を作る
        for del_elem in del_elements:
            # 削除runを複製し、挿入へ変換
            runs = list(del_elem.getElementsByTagName("w:r"))
            if not runs:
                continue

            # 挿入ラッパーを作成
            ins_elem = self.dom.createElement("w:ins")

            for run in runs:
                # runを複製
                new_run = run.cloneNode(True)

                # w:delText → w:t に変換
                for del_text in list(new_run.getElementsByTagName("w:delText")):
                    t_elem = self.dom.createElement("w:t")
                    # エンティティ対応のため、子ノードをすべてコピー（firstChildだけでなく）
                    while del_text.firstChild:
                        t_elem.appendChild(del_text.firstChild)
                    for i in range(del_text.attributes.length):
                        attr = del_text.attributes.item(i)
                        t_elem.setAttribute(attr.name, attr.value)
                    del_text.parentNode.replaceChild(t_elem, del_text)

                # run属性を更新: w:rsidDel → w:rsidR
                if new_run.hasAttribute("w:rsidDel"):
                    new_run.setAttribute("w:rsidR", new_run.getAttribute("w:rsidDel"))
                    new_run.removeAttribute("w:rsidDel")
                elif not new_run.hasAttribute("w:rsidR"):
                    new_run.setAttribute("w:rsidR", self.rsid)

                ins_elem.appendChild(new_run)

            # 新しい挿入を削除の後ろに挿入
            nodes = self.insert_after(del_elem, ins_elem.toxml())

            # 単一w:delを処理している場合、生成した挿入を追跡
            if is_single_del and nodes:
                created_insertion = nodes[0]

        # 入力タイプに応じて返す
        if is_single_del and created_insertion:
            return [elem, created_insertion]
        else:
            return [elem]

    @staticmethod
    def suggest_paragraph(xml_content: str) -> str:
        """段落XMLを変換し、挿入の追跡変更ラップ（tracked change wrapping）を追加します。

        runを<w:ins>で包み、番号付きリスト向けに w:pPr 内の w:rPr に <w:ins/> を追加します。

        引数:
            xml_content: <w:p>要素を含むXML文字列

        戻り値:
            str: 追跡変更ラップを追加した変換後XML
        """
        wrapper = f'<root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">{xml_content}</root>'
        doc = minidom.parseString(wrapper)
        para = doc.getElementsByTagName("w:p")[0]

        # w:pPr が存在することを保証
        pPr_list = para.getElementsByTagName("w:pPr")
        if not pPr_list:
            pPr = doc.createElement("w:pPr")
            para.insertBefore(
                pPr, para.firstChild
            ) if para.firstChild else para.appendChild(pPr)
        else:
            pPr = pPr_list[0]

        # w:pPr 内に w:rPr が存在することを保証
        rPr_list = pPr.getElementsByTagName("w:rPr")
        if not rPr_list:
            rPr = doc.createElement("w:rPr")
            pPr.appendChild(rPr)
        else:
            rPr = rPr_list[0]

        # w:rPr に <w:ins/> を追加
        ins_marker = doc.createElement("w:ins")
        rPr.insertBefore(
            ins_marker, rPr.firstChild
        ) if rPr.firstChild else rPr.appendChild(ins_marker)

        # w:pPr以外の子要素をすべて<w:ins>で包む
        ins_wrapper = doc.createElement("w:ins")
        for child in [c for c in para.childNodes if c.nodeName != "w:pPr"]:
            para.removeChild(child)
            ins_wrapper.appendChild(child)
        para.appendChild(ins_wrapper)

        return para.toxml()

    def suggest_deletion(self, elem):
        """w:r または w:p 要素を追跡変更付きの削除としてマークします（DOMをin-placeで操作）。

        - w:r: <w:del>で包み、<w:t>を<w:delText>へ変換し、w:rPrを保持します
        - w:p（通常）: 内容を<w:del>で包み、<w:t>を<w:delText>へ変換します
        - w:p（番号付きリスト）: w:pPr 内の w:rPr に <w:del/> を追加し、内容を<w:del>で包みます

        引数:
            elem: 既存の追跡変更がない w:r または w:p のDOM要素

        戻り値:
            Element: 変更後の要素

        例外:
            ValueError: 既存の追跡変更がある、または構造が不正な場合
        """
        if elem.nodeName == "w:r":
            # 既存のw:delTextがないか確認
            if elem.getElementsByTagName("w:delText"):
                raise ValueError("w:r 要素に既に w:delText が含まれています")

            # w:t → w:delText に変換
            for t_elem in list(elem.getElementsByTagName("w:t")):
                del_text = self.dom.createElement("w:delText")
                # エンティティ対応のため、子ノードをすべてコピー（firstChildだけでなく）
                while t_elem.firstChild:
                    del_text.appendChild(t_elem.firstChild)
                # xml:spaceなどの属性を保持
                for i in range(t_elem.attributes.length):
                    attr = t_elem.attributes.item(i)
                    del_text.setAttribute(attr.name, attr.value)
                t_elem.parentNode.replaceChild(del_text, t_elem)

            # run属性を更新: w:rsidR → w:rsidDel
            if elem.hasAttribute("w:rsidR"):
                elem.setAttribute("w:rsidDel", elem.getAttribute("w:rsidR"))
                elem.removeAttribute("w:rsidR")
            elif not elem.hasAttribute("w:rsidDel"):
                elem.setAttribute("w:rsidDel", self.rsid)

            # w:del で包む
            del_wrapper = self.dom.createElement("w:del")
            parent = elem.parentNode
            parent.insertBefore(del_wrapper, elem)
            parent.removeChild(elem)
            del_wrapper.appendChild(elem)

            # 削除ラッパーへ属性を注入（付与）
            self._inject_attributes_to_nodes([del_wrapper])

            return del_wrapper

        elif elem.nodeName == "w:p":
            # 既存の追跡変更がないか確認
            if elem.getElementsByTagName("w:ins") or elem.getElementsByTagName("w:del"):
                raise ValueError("w:p 要素に既に追跡変更（tracked changes）が含まれています")

            # 番号付きリスト項目か確認
            pPr_list = elem.getElementsByTagName("w:pPr")
            is_numbered = pPr_list and pPr_list[0].getElementsByTagName("w:numPr")

            if is_numbered:
                # w:pPr内のw:rPrに <w:del/> を追加
                pPr = pPr_list[0]
                rPr_list = pPr.getElementsByTagName("w:rPr")

                if not rPr_list:
                    rPr = self.dom.createElement("w:rPr")
                    pPr.appendChild(rPr)
                else:
                    rPr = rPr_list[0]

                # <w:del/> マーカーを追加
                del_marker = self.dom.createElement("w:del")
                rPr.insertBefore(
                    del_marker, rPr.firstChild
                ) if rPr.firstChild else rPr.appendChild(del_marker)

            # 全runの w:t → w:delText を変換
            for t_elem in list(elem.getElementsByTagName("w:t")):
                del_text = self.dom.createElement("w:delText")
                # エンティティ対応のため、子ノードをすべてコピー（firstChildだけでなく）
                while t_elem.firstChild:
                    del_text.appendChild(t_elem.firstChild)
                # xml:spaceなどの属性を保持
                for i in range(t_elem.attributes.length):
                    attr = t_elem.attributes.item(i)
                    del_text.setAttribute(attr.name, attr.value)
                t_elem.parentNode.replaceChild(del_text, t_elem)

            # run属性を更新: w:rsidR → w:rsidDel
            for run in elem.getElementsByTagName("w:r"):
                if run.hasAttribute("w:rsidR"):
                    run.setAttribute("w:rsidDel", run.getAttribute("w:rsidR"))
                    run.removeAttribute("w:rsidR")
                elif not run.hasAttribute("w:rsidDel"):
                    run.setAttribute("w:rsidDel", self.rsid)

            # w:pPr以外の子要素を <w:del> で包む
            del_wrapper = self.dom.createElement("w:del")
            for child in [c for c in elem.childNodes if c.nodeName != "w:pPr"]:
                elem.removeChild(child)
                del_wrapper.appendChild(child)
            elem.appendChild(del_wrapper)

            # 削除ラッパーへ属性を注入（付与）
            self._inject_attributes_to_nodes([del_wrapper])

            return elem

        else:
            raise ValueError(f"要素は w:r または w:p である必要があります: {elem.nodeName}")


def _generate_hex_id() -> str:
    """para/durable ID用のランダムな8桁16進IDを生成します。

    OOXML仕様により、値は 0x7FFFFFFF 未満に制約されます:
    - paraId は < 0x80000000
    - durableId は < 0x7FFFFFFF
    ここでは両方に対して、より厳しい制約（0x7FFFFFFF）を適用します。
    """
    return f"{random.randint(1, 0x7FFFFFFE):08X}"


def _generate_rsid() -> str:
    """ランダムな8桁16進RSIDを生成します。"""
    return "".join(random.choices("0123456789ABCDEF", k=8))


class Document:
    """アンパック済みWordドキュメントのコメントを管理します。"""

    def __init__(
        self,
        unpacked_dir,
        rsid=None,
        track_revisions=False,
        author="Claude",
        initials="C",
    ):
        """アンパック済みWordドキュメントのディレクトリを指定して初期化します。

        コメント基盤（people.xml、RSIDなど）も必要に応じて自動セットアップします。

        引数:
            unpacked_dir: アンパック済みDOCXディレクトリのパス（`word/` サブディレクトリを含むこと）
            rsid: 全コメント要素に使うRSID（任意）。未指定の場合は生成します
            track_revisions: Trueの場合、settings.xmlで追跡変更（track revisions）を有効化します（既定: False）
            author: コメント用の既定著者名（既定: "Claude"）
            initials: コメント用の既定著者イニシャル（既定: "C"）
        """
        self.original_path = Path(unpacked_dir)

        if not self.original_path.exists() or not self.original_path.is_dir():
            raise ValueError(f"ディレクトリが見つかりません: {unpacked_dir}")

        # アンパック内容とベースライン用のサブディレクトリを持つ一時ディレクトリを作成
        self.temp_dir = tempfile.mkdtemp(prefix="docx_")
        self.unpacked_path = Path(self.temp_dir) / "unpacked"
        shutil.copytree(self.original_path, self.unpacked_path)

        # 検証ベースライン用に、元ディレクトリを一時.docxへパック（unpacked外）
        self.original_docx = Path(self.temp_dir) / "original.docx"
        pack_document(self.original_path, self.original_docx, validate=False)

        self.word_path = self.unpacked_path / "word"

        # rsid未指定なら生成
        self.rsid = rsid if rsid else _generate_rsid()
        print(f"RSIDを使用します: {self.rsid}")

        # author/initialsのデフォルトを設定
        self.author = author
        self.initials = initials

        # 遅延ロードするeditorのキャッシュ
        self._editors = {}

        # コメント関連ファイルのパス
        self.comments_path = self.word_path / "comments.xml"
        self.comments_extended_path = self.word_path / "commentsExtended.xml"
        self.comments_ids_path = self.word_path / "commentsIds.xml"
        self.comments_extensible_path = self.word_path / "commentsExtensible.xml"

        # 既存コメントを読み込み、次のIDを決定（セットアップでファイルを書き換える前）
        self.existing_comments = self._load_existing_comments()
        self.next_comment_id = self._get_next_comment_id()

        # document.xml editorへの簡易アクセス（準プライベート）
        self._document = self["word/document.xml"]

        # 追跡変更の基盤をセットアップ
        self._setup_tracking(track_revisions=track_revisions)

        # people.xml にauthorを追加
        self._add_author_to_people(author)

    def __getitem__(self, xml_path: str) -> DocxXMLEditor:
        """指定されたXMLファイルに対応するDocxXMLEditorを取得（必要なら作成）します。

        `doc["word/document.xml"]` のようなブラケット記法で、遅延ロードされたeditorを使えます。

        引数:
            xml_path: XMLファイルの相対パス（例: "word/document.xml", "word/comments.xml"）

        戻り値:
            指定ファイルに対応するDocxXMLEditorインスタンス

        例外:
            ValueError: ファイルが存在しない場合

        例:
            # document.xml からノードを取得
            node = doc["word/document.xml"].get_node(tag="w:del", attrs={"w:id": "1"})

            # comments.xml からノードを取得
            comment = doc["word/comments.xml"].get_node(tag="w:comment", attrs={"w:id": "0"})
        """
        if xml_path not in self._editors:
            file_path = self.unpacked_path / xml_path
            if not file_path.exists():
                raise ValueError(f"XMLファイルが見つかりません: {xml_path}")
            # すべてのeditorでRSID/author/initialsを統一して付与する
            self._editors[xml_path] = DocxXMLEditor(
                file_path, rsid=self.rsid, author=self.author, initials=self.initials
            )
        return self._editors[xml_path]

    def add_comment(self, start, end, text: str) -> int:
        """startからendまでの範囲にコメントを追加します。

        引数:
            start: コメント範囲の開始点となるDOM要素
            end: コメント範囲の終了点となるDOM要素
            text: コメント本文

        戻り値:
            作成したコメントID

        例:
            start_node = cm.get_document_node(tag="w:del", id="1")
            end_node = cm.get_document_node(tag="w:ins", id="2")
            cm.add_comment(start=start_node, end=end_node, text="Explanation")
        """
        comment_id = self.next_comment_id
        para_id = _generate_hex_id()
        durable_id = _generate_hex_id()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # document.xml にコメント範囲を即時追加
        self._document.insert_before(start, self._comment_range_start_xml(comment_id))

        # endノードが段落なら、その中にコメントマークアップを追加
        # そうでなければ直後に挿入（runレベルのアンカー用）
        if end.tagName == "w:p":
            self._document.append_to(end, self._comment_range_end_xml(comment_id))
        else:
            self._document.insert_after(end, self._comment_range_end_xml(comment_id))

        # comments.xml に即時追加
        self._add_to_comments_xml(
            comment_id, para_id, text, self.author, self.initials, timestamp
        )

        # commentsExtended.xml に即時追加
        self._add_to_comments_extended_xml(para_id, parent_para_id=None)

        # commentsIds.xml に即時追加
        self._add_to_comments_ids_xml(para_id, durable_id)

        # commentsExtensible.xml に即時追加
        self._add_to_comments_extensible_xml(durable_id)

        # 返信が動くよう existing_comments を更新
        self.existing_comments[comment_id] = {"para_id": para_id}

        self.next_comment_id += 1
        return comment_id

    def reply_to_comment(
        self,
        parent_comment_id: int,
        text: str,
    ) -> int:
        """既存のコメントに返信（リプライ）を追加します。

        引数:
            parent_comment_id: 返信先（親）コメントの w:id
            text: 返信本文

        戻り値:
            作成した返信コメントのID

        例:
            cm.reply_to_comment(parent_comment_id=0, text="I agree with this change")
        """
        if parent_comment_id not in self.existing_comments:
            raise ValueError(f"親コメントが見つかりません: id={parent_comment_id}")

        parent_info = self.existing_comments[parent_comment_id]
        comment_id = self.next_comment_id
        para_id = _generate_hex_id()
        durable_id = _generate_hex_id()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # document.xml にコメント範囲を即時追加
        parent_start_elem = self._document.get_node(
            tag="w:commentRangeStart", attrs={"w:id": str(parent_comment_id)}
        )
        parent_ref_elem = self._document.get_node(
            tag="w:commentReference", attrs={"w:id": str(parent_comment_id)}
        )

        self._document.insert_after(
            parent_start_elem, self._comment_range_start_xml(comment_id)
        )
        parent_ref_run = parent_ref_elem.parentNode
        self._document.insert_after(
            parent_ref_run, f'<w:commentRangeEnd w:id="{comment_id}"/>'
        )
        self._document.insert_after(
            parent_ref_run, self._comment_ref_run_xml(comment_id)
        )

        # comments.xml に即時追加
        self._add_to_comments_xml(
            comment_id, para_id, text, self.author, self.initials, timestamp
        )

        # commentsExtended.xml に即時追加（親情報付き）
        self._add_to_comments_extended_xml(
            para_id, parent_para_id=parent_info["para_id"]
        )

        # commentsIds.xml に即時追加
        self._add_to_comments_ids_xml(para_id, durable_id)

        # commentsExtensible.xml に即時追加
        self._add_to_comments_extensible_xml(durable_id)

        # 返信が動くよう existing_comments を更新
        self.existing_comments[comment_id] = {"para_id": para_id}

        self.next_comment_id += 1
        return comment_id

    def __del__(self):
        """削除時に一時ディレクトリをクリーンアップします。"""
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def validate(self) -> None:
        """XSDスキーマと追跡変更（redlining）ルールに照らしてドキュメントを検証します。

        例外:
            ValueError: 検証に失敗した場合
        """
        # 現在状態でバリデータを作成
        schema_validator = DOCXSchemaValidator(
            self.unpacked_path, self.original_docx, verbose=False
        )
        redlining_validator = RedliningValidator(
            self.unpacked_path, self.original_docx, verbose=False
        )

        # 検証を実行
        if not schema_validator.validate():
            raise ValueError("スキーマ検証に失敗しました")
        if not redlining_validator.validate():
            raise ValueError("追跡変更（redlining）検証に失敗しました")

    def save(self, destination=None, validate=True) -> None:
        """変更したXMLファイルをすべて保存し、保存先ディレクトリへコピーします。

        `add_comment()` や `reply_to_comment()` で行った変更もここで永続化されます。

        引数:
            destination: 保存先パス（任意）。Noneの場合は元ディレクトリへ上書き保存します
            validate: Trueの場合、保存前にドキュメントを検証します（既定: True）
        """
        # コメントファイルがある場合のみ、relationshipとcontent typeを保証
        if self.comments_path.exists():
            self._ensure_comment_relationships()
            self._ensure_comment_content_types()

        # 変更したXMLを一時ディレクトリに保存
        for editor in self._editors.values():
            editor.save()

        # デフォルトで検証する
        if validate:
            self.validate()

        # 一時ディレクトリの内容を保存先（または元ディレクトリ）へコピー
        target_path = Path(destination) if destination else self.original_path
        shutil.copytree(self.unpacked_path, target_path, dirs_exist_ok=True)

    # ==================== Private: 初期化 ====================

    def _get_next_comment_id(self):
        """次に利用可能なコメントIDを取得します。"""
        if not self.comments_path.exists():
            return 0

        editor = self["word/comments.xml"]
        max_id = -1
        for comment_elem in editor.dom.getElementsByTagName("w:comment"):
            comment_id = comment_elem.getAttribute("w:id")
            if comment_id:
                try:
                    max_id = max(max_id, int(comment_id))
                except ValueError:
                    pass
        return max_id + 1

    def _load_existing_comments(self):
        """返信を可能にするため、既存コメントをファイルから読み込みます。"""
        if not self.comments_path.exists():
            return {}

        editor = self["word/comments.xml"]
        existing = {}

        for comment_elem in editor.dom.getElementsByTagName("w:comment"):
            comment_id = comment_elem.getAttribute("w:id")
            if not comment_id:
                continue

            # コメント内のw:p要素からpara_idを取得
            para_id = None
            for p_elem in comment_elem.getElementsByTagName("w:p"):
                para_id = p_elem.getAttribute("w14:paraId")
                if para_id:
                    break

            if not para_id:
                continue

            existing[int(comment_id)] = {"para_id": para_id}

        return existing

    # ==================== Private: セットアップメソッド ====================

    def _setup_tracking(self, track_revisions=False):
        """アンパック済みディレクトリにコメント用の基盤（ファイル/参照）をセットアップします。

        引数:
            track_revisions: Trueの場合、settings.xmlで追跡変更（track revisions）を有効化します
        """
        # word/people.xml を作成または更新
        people_file = self.word_path / "people.xml"
        self._update_people_xml(people_file)

        # XMLファイルを更新
        self._add_content_type_for_people(self.unpacked_path / "[Content_Types].xml")
        self._add_relationship_for_people(
            self.word_path / "_rels" / "document.xml.rels"
        )

        # settings.xml にRSIDは常に追加し、必要ならtrackRevisionsを有効化
        self._update_settings(
            self.word_path / "settings.xml", track_revisions=track_revisions
        )

    def _update_people_xml(self, path):
        """people.xml が無ければ作成します。"""
        if not path.exists():
            # テンプレートからコピー
            shutil.copy(TEMPLATE_DIR / "people.xml", path)

    def _add_content_type_for_people(self, path):
        """[Content_Types].xml に people.xml のcontent typeが無ければ追加します。"""
        editor = self["[Content_Types].xml"]

        if self._has_override(editor, "/word/people.xml"):
            return

        # Override要素を追加
        root = editor.dom.documentElement
        override_xml = '<Override PartName="/word/people.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.people+xml"/>'
        editor.append_to(root, override_xml)

    def _add_relationship_for_people(self, path):
        """document.xml.rels に people.xml のrelationshipが無ければ追加します。"""
        editor = self["word/_rels/document.xml.rels"]

        if self._has_relationship(editor, "people.xml"):
            return

        root = editor.dom.documentElement
        root_tag = root.tagName  # type: ignore
        prefix = root_tag.split(":")[0] + ":" if ":" in root_tag else ""
        next_rid = editor.get_next_rid()

        # relationshipエントリを作成
        rel_xml = f'<{prefix}Relationship Id="{next_rid}" Type="http://schemas.microsoft.com/office/2011/relationships/people" Target="people.xml"/>'
        editor.append_to(root, rel_xml)

    def _update_settings(self, path, track_revisions=False):
        """RSIDを追加し、必要に応じてsettings.xmlで追跡変更（track revisions）を有効化します。

        引数:
            path: settings.xml のパス
            track_revisions: Trueの場合、trackRevisions要素を追加します

        OOXMLスキーマ順に従って要素を配置します:
        - trackRevisions: early (before defaultTabStop)
        - rsids: late (after compat)
        """
        editor = self["word/settings.xml"]
        root = editor.get_node(tag="w:settings")
        prefix = root.tagName.split(":")[0] if ":" in root.tagName else "w"

        # 要求されていればtrackRevisionsを追加
        if track_revisions:
            track_revisions_exists = any(
                elem.tagName == f"{prefix}:trackRevisions"
                for elem in editor.dom.getElementsByTagName(f"{prefix}:trackRevisions")
            )

            if not track_revisions_exists:
                track_rev_xml = f"<{prefix}:trackRevisions/>"
                # documentProtection/defaultTabStopの前、または先頭への挿入を試みる
                inserted = False
                for tag in [f"{prefix}:documentProtection", f"{prefix}:defaultTabStop"]:
                    elements = editor.dom.getElementsByTagName(tag)
                    if elements:
                        editor.insert_before(elements[0], track_rev_xml)
                        inserted = True
                        break
                if not inserted:
                    # settingsの先頭子として挿入
                    if root.firstChild:
                        editor.insert_before(root.firstChild, track_rev_xml)
                    else:
                        editor.append_to(root, track_rev_xml)

        # rsidsセクションの有無を常にチェック
        rsids_elements = editor.dom.getElementsByTagName(f"{prefix}:rsids")

        if not rsids_elements:
            # 新しいrsidsセクションを追加
            rsids_xml = f'''<{prefix}:rsids>
  <{prefix}:rsidRoot {prefix}:val="{self.rsid}"/>
  <{prefix}:rsid {prefix}:val="{self.rsid}"/>
</{prefix}:rsids>'''

            # compatの後、clrSchemeMappingの前、または閉じタグの前へ挿入を試みる
            inserted = False
            compat_elements = editor.dom.getElementsByTagName(f"{prefix}:compat")
            if compat_elements:
                editor.insert_after(compat_elements[0], rsids_xml)
                inserted = True

            if not inserted:
                clr_elements = editor.dom.getElementsByTagName(
                    f"{prefix}:clrSchemeMapping"
                )
                if clr_elements:
                    editor.insert_before(clr_elements[0], rsids_xml)
                    inserted = True

            if not inserted:
                editor.append_to(root, rsids_xml)
        else:
            # このrsidが既に存在するか確認
            rsids_elem = rsids_elements[0]
            rsid_exists = any(
                elem.getAttribute(f"{prefix}:val") == self.rsid
                for elem in rsids_elem.getElementsByTagName(f"{prefix}:rsid")
            )

            if not rsid_exists:
                rsid_xml = f'<{prefix}:rsid {prefix}:val="{self.rsid}"/>'
                editor.append_to(rsids_elem, rsid_xml)

    # ==================== Private: XMLファイル作成 ====================

    def _add_to_comments_xml(
        self, comment_id, para_id, text, author, initials, timestamp
    ):
        """comments.xml にコメントを1件追加します。"""
        if not self.comments_path.exists():
            shutil.copy(TEMPLATE_DIR / "comments.xml", self.comments_path)

        editor = self["word/comments.xml"]
        root = editor.get_node(tag="w:comments")

        escaped_text = (
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        # 注: w:p上の w:rsidR / w:rsidRDefault / w:rsidP、w:r上の w:rsidR、
        #     および w:comment上の w:author / w:date / w:initials は DocxXMLEditor が自動付与します
        comment_xml = f'''<w:comment w:id="{comment_id}">
  <w:p w14:paraId="{para_id}" w14:textId="77777777">
    <w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:annotationRef/></w:r>
    <w:r><w:rPr><w:color w:val="000000"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr><w:t>{escaped_text}</w:t></w:r>
  </w:p>
</w:comment>'''
        editor.append_to(root, comment_xml)

    def _add_to_comments_extended_xml(self, para_id, parent_para_id):
        """commentsExtended.xml にコメントを1件追加します。"""
        if not self.comments_extended_path.exists():
            shutil.copy(
                TEMPLATE_DIR / "commentsExtended.xml", self.comments_extended_path
            )

        editor = self["word/commentsExtended.xml"]
        root = editor.get_node(tag="w15:commentsEx")

        if parent_para_id:
            xml = f'<w15:commentEx w15:paraId="{para_id}" w15:paraIdParent="{parent_para_id}" w15:done="0"/>'
        else:
            xml = f'<w15:commentEx w15:paraId="{para_id}" w15:done="0"/>'
        editor.append_to(root, xml)

    def _add_to_comments_ids_xml(self, para_id, durable_id):
        """commentsIds.xml にコメントを1件追加します。"""
        if not self.comments_ids_path.exists():
            shutil.copy(TEMPLATE_DIR / "commentsIds.xml", self.comments_ids_path)

        editor = self["word/commentsIds.xml"]
        root = editor.get_node(tag="w16cid:commentsIds")

        xml = f'<w16cid:commentId w16cid:paraId="{para_id}" w16cid:durableId="{durable_id}"/>'
        editor.append_to(root, xml)

    def _add_to_comments_extensible_xml(self, durable_id):
        """commentsExtensible.xml にコメントを1件追加します。"""
        if not self.comments_extensible_path.exists():
            shutil.copy(
                TEMPLATE_DIR / "commentsExtensible.xml", self.comments_extensible_path
            )

        editor = self["word/commentsExtensible.xml"]
        root = editor.get_node(tag="w16cex:commentsExtensible")

        xml = f'<w16cex:commentExtensible w16cex:durableId="{durable_id}"/>'
        editor.append_to(root, xml)

    # ==================== Private: XML断片 ====================

    def _comment_range_start_xml(self, comment_id):
        """comment range start のXMLを生成します。"""
        return f'<w:commentRangeStart w:id="{comment_id}"/>'

    def _comment_range_end_xml(self, comment_id):
        """参照run付きの comment range end XMLを生成します。

        注: w:rsidR は DocxXMLEditor により自動付与されます。
        """
        return f'''<w:commentRangeEnd w:id="{comment_id}"/>
<w:r>
  <w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>
  <w:commentReference w:id="{comment_id}"/>
</w:r>'''

    def _comment_ref_run_xml(self, comment_id):
        """comment reference run のXMLを生成します。

        注: w:rsidR は DocxXMLEditor により自動付与されます。
        """
        return f'''<w:r>
  <w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>
  <w:commentReference w:id="{comment_id}"/>
</w:r>'''

    # ==================== Private: メタデータ更新 ====================

    def _has_relationship(self, editor, target):
        """指定targetのrelationshipが存在するか確認します。"""
        for rel_elem in editor.dom.getElementsByTagName("Relationship"):
            if rel_elem.getAttribute("Target") == target:
                return True
        return False

    def _has_override(self, editor, part_name):
        """指定part nameのoverrideが存在するか確認します。"""
        for override_elem in editor.dom.getElementsByTagName("Override"):
            if override_elem.getAttribute("PartName") == part_name:
                return True
        return False

    def _has_author(self, editor, author):
        """people.xml にauthorが既に存在するか確認します。"""
        for person_elem in editor.dom.getElementsByTagName("w15:person"):
            if person_elem.getAttribute("w15:author") == author:
                return True
        return False

    def _add_author_to_people(self, author):
        """people.xml にauthorを追加します（初期化中に呼ばれます）。"""
        people_path = self.word_path / "people.xml"

        # people.xml は _setup_tracking で既に作成されている前提
        if not people_path.exists():
            raise ValueError("people.xml は _setup_tracking の後に存在している必要があります")

        editor = self["word/people.xml"]
        root = editor.get_node(tag="w15:people")

        # authorが既に存在するか確認
        if self._has_author(editor, author):
            return

        # インジェクションを防ぐため、適切にXMLエスケープしてauthorを追加
        escaped_author = html.escape(author, quote=True)
        person_xml = f'''<w15:person w15:author="{escaped_author}">
  <w15:presenceInfo w15:providerId="None" w15:userId="{escaped_author}"/>
</w15:person>'''
        editor.append_to(root, person_xml)

    def _ensure_comment_relationships(self):
        """word/_rels/document.xml.rels にコメント用relationshipがあることを保証します。"""
        editor = self["word/_rels/document.xml.rels"]

        if self._has_relationship(editor, "comments.xml"):
            return

        root = editor.dom.documentElement
        root_tag = root.tagName  # type: ignore
        prefix = root_tag.split(":")[0] + ":" if ":" in root_tag else ""
        next_rid_num = int(editor.get_next_rid()[3:])

        # relationship要素を追加
        rels = [
            (
                next_rid_num,
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
                "comments.xml",
            ),
            (
                next_rid_num + 1,
                "http://schemas.microsoft.com/office/2011/relationships/commentsExtended",
                "commentsExtended.xml",
            ),
            (
                next_rid_num + 2,
                "http://schemas.microsoft.com/office/2016/09/relationships/commentsIds",
                "commentsIds.xml",
            ),
            (
                next_rid_num + 3,
                "http://schemas.microsoft.com/office/2018/08/relationships/commentsExtensible",
                "commentsExtensible.xml",
            ),
        ]

        for rel_id, rel_type, target in rels:
            rel_xml = f'<{prefix}Relationship Id="rId{rel_id}" Type="{rel_type}" Target="{target}"/>'
            editor.append_to(root, rel_xml)

    def _ensure_comment_content_types(self):
        """[Content_Types].xml にコメント用content typeがあることを保証します。"""
        editor = self["[Content_Types].xml"]

        if self._has_override(editor, "/word/comments.xml"):
            return

        root = editor.dom.documentElement

        # Override要素を追加
        overrides = [
            (
                "/word/comments.xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
            ),
            (
                "/word/commentsExtended.xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml",
            ),
            (
                "/word/commentsIds.xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsIds+xml",
            ),
            (
                "/word/commentsExtensible.xml",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtensible+xml",
            ),
        ]

        for part_name, content_type in overrides:
            override_xml = (
                f'<Override PartName="{part_name}" ContentType="{content_type}"/>'
            )
            editor.append_to(root, override_xml)
