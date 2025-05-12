"""
embedding.py

Markdownテキストの階層的分割・要約・埋め込み生成を行うモジュール。
PLaMo埋め込みモデルとChatGPT APIを利用。
"""
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer
import re
import json
from pocket_rag.gpt import ask_chatgpt


def summarize_text(content):
    """
    テキストを100文字以内で要約する（ChatGPT API利用）
    Args:
        content (str): 要約対象のテキスト
    Returns:
        str: 要約文
    """

    system_prompt = """
あなたはRAGシステムのための優秀な要約AIです。ユーザーから入力されたテキストから、後続の検索や利用を容易にするために、事実情報を高密度に抽出・要約してください。以下の条件に従ってください。

- 要約は必ず300文字以内に収めてください。
- 文章に含まれる固有名詞（人名、組織名、地名、製品名など）、日時、数値、主要な出来事、具体的な事実関係を可能な限り多く含めてください。
- **最も重要なのは、生成される要約に含まれる情報量（特に抽出されたエンティティや事実）を最大化することです。** 文章としての自然さや文法的な正確さは不必要です。
- 内容に意味がない場合は、要約を生成せず「要約なし」の文字列を返してください。

例：
株式会社ABCは、2023年に新製品「XYZ」を発表。AI技術を活用した自動運転機能を搭載。発表会は東京ビッグサイトで開催、多数のメディアが参加
"""
    return ask_chatgpt(content, system_prompt=system_prompt, model="gpt-4.1-mini")

def split_long_text(content):
    """
    1000文字を超えるテキストを意味のまとまりで分割する（ChatGPT API利用）
    Args:
        content (str): 分割対象のテキスト
    Returns:
        list[dict]: 分割されたテキストのリスト（各要素は{'text': ...}）
    """
    system_prompt = """
あなたは、与えられた長いテキストを、RAGシステムでの利用に適したチャンクに分割するタスクを実行します。

以下のルールに従って分割してください。

-「意味のまとまり」（例: 段落、セクション、リスト項目など）を基本単位として分割してください。
- 各チャンクの文字数は、最大500文字以下としてください。
- 分割後の文章は、分割前とまったく同じ文章を維持するようにしてください。
- 分割されたチャンクのリストをJSON形式で出力してください。各要素は以下の形式の辞書とします。\\`\\`\\`や完了を伝えるメッセージは含めないでください。

```json
{
    chunks: [
        {"text": "分割されたチャンクのテキスト"}
    ]
}
```
"""
    split_result = ask_chatgpt(
        content,
        system_prompt=system_prompt,
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
    )
    return json.loads(split_result)

class Embedding:
    """
    PLaMo埋め込みモデルとChatGPT APIを用いたテキスト分割・要約・埋め込み生成クラス
    """
    def __init__(self):
        """
        PLaMo埋め込みモデルの初期化
        """
        self.tokenizer = AutoTokenizer.from_pretrained(
            "pfnet/plamo-embedding-1b", trust_remote_code=True
        )
        self.model = AutoModel.from_pretrained("pfnet/plamo-embedding-1b", trust_remote_code=True)
        device = "cpu"
        self.model = self.model.to(device)

    def split_text(self, text: str) -> list[dict]:
        """
        Markdownテキストをheadingごとに階層的に分割し、
        1000文字を超える場合はchatGPTで意味のまとまりで分割、
        各まとまりごとに要約文を生成する。
        Args:
            text (str): Markdown形式のテキスト
        Returns:
            list[dict]: 階層的な分割・要約結果
        """
        headings = extract_headings(text)  # heading情報を抽出
        return build_tree(headings, text, 0, len(headings), 1)  # 階層ツリーを構築

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        PLaMoモデルを使用してテキストの埋め込みベクトルを生成する
        Args:
            text (str): 埋め込み対象テキスト
        Returns:
            np.ndarray: 埋め込みベクトル
        """
        with torch.inference_mode():
            embedding = self.model.encode_document([text], self.tokenizer)
            return embedding.cpu().numpy().squeeze()
        
    def generate_query(self, text: str) -> np.ndarray:
        """
        PLaMoモデルを使用して検索用ベクトルを生成する
        Args:
            text (str): クエリテキスト
        Returns:
            np.ndarray: 検索用ベクトル
        """
        with torch.inference_mode():
            embedding = self.model.encode_query([text], self.tokenizer)
            return embedding.cpu().numpy().squeeze()
