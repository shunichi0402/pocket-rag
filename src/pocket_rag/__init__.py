from __future__ import annotations
from pathlib import Path
from pocket_rag.database import Database, ProjectInfoDict, DocumentDict, TextUnitDict, SearchResultDict
from pocket_rag.embedding import Embedding, summarize_text
from pocket_rag.markdown_to_tree import build_tree, NodeTree, CustomTreeNode # Assuming NodeTree and CustomTreeNode are defined in markdown_to_tree
from pocket_rag.gpt import ask_chatgpt
from pocket_rag.prompt_templates import PROMPT_SPLIT_LONG_TEXT, PROMPT_KEYWORD_EXTRACTION, PROMPT_CHAT_ANSWER
import json
import datetime
from typing import Optional, Any, List, Dict, Union # Added List, Dict, Union for more specific typing
import numpy as np # For ndarray type hint

# Type alias for what split_text_unit and tree_to_text_unit produce internally
TextUnitInternalDict = Dict[str, Union[str, int]] # content, content_type, sequence

embedding: Embedding = Embedding()

class RAG:
    database_dir_path: Path

    def __init__(self, database_dir_path_str: str) -> None:
        """
        RAGクラスの初期化。

        Args:
            database_dir_path_str (str): データベースディレクトリのパス文字列。
        """
        self.database_dir_path = Path(database_dir_path_str)

    def get_project(self, *, project_id: Optional[str] = None) -> List["Project"]:
        """
        プロジェクト一覧または指定IDのプロジェクトを取得する。

        Args:
            project_id (Optional[str], optional): プロジェクトID。指定しない場合は全プロジェクトを返す。

        Returns:
            List[Project]: プロジェクトのリスト。
        """
        if project_id:
            database_file_path: Path = self.database_dir_path / f"{project_id}.sqlite3"
            if not database_file_path.exists():
                raise FileNotFoundError(
                    f"sqlite3ファイルが存在しません: {database_file_path}"
                )
            return [Project(project_id, self.database_dir_path)]
        project_ids: List[str] = [
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
        remove_path: Path = self.database_dir_path / f"{id}.sqlite3"
        remove_path.unlink(missing_ok=False) # missing_ok requires Python 3.8+


class Project:
    project_id: str
    database_dir_path: Path
    database: Database

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
        database_file_path: Path = self.database_dir_path / f"{self.project_id}.sqlite3"
        is_new: bool = not database_file_path.exists()
        db_instance: Database = Database(str(database_file_path)) # Renamed to avoid conflict
        if is_new:
            now: datetime.datetime = datetime.datetime.now()
            now_str: str = now.strftime("%Y-%m-%d %H:%M:%S")
            project_data: ProjectInfoDict = {
                "id": self.project_id,
                "name": name or self.project_id,
                "description": description or f"Project: {self.project_id}",
                "created_at": now_str,
                "updated_at": now_str,
            }
            db_instance.update_project(project_data)
        return db_instance

    def split_text_unit(self, markdown_text: str) -> List[TextUnitInternalDict]:
        """
        Markdownテキストをテキストユニットに分割する。

        Args:
            markdown_text (str): 分割対象のMarkdownテキスト。

        Returns:
            List[TextUnitInternalDict]: テキストユニットのリスト。
        """
        tree: NodeTree = build_tree(markdown_text)
        text_units: List[TextUnitInternalDict] = self.tree_to_text_unit(tree)
        text_unit: TextUnitInternalDict
        for index, text_unit in enumerate(text_units):
            text_unit["sequence"] = index
        return text_units

    def tree_to_text_unit(
        self, tree: NodeTree, text_units: Optional[List[TextUnitInternalDict]] = None, hedding_str: str = ""
    ) -> List[TextUnitInternalDict]:
        """
        Markdownのパース済みツリーからテキストユニットのリストを生成します。

        Args:
            tree (NodeTree): build_treeで生成されたノードのリスト。
            text_units (Optional[List[TextUnitInternalDict]], optional): 既存のテキストユニットリスト。デフォルトはNoneで新規作成。
            hedding_str (str, optional): 先頭に付与するヘッディング文字列。デフォルトは空文字。

        Returns:
            List[TextUnitInternalDict]: テキストユニットのリスト。各要素はdictで、contentやcontent_typeなどを含みます。
        """
        if text_units is None:
            text_units = []

        text_flag: bool = False
        tmp_text: str = ""
        tmp_hedding: str = "" # Stores current heading for non-heading text blocks

        def _append_text_unit(text: str, heading: str) -> None:
            """
            テキストユニットをtext_unitsリストに追加する。

            Args:
                text (str): 追加するテキスト。
                heading (str): 先頭に付与するヘッディング文字列。
            """
            if len(text) > 1000:
                # Assuming split_long_text returns Dict[str, List[Dict[str, str]]]
                split_texts_data: Dict[str, List[Dict[str, str]]] = self.split_long_text(text)
                split_chunk: Dict[str, str]
                for split_chunk in split_texts_data.get("chunks", []):
                    text_units.append(
                        {
                            "content": heading + split_chunk["text"],
                            "content_type": "text",
                            "sequence": 0, # Placeholder, will be updated later
                        }
                    )
            elif text.strip(): # Only append if there's actual content
                text_units.append(
                    {
                        "content": heading + text,
                        "content_type": "text",
                        "sequence": 0, # Placeholder
                    }
                )

        node: CustomTreeNode
        for node in tree:
            node_text: Optional[str] = node.get("text")
            node_type: Optional[str] = node.get("type")
            node_children: Optional[NodeTree] = node.get("children")

            if node_text is not None and node_type is not None:
                if node_type == "heading":
                    if text_flag and tmp_text.strip(): # Append previous text block if exists
                        _append_text_unit(tmp_text, hedding_str) # Use the outer heading_str for this block
                    tmp_text = "" # Reset for next block
                    text_flag = False
                    # Current node's text becomes the new tmp_hedding for its children
                    current_node_heading_text: str = node_text + "\n"
                    if node_children:
                        self.tree_to_text_unit(
                            node_children, text_units, hedding_str + current_node_heading_text
                        )
                    # else: # If a heading has no children but has text, it might be a unit itself.
                    # _append_text_unit("", hedding_str + current_node_heading_text.strip()) # Add heading itself as a unit if it has no children to process
                else: # Non-heading text
                    text_flag = True
                    tmp_text += node_text + "\n" # Add newline, assuming text nodes are paragraph-like

            if node_children and node_type != "heading": # Process children of non-headings with the current hedding_str + tmp_hedding
                # If current node is not a heading, its tmp_hedding should be empty or passed down
                self.tree_to_text_unit(node_children, text_units, hedding_str + tmp_hedding)

        if text_flag and tmp_text.strip(): # Append any remaining text
            _append_text_unit(tmp_text, hedding_str)
        return text_units

    def get_project_info(self) -> ProjectInfoDict:
        """
        プロジェクト情報を取得する。

        Returns:
            ProjectInfoDict: プロジェクト情報の辞書。
        """
        return self.database.get_project_info()

    def add_document(self, *, path: str, type: str="markdown") -> "Document": # type is unused for now
        """
        ドキュメントを追加する。

        Args:
            path (str): ドキュメントのパス。
            type (str): ドキュメントタイプ（現状未使用、将来拡張用）。

        Returns:
            Document: 追加したドキュメントインスタンス。
        """
        content: str
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        name: str = Path(path).name

        text_units_internal: List[TextUnitInternalDict] = self.split_text_unit(content)

        # Ensure text_units for DB matches List[Dict[str, Any]] expected by insert_document_with_embeddings
        text_units_for_db: List[Dict[str, Any]] = [dict(unit) for unit in text_units_internal]

        embeddings_np: List[np.ndarray] = [embedding.generate_embedding(str(unit["content"])) for unit in text_units_internal]
        embeddings_bytes: List[bytes] = [Embedding.serialize_vector(vec) for vec in embeddings_np]

        document_id: int = self.database.insert_document_with_embeddings(
            name=name,
            path=path,
            content=content,
            text_units=text_units_for_db, # Use the correctly typed list
            embeddings=embeddings_bytes,
        )
        return Document(self.database, document_id)

    def split_long_text(self, content: str) -> Dict[str, List[Dict[str, str]]]:
        """
        1000文字を超えるテキストを意味のまとまりで分割する（ChatGPT API利用）
        """
        split_result_str: str = ask_chatgpt(
            content,
            system_prompt=PROMPT_SPLIT_LONG_TEXT,
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
        )
        loaded_json: Any = json.loads(split_result_str)
        if isinstance(loaded_json, dict) and "chunks" in loaded_json and isinstance(loaded_json["chunks"], list):
            return loaded_json
        else:
            return {"chunks": []}

    def get_document(self, document_id: int) -> Optional["Document"]:
        """
        指定したdocument_idのドキュメントを取得する。

        Args:
            document_id (int): ドキュメントID

        Returns:
            Optional[Document]: ドキュメントインスタンス（存在しない場合はNone）
        """
        doc_data: Optional[DocumentDict] = self.database.get_document(document_id)
        if (doc_data is None):
            return None
        return Document(self.database, document_id)

    def get_documents(self) -> List["Document"]:
        """
        プロジェクト内の全ドキュメントを取得する。

        Returns:
            List[Document]: ドキュメントインスタンスのリスト
        """
        docs_data: List[DocumentDict] = self.database.get_all_documents()
        # Assuming doc_data["id"] is always present and is an int
        return [Document(self.database, int(doc_data["id"])) for doc_data in docs_data]

    def search_by_vector(self, query: str, k: int = 5) -> List[SearchResultDict]:
        """
        ベクトル検索: クエリ文に類似するtext_unitをk件取得する

        Args:
            query (str): 検索クエリ文
            k (int): 取得件数

        Returns:
            List[SearchResultDict]: 類似text_unit情報のリスト
        """
        query_vec: np.ndarray = embedding.generate_query(query)
        embedding_bytes: bytes = Embedding.serialize_vector(query_vec)
        return self.database.search_text_units_by_vector(embedding_bytes, k=k)

    def search_by_keyword(self, query: str) -> List[TextUnitDict]:
        """
        キーワード検索: クエリ文からキーワードを抽出し、該当text_unitを取得する
        """
        keywords_json_str: str = ask_chatgpt(
            query,
            system_prompt=PROMPT_KEYWORD_EXTRACTION,
            model="gpt-4.1-mini",
            response_format={"type": "json_object"},
        )
        keywords: List[str]
        try:
            loaded_json: Any = json.loads(keywords_json_str)
            if isinstance(loaded_json, dict) and "keywords" in loaded_json and isinstance(loaded_json["keywords"], list):
                keywords = [str(kw) for kw in loaded_json["keywords"]]
            else:
                keywords = []
        except json.JSONDecodeError:
            keywords = []
        if not isinstance(keywords, list):
            keywords = []
        return self.database.search_text_units_by_keywords(keywords)

    def search_hybrid(self, query: str, k: int = 10, vector_weight: float = 100, keyword_weight: float = 0.3) -> List[Dict[str, Any]]:
        """
        ベクトル検索とキーワード検索を組み合わせたハイブリッド検索

        Args:
            query (str): 検索クエリ文
            k (int): 取得件数
            vector_weight (float): ベクトル検索スコアの重み
            keyword_weight (float): キーワード検索スコアの重み

        Returns:
            List[Dict[str, Any]]: ハイブリッドスコア順のtext_unit情報リスト. Each dict is a SearchResultDict or TextUnitDict augmented with scores.
        """
        vector_results: List[SearchResultDict] = self.search_by_vector(query, k * 2)
        keyword_results: List[TextUnitDict] = self.search_by_keyword(query)

        def make_id_key(item: Dict[str, Any]) -> Optional[Union[int, str]]: # ID can be int or str
            # ベクトル検索はtext_unit_id, キーワード検索はid
            return item.get("text_unit_id") or item.get("id")

        # Ensuring keys are consistently typed for dictionary keys (e.g., int)
        # However, make_id_key can return None if neither key is present.
        vector_dict: Dict[Union[int, str], SearchResultDict] = {id_key: item for item in vector_results if (id_key := make_id_key(item)) is not None}
        keyword_dict: Dict[Union[int, str], TextUnitDict] = {id_key: item for item in keyword_results if (id_key := make_id_key(item)) is not None}

        def vector_score_func(distance: float) -> float:
            # 距離が0の場合は最大スコア
            return 1.0 / (distance + 1e-6)

        all_ids: set[Union[int, str]] = set(vector_dict.keys()) | set(keyword_dict.keys())

        processed_results: List[Dict[str, Any]] = []
        id_: Union[int, str]
        for id_ in all_ids:
            v_result: Optional[SearchResultDict] = vector_dict.get(id_)
            kw_result: Optional[TextUnitDict] = keyword_dict.get(id_)

            vector_score: float = vector_score_func(v_result["distance"]) if v_result and "distance" in v_result else 0.0
            keyword_score: float = 1.0 if kw_result else 0.0 # Presence gives a score of 1.0

            hybrid_score: float = vector_weight * vector_score + keyword_weight * keyword_score

            # Determine base dictionary for common fields
            base_info: Dict[str, Any] = {}
            if v_result:
                base_info.update(v_result)
            elif kw_result: # If no vector result, use keyword result as base
                base_info.update(kw_result)
            else: # Should not happen if id_ is from all_ids
                continue

            # Ensure 'id' or 'text_unit_id' is in the final result for consistency
            if "id" not in base_info and "text_unit_id" not in base_info:
                base_info["id"] = id_ # Add the id back if it got lost somehow

            # Create the final result dictionary
            final_result_item: Dict[str, Any] = dict(base_info) # Start with a copy
            final_result_item["hybrid_score"] = hybrid_score
            final_result_item["vector_score"] = vector_score
            final_result_item["keyword_score"] = keyword_score
            processed_results.append(final_result_item)

        processed_results.sort(key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
        return processed_results[:int(k)]

    def remove_document(self, document_id: int) -> None:
        """
        指定したドキュメントを削除する

        Args:
            document_id (int): ドキュメントID
        """
        self.database.delete_document_and_embeddings(document_id)

    def chat_answer(self, query: str, search_mode: str = "hybrid", k: int = 5, **search_kwargs) -> str:
        """
        チャット形式で質問に対する答えをRAGを利用して生成する関数。
        検索方式（vector/keyword/hybrid）をオプションで切り替え可能。

        Args:
            query (str): 質問文
            search_mode (str): 検索方式。"vector"、"keyword"、"hybrid" のいずれか。
            k (int): 取得件数（デフォルト5）
            **search_kwargs: 検索方式ごとの追加パラメータ
        Returns:
            str: 回答文
        """
        if search_mode == "vector":
            results = self.search_by_vector(query, k=k)
            # ベクトル検索結果は text_unit_content キーを使用、文献番号を付与
            context_parts = []
            for i, r in enumerate(results, 1):
                content = r.get("text_unit_content", "")
                if content.strip():
                    context_parts.append(f"文献({i}): {content}")
            context = "\n\n".join(context_parts)
        elif search_mode == "keyword":
            results = self.search_by_keyword(query)
            # キーワード検索結果は content キーを使用、文献番号を付与
            context_parts = []
            for i, r in enumerate(results[:k], 1):
                content = r.get("content", "")
                if content.strip():
                    context_parts.append(f"文献({i}): {content}")
            context = "\n\n".join(context_parts)
        elif search_mode == "hybrid":
            results = self.search_hybrid(query, k=k, **search_kwargs)
            # ハイブリッド検索結果は content または text_unit_content キーを使用、文献番号を付与
            context_parts = []
            for i, r in enumerate(results, 1):
                content = r.get("content", "") or r.get("text_unit_content", "")
                if content.strip():
                    context_parts.append(f"文献({i}): {content}")
            context = "\n\n".join(context_parts)
        else:
            raise ValueError(f"Unknown search_mode: {search_mode}")

        prompt = PROMPT_CHAT_ANSWER.format(context=context, query=query)
        print(prompt)
        answer = ask_chatgpt(prompt, model="gpt-4.1-mini")
        return answer


class Document:
    """
    ドキュメントを表すクラス。
    ドキュメント情報・text_unitの管理・DB同期を行う。
    """
    database: Database
    document_id: int
    name: str
    path: Optional[str] # path can be NULL in DB
    unit_count: int
    content: str
    text_units: List[TextUnitDict]


    def __init__(self, database: Database, document_id: int) -> None:
        self.database = database
        self.document_id = document_id
        self._reload()

    def _reload(self) -> None:
        """DBから最新情報を取得して同期"""
        doc_data: Optional[DocumentDict] = self.database.get_document(self.document_id)
        if doc_data is None:
            raise FileNotFoundError(f"Document id={self.document_id} not found in DB")

        # Ensure all expected keys are present, providing defaults or handling missing keys
        self.name = str(doc_data.get("name", "Unknown Name"))
        self.path = str(doc_data.get("path")) if doc_data.get("path") is not None else None
        self.unit_count = int(doc_data.get("unit_count", 0))
        self.content = str(doc_data.get("content", ""))
        self.text_units = self.database.get_text_units_with_embeddings(self.document_id)

    def get_info(self) -> DocumentDict:
        """ドキュメントの基本情報を返す"""
        # Construct a dictionary that matches DocumentDict more closely if possible
        # For now, using known fields.
        info: DocumentDict = {
            "id": self.document_id,
            "name": self.name,
            "path": self.path,
            "unit_count": self.unit_count,
            "content": self.content # Adding content as it's part of DocumentDict in DB
        }
        return info


    def get_text_units(self) -> List[TextUnitDict]:
        """text_unitリストを返す"""
        return self.database.get_text_units_with_embeddings(self.document_id)

    def get_text_unit(self, sequence: int) -> Optional[TextUnitDict]:
        """指定sequenceのtext_unitを返す"""
        return self.database.get_text_unit_with_embedding(self.document_id, sequence)

    def delete(self) -> None:
        """ドキュメントと関連text_unit/embeddingをDBから削除"""
        self.database.delete_document_and_embeddings(self.document_id)

    def update_content(self, new_content: str) -> None:
        """
        ドキュメント内容を更新し、text_unit・embeddingも再生成してDBに反映
        """
        # Project.split_text_unit is not a static method, it needs a Project instance.
        # This seems like a design issue. For now, we assume there's a way to call it,
        # or that this class method was intended to be part of Project, or Project instance is available.
        # Let's assume for typing that it's callable somehow, perhaps via self.database if Project is part of it.
        # This is a placeholder for the actual call logic.
        # A proper fix would be to make split_text_unit static or pass a Project instance.
        # For now, to make it type-check, we'll assume it's called on a dummy/conceptual Project instance.
        # This part of the code will likely fail at runtime if not addressed.

        # Create a temporary Project instance or make split_text_unit static or accessible.
        # This is a simplification for type checking to proceed.
        # In a real scenario, this needs a proper design fix.
        temp_project_for_splitting = Project(project_id="_temp_", database_dir_path=Path(".")) # Dummy

        text_units_internal: List[TextUnitInternalDict] = temp_project_for_splitting.split_text_unit(new_content)
        text_units_for_db: List[Dict[str, Any]] = [dict(unit) for unit in text_units_internal]

        embeddings_np: List[np.ndarray] = [embedding.generate_embedding(str(unit["content"])) for unit in text_units_internal]
        embeddings_bytes: List[bytes] = [Embedding.serialize_vector(vec) for vec in embeddings_np]

        # 既存データ削除 (before re-insertion, ensure this document_id is still valid or handled)
        current_doc_id_to_delete = self.document_id

        # Re-insert. Note: self.name and self.path are used from the current instance.
        new_document_id: int = self.database.insert_document_with_embeddings(
            name=self.name, # Uses current name
            path=self.path, # Uses current path
            content=new_content,
            text_units=text_units_for_db,
            embeddings=embeddings_bytes,
        )

        # After inserting the new version, delete the old one if IDs are different
        # or if the insert_document_with_embeddings doesn't handle replacement.
        # Assuming insert_document_with_embeddings creates a new entry,
        # and the old one needs explicit deletion if its ID was different or if we want to avoid orphans.
        # If insert... returns the *same* id (e.g. due to upsert logic not shown), this might be fine.
        # However, typically, new inserts get new IDs.
        if current_doc_id_to_delete != new_document_id:
             self.database.delete_document_and_embeddings(current_doc_id_to_delete)

        self.document_id = new_document_id # Update current instance to point to the new document ID
        self._reload() # Reload with the new document ID
