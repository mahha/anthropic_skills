> **注:** このリポジトリには、Claude用のスキルのAnthropicによる実装が含まれています。Agent Skills標準に関する情報については、[agentskills.io](http://agentskills.io)を参照してください。

# スキル
スキルは、Claudeが専門的なタスクのパフォーマンスを向上させるために動的に読み込む、指示、スクリプト、リソースのフォルダです。スキルは、会社のブランドガイドラインを使用してドキュメントを作成する、組織固有のワークフローを使用してデータを分析する、個人タスクを自動化するなど、Claudeが特定のタスクを繰り返し可能な方法で完了する方法を教えます。

詳細については、以下を確認してください：
- [スキルとは？](https://support.claude.com/en/articles/12512176-what-are-skills)
- [Claudeでのスキルの使用](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [カスタムスキルの作成方法](https://support.claude.com/en/articles/12512198-creating-custom-skills)
- [Agent Skillsでエージェントを実世界に対応させる](https://anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

# このリポジトリについて

このリポジトリには、Claudeのスキルシステムで可能なことを示すスキルが含まれています。これらのスキルは、クリエイティブなアプリケーション（アート、音楽、デザイン）から技術的なタスク（Webアプリのテスト、MCPサーバーの生成）まで、エンタープライズワークフロー（コミュニケーション、ブランディングなど）まで多岐にわたります。

各スキルは、Claudeが使用する指示とメタデータを含む`SKILL.md`ファイルを持つ独自のフォルダに自己完結しています。これらのスキルを閲覧して、独自のスキルのインスピレーションを得たり、さまざまなパターンやアプローチを理解したりしてください。

このリポジトリ内の多くのスキルはオープンソース（Apache 2.0）です。また、[Claudeのドキュメント機能](https://www.anthropic.com/news/create-files)を支えるドキュメント作成・編集スキルを、[`skills/docx`](./skills/docx)、[`skills/pdf`](./skills/pdf)、[`skills/pptx`](./skills/pptx)、[`skills/xlsx`](./skills/xlsx)サブフォルダに含めています。これらはオープンソースではなくソース利用可能ですが、本番AIアプリケーションで積極的に使用されているより複雑なスキルの参考として、開発者と共有したいと考えています。

## 免責事項

**これらのスキルは、デモンストレーションおよび教育目的でのみ提供されています。** Claudeでこれらの機能の一部が利用可能な場合でも、Claudeから受け取る実装と動作は、これらのスキルに示されているものとは異なる場合があります。これらのスキルは、パターンと可能性を示すことを目的としています。重要なタスクに依存する前に、必ず独自の環境でスキルを十分にテストしてください。

# スキルセット
- [./skills](./skills): クリエイティブ＆デザイン、開発＆技術、エンタープライズ＆コミュニケーション、およびドキュメントスキルのスキル例
- [./spec](./spec): Agent Skills仕様
- [./template](./template): スキルテンプレート

# Claude Code、Claude.ai、およびAPIで試す

## Claude Code
Claude Codeで次のコマンドを実行して、このリポジトリをClaude Codeプラグインマーケットプレイスとして登録できます：
```
/plugin marketplace add anthropics/skills
```

次に、特定のスキルセットをインストールするには：
1. `Browse and install plugins`を選択
2. `anthropic-agent-skills`を選択
3. `document-skills`または`example-skills`を選択
4. `Install now`を選択

または、次のいずれかのプラグインを直接インストールします：
```
/plugin install document-skills@anthropic-agent-skills
/plugin install example-skills@anthropic-agent-skills
```

プラグインをインストールした後、スキルに言及するだけで使用できます。たとえば、マーケットプレイスから`document-skills`プラグインをインストールした場合、Claude Codeに「PDFスキルを使用して`path/to/some-file.pdf`からフォームフィールドを抽出する」などの操作を依頼できます。

## Claude.ai

これらのサンプルスキルはすべて、Claude.aiの有料プランで既に利用可能です。

このリポジトリから任意のスキルを使用したり、カスタムスキルをアップロードしたりするには、[Claudeでのスキルの使用](https://support.claude.com/en/articles/12512180-using-skills-in-claude#h_a4222fa77b)の指示に従ってください。

## Claude API

Anthropicの事前構築済みスキルを使用し、Claude API経由でカスタムスキルをアップロードできます。詳細については、[Skills APIクイックスタート](https://docs.claude.com/en/api/skills-guide#creating-a-skill)を参照してください。

# 基本的なスキルの作成

スキルは簡単に作成できます。YAMLフロントマターと指示を含む`SKILL.md`ファイルを持つフォルダだけです。このリポジトリの**template-skill**を開始点として使用できます：

```markdown
---
name: my-skill-name
description: このスキルが何をするか、いつ使用するかの明確な説明
---

# マイスキル名

[このスキルがアクティブなときにClaudeが従う指示をここに追加]

## 例
- 使用例1
- 使用例2

## ガイドライン
- ガイドライン1
- ガイドライン2
```

フロントマターには2つのフィールドのみが必要です：
- `name` - スキルの一意の識別子（小文字、スペースはハイフン）
- `description` - スキルが何をするか、いつ使用するかの完全な説明

下のマークダウンコンテンツには、Claudeが従う指示、例、ガイドラインが含まれています。詳細については、[カスタムスキルの作成方法](https://support.claude.com/en/articles/12512198-creating-custom-skills)を参照してください。

# パートナースキル

スキルは、Claudeに特定のソフトウェアの使用を改善する方法を教える優れた方法です。パートナーからの素晴らしいサンプルスキルを見つけたら、ここでいくつかを紹介する場合があります：

- **Notion** - [Notion Skills for Claude](https://www.notion.so/notiondevs/Notion-Skills-for-Claude-28da4445d27180c7af1df7d8615723d0)

