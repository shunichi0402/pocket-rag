from dotenv import load_dotenv
load_dotenv()

from pocket_rag import RAG
import json

rag = RAG("./database")
rag.add_project("test", "テストプロジェクト", "サンプルで使用するテストプロジェクトです。")
project = rag.get_project(project_id="test")[0]
project.add_document(path="./test.md", type = "markdown")
text_units = project.search_hybrid("坂本龍馬について教えてください", 3)
rag.remove_document

with open("./result.json", "w", encoding="utf-8") as f:
    json.dump(text_units, f, ensure_ascii=False)
