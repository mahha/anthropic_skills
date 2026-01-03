import sys
from pypdf import PdfReader


# PDFに入力可能なフォームフィールドがあるかどうかを判定するためにClaudeが実行するスクリプト。forms.mdを参照。


reader = PdfReader(sys.argv[1])
if (reader.get_fields()):
    print("This PDF has fillable form fields")
else:
    print("This PDF does not have fillable form fields; you will need to visually determine where to enter data")
