from __future__ import annotations
from collections import defaultdict
import sqlite3
import sqlite_vec
from typing import List, Dict, Optional, Tuple, Any

# Type Aliases
Row = Tuple[Any, ...] # Generic database row
ProjectInfoDict = Dict[str, str]
DocumentDict = Dict[str, Any] # Could be a TypedDict for more precision
TextUnitDict = Dict[str, Any]  # Could be a TypedDict for more precision
SearchResultDict = Dict[str, Any] # For search results


class Database:
    def __init__(self, database_path: str) -> None:
        self.database_path: str = database_path
        self._setup_database()

    def _connect_db(self) -> sqlite3.Connection:
        """データベースに接続する"""
        conn: sqlite3.Connection = sqlite3.connect(self.database_path, timeout=10)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)

        return conn

    def _setup_database(self) -> None:
        """データベーステーブルの初期設定"""

        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()
        # project info
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS "project_info"(
                "key" TEXT PRIMARY KEY,
                "value" TEXT NOT NULL
            );
            """
        )
        # documents
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS "documents"(
                "id" INTEGER PRIMARY KEY,
                "name" TEXT NOT NULL,
                "path" TEXT,
                "unit_count" INTEGER NOT NULL,
                "content" TEXT NOT NULL
            );
            """
        )
        # text_units
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS "text_units"(
                "id" INTEGER PRIMARY KEY,
                "document_id" INTEGER NOT NULL,
                "sequence" INTEGER NOT NULL,
                "content" TEXT NOT NULL,
                "content_type" TEXT NOT NULL
            );
            """
        )
        # test_unit_embeddings
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS "text_units_vec" USING vec0(
                embedding float[2048]
            );
            """
        )

        conn.commit()
        conn.close()

    def update_project(self, params: ProjectInfoDict) -> None:
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()

        for key, value in params.items():
            cursor.execute('INSERT OR REPLACE INTO "project_info" (key, value) VALUES (?, ?);', (key, value))

        conn.commit()
        conn.close()

    def get_project_info(self) -> ProjectInfoDict:
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()

        cursor.execute('SELECT * FROM "project_info";')
        rows: List[Tuple[str, str]] = cursor.fetchall() # key, value are both TEXT
        result: ProjectInfoDict = {}

        for row in rows:
            result[row[0]] = row[1]

        conn.commit() # Not strictly necessary for SELECT, but doesn't hurt.
        conn.close()
        return result

    def get_document(self, document_id: int) -> Optional[DocumentDict]:
        """
        指定したdocument_idのドキュメントを取得する
        """
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, path, unit_count, content FROM "documents" WHERE id = ?;',
            (document_id,)
        )
        row: Optional[Tuple[int, str, Optional[str], int, str]] = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "path": row[2],
                "unit_count": row[3],
                "content": row[4],
            }
        else:
            return None

    def get_all_documents(self) -> List[DocumentDict]:
        """
        すべてのドキュメントを取得する
        """
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, path, unit_count, content FROM "documents";'
        )
        rows: List[Tuple[int, str, Optional[str], int, str]] = cursor.fetchall()
        conn.close()
        return [
            {
                "id": row[0],
                "name": row[1],
                "path": row[2],
                "unit_count": row[3],
                "content": row[4],
            }
            for row in rows
        ]

    def get_text_units_with_embeddings(self, document_id: int) -> List[TextUnitDict]:
        """
        指定したドキュメントのすべてのtext_unitsとその埋め込みベクトルを取得する
        """
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT tu.id, tu.document_id, tu.sequence, tu.content, tu.content_type, tuv.embedding
            FROM text_units tu
            LEFT JOIN text_units_vec tuv ON tu.id = tuv.rowid
            WHERE tu.document_id = ?
            ORDER BY tu.sequence ASC
            ''',
            (document_id,)
        )
        rows: List[Tuple[int, int, int, str, str, Optional[bytes]]] = cursor.fetchall()
        conn.close()
        return [
            {
                "id": row[0],
                "document_id": row[1],
                "sequence": row[2],
                "content": row[3],
                "content_type": row[4],
                "embedding": row[5],  # Noneの場合もあり
            }
            for row in rows
        ]

    def get_text_unit_with_embedding(self, document_id: int, sequence: int) -> Optional[TextUnitDict]:
        """
        指定したドキュメントの指定したsequenceのtext_unitとその埋め込みベクトルを取得する
        """
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT tu.id, tu.document_id, tu.sequence, tu.content, tu.content_type, tuv.embedding
            FROM text_units tu
            LEFT JOIN text_units_vec tuv ON tu.id = tuv.rowid
            WHERE tu.document_id = ? AND tu.sequence = ?
            ''',
            (document_id, sequence)
        )
        row: Optional[Tuple[int, int, int, str, str, Optional[bytes]]] = cursor.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "document_id": row[1],
                "sequence": row[2],
                "content": row[3],
                "content_type": row[4],
                "embedding": row[5],  # Noneの場合もあり
            }
        else:
            return None

    def insert_document_with_embeddings(
        self,
        name: str,
        path: Optional[str], # Changed from str | None
        content: str,
        text_units: List[Dict[str, Any]], # Specific TypedDict would be better
        embeddings: List[bytes]
    ) -> int:
        """
        ドキュメント・text_units・埋め込みベクトルをまとめて登録する
        text_units: [{ "sequence": int, "content": str, "content_type": str }]
        embeddings: [bytes]  # text_unitsと同じ順序
        戻り値: 登録したドキュメントのid
        """
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()

        # ドキュメント登録
        cursor.execute(
            '''
            INSERT INTO documents (name, path, unit_count, content)
            VALUES (?, ?, ?, ?)
            ''',
            (name, path, len(text_units), content)
        )
        # cursor.lastrowid is Optional[int], but after a successful INSERT, it should be an int.
        # If an error occurred, an exception would likely be raised before this point.
        doc_id: Optional[int] = cursor.lastrowid
        if doc_id is None:
            # This case should ideally not happen if the INSERT was successful
            # and the table has an autoincrementing primary key.
            # Handling it defensively.
            conn.rollback()
            conn.close()
            raise sqlite3.Error("Failed to retrieve document_id after insert.")
        document_id: int = doc_id


        # text_units登録
        text_unit_ids: List[int] = []
        unit: Dict[str, Any]
        for unit in text_units: # removed enumerate as i is not used
            cursor.execute(
                '''
                INSERT INTO text_units (document_id, sequence, content, content_type)
                VALUES (?, ?, ?, ?)
                ''',
                (document_id, unit["sequence"], unit["content"], unit["content_type"])
            )
            tu_id: Optional[int] = cursor.lastrowid
            if tu_id is None:
                conn.rollback()
                conn.close()
                raise sqlite3.Error("Failed to retrieve text_unit_id after insert.")
            text_unit_ids.append(tu_id)

        # text_units_vec（埋め込み）登録
        rowid: int
        embedding_bytes: bytes # Renamed from embedding to avoid conflict
        for rowid, embedding_bytes in zip(text_unit_ids, embeddings):
            cursor.execute(
                '''
                INSERT INTO text_units_vec (rowid, embedding) VALUES (?, ?)
                ''',
                (rowid, embedding_bytes)
            )

        conn.commit()
        conn.close()
        return document_id

    def delete_document_and_embeddings(self, document_id: int) -> None:
        """
        指定したドキュメントとその関連text_units・埋め込みをすべて削除する
        """
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()

        # 関連するtext_unitのidを取得
        cursor.execute(
            'SELECT id FROM text_units WHERE document_id = ?',
            (document_id,)
        )
        text_unit_ids: List[int] = [row[0] for row in cursor.fetchall()]

        # text_units_vec（埋め込み）削除
        tu_id: int
        for tu_id in text_unit_ids:
            cursor.execute(
                'DELETE FROM text_units_vec WHERE rowid = ?',
                (tu_id,)
            )

        # text_units削除
        cursor.execute(
            'DELETE FROM text_units WHERE document_id = ?',
            (document_id,)
        )

        # documents削除
        cursor.execute(
            'DELETE FROM documents WHERE id = ?',
            (document_id,)
        )

        conn.commit()
        conn.close()

    def search_text_units_by_vector(self, embedding: bytes, k: int = 5) -> List[SearchResultDict]:
        """
        ベクトル検索: embeddingベクトルに類似するtext_unitをk件取得する
        """
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute(
            """
            SELECT text_units_vec.rowid, text_units_vec.distance, tu.content, d.content
            FROM text_units_vec
            JOIN text_units tu ON text_units_vec.rowid = tu.id
            JOIN documents d ON tu.document_id = d.id
            WHERE text_units_vec.embedding MATCH ? AND k = ?
            ORDER BY text_units_vec.distance ASC
            """,  # Corrected: MATCH, not match. k = ? might be sqlite-vec specific syntax or needs to be part of MATCH. Assuming it's correct.
            (embedding, k),
        )
        # Assuming rowid is int, distance is float, content is str
        rows: List[Tuple[int, float, str, str]] = cursor.fetchall()
        conn.close()
        return [
            {
                "text_unit_id": row[0],
                "distance": row[1],
                "text_unit_content": row[2],
                "document_content": row[3],
            }
            for row in rows
        ]

    def search_text_units_by_keywords(self, keywords: List[str]) -> List[TextUnitDict]:
        """
        キーワード検索: 指定キーワードが含まれるtext_unitを取得する
        """
        conn: sqlite3.Connection = self._connect_db()
        cursor: sqlite3.Cursor = conn.cursor()
        # OR検索 based on original code: any keyword matches
        where_clause: str = " OR ".join(["tu.content LIKE ?" for _ in keywords])
        params: List[str] = [f"%{kw}%" for kw in keywords]

        # Ensure keywords list is not empty to prevent SQL syntax error with empty WHERE clause
        if not keywords:
            conn.close()
            return []

        sql: str = f'''
            SELECT tu.id, tu.document_id, tu.sequence, tu.content, tu.content_type
            FROM text_units tu
            WHERE {where_clause}
            ORDER BY tu.document_id, tu.sequence
            '''
        # print(sql) # Original code had a print here, kept for consistency if needed for debugging.
        cursor.execute(sql, params)
        # Assuming id, document_id, sequence are int; content, content_type are str
        rows: List[Tuple[int, int, int, str, str]] = cursor.fetchall()
        conn.close()
        return [
            {
                "id": row[0],
                "document_id": row[1],
                "sequence": row[2],
                "content": row[3],
                "content_type": row[4],
            }
            for row in rows
        ]
