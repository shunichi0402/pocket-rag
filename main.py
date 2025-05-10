from pocket_rag import RAG

rag = RAG('./database')
project_info = rag.get_project()[0].get_project_info()
rag.remove_project(project_info.get("id"))
