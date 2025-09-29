import os
import re
from haystack import Pipeline
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.dataclasses import ChatMessage 
from haystack.components.builders.chat_prompt_builder import ChatPromptBuilder
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator
from haystack.utils import Secret
from dotenv import load_dotenv
import google.generativeai as genai
from neo4j import GraphDatabase

# ---------------------- Setup ----------------------
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ---------------------- Summarizer ----------------------
def summarizer(content: str):
    def removeSymbols(response):
        return response.strip().replace("*", '')
    
    def gemini_pro_response(user_prompt):
        gemini_pro_model = genai.GenerativeModel("gemini-2.5-flash")
        response = gemini_pro_model.generate_content(user_prompt)
        return removeSymbols(response.text)

    prompt = '''You're an expert content summarizer, given the content to you, you need to summarize the content in
    such a way that the important context or words are highlighted and 
    you give a detailed, easy to understand and effective insightful summary'''
    return gemini_pro_response(prompt + content)


# ---------------------- RAG Pipeline ----------------------
def run_rag_pipeline(question: str) -> str:
    LLM_MODEL_NAME = "gemini-2.5-flash"
    EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
    connection_string = Secret.from_env_var("CONN_STR")

    document_store = PgvectorDocumentStore(
        connection_string=connection_string,
        table_name="document_sections_embeddings",
        embedding_dimension=1024
    )

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

    if isinstance(answer, list):
        answer = " ".join([a.text if hasattr(a, 'text') else str(a) for a in answer])
    elif hasattr(answer, 'text'):
        answer = answer.text
    elif isinstance(answer, str) and "TextContent(text=" in answer:
        match = re.search(r"TextContent\(text='(.*?)'\)", answer)
        if match:
            answer = match.group(1)

    return str(answer)


# ---------------------- GraphDB Dynamic Query ----------------------
def run_dynamic_cypher(question: str):
    schema_context = """
    Available entities: Document, Person, Department, Directive, Incident, Equipment.
    Relationships: 
      (Document)-[:AUTHORED_BY]->(Person)
      (Document)-[:BELONGS_TO]->(Department)
      (Document)-[:MANDATED_BY]->(Directive)
      (Document)-[:REFERENCES]->(Incident|Equipment)
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""{schema_context}

    User request: "{question}"
    Write a Cypher query to answer this request. Only return the Cypher query, nothing else.
    """
    response = model.generate_content(prompt)
    cypher_query = response.text.strip().replace("```cypher", "").replace("```", "").strip()

    print(f"[Generated Cypher] {cypher_query}")

    with driver.session(database="neo4j") as session:
        results = session.run(cypher_query).data()
    return results


# ---------------------- Router ----------------------
GRAPH_KEYWORDS = [
    "author", "issued by", "directive", "incident", "equipment",
    "department", "provenance", "source", "created by", "who wrote", "mandated by"
]

def classify_with_llm(question: str) -> str:
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
    You are a router that decides if a question should be answered using:
    - "GRAPH" if it is about metadata, provenance, relationships, directives, authorship, incidents, equipment, or departments.
    - "RAG" if it is about content, or generating multiple answers etc., 

    Question: "{question}"
    Reply ONLY with GRAPH or RAG.
    """
    resp = model.generate_content(prompt)
    return resp.text.strip().upper()

# def decide_db(question: str) -> str:
#     q = question.lower()
#     if any(k in q for k in GRAPH_KEYWORDS):
#         return "GRAPH"
#     return classify_with_llm(question)


# ---------------------- Main Dispatcher ----------------------
def ask_question_with_router(question: str):
    decision = classify_with_llm(question)
    print(f"[Router Decision] {decision}")

    if decision == "RAG":
        return run_rag_pipeline(question)
    elif decision == "GRAPH":
        return run_dynamic_cypher(question)
    else:
        return "Could not classify the question."


# ---------------------- Test ----------------------
if __name__ == "__main__":
    q1 = "What is the dwell time at stations?"
    print("\nQ1:", ask_question_with_router(q1))

    q2 = "Find all documents authored by Anil Kumar"
    print("\nQ2:", ask_question_with_router(q2))

