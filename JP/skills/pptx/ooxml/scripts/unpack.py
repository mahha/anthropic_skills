#!/usr/bin/env python3
"""Officeファイル（.docx/.pptx/.xlsx）をアンパックし、XML内容を整形します。"""

import random
import sys
import defusedxml.minidom
import zipfile
from pathlib import Path

# コマンドライン引数を取得
assert len(sys.argv) == 3, "Usage: python unpack.py <office_file> <output_dir>"
input_file, output_dir = sys.argv[1], sys.argv[2]

# 展開して整形
output_path = Path(output_dir)
output_path.mkdir(parents=True, exist_ok=True)
zipfile.ZipFile(input_file).extractall(output_path)

# すべてのXMLファイルを整形（pretty print）
xml_files = list(output_path.rglob("*.xml")) + list(output_path.rglob("*.rels"))
for xml_file in xml_files:
    content = xml_file.read_text(encoding="utf-8")
    dom = defusedxml.minidom.parseString(content)
    xml_file.write_bytes(dom.toprettyxml(indent="  ", encoding="ascii"))

# .docxの場合、追跡変更（tracked changes）用にRSID候補を提案
if input_file.endswith(".docx"):
    suggested_rsid = "".join(random.choices("0123456789ABCDEF", k=8))
    print(f"Suggested RSID for edit session: {suggested_rsid}")
