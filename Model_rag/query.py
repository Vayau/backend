# query.py
import os
from dotenv import load_dotenv
from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.dataclasses import ChatMessage 
from haystack.components.builders.chat_prompt_builder import ChatPromptBuilder
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator
from haystack.utils import Secret

def ask_question(question: str):
    """
    Runs the RAG pipeline to answer a given question.
    
    :param question: The user's question.
    :return: The generated answer as a string.
    """
    print(f"Running query: '{question}'")
    
    # --- 1. SETUP ---
    load_dotenv()
    LLM_MODEL_NAME = "gemini-1.5-flash-latest"
    EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
    connection_string = Secret.from_env_var("CONN_STR")
    google_api_key = Secret.from_env_var("GOOGLE_API_KEY")

    document_store = PgvectorDocumentStore(
        connection_string=connection_string,
        table_name="document_sections_embeddings",
        embedding_dimension=1024
    )
    
    # --- 2. CREATE AND RUN THE QUERYING PIPELINE ---
    chat_prompt_template = [
        ChatMessage.from_system("Answer the question based only on the provided documents."),
        ChatMessage.from_user(
            """
            Documents:
            {% for doc in documents %}
                {{ doc.content }}
            {% endfor %}

            Question: {{question}}
            """
        )
    ]
    
    query_pipeline = Pipeline()
    query_pipeline.add_component("text_embedder", SentenceTransformersTextEmbedder(model=EMBEDDING_MODEL_NAME))
    query_pipeline.add_component("retriever", PgvectorEmbeddingRetriever(document_store=document_store, top_k=3))
    query_pipeline.add_component("message_builder", ChatPromptBuilder(template=chat_prompt_template, required_variables=["question"]))
    query_pipeline.add_component("llm", GoogleGenAIChatGenerator(model=LLM_MODEL_NAME))

    query_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
    query_pipeline.connect("retriever.documents", "message_builder.documents")
    query_pipeline.connect("message_builder.prompt", "llm.messages")
    
    result = query_pipeline.run({
        "text_embedder": {"text": question},
        "message_builder": {"question": question}
    })
    
    answer = result["llm"]["replies"][0]._content
    return answer

# This block allows you to run this file directly as a script for testing
if __name__ == "__main__":
    user_question = "What is the dwell time at stations?"
    answer = ask_question(question=user_question)
    
    print("\n" + "="*30)
    print(f"Question: {user_question}")
    print(f"Answer: {answer}")
    print("="*30)