from __future__ import annotations
from pathlib import Path
from pocket_rag.database import Database
import datetime


class RAG:
    def __init__(self, database_dir_path_str):
        self.database_dir_path = Path(database_dir_path_str)

    def get_project(self, *, project_id=None) -> list[Project]:
        if project_id:
            database_file_path = self.database_dir_path / f"{project_id}.sqlite3"

            if not database_file_path.exists():
                raise FileNotFoundError(f"sqlite3ファイルが存在しません: {database_file_path}")
            
            return [Project(project_id, self.database_dir_path)]
        
        else:
            project_ids = [f.stem for f in self.database_dir_path.iterdir() if f.is_file() and f.suffix == '.sqlite3']
            return [Project(project_id, self.database_dir_path) for project_id in project_ids]
    
    def add_project(self, id, *, name:str | None = None , description:str | None = None) -> Project:
        # プロジェクトの追加
        # すでに存在している場合にはそのプロジェクトを返す。
        return Project(id, self.database_dir_path, name=name, description=description)

    def remove_project(self, id) -> None:
        remove_path = self.database_dir_path / f"{id}.sqlite3"
        remove_path.unlink(missing_ok=False)

class Project:
    def __init__(
            self,
            project_id: str,
            database_dir_path: Path,
            *,
            name: str | None = None,
            description: str | None = None
        ) -> None:
        self.project_id = project_id
        self.database_dir_path = database_dir_path
        self.database = self.setup_project(name, description)

    def setup_project(self, name, description) -> Database:
        database_file_path = self.database_dir_path / f"{self.project_id}.sqlite3"
        is_new = not database_file_path.exists()
        database = Database(str(database_file_path))

        if is_new:
            now = datetime.datetime.now()

            database.update_project({
                "id": f"{self.project_id}",
                "name": name or f"{self.project_id}",
                "description": description or f"Project: {self.project_id}",
                "created_at": f"{now.strftime("%Y-%m-%d %H:%M:%S")}",
                "updated_at": f"{now.strftime("%Y-%m-%d %H:%M:%S")}"
            })

        return database
    
    def get_project_info(self) -> dict[str, str]:
        return self.database.get_project_info()
    
    def get_document(self, *, document_id) -> list[Document]:
        pass

class Document:
    pass