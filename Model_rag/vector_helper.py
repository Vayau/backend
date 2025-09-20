# vector_helper.py
import os
from dotenv import load_dotenv
from haystack import Pipeline
from haystack.dataclasses import Document
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore
from haystack.utils import Secret

def create_vector_embeddings(document_id: str, document_content: str):
    """
    Helper function to create vector embeddings for a document.
    This function chunks, embeds, and indexes a document into the Supabase vector store.
    
    :param document_id: The unique UUID of the document from the 'documents' table.
    :param document_content: The full text content of the document.
    :return: dict with success status and message
    """
    try:
        print(f"Starting vector embedding creation for document ID: {document_id}...")
        
        # --- 1. SETUP ---
        load_dotenv()
        EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
        connection_string = Secret.from_env_var("CONN_STR")

        document_store = PgvectorDocumentStore(
            connection_string=connection_string,
            table_name="document_sections_embeddings",
            embedding_dimension=1024,
            vector_function="cosine_similarity"
        )
        
        # --- 2. CREATE AND RUN THE INDEXING PIPELINE ---

        # The splitter will automatically create chunks and preserve the metadata.
        parent_document = Document(
            id=document_id, # Set the ID here
            content=document_content,
        )

        indexing_pipeline = Pipeline()
        indexing_pipeline.add_component("splitter", DocumentSplitter(split_by="sentence", split_length=6, split_overlap=2))
        indexing_pipeline.add_component("embedder", SentenceTransformersDocumentEmbedder(model=EMBEDDING_MODEL_NAME))
        indexing_pipeline.add_component("writer", DocumentWriter(document_store=document_store, policy=DuplicatePolicy.OVERWRITE))
        indexing_pipeline.connect("splitter.documents", "embedder.documents")
        indexing_pipeline.connect("embedder.documents", "writer.documents")

        # Run the pipeline to chunk, embed, and write the document
        indexing_pipeline.run({"splitter": {"documents": [parent_document]}})
        print(f"Vector embedding creation complete for document {document_id}.")
        
        return {
            "success": True,
            "message": f"Vector embeddings created successfully for document {document_id}",
            "document_id": document_id
        }
        
    except Exception as e:
        error_msg = f"Failed to create vector embeddings for document {document_id}: {str(e)}"
        print(error_msg)
        return {
            "success": False,
            "message": error_msg,
            "document_id": document_id,
            "error": str(e)
        }


# This block allows you to run this file directly as a script for testing
if __name__ == "__main__":
    TEST_DOC_ID = "test-document-123"
    test_content = """
    This is a test document for vector embedding creation.
    It contains multiple sentences to test the chunking and embedding process.
    The document should be split into chunks and embedded into the vector store.
    """
    
    result = create_vector_embeddings(TEST_DOC_ID, test_content)
    print(f"Result: {result}")
