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

    def get_documents(self):
        conn = self._connect_db()
        cursor = conn.cursor()

        query = """
        SELECT 
            documents.id AS document_id,
            documents.name AS document_name,
            documents.path AS document_path,
            documents.unit_count AS unit_count,
            documents.content AS document_content,
            text_units.sequence,
            text_units.content,
            text_units_vec.embedding
        FROM documents
        JOIN text_units ON documents.id = text_units.document_id
        JOIN text_units_vec ON text_units.id = text_units_vec.rowid
        ORDER BY documents.id, text_units.sequence;
        """

        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        documents_dict = defaultdict(lambda: {
            "document": {},
            "text_units": []
        })

        for (
            doc_id,
            name,
            path,
            unit_count,
            document_content,
            sequence,
            content,
            embedding,
        ) in results:
            doc_entry = documents_dict[doc_id]
            doc_entry["document"] = {
                "id": doc_id,
                "name": name,
                "path": path,
                "unit_count": unit_count,
                "content": document_content,
            }
            doc_entry["text_units"].append({
                "sequence": sequence,
                "content": content,
                "embedding": list(embedding)
            })

        return list(documents_dict.values())

    def get_document_by_id(self, document_id):
        conn = self._connect_db()
        cursor = conn.cursor()

        query = """
        SELECT 
            documents.id AS document_id,
            documents.name AS document_name,
            documents.path AS document_path,
            documents.unit_count AS unit_count,
            documents.content AS document_content,
            text_units.sequence,
            text_units.content,
            text_units_vec.embedding
        FROM documents
        JOIN text_units ON documents.id = text_units.document_id
        JOIN text_units_vec ON text_units.id = text_units_vec.rowid
        WHERE documents.id = ?
        ORDER BY text_units.sequence;
        """

        cursor.execute(query, (document_id,))
        results = cursor.fetchall()
        conn.close()

        if not results:
            return None

        doc_data = {
            "document": {
                "id": results[0][0],
                "name": results[0][1],
                "path": results[0][2],
                "unit_count": results[0][3],
                "content": results[0][4],
            },
            "text_units": [
                {"sequence": seq, "content": content, "embedding": list(embedding)}
                for (_, _, _, _, _, seq, content, embedding) in results
            ]
        }

        return doc_data
