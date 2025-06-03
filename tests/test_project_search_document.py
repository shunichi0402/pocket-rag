import pytest
from pathlib import Path
import shutil
import os
import json

# Set dummy API key as early as possible to avoid OpenAI client init error on import
os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing_search_early"

from unittest.mock import patch, MagicMock, ANY

from pocket_rag import RAG, Project, Document
from pocket_rag.database import Database, SearchResultDict, TextUnitDict # For type hinting
from pocket_rag.embedding import Embedding # For type hinting if needed for mocks
import numpy as np # For dummy embedding vector

# Common Test Setup
TEST_DB_DIR_SEARCH = Path("./test_search_databases")

# The fixture below is good practice but might not run early enough for this specific import issue.
# The direct os.environ set above is a more forceful workaround.
# @pytest.fixture(scope="session", autouse=True)
# def set_dummy_openai_api_key_search():
#     """Set a dummy OPENAI_API_KEY for the test session."""
#     original_key = os.environ.get("OPENAI_API_KEY")
#     os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing_search_fixture"
#     yield
#     if original_key is None:
#         if "OPENAI_API_KEY" in os.environ: # Ensure key exists before trying to delete
#             del os.environ["OPENAI_API_KEY"]
#     else:
#         os.environ["OPENAI_API_KEY"] = original_key

@pytest.fixture(scope="function")
def temp_db_dir_search():
    """Create a temporary directory for databases for search tests."""
    TEST_DB_DIR_SEARCH.mkdir(parents=True, exist_ok=True)
    yield TEST_DB_DIR_SEARCH
    if TEST_DB_DIR_SEARCH.exists():
        shutil.rmtree(TEST_DB_DIR_SEARCH)

@pytest.fixture
def mock_embedding_search():
    """Mocks Embedding methods for search tests, ensuring global instance is patched."""
    # 1. Patch the Embedding class: Any Embedding() call will return mock_emb_instance
    with patch('pocket_rag.embedding.Embedding', autospec=True) as mock_embedding_class:
        mock_emb_instance = mock_embedding_class.return_value

        # Configure methods on this instance
        # generate_embedding should directly return a numpy array as expected by the main code
        mock_emb_instance.generate_embedding.return_value = np.array([0.1] * 2048, dtype=np.float32)
        mock_emb_instance.generate_query.return_value = np.array([0.5] * 2048, dtype=np.float32)

        # 2. Patch the static method Embedding.serialize_vector
        # This needs to be patched on the original Embedding class if called as Embedding.serialize_vector()
        with patch.object(Embedding, 'serialize_vector', return_value=b'\0' * (2048 * 4)) as mock_static_serialize_vector:
            # 3. Patch the global 'embedding' instance in pocket_rag.__init__ to be our mock_emb_instance
            # This ensures that code calling `embedding.method()` uses the mocked instance.
            with patch('pocket_rag.embedding', new=mock_emb_instance) as patched_global_embedding_instance:
                # Yield the instance that is now globally patched, and the static method mock
                yield patched_global_embedding_instance, mock_static_serialize_vector


@pytest.fixture
def mock_ask_chatgpt_search():
    """Mocks ask_chatgpt for search tests. Patches where it's used in pocket_rag.__init__."""
    # pocket_rag.__init__ uses `from pocket_rag.gpt import ask_chatgpt`
    # and then calls `ask_chatgpt` directly.
    # So, we need to patch `ask_chatgpt` in the `pocket_rag` (i.e. `pocket_rag.__init__`) namespace.
    with patch('pocket_rag.ask_chatgpt', autospec=True) as mock_chatgpt:
        mock_chatgpt.return_value = json.dumps({"keywords": ["mocked", "keyword"]})
        yield mock_chatgpt

@pytest.fixture
def populated_project(temp_db_dir_search: Path, mock_embedding_search, mock_ask_chatgpt_search) -> Project:
    """Fixture to create a Project and add a dummy document."""
    rag = RAG(str(temp_db_dir_search))
    project = rag.add_project(id="search_proj", name="Search Test Project")

    # Create a dummy markdown file content
    dummy_md_content = "# Title 1\nContent for section 1.\n## Subtitle\nMore content."
    dummy_file_path = temp_db_dir_search / "dummy_doc.md"
    dummy_file_path.write_text(dummy_md_content)

    # Mock ask_chatgpt for split_long_text during document addition if text is long
    # For this short text, it might not be called.
    mock_ask_chatgpt_search.return_value = json.dumps({"chunks": [{"text": dummy_md_content}]})

    project.add_document(path=str(dummy_file_path))
    return project

# --- Test Cases ---

class TestProjectSearch:
    def test_search_by_vector(self, populated_project: Project, mock_embedding_search):
        mock_emb_instance, mock_serialize_vector = mock_embedding_search

        # Expected query vector (from mock_embedding_search.generate_query)
        expected_query_vector_np = np.array([0.5] * 2048, dtype=np.float32)
        expected_serialized_vector = b'\0' * (2048 * 4) # Matching mock_serialize_vector

        # Mock the database response for vector search
        mock_db_search_results: List[SearchResultDict] = [
            {"text_unit_id": 1, "distance": 0.1, "text_unit_content": "Content 1", "document_content": "Doc Content 1"},
            {"text_unit_id": 2, "distance": 0.2, "text_unit_content": "Content 2", "document_content": "Doc Content 2"},
        ]
        with patch.object(populated_project.database, 'search_text_units_by_vector', return_value=mock_db_search_results) as mock_db_call:
            # mock_serialize_vector is the mock for the static method Embedding.serialize_vector
            # Reset its call count because populated_project fixture would have called it during add_document
            mock_serialize_vector.reset_mock()

            results = populated_project.search_by_vector("test query for vector", k=2)

        mock_emb_instance.generate_query.assert_called_once_with("test query for vector")

        # Embedding.serialize_vector is static. Check its mock (mock_serialize_vector) was called once for the query.
        mock_serialize_vector.assert_called_once() # Check it was called (at least once, reset should make it once)
        actual_call_args, _ = mock_serialize_vector.call_args
        assert np.array_equal(actual_call_args[0], expected_query_vector_np), \
            f"Expected call with a specific numpy array, got {actual_call_args[0]}"

        mock_db_call.assert_called_once_with(expected_serialized_vector, k=2)
        assert results == mock_db_search_results

    def test_search_by_keyword(self, populated_project: Project, mock_ask_chatgpt_search):
        expected_keywords = ["extracted", "keyword1"]
        mock_ask_chatgpt_search.return_value = json.dumps({"keywords": expected_keywords})

        mock_db_keyword_results: List[TextUnitDict] = [
            {"id": 10, "document_id":1, "sequence": 0, "content": "Text with extracted keyword1", "content_type": "text"},
        ]
        with patch.object(populated_project.database, 'search_text_units_by_keywords', return_value=mock_db_keyword_results) as mock_db_call:
            results = populated_project.search_by_keyword("test query for keywords")

        mock_ask_chatgpt_search.assert_called_once_with("test query for keywords", system_prompt=ANY, model=ANY, response_format=ANY)
        mock_db_call.assert_called_once_with(expected_keywords)
        assert results == mock_db_keyword_results

    def test_search_hybrid(self, populated_project: Project, mock_embedding_search, mock_ask_chatgpt_search):
        # Mock underlying search methods of the project instance for easier control
        # or ensure database mocks are hit correctly. Here, mocking project methods.

        mock_vector_results: List[SearchResultDict] = [
            {"text_unit_id": 1, "distance": 0.1, "text_unit_content": "Vector Result 1", "document_content": "Doc1"},
            {"text_unit_id": 3, "distance": 0.3, "text_unit_content": "Vector Result 2", "document_content": "Doc2"},
        ]
        mock_keyword_results: List[TextUnitDict] = [
            {"id": 1, "document_id":1, "sequence":0, "content": "Keyword Result 1 (matches Vector 1)", "content_type":"text"},
            {"id": 4, "document_id":2, "sequence":1, "content": "Keyword Result 3 (unique)", "content_type":"text"},
        ]

        with patch.object(populated_project, 'search_by_vector', return_value=mock_vector_results) as mock_proj_vec_search, \
             patch.object(populated_project, 'search_by_keyword', return_value=mock_keyword_results) as mock_proj_kw_search:

            results = populated_project.search_hybrid("hybrid query", k=3, vector_weight=1.0, keyword_weight=1.0)

            mock_proj_vec_search.assert_called_once_with("hybrid query", 3 * 2) # k * 2
            mock_proj_kw_search.assert_called_once_with("hybrid query")

            assert len(results) <= 3
            # Check if results are combined and scored (simplified check)
            # Item with id 1 should have a higher score due to appearing in both
            found_id1 = False
            for res in results:
                if res.get("text_unit_id") == 1 or res.get("id") == 1:
                    found_id1 = True
                    assert "hybrid_score" in res
                    # More detailed score assertion would require recalculating expected scores
            assert found_id1


class TestDocumentOperations:
    @pytest.fixture
    def doc_for_ops(self, populated_project: Project) -> Document:
        """Provides a document from the populated project for operations tests."""
        # Assumes populated_project adds at least one document and returns the project.
        # We need to get one of its documents.
        docs = populated_project.get_documents()
        if not docs:
            # If populated_project didn't actually add a doc that's retrievable here,
            # we might need to add one explicitly.
            # For now, assume populated_project is set up to have at least one doc.
            pytest.fail("Populated project has no documents for testing operations.")
        return docs[0] # Take the first document

    def test_update_document_content(self, doc_for_ops: Document, populated_project: Project, mock_embedding_search, mock_ask_chatgpt_search):
        original_doc_id = doc_for_ops.document_id
        new_content = "This is the updated content for the document."

        # Mock for split_long_text if new_content is long
        mock_ask_chatgpt_search.return_value = json.dumps({"chunks": [{"text": new_content}]})

        # Mock for the Project.split_text_unit called inside Document.update_content
        # This is tricky due to the design issue noted (Document calling Project's instance method)
        # We patch it on the Project class level for this test.
        mock_split_units_result = [{"content": new_content, "content_type": "text", "sequence": 0}]
        new_doc_id = original_doc_id + 100

        def mock_get_document_side_effect(doc_id_called):
            if doc_id_called == new_doc_id:
                return {
                    "id": new_doc_id, "name": doc_for_ops.name, "path": doc_for_ops.path,
                    "unit_count": len(mock_split_units_result), "content": new_content,
                }
            elif doc_id_called == original_doc_id: # Before reload, if it's fetched for some reason
                 return {
                    "id": original_doc_id, "name": "Original Name", "path": "original/path", # Dummy original
                    "unit_count": 1, "content": "Original Content",
                }
            return None

        with patch('pocket_rag.Project.split_text_unit', return_value=mock_split_units_result, autospec=True) as mock_project_split, \
             patch.object(doc_for_ops.database, 'delete_document_and_embeddings') as mock_db_delete, \
             patch.object(doc_for_ops.database, 'insert_document_with_embeddings', return_value=new_doc_id) as mock_db_insert, \
             patch.object(doc_for_ops.database, 'get_document', side_effect=mock_get_document_side_effect) as mock_db_get_doc:
            doc_for_ops.update_content(new_content)

        # Check how mock_project_split (the mock for Project.split_text_unit) was called
        mock_project_split.assert_called_once() # Ensure it was called
        call_args_list = mock_project_split.call_args_list
        # The first argument to the mocked method should be the Project instance, second is new_content
        assert isinstance(call_args_list[0][0][0], Project) # Check self argument is a Project instance
        assert call_args_list[0][0][1] == new_content     # Check the new_content argument

        mock_db_delete.assert_called_once_with(original_doc_id)
        mock_db_insert.assert_called_once()

        # Check keyword arguments passed to insert_document_with_embeddings
        pos_args, kw_args = mock_db_insert.call_args
        assert not pos_args # Should be empty as all args were passed as keywords
        assert kw_args.get('name') == doc_for_ops.name
        assert kw_args.get('path') == doc_for_ops.path
        assert kw_args.get('content') == new_content
        assert kw_args.get('text_units') == mock_split_units_result
        # `embeddings` argument is also passed, but harder to assert exact value without capturing it.
        # We can at least check if it was provided.
        assert 'embeddings' in kw_args

        assert doc_for_ops.document_id == new_doc_id
        # _reload calls get_document, which is now mocked
        mock_db_get_doc.assert_any_call(new_doc_id) # Check that _reload tried to fetch the new doc
        assert doc_for_ops.content == new_content

        mock_emb_instance, _ = mock_embedding_search
        # Check if generate_embedding was called for each unit in mock_split_units_result
        # For this test, mock_split_units_result has one unit.
        mock_emb_instance.generate_embedding.assert_any_call(new_content)


    def test_delete_document(self, doc_for_ops: Document, populated_project: Project):
        doc_id_to_delete = doc_for_ops.document_id

        # Mock get_document to return None after deletion for the specific ID
        def mock_get_document_after_delete(doc_id_called):
            if doc_id_called == doc_id_to_delete:
                return None
            # For any other ID, you might want to return a dummy doc or raise error
            # For this test, only caring about the deleted ID.
            return {"id": doc_id_called, "name": "Some other doc", "path": "", "unit_count": 0, "content": ""}

        with patch.object(populated_project.database, 'delete_document_and_embeddings') as mock_db_delete, \
             patch.object(populated_project.database, 'get_document', side_effect=mock_get_document_after_delete) as mock_get_doc_deleted:

            doc_for_ops.delete() # This calls mock_db_delete

            # Verify the document is no longer retrievable via project.get_document
            assert populated_project.get_document(doc_id_to_delete) is None

        mock_db_delete.assert_called_once_with(doc_id_to_delete)
        mock_get_doc_deleted.assert_called_with(doc_id_to_delete)
