"""MCPサーバー評価ハーネス

このスクリプトは、テスト質問をMCPサーバーに対して実行し、Claudeで評価します。
"""

import argparse
import asyncio
import json
import re
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from connections import create_connection

EVALUATION_PROMPT = """あなたはツールにアクセスできるAIアシスタントです。

タスクが与えられたら、必ず以下を行ってください:
1. 利用可能なツールを使ってタスクを完了する
2. アプローチの各ステップの要約を <summary> タグで囲んで提示する
3. 提供されたツールへのフィードバックを <feedback> タグで囲んで提示する
4. 最終回答を <response> タグで囲んで提示する

要約（Summary）の要件:
- <summary> タグ内では、次を説明してください:
  - タスク完了のために行った手順
  - どのツールを、どの順番で、なぜ使ったか
  - 各ツールに渡した入力
  - 各ツールから得た出力
  - どのようにして回答に到達したかの要約

フィードバック（Feedback）の要件:
- <feedback> タグ内では、ツールに対する建設的なフィードバックを提供してください:
  - ツール名について: 分かりやすく説明的か
  - 入力パラメータについて: ドキュメントは十分か。必須/任意の区別は明確か
  - 説明文について: ツールの動作を正確に説明しているか
  - ツール利用中に遭遇したエラーについて: 実行失敗やトークン過多などはあったか
  - 改善点を具体的に挙げ、なぜ有用か（WHY）も説明する
  - 具体的かつ実行可能な提案にする

回答（Response）の要件:
- 回答は簡潔にし、質問に直接答えてください
- 最終回答は必ず <response> タグで囲んでください
- 解決できない場合は <response>NOT_FOUND</response> を返してください
- 数値回答は数値のみを返してください
- IDはIDのみを返してください
- 名前/テキストは要求された文字列をそのまま返してください
- <response> は最後に置いてください"""


def parse_evaluation_file(file_path: Path) -> list[dict[str, Any]]:
    """qa_pair要素を含むXML評価ファイルをパースします。"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        evaluations = []

        for qa_pair in root.findall(".//qa_pair"):
            question_elem = qa_pair.find("question")
            answer_elem = qa_pair.find("answer")

            if question_elem is not None and answer_elem is not None:
                evaluations.append({
                    "question": (question_elem.text or "").strip(),
                    "answer": (answer_elem.text or "").strip(),
                })

        return evaluations
    except Exception as e:
        print(f"評価ファイルのパースエラー {file_path}: {e}")
        return []


def extract_xml_content(text: str, tag: str) -> str | None:
    """XMLタグから内容を抽出します。"""
    pattern = rf"<{tag}>(.*?)</{tag}>"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches[-1].strip() if matches else None


async def agent_loop(
    client: Anthropic,
    model: str,
    question: str,
    tools: list[dict[str, Any]],
    connection: Any,
) -> tuple[str, dict[str, Any]]:
    """MCPツールを使ってエージェントループを実行します。"""
    messages = [{"role": "user", "content": question}]

    response = await asyncio.to_thread(
        client.messages.create,
        model=model,
        max_tokens=4096,
        system=EVALUATION_PROMPT,
        messages=messages,
        tools=tools,
    )

    messages.append({"role": "assistant", "content": response.content})

    tool_metrics = {}

    while response.stop_reason == "tool_use":
        tool_use = next(block for block in response.content if block.type == "tool_use")
        tool_name = tool_use.name
        tool_input = tool_use.input

        tool_start_ts = time.time()
        try:
            tool_result = await connection.call_tool(tool_name, tool_input)
            tool_response = json.dumps(tool_result) if isinstance(tool_result, (dict, list)) else str(tool_result)
        except Exception as e:
            tool_response = f"ツール実行エラー {tool_name}: {str(e)}\n"
            tool_response += traceback.format_exc()
        tool_duration = time.time() - tool_start_ts

        if tool_name not in tool_metrics:
            tool_metrics[tool_name] = {"count": 0, "durations": []}
        tool_metrics[tool_name]["count"] += 1
        tool_metrics[tool_name]["durations"].append(tool_duration)

        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": tool_response,
            }]
        })

        response = await asyncio.to_thread(
            client.messages.create,
            model=model,
            max_tokens=4096,
            system=EVALUATION_PROMPT,
            messages=messages,
            tools=tools,
        )
        messages.append({"role": "assistant", "content": response.content})

    response_text = next(
        (block.text for block in response.content if hasattr(block, "text")),
        None,
    )
    return response_text, tool_metrics


async def evaluate_single_task(
    client: Anthropic,
    model: str,
    qa_pair: dict[str, Any],
    tools: list[dict[str, Any]],
    connection: Any,
    task_index: int,
) -> dict[str, Any]:
    """指定ツール群で1つのQAペアを評価します。"""
    start_time = time.time()

    print(f"タスク{task_index + 1}: 質問を実行します: {qa_pair['question']}")
    response, tool_metrics = await agent_loop(client, model, qa_pair["question"], tools, connection)

    response_value = extract_xml_content(response, "response")
    summary = extract_xml_content(response, "summary")
    feedback = extract_xml_content(response, "feedback")

    duration_seconds = time.time() - start_time

    return {
        "question": qa_pair["question"],
        "expected": qa_pair["answer"],
        "actual": response_value,
        "score": int(response_value == qa_pair["answer"]) if response_value else 0,
        "total_duration": duration_seconds,
        "tool_calls": tool_metrics,
        "num_tool_calls": sum(len(metrics["durations"]) for metrics in tool_metrics.values()),
        "summary": summary,
        "feedback": feedback,
    }


REPORT_HEADER = """
# 評価レポート

## サマリ

- **Accuracy**: {correct}/{total} ({accuracy:.1f}%)
- **平均タスク所要時間**: {average_duration_s:.2f}s
- **タスクあたり平均ツール呼び出し回数**: {average_tool_calls:.2f}
- **総ツール呼び出し回数**: {total_tool_calls}

---
"""

TASK_TEMPLATE = """
### Task {task_num}

**質問**: {question}
**正解（Ground Truth）**: `{expected_answer}`
**実回答**: `{actual_answer}`
**正誤**: {correct_indicator}
**所要時間**: {total_duration:.2f}s
**ツール呼び出し**: {tool_calls}

**要約**
{summary}

**フィードバック**
{feedback}

---
"""


async def run_evaluation(
    eval_path: Path,
    connection: Any,
    model: str = "claude-3-7-sonnet-20250219",
) -> str:
    """MCPサーバーのツール群で評価を実行します。"""
    print("🚀 評価を開始します")

    client = Anthropic()

    tools = await connection.list_tools()
    print(f"📋 MCPサーバーからツールを{len(tools)}個読み込みました")

    qa_pairs = parse_evaluation_file(eval_path)
    print(f"📋 評価タスクを{len(qa_pairs)}件読み込みました")

    results = []
    for i, qa_pair in enumerate(qa_pairs):
        print(f"タスク処理中 {i + 1}/{len(qa_pairs)}")
        result = await evaluate_single_task(client, model, qa_pair, tools, connection, i)
        results.append(result)

    correct = sum(r["score"] for r in results)
    accuracy = (correct / len(results)) * 100 if results else 0
    average_duration_s = sum(r["total_duration"] for r in results) / len(results) if results else 0
    average_tool_calls = sum(r["num_tool_calls"] for r in results) / len(results) if results else 0
    total_tool_calls = sum(r["num_tool_calls"] for r in results)

    report = REPORT_HEADER.format(
        correct=correct,
        total=len(results),
        accuracy=accuracy,
        average_duration_s=average_duration_s,
        average_tool_calls=average_tool_calls,
        total_tool_calls=total_tool_calls,
    )

    report += "".join([
        TASK_TEMPLATE.format(
            task_num=i + 1,
            question=qa_pair["question"],
            expected_answer=qa_pair["answer"],
            actual_answer=result["actual"] or "N/A",
            correct_indicator="✅" if result["score"] else "❌",
            total_duration=result["total_duration"],
            tool_calls=json.dumps(result["tool_calls"], indent=2),
            summary=result["summary"] or "N/A",
            feedback=result["feedback"] or "N/A",
        )
        for i, (qa_pair, result) in enumerate(zip(qa_pairs, results))
    ])

    return report


def parse_headers(header_list: list[str]) -> dict[str, str]:
    """'Key: Value'形式のヘッダー文字列をdictにパースします。"""
    headers = {}
    if not header_list:
        return headers

    for header in header_list:
        if ":" in header:
            key, value = header.split(":", 1)
            headers[key.strip()] = value.strip()
        else:
            print(f"警告: 不正なヘッダーを無視します: {header}")
    return headers


def parse_env_vars(env_list: list[str]) -> dict[str, str]:
    """'KEY=VALUE'形式の環境変数文字列をdictにパースします。"""
    env = {}
    if not env_list:
        return env

    for env_var in env_list:
        if "=" in env_var:
            key, value = env_var.split("=", 1)
            env[key.strip()] = value.strip()
        else:
            print(f"警告: 不正な環境変数を無視します: {env_var}")
    return env


async def main():
    parser = argparse.ArgumentParser(
        description="テスト質問を使ってMCPサーバーを評価します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  # Evaluate a local stdio MCP server
  python evaluation.py -t stdio -c python -a my_server.py eval.xml

  # Evaluate an SSE MCP server
  python evaluation.py -t sse -u https://example.com/mcp -H "Authorization: Bearer token" eval.xml

  # Evaluate an HTTP MCP server with custom model
  python evaluation.py -t http -u https://example.com/mcp -m claude-3-5-sonnet-20241022 eval.xml
        """,
    )

    parser.add_argument("eval_file", type=Path, help="評価XMLファイルのパス")
    parser.add_argument("-t", "--transport", choices=["stdio", "sse", "http"], default="stdio", help="トランスポート種別（デフォルト: stdio）")
    parser.add_argument("-m", "--model", default="claude-3-7-sonnet-20250219", help="使用するClaudeモデル（デフォルト: claude-3-7-sonnet-20250219）")

    stdio_group = parser.add_argument_group("stdioオプション")
    stdio_group.add_argument("-c", "--command", help="MCPサーバーを起動するコマンド（stdioのみ）")
    stdio_group.add_argument("-a", "--args", nargs="+", help="コマンド引数（stdioのみ）")
    stdio_group.add_argument("-e", "--env", nargs="+", help="環境変数（KEY=VALUE形式、stdioのみ）")

    remote_group = parser.add_argument_group("sse/httpオプション")
    remote_group.add_argument("-u", "--url", help="MCPサーバーURL（sse/httpのみ）")
    remote_group.add_argument("-H", "--header", nargs="+", dest="headers", help="HTTPヘッダー（'Key: Value'形式、sse/httpのみ）")

    parser.add_argument("-o", "--output", type=Path, help="評価レポートの出力先（デフォルト: stdout）")

    args = parser.parse_args()

    if not args.eval_file.exists():
        print(f"エラー: 評価ファイルが見つかりません: {args.eval_file}")
        sys.exit(1)

    headers = parse_headers(args.headers) if args.headers else None
    env_vars = parse_env_vars(args.env) if args.env else None

    try:
        connection = create_connection(
            transport=args.transport,
            command=args.command,
            args=args.args,
            env=env_vars,
            url=args.url,
            headers=headers,
        )
    except ValueError as e:
        print(f"エラー: {e}")
        sys.exit(1)

    print(f"🔗 {args.transport} でMCPサーバーへ接続します...")

    async with connection:
        print("✅ 接続しました")
        report = await run_evaluation(args.eval_file, connection, args.model)

        if args.output:
            args.output.write_text(report)
            print(f"\n✅ レポートを保存しました: {args.output}")
        else:
            print("\n" + report)


if __name__ == "__main__":
    asyncio.run(main())
