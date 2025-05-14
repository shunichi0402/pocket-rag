from __future__ import annotations
from pathlib import Path
from pocket_rag.database import Database
from pocket_rag.embedding import Embedding, summarize_text
from pocket_rag.markdown_to_tree import build_tree
from pocket_rag.gpt import ask_chatgpt
import json
import datetime
from typing import Optional, Any


embedding = Embedding()

class RAG:
    def __init__(self, database_dir_path_str: str) -> None:
        """
        RAGクラスの初期化。

        Args:
            database_dir_path_str (str): データベースディレクトリのパス文字列。
        """
        self.database_dir_path = Path(database_dir_path_str)

    def get_project(self, *, project_id: Optional[str] = None) -> list["Project"]:
        """
        プロジェクト一覧または指定IDのプロジェクトを取得する。

        Args:
            project_id (Optional[str], optional): プロジェクトID。指定しない場合は全プロジェクトを返す。

        Returns:
            list[Project]: プロジェクトのリスト。
        """
        if project_id:
            database_file_path = self.database_dir_path / f"{project_id}.sqlite3"
            if not database_file_path.exists():
                raise FileNotFoundError(
                    f"sqlite3ファイルが存在しません: {database_file_path}"
                )
            return [Project(project_id, self.database_dir_path)]
        project_ids = [
            f.stem
            for f in self.database_dir_path.iterdir()
            if f.is_file() and f.suffix == ".sqlite3"
        ]
        return [Project(pid, self.database_dir_path) for pid in project_ids]

    def add_project(
        self, id: str, *, name: Optional[str] = None, description: Optional[str] = None
    ) -> "Project":
        """
        プロジェクトを追加する。既に存在する場合は既存のプロジェクトを返す。

        Args:
            id (str): プロジェクトID。
            name (Optional[str], optional): プロジェクト名。
            description (Optional[str], optional): プロジェクト説明。

        Returns:
            Project: 追加または取得したプロジェクト。
        """
        return Project(id, self.database_dir_path, name=name, description=description)

    def remove_project(self, id: str) -> None:
        """
        プロジェクトを削除する。

        Args:
            id (str): プロジェクトID。
        """
        remove_path = self.database_dir_path / f"{id}.sqlite3"
        remove_path.unlink(missing_ok=False)


class Project:
    def __init__(
        self,
        project_id: str,
        database_dir_path: Path,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Projectクラスの初期化。

        Args:
            project_id (str): プロジェクトID。
            database_dir_path (Path): データベースディレクトリのパス。
            name (Optional[str], optional): プロジェクト名。
            description (Optional[str], optional): プロジェクト説明。
        """
        self.project_id = project_id
        self.database_dir_path = database_dir_path
        self.database = self._setup_project(name, description)

    def _setup_project(
        self, name: Optional[str], description: Optional[str]
    ) -> Database:
        """
        プロジェクト用のデータベースをセットアップする。

        Args:
            name (Optional[str]): プロジェクト名。
            description (Optional[str]): プロジェクト説明。

        Returns:
            Database: セットアップ済みのDatabaseインスタンス。
        """
        database_file_path = self.database_dir_path / f"{self.project_id}.sqlite3"
        is_new = not database_file_path.exists()
        database = Database(str(database_file_path))
        if is_new:
            now = datetime.datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            database.update_project(
                {
                    "id": self.project_id,
                    "name": name or self.project_id,
                    "description": description or f"Project: {self.project_id}",
                    "created_at": now_str,
                    "updated_at": now_str,
                }
            )
        return database

    def split_text_unit(self, markdown_text: str) -> list[dict[str, Any]]:
        """
        Markdownテキストをテキストユニットに分割する。

        Args:
            markdown_text (str): 分割対象のMarkdownテキスト。

        Returns:
            list[dict[str, Any]]: テキストユニットのリスト。
        """
        tree = build_tree(markdown_text)
        text_units = self.tree_to_text_unit(tree)
        for index, text_unit in enumerate(text_units):
            text_unit["sequence"] = index
        return text_units

    def tree_to_text_unit(
        self, tree: list, text_units: Optional[list] = None, hedding_str: str = ""
    ) -> list:
        """
        Markdownのパース済みツリーからテキストユニットのリストを生成します。

        Args:
            tree (list): build_treeで生成されたノードのリスト。
            text_units (Optional[list], optional): 既存のテキストユニットリスト。デフォルトはNoneで新規作成。
            hedding_str (str, optional): 先頭に付与するヘッディング文字列。デフォルトは空文字。

        Returns:
            list: テキストユニットのリスト。各要素はdictで、contentやcontent_typeなどを含みます。
        """
        if text_units is None:
            text_units = []
        text_flag = False
        tmp_text = ""
        tmp_hedding = ""

        def _append_text_unit(text, heading):
            """
            テキストユニットをtext_unitsリストに追加する。

            Args:
                text (str): 追加するテキスト。
                heading (str): 先頭に付与するヘッディング文字列。
            """
            if len(text) > 1000:
                split_texts = self.split_long_text(text)
                for split_text in split_texts["chunks"]:
                    text_units.append(
                        {
                            "content": heading + split_text["text"],
                            "content_type": "text",
                            "sequence": 0,
                        }
                    )
            else:
                text_units.append(
                    {
                        "content": heading + text,
                        "content_type": "text",
                        "sequence": 0,
                    }
                )

        for node in tree:
            if "text" in node and "type" in node:
                if node["type"] == "heading":
                    if text_flag:
                        _append_text_unit(tmp_text, hedding_str)
                    tmp_text = ""
                    text_flag = False
                    tmp_hedding = node["text"] + "\n"
                    # headingの場合は子ノード処理へ進む
                    if "children" in node:
                        self.tree_to_text_unit(
                            node["children"], text_units, hedding_str + tmp_hedding
                        )
                    continue
                # heading以外
                text_flag = True
                tmp_text += node["text"]
            if "children" in node:
                self.tree_to_text_unit(
                    node["children"], text_units, hedding_str + tmp_hedding
                )
        if text_flag:
            _append_text_unit(tmp_text, hedding_str)
        return text_units

    def get_project_info(self) -> dict[str, str]:
        """
        プロジェクト情報を取得する。

        Returns:
            dict[str, str]: プロジェクト情報の辞書。
        """
        return self.database.get_project_info()

    def add_document(self, *, path: str, type: str="markdown") -> "Document":
        """
        ドキュメントを追加する。

        Args:
            path (str): ドキュメントのパス。
            type (str): ドキュメントタイプ（現状未使用、将来拡張用）。

        Returns:
            Document: 追加したドキュメントインスタンス。
        """
        # マークダウンファイル読み込み
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        name = Path(path).name
        # テキストユニット分割
        text_units = self.split_text_unit(content)
        # 埋め込み生成
        embeddings = [embedding.generate_embedding(unit["content"]) for unit in text_units]
        # バイト列に変換
        embeddings_bytes = [Embedding.serialize_vector(vec) for vec in embeddings]
        # DB登録
        document_id = self.database.insert_document_with_embeddings(
            name=name,
            path=path,
            content=content,
            text_units=text_units,
            embeddings=embeddings_bytes,
        )
        return Document(self.database, document_id)

    def split_long_text(self, content: str) -> dict:
        """
        1000文字を超えるテキストを意味のまとまりで分割する（ChatGPT API利用）

        Args:
            content (str): 分割対象のテキスト

        Returns:
            dict: {"chunks": [{"text": ...}, ...]}
        """
        system_prompt = """
あなたは、与えられた長いテキストを、RAGシステムでの利用に適したチャンクに分割するタスクを実行します。

以下のルールに従って分割してください。

-「意味のまとまり」（例: 同じ話題、同じトピック、同じ段落）を基本単位として分割してください。
- 各チャンクの文字数は、最大1000文字以下としてください。
- 「文字数の制限」と「意味のまとまりの制限」を満たす中で、なるべく少ないチャンク数になるように分割してください。
- 分割後の文章は、分割前とまったく同じ文章を維持するようにしてください。
- 分割されたチャンクのリストをJSON形式で出力してください。

```json
{chunks: [
    {"text": "分割されたチャンクのテキスト"}
]}
```
        """
        split_result = ask_chatgpt(
            content,
            system_prompt=system_prompt,
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
        )
        return json.loads(split_result)

    def get_document(self, document_id: int) -> "Document | None":
        """
        指定したdocument_idのドキュメントを取得する。

        Args:
            document_id (int): ドキュメントID

        Returns:
            Document | None: ドキュメントインスタンス（存在しない場合はNone）
        """
        doc = self.database.get_document(document_id)
        if (doc is None):
            return None
        return Document(self.database, document_id)

    def get_documents(self) -> list["Document"]:
        """
        プロジェクト内の全ドキュメントを取得する。

        Returns:
            list[Document]: ドキュメントインスタンスのリスト
        """
        docs = self.database.get_all_documents()
        return [Document(self.database, doc["id"]) for doc in docs]

    def search_by_vector(self, query: str, k: int = 5) -> list[dict]:
        """
        ベクトル検索: クエリ文に類似するtext_unitをk件取得する

        Args:
            query (str): 検索クエリ文
            k (int): 取得件数

        Returns:
            list[dict]: 類似text_unit情報のリスト
        """
        query_vec = embedding.generate_query(query)
        embedding_bytes = Embedding.serialize_vector(query_vec)
        return self.database.search_text_units_by_vector(embedding_bytes, k=k)

    def search_by_keyword(self, query: str) -> list[dict]:
        """
        キーワード検索: クエリ文からキーワードを抽出し、該当text_unitを取得する

        Args:
            query (str): 検索クエリ文

        Returns:
            list[dict]: 該当text_unit情報のリスト
        """
        # ChatGPTでキーワード抽出
        system_prompt = """
あなたはRAG（Retrieval-Augmented Generation）システムのためのキーワード抽出AIです。ユーザーが知りたいこと・質問の要点を正確に捉え、検索に有用な日本語キーワードを5個程度抽出してください。
抽出するキーワードは、質問の主題や知りたい内容の要点を必ず含めてください。
出力は厳格に以下のJSONオブジェクト形式で返してください。
例: { "keywords": ["AI", "自動運転", "製品名"] }
"""
        keywords_json = ask_chatgpt(
            query,
            system_prompt=system_prompt,
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
        )
        try:
            keywords = json.loads(keywords_json)["keywords"]
            print(keywords)
        except Exception:
            keywords = []
        if not isinstance(keywords, list):
            keywords = []
        return self.database.search_text_units_by_keywords(keywords)

    def search_hybrid(self, query: str, k: int = 10, vector_weight: float = 100, keyword_weight: float = 0.3) -> list[dict]:
        """
        ベクトル検索とキーワード検索を組み合わせたハイブリッド検索

        Args:
            query (str): 検索クエリ文
            k (int): 取得件数
            vector_weight (float): ベクトル検索スコアの重み
            keyword_weight (float): キーワード検索スコアの重み

        Returns:
            list[dict]: ハイブリッドスコア順のtext_unit情報リスト
        """
        # ベクトル検索
        vector_results = self.search_by_vector(query, k * 2)
        # キーワード検索
        keyword_results = self.search_by_keyword(query)

        # idでマージするためのdict化
        def make_id_key(item):
            # ベクトル検索はtext_unit_id, キーワード検索はid
            return item.get("text_unit_id") or item.get("id")

        vector_dict = {make_id_key(item): item for item in vector_results}
        keyword_dict = {make_id_key(item): item for item in keyword_results}

        # ベクトルスコア: 距離が小さいほどスコアが高い（正規化せず逆数で比較）
        def vector_score_func(distance):
            # 距離が0の場合は最大スコア
            return 1.0 / (distance + 1e-6)

        all_ids = set(vector_dict.keys()) | set(keyword_dict.keys())
        results = []
        for id_ in all_ids:
            v = vector_dict.get(id_)
            keyword_hit = keyword_dict.get(id_)
            vector_score = vector_score_func(v["distance"]) if v else 0.0
            keyword_score = 1.0 if keyword_hit else 0.0
            hybrid_score = vector_weight * vector_score + keyword_weight * keyword_score
            base = v if v else keyword_hit
            result = dict(base)
            result["hybrid_score"] = hybrid_score
            result["vector_score"] = vector_score
            result["keyword_score"] = keyword_score
            results.append(result)

        results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        # kがintでない場合に備えて明示的にint変換
        return results[:int(k)]

    def remove_document(self, document_id: int) -> None:
        """
        指定したドキュメントを削除する

        Args:
            document_id (int): ドキュメントID
        """
        self.database.delete_document_and_embeddings(document_id)


class Document:
    """
    ドキュメントを表すクラス。
    ドキュメント情報・text_unitの管理・DB同期を行う。
    """
    def __init__(self, database: Database, document_id: int):
        self.database = database
        self.document_id = document_id
        self._reload()

    def _reload(self):
        """DBから最新情報を取得して同期"""
        doc = self.database.get_document(self.document_id)
        if doc is None:
            raise FileNotFoundError(f"Document id={self.document_id} not found in DB")
        self.name = doc["name"]
        self.path = doc["path"]
        self.unit_count = doc["unit_count"]
        self.content = doc["content"]
        self.text_units = self.database.get_text_units_with_embeddings(self.document_id)

    def get_info(self) -> dict:
        """ドキュメントの基本情報を返す"""
        return {
            "id": self.document_id,
            "name": self.name,
            "path": self.path,
            "unit_count": self.unit_count,
        }

    def get_text_units(self) -> list[dict]:
        """text_unitリストを返す"""
        return self.database.get_text_units_with_embeddings(self.document_id)

    def get_text_unit(self, sequence: int) -> dict | None:
        """指定sequenceのtext_unitを返す"""
        return self.database.get_text_unit_with_embedding(self.document_id, sequence)

    def delete(self):
        """ドキュメントと関連text_unit/embeddingをDBから削除"""
        self.database.delete_document_and_embeddings(self.document_id)

    def update_content(self, new_content: str):
        """
        ドキュメント内容を更新し、text_unit・embeddingも再生成してDBに反映
        """
        # テキストユニット分割
        text_units = Project.split_text_unit(self, new_content)
        # 埋め込み生成
        embeddings = [embedding.generate_embedding(unit["content"]) for unit in text_units]
        embeddings_bytes = [Embedding.serialize_vector(vec) for vec in embeddings]
        # 既存データ削除
        self.delete()
        # 再登録
        document_id = self.database.insert_document_with_embeddings(
            name=self.name,
            path=self.path,
            content=new_content,
            text_units=text_units,
            embeddings=embeddings_bytes,
        )
        self.document_id = document_id
        self._reload()
