"""
embedding.py

Markdownテキストの階層的分割・要約・埋め込み生成を行うモジュール。
PLaMo埋め込みモデルとChatGPT APIを利用。
"""
import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer
from transformers.tokenization_utils_base import PreTrainedTokenizerBase
from transformers.modeling_utils import PreTrainedModel
import re
import json
from pocket_rag.gpt import ask_chatgpt
from pocket_rag.prompt_templates import PROMPT_SUMMARIZE_TEXT
from numpy.typing import NDArray
from typing import List, Dict, Optional, Any


def summarize_text(content: str) -> str:
    """
    テキストを100文字以内で要約する（ChatGPT API利用）
    Args:
        content (str): 要約対象のテキスト
    Returns:
        str: 要約文
    """

    return ask_chatgpt(content, system_prompt=PROMPT_SUMMARIZE_TEXT, model="gpt-4.1-mini")



class Embedding:
    """
    PLaMo埋め込みモデルとChatGPT APIを用いたテキスト分割・要約・埋め込み生成クラス
    """
    tokenizer: PreTrainedTokenizerBase
    model: PreTrainedModel

    def __init__(self) -> None:
        """
        PLaMo埋め込みモデルの初期化
        """
        self.tokenizer = AutoTokenizer.from_pretrained(
            "pfnet/plamo-embedding-1b", trust_remote_code=True
        )
        # Type assertion for model as PreTrainedModel, AutoModel returns PreTrainedModel
        self.model: PreTrainedModel = AutoModel.from_pretrained("pfnet/plamo-embedding-1b", trust_remote_code=True)
        device: str = "cpu"
        self.model = self.model.to(device)

    def generate_embedding(self, text: str) -> NDArray[np.float32]:
        """
        PLaMoモデルを使用してテキストの埋め込みベクトルを生成する
        Args:
            text (str): 埋め込み対象テキスト
        Returns:
            np.ndarray[np.float32]: 埋め込みベクトル
        """
        with torch.inference_mode():
            # Assuming model.encode_document returns a Tensor
            embedding: torch.Tensor = self.model.encode_document([text], self.tokenizer)
            # Squeeze might return a scalar if the tensor becomes 0-dim, but PLaMo embeddings are vectors.
            # Ensuring the return is always NDArray[np.float32]
            squeezed_embedding: np.ndarray = embedding.cpu().numpy().squeeze()
            return squeezed_embedding.astype(np.float32)
        
    def generate_query(self, text: str) -> NDArray[np.float32]:
        """
        PLaMoモデルを使用して検索用ベクトルを生成する
        Args:
            text (str): クエリテキスト
        Returns:
            np.ndarray[np.float32]: 検索用ベクトル
        """
        with torch.inference_mode():
            # Assuming model.encode_query returns a Tensor
            embedding: torch.Tensor = self.model.encode_query([text], self.tokenizer)
            squeezed_embedding: np.ndarray = embedding.cpu().numpy().squeeze()
            return squeezed_embedding.astype(np.float32)

    @staticmethod
    def serialize_vector(vector: NDArray[np.float32]) -> bytes:
        """ベクトルをバイト形式にシリアライズする"""
        return np.asarray(vector).astype(np.float32).tobytes()