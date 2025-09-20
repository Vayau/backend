import os
from dotenv import load_dotenv
from haystack.utils import Secret
from haystack import Pipeline
from haystack.dataclasses import Document, ChatMessage
from haystack.components.writers import DocumentWriter
from haystack.components.preprocessors.document_splitter import DocumentSplitter
from haystack_integrations.components.generators.google_genai import GoogleGenAIChatGenerator
from haystack.components.builders import ChatPromptBuilder
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore
from vector_embeddings import HaystackEmbeddingGenerator
from haystack.document_stores.types import DuplicatePolicy
from haystack.utils import Secret

load_dotenv()

LLM_MODEL_NAME = "gemini-2.5-flash"
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
TABLE_NAME = "document_sections_embeddings"
EMBEDDING_DIMENSION = 1024

# Configure secrets using Haystack Secret so integrations expecting Secret objects work
google_api_key = Secret.from_env_var("GOOGLE_API_KEY")
connection_string = Secret.from_env_var("CONN_STR")


# Initialize custom components
print("Initializing components...")
embedder = HaystackEmbeddingGenerator(model_name=EMBEDDING_MODEL_NAME)
document_store = PgvectorDocumentStore(
    connection_string=connection_string,
    table_name=TABLE_NAME, # Ensure this matches your table
    embedding_dimension=EMBEDDING_DIMENSION,
    vector_function="cosine_similarity")
print("Components initialized.")


# --- 2. INDEXING PROCESS ---

print("\nStarting indexing process...")
PARENT_DOC_ID = "70c10cdc-624a-490f-96da-0b190d082893"
full_document_content = """
Company: Kochi Metro Rail Ltd (KMRL) Document ID: KMRL-O&M-OPT-SOP-068 SOP Number: 15 Revision: 05 Title: SOP for Resumption of revenue service post lock down period Date: 01.09.2020 
1. Introduction and Applicability This procedure provides guidelines for the working of stations and trains during the resumption of revenue service. 
It is applicable to all KMRL O&M staff and contractors involved in the working of trains and stations. Deputy Heads of Departments (Dy HODs) must ensure the SOP is circulated and acknowledged by all staff. 
2. Headway and Train Service The resumption of services will occur in a staged manner. 
Stage I (07.09.2020 & 08.09.2020): Revenue services will run from 07:00 to 12:00 and 14:00 to 20:00 with a 10-minute headway. No passenger services will be available between 12:00 and 14:00. Stage II (From 09.09.2020 onwards): Weekdays: Services will run from 07:00 to 22:00. Sundays: Services will start from 08:00. 
Management may adjust the headway based on passenger patronage. A trial run must be conducted before revenue services begin. 
Dwell time at stations will be a minimum of 20 seconds for ventilation. Layover time at terminals will be a minimum of 5 minutes with saloon doors open. Stations in containment zones will be closed to the public. 3. Preparatory Works and System Fitness All departments must ensure systems are safe and healthy before service resumption. Dy HODs must provide fitness certificates for their respective systems to stations and the Operations Control Centre (OCC). This includes: Track, Structure, and SOD clearance from CTR. Traction fitness from PST. Electrical installations, lifts, and escalators fitness. Train fitness from RST. ATP, signaling equipment, and gears fitness from STC. Telecom (PIDS, PAS) and AFC system fitness from COM. 4. Cleaning and Disinfection of Trains All trains will be sent to the depot daily after service. The RST department must clean the air-conditioner ducts before a train is in service. AC filters must be cleaned weekly. The saloon AC temperature will be set to 26 degrees Celsius, with a relative humidity of 40-70%. Train interiors, including grab poles, handles, and seats, will be cleaned nightly with disinfectant. Metallic surfaces can be cleaned with a 70% alcohol-based cleaner. All trains in service will be sprayed with a hypochlorite-based disinfectant. 5. Passenger Screening, Sanitization, and Social Distancing All stations will be disinfected daily. Foot-pedal operated hand sanitizers will be available at all station entry points. All passengers must wear masks. Passengers will be screened for body temperature with an infrared thermometer. Thermal cameras will be used at high-footfall stations. If a person shows symptoms of COVID-19, they will be guided to an isolated area, and the Station Controller must email idspekm@gmail.com, call the Tele health Help Line at 8086882228, follow instructions, and report to the OCC. Lifts will be limited to 2-3 persons. Passengers are advised to stand on alternate steps on escalators. Public contact points like AFC gates, counters, and handrails must be cleaned with disinfectant every 4 hours or sooner. Contactless frisking will be performed. Usage of the Aarogya Setu App will be encouraged. 6. Crowd Control Crowds will be regulated, and entry may be restricted if platforms become crowded. A maximum of two entry gates per station will be kept open. Executives at the AM/Manager level will be deployed to monitor every three stations for cleanliness and social distancing. Liaison with state police and local administration is required to manage crowds outside stations. 7. Guidelines for Staff Breath Analyser (BA) tests are exempted until further orders; a declaration must be signed instead. Train Operators must wear masks and gloves while on duty. All staff must undergo thermal screening before their shift. Workplaces, especially frequently touched surfaces, must be frequently sanitized. Social distancing of at least 6 feet must be maintained in gatherings and meetings. Employees at higher risk, including pregnant employees, should not be assigned to front-line work.
"""

# Step 2a: Create a single Document object for the entire text
parent_document = Document(id=PARENT_DOC_ID, content=full_document_content)

# Step 2b: Use Haystack's DocumentSplitter to chunk the text
splitter = DocumentSplitter(split_by="sentence", split_length=6, split_overlap=2)
splitter.warm_up()
document_chunks = splitter.run(documents=[parent_document])["documents"]


# Step 2c: Generate embeddings for the chunks using your utility
contents_to_embed = [chunk.content for chunk in document_chunks]
embeddings = embedder.embed(contents_to_embed)

# Step 2d: Add the embeddings back to the Document objects
for chunk, embedding in zip(document_chunks, embeddings):
    chunk.embedding = embedding

# Step 2e: Write the final chunks (with metadata and embeddings) to Supabase
document_store.write_documents(document_chunks, policy=DuplicatePolicy.OVERWRITE)
print(f"Indexing complete. {len(document_chunks)} chunks stored in Supabase.")


# --- 3. QUERYING PIPELINE ---

chat_prompt_template = [
    ChatMessage.from_user(
        """
Answer the question based only on the following documents.
If the documents do not contain the answer, state that you don't have enough information.

Documents:
{% for doc in documents %}
    {{ doc.content }}
{% endfor %}

Question: {{question}}
"""
    )
]

query_pipeline = Pipeline()
query_pipeline.add_component("text_embedder", embedder.text_embedder) # Reusing the embedder from our utility
query_pipeline.add_component("retriever", PgvectorEmbeddingRetriever(document_store=document_store, top_k=3))
query_pipeline.add_component("message_builder", ChatPromptBuilder(template=chat_prompt_template, required_variables=["question"]))
query_pipeline.add_component("llm", GoogleGenAIChatGenerator(model=LLM_MODEL_NAME))

query_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
query_pipeline.connect("retriever.documents", "message_builder.documents")
query_pipeline.connect("message_builder.prompt", "llm.messages")


# --- 4. RUN THE QUERY ---
print("\nRunning query pipeline...")
user_question = "When will the passenger services not be available?"
result = query_pipeline.run({
    "text_embedder": {"text": user_question},
    "message_builder": {"question": user_question}
})

print(f"\nQuestion: {user_question}")
print("Answer:")
print(result["llm"]["replies"][0]._content)