from __future__ import annotations
from collections import defaultdict
import sqlite3
import sqlite_vec


class Database:
    def __init__(self, database_path: str) -> None:
        self.database_path: str = database_path
        self._setup_database()

    def _connect_db(self) -> sqlite3.Connection:
        """データベースに接続する"""
        conn = sqlite3.connect(self.database_path, timeout=10)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)

        return conn

    def _setup_database(self):
        """データベーステーブルの初期設定"""

        conn = self._connect_db()
        cursor = conn.cursor()
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

    def update_project(self, params) -> None:
        conn = self._connect_db()
        cursor = conn.cursor()

        for key, value in params.items():
            cursor.execute('INSERT OR REPLACE INTO "project_info" (key, value) VALUES (?, ?);', (key, value))

        conn.commit()
        conn.close()

    def get_project_info(self) -> dict[str, str]:
        conn = self._connect_db()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM "project_info";')
        rows = cursor.fetchall()
        result = {}

        for row in rows:
            result[row[0]] = row[1]

        conn.commit()
        conn.close()
        return result

    def get_document(self, document_id: int) -> dict | None:
        """
        指定したdocument_idのドキュメントを取得する
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, path, unit_count, content FROM "documents" WHERE id = ?;',
            (document_id,)
        )
        row = cursor.fetchone()
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

    def get_all_documents(self) -> list[dict]:
        """
        すべてのドキュメントを取得する
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, name, path, unit_count, content FROM "documents";'
        )
        rows = cursor.fetchall()
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

    def get_text_units_with_embeddings(self, document_id: int) -> list[dict]:
        """
        指定したドキュメントのすべてのtext_unitsとその埋め込みベクトルを取得する
        """
        conn = self._connect_db()
        cursor = conn.cursor()
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
        rows = cursor.fetchall()
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

    def get_text_unit_with_embedding(self, document_id: int, sequence: int) -> dict | None:
        """
        指定したドキュメントの指定したsequenceのtext_unitとその埋め込みベクトルを取得する
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT tu.id, tu.document_id, tu.sequence, tu.content, tu.content_type, tuv.embedding
            FROM text_units tu
            LEFT JOIN text_units_vec tuv ON tu.id = tuv.rowid
            WHERE tu.document_id = ? AND tu.sequence = ?
            ''',
            (document_id, sequence)
        )
        row = cursor.fetchone()
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
        path: str | None,
        content: str,
        text_units: list[dict],
        embeddings: list[bytes]
    ) -> int:
        """
        ドキュメント・text_units・埋め込みベクトルをまとめて登録する
        text_units: [{ "sequence": int, "content": str, "content_type": str }]
        embeddings: [bytes]  # text_unitsと同じ順序
        戻り値: 登録したドキュメントのid
        """
        conn = self._connect_db()
        cursor = conn.cursor()

        # ドキュメント登録
        cursor.execute(
            '''
            INSERT INTO documents (name, path, unit_count, content)
            VALUES (?, ?, ?, ?)
            ''',
            (name, path, len(text_units), content)
        )
        document_id = cursor.lastrowid

        # text_units登録
        text_unit_ids = []
        for i, unit in enumerate(text_units):
            cursor.execute(
                '''
                INSERT INTO text_units (document_id, sequence, content, content_type)
                VALUES (?, ?, ?, ?)
                ''',
                (document_id, unit["sequence"], unit["content"], unit["content_type"])
            )
            text_unit_ids.append(cursor.lastrowid)

        # text_units_vec（埋め込み）登録
        for rowid, embedding in zip(text_unit_ids, embeddings):
            cursor.execute(
                '''
                INSERT INTO text_units_vec (rowid, embedding) VALUES (?, ?)
                ''',
                (rowid, embedding)
            )

        conn.commit()
        conn.close()
        return document_id

    def delete_document_and_embeddings(self, document_id: int) -> None:
        """
        指定したドキュメントとその関連text_units・埋め込みをすべて削除する
        """
        conn = self._connect_db()
        cursor = conn.cursor()

        # 関連するtext_unitのidを取得
        cursor.execute(
            'SELECT id FROM text_units WHERE document_id = ?',
            (document_id,)
        )
        text_unit_ids = [row[0] for row in cursor.fetchall()]

        # text_units_vec（埋め込み）削除
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

    def search_text_units_by_vector(self, embedding: bytes, k: int = 5) -> list[dict]:
        """
        ベクトル検索: embeddingベクトルに類似するtext_unitをk件取得する
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT text_units_vec.rowid, text_units_vec.distance, tu.content, d.content
            FROM text_units_vec
            JOIN text_units tu ON text_units_vec.rowid = tu.id
            JOIN documents d ON tu.document_id = d.id
            WHERE text_units_vec.embedding match ? AND k = ?
            ORDER BY text_units_vec.distance ASC
            """,
            (embedding, k),
        )
        rows = cursor.fetchall()
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

    def search_text_units_by_keywords(self, keywords: list[str]) -> list[dict]:
        """
        キーワード検索: 指定キーワードが含まれるtext_unitを取得する
        """
        conn = self._connect_db()
        cursor = conn.cursor()
        # AND検索: 全キーワードが含まれるtext_unit
        where_clause = " OR ".join(["tu.content LIKE ?" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]
        sql = f'''
            SELECT tu.id, tu.document_id, tu.sequence, tu.content, tu.content_type
            FROM text_units tu
            WHERE {where_clause}
            ORDER BY tu.document_id, tu.sequence
            '''
        print(sql)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
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
