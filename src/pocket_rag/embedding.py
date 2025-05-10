import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer
import re
import json
from pocket_rag.gpt import ask_chatgpt

# --- split_text用補助関数 ---
def extract_headings(text):
    """
    Markdownテキストからheading情報を抽出する
    戻り値: [(開始位置, 階層レベル, タイトル), ...]
    """
    heading_pattern = re.compile(r'^(#+) (.*)', re.MULTILINE)
    return [(m.start(), len(m.group(1)), m.group(2)) for m in heading_pattern.finditer(text)]

def summarize_text(content):
    """
    テキストを100文字以内で要約する（ChatGPT API利用）
    """
    summary_prompt = f"次のテキストを100文字以内で要約してください。\n---\n{content}\n---"
    return ask_chatgpt(summary_prompt, system_prompt="あなたは優秀な要約AIです。", model="gpt-4.1-mini")

def split_long_text(content):
    """
    1000文字を超えるテキストを意味のまとまりで分割する（ChatGPT API利用）
    """
    split_prompt = (
        f"次のMarkdownテキストを意味のまとまりで1000文字以下に分割してください。\n\n---\n{content}\n---\n"
        "分割結果はJSONリストで返してください。各要素はtextキーを持つ辞書としてください。"
    )
    split_result = ask_chatgpt(split_prompt, system_prompt="あなたは優秀な文章分割AIです。", model="gpt-4.1-mini")
    return json.loads(split_result)

def build_tree(headings, text, start_idx, end_idx, level):
    """
    headingリストをもとに階層的なまとまりのツリーを構築する
    """
    nodes = []
    idx = start_idx
    while idx < len(headings):
        pos, h_level, h_title = headings[idx]
        if h_level < level:
            break
        if h_level > level:
            idx += 1
            continue
        # 次の同レベルheadingまでの範囲を決定
        next_idx = idx + 1
        while next_idx < len(headings) and headings[next_idx][1] > level:
            next_idx += 1
        content_start = headings[idx][0]
        content_end = headings[next_idx][0] if next_idx < len(headings) else len(text)
        content = text[content_start:content_end].strip()
        # 1000文字超ならchatGPTで分割
        if len(content) > 1000:
            try:
                split_chunks = split_long_text(content)
                children = []
                for chunk in split_chunks:
                    chunk_text = chunk["text"]
                    summary = summarize_text(chunk_text)
                    children.append({"text": chunk_text, "summary": summary, "children": []})
                node = {"text": content, "summary": "", "children": children}
            except Exception as e:
                node = {"text": content, "summary": f"分割失敗: {e}", "children": []}
        else:
            summary = summarize_text(content)
            children = build_tree(headings, text, idx + 1, end_idx, level + 1)
            node = {"text": content, "summary": summary, "children": children}
        nodes.append(node)
        idx = next_idx
    return nodes

class Embedding:
    def __init__(self):
        # PLaMo埋め込みモデルのロード
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
        戻り値はdictのリスト [{'text': ..., 'summary': ..., 'children': [...]}]
        """
        headings = extract_headings(text)  # heading情報を抽出
        return build_tree(headings, text, 0, len(headings), 1)  # 階層ツリーを構築

    def generate_embedding(self, text: str) -> np.ndarray:
        """PLaMoモデルを使用してテキストの埋め込みベクトルを生成する"""
        with torch.inference_mode():
            embedding = self.model.encode_document([text], self.tokenizer)
            return embedding.cpu().numpy().squeeze()
        
    def generate_query(self, text: str) -> np.ndarray:
        """PLaMoモデルを使用して検索用ベクトルを生成する"""
        with torch.inference_mode():
            embedding = self.model.encode_query([text], self.tokenizer)
            return embedding.cpu().numpy().squeeze()
