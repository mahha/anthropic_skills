# 出力パターン

スキルが一貫して高品質な出力を生成する必要がある場合、これらのパターンを使用します。

## テンプレートパターン

出力フォーマットのテンプレートを提供します。必要に応じて厳格さのレベルを合わせます。

**厳格な要件（APIレスポンスやデータ形式など）の場合：**

```markdown
## レポート構造

常にこの正確なテンプレート構造を使用：

# [分析タイトル]

## エグゼクティブサマリー
[主要な発見の1段落概要]

## 主要な発見
- 発見1（根拠データ付き）
- 発見2（根拠データ付き）
- 発見3（根拠データ付き）

## 推奨事項
1. 具体的で実行可能な推奨
2. 具体的で実行可能な推奨
```

**柔軟なガイダンス（状況に応じた調整が有用な場合）：**

```markdown
## レポート構造

妥当なデフォルト形式です。必要に応じて調整してください：

# [分析タイトル]

## エグゼクティブサマリー
[概要]

## 主要な発見
[発見内容に応じてセクションを調整]

## 推奨事項
[具体的な状況に合わせて調整]

分析タイプに合わせてセクションを調整してください。
```

## 例（Examples）パターン

出力品質が「例を見ること」によって上がるタイプのスキルでは、入力/出力のペアを示します：

```markdown
## コミットメッセージフォーマット

次の例に従ってコミットメッセージを生成：

**例1:**
入力: Added user authentication with JWT tokens
出力:
```
feat(auth): implement JWT-based authentication

Add login endpoint and token validation middleware
```

**例2:**
入力: Fixed bug where dates displayed incorrectly in reports
出力:
```
fix(reports): correct date formatting in timezone conversion

Use UTC timestamps consistently across report generation
```

このスタイルに従う：type(scope): 短い説明、その後に詳細。
```

例は、説明文よりも「望ましいスタイル」と「求める詳細度」をClaudeに明確に伝えられます。


