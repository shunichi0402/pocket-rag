import pytest
from pathlib import Path
import shutil
import os

# Attempt to set the environment variable as early as possible
os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing_early_init"

from unittest.mock import patch, MagicMock

from pocket_rag import RAG, Project, Document # Assuming Document might be needed for assertions
from pocket_rag.database import Database # For type hinting if needed
from pocket_rag.embedding import Embedding # For type hinting if needed for mocks

# Define a temporary directory for test databases
TEST_DB_DIR = Path("./test_rag_databases")

# @pytest.fixture(scope="session", autouse=True) # Keep this, but the above direct set is for testing the theory
# def set_dummy_openai_api_key():
#     """Set a dummy OPENAI_API_KEY for the test session to allow client initialization."""
#     original_key = os.environ.get("OPENAI_API_KEY")
#     os.environ["OPENAI_API_KEY"] = "dummy_key_for_testing_purposes_fixture" # Different key for fixture
#     print(f"Fixture: OPENAI_API_KEY set to {os.environ['OPENAI_API_KEY']}")
#     yield
#     if original_key is None:
#         del os.environ["OPENAI_API_KEY"]
#         print(f"Fixture: OPENAI_API_KEY deleted")
#     else:
#         os.environ["OPENAI_API_KEY"] = original_key
#         print(f"Fixture: OPENAI_API_KEY restored to {original_key}")


@pytest.fixture(scope="function")
def temp_db_dir():
    """Create a temporary directory for databases before each test, clean up after."""
    TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
    yield TEST_DB_DIR
    # Clean up: remove the directory and all its contents
    if TEST_DB_DIR.exists():
        shutil.rmtree(TEST_DB_DIR)

@pytest.fixture
def mock_embedding():
    """Mocks the global embedding object and its methods."""
    with patch('pocket_rag.embedding.Embedding', autospec=True) as mock_embedding_class:
        mock_instance = mock_embedding_class.return_value
        mock_instance.generate_embedding.return_value = MagicMock(spec=object) # Return a dummy numpy array like object
        mock_instance.generate_query.return_value = MagicMock(spec=object)
        # Embedding.serialize_vector is a static method
        with patch.object(Embedding, 'serialize_vector', return_value=b'mocked_vector_bytes') as mock_serialize:
            # Patch the global 'embedding' instance in pocket_rag.__init__
            with patch('pocket_rag.embedding', mock_instance): # if global embedding is used in pocket_rag
                 with patch('pocket_rag.Embedding.serialize_vector', mock_serialize): # if static method is called directly
                    yield mock_instance, mock_serialize


@pytest.fixture
def mock_ask_chatgpt():
    """Mocks the ask_chatgpt function."""
    with patch('pocket_rag.gpt.ask_chatgpt', autospec=True) as mock_chatgpt:
        # Default mock for split_long_text
        mock_chatgpt.return_value = '{"chunks": [{"text": "mocked split text"}]}'
        yield mock_chatgpt


class TestRAG:
    def test_add_get_remove_project(self, temp_db_dir, mock_embedding, mock_ask_chatgpt):
        rag = RAG(str(temp_db_dir))
        project_id = "test_project1"
        project_name = "Test Project One"
        project_description = "A project for testing RAG."

        # Add project
        project_instance = rag.add_project(id=project_id, name=project_name, description=project_description)
        assert project_instance is not None
        assert project_instance.project_id == project_id

        # Get project
        retrieved_projects = rag.get_project(project_id=project_id)
        assert len(retrieved_projects) == 1
        retrieved_project = retrieved_projects[0]
        assert retrieved_project.project_id == project_id

        project_info = retrieved_project.get_project_info()
        assert project_info["name"] == project_name
        assert project_info["description"] == project_description

        # Check database file was created
        db_file = temp_db_dir / f"{project_id}.sqlite3"
        assert db_file.exists()

        # Remove project
        rag.remove_project(project_id)
        assert not db_file.exists()

        # Verify getting non-existent project raises error or returns empty
        with pytest.raises(FileNotFoundError): # Or check for empty list depending on desired behavior
             rag.get_project(project_id="non_existent_project") # This will try to access a non-existent file.

        # Test getting all projects when one was removed (should be empty or not include the removed one)
        remaining_projects = rag.get_project() # Get all
        assert project_id not in [p.project_id for p in remaining_projects]


class TestProject:
    @pytest.fixture
    def test_project(self, temp_db_dir, mock_embedding, mock_ask_chatgpt) -> Project:
        """Fixture to create a standard Project for testing."""
        rag = RAG(str(temp_db_dir))
        project_id = "doc_test_project"
        project_name = "Document Test Project"
        return rag.add_project(id=project_id, name=project_name)

    @pytest.fixture
    def dummy_md_file(self, tmp_path: Path) -> Path:
        """Creates a dummy markdown file for testing add_document."""
        md_content = "# Test Header\n\nThis is a test document."
        file_path = tmp_path / "test_doc.md"
        file_path.write_text(md_content, encoding="utf-8")
        return file_path

    def test_add_get_document(self, test_project: Project, dummy_md_file: Path, mock_embedding, mock_ask_chatgpt):
        # Mocking for embedding generation within add_document
        mock_emb_instance, mock_serialize_vector = mock_embedding

        # Mock the return of generate_embedding to be a simple list-like object for .cpu().numpy().squeeze()
        # and ensure serialize_vector is correctly patched if it's called as a static method.
        dummy_embedding_vector = [0.1, 0.2] # Simplified representation
        mock_emb_instance.generate_embedding.return_value = MagicMock(
            cpu=MagicMock(return_value=MagicMock(
                numpy=MagicMock(return_value=MagicMock(
                    squeeze=MagicMock(return_value=dummy_embedding_vector)
                ))
            ))
        )
        # Embedding.serialize_vector is a static method.
        # It needs to return a byte string of length 2048 * 4 = 8192 for a float[2048] vector.
        Embedding.serialize_vector = MagicMock(return_value=b'\0' * (2048 * 4))


        # Setup mock for ask_chatgpt if split_long_text is called within add_document indirectly
        # (e.g. if default content is too long, though unlikely for dummy_md_file)
        mock_ask_chatgpt.return_value = '{"chunks": [{"text": "mocked split text for add_document"}]}'


        doc_instance = test_project.add_document(path=str(dummy_md_file))
        assert doc_instance is not None
        assert doc_instance.name == dummy_md_file.name

        retrieved_doc = test_project.get_document(document_id=doc_instance.document_id)
        assert retrieved_doc is not None
        assert retrieved_doc.document_id == doc_instance.document_id
        assert retrieved_doc.name == dummy_md_file.name

        # Verify content was processed (length of text_units > 0)
        text_units = retrieved_doc.get_text_units()
        assert len(text_units) > 0
        assert text_units[0]["content"].strip().startswith("# Test Header") # Basic check

        # Verify generate_embedding was called
        mock_emb_instance.generate_embedding.assert_called()
        Embedding.serialize_vector.assert_called()


    def test_get_project_info(self, test_project: Project):
        info = test_project.get_project_info()
        assert info is not None
        assert info["id"] == test_project.project_id
        assert info["name"] == "Document Test Project" # As set in the fixture
        assert "description" in info
        assert "created_at" in info
        assert "updated_at" in info
