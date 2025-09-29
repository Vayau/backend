# index.py
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
from neo4j import GraphDatabase
load_dotenv()

def insert_into_graph(metadata: dict):
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    query = """
    MERGE (d:Document {doc_id:$doc_id})
    SET d.title=$title, d.doc_type=$doc_type, d.source_system=$source_system,
        d.date=$date, d.version=$version, d.language=$language

    MERGE (p:Person {person_id:$person_id})
    SET p.name=$person_name, p.role=$person_role
    MERGE (d)-[:AUTHORED_BY]->(p)

    MERGE (dep:Department {dept_id:$dept_id})
    SET dep.name=$dept_name
    MERGE (d)-[:BELONGS_TO]->(dep)

    FOREACH (_ IN CASE WHEN $directive_id IS NULL THEN [] ELSE [1] END |
        MERGE (dir:Directive {directive_id:$directive_id})
        SET dir.issued_by=$directive_issued_by, dir.date=$directive_date
        MERGE (d)-[:MANDATED_BY]->(dir)
    )

    FOREACH (_ IN CASE WHEN $incident_id IS NULL THEN [] ELSE [1] END |
        MERGE (i:Incident {incident_id:$incident_id})
        SET i.date=$incident_date, i.summary=$incident_summary
        MERGE (d)-[:REFERENCES]->(i)
    )

    FOREACH (_ IN CASE WHEN $equipment_id IS NULL THEN [] ELSE [1] END |
        MERGE (e:Equipment {equipment_id:$equipment_id})
        SET e.name=$equipment_name, e.system=$equipment_system
        MERGE (d)-[:REFERENCES]->(e)
    )
    RETURN d
    """

    with neo4j_driver.session(database="neo4j") as session:
        res = session.run(query, **metadata)
        print("✅ Inserted document:", metadata["doc_id"], res.data())


def index_document(parent_doc_id: str, document_content: str):
    """
    Chunks, embeds, and indexes a single document into the Supabase vector store.
    
    :param parent_doc_id: The unique UUID of the parent document from your 'documents' table.
    :param document_content: The full text content of the document.
    """
    print(f"Starting indexing for document ID: {parent_doc_id}...")
    
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

    parent_document = Document(
        id=parent_doc_id, 
        content=document_content,
    )

    indexing_pipeline = Pipeline()
    indexing_pipeline.add_component("splitter", DocumentSplitter(split_by="sentence", split_length=6, split_overlap=2))
    indexing_pipeline.add_component("embedder", SentenceTransformersDocumentEmbedder(model=EMBEDDING_MODEL_NAME))
    indexing_pipeline.add_component("writer", DocumentWriter(document_store=document_store, policy=DuplicatePolicy.OVERWRITE))
    indexing_pipeline.connect("splitter.documents", "embedder.documents")
    indexing_pipeline.connect("embedder.documents", "writer.documents")

    indexing_pipeline.run({"splitter": {"documents": [parent_document]}})
    print(f"Indexing complete for document {parent_doc_id}.")


# This block allows you to run this file directly as a script for testing
if __name__ == "__main__":
    PARENT_DOC_ID = "70c10cdc-624a-490f-96da-0b190d082893"
    full_document_content = """
    Company: Kochi Metro Rail Ltd (KMRL) Document ID: KMRL-O&M-OPT-SOP-068 SOP Number: 15 Revision: 05 Title: SOP for Resumption of revenue service post lock down period Date: 01.09.2020 1. Introduction and Applicability This procedure provides guidelines for the working of stations and trains during the resumption of revenue service. It is applicable to all KMRL O&M staff and contractors involved in the working of trains and stations. Deputy Heads of Departments (Dy HODs) must ensure the 
    SOP is circulated and acknowledged by all staff. 2. Headway and Train Service The resumption of services will occur in a staged manner. 
    Stage I (07.09.2020 & 08.09.2020): Revenue services will run from 07:00 to 12:00 and 14:00 to 20:00 with a 10-minute headway. 
    No passenger services will be available between 12:00 and 14:00. Stage II (From 09.09.2020 onwards): Weekdays: Services will run from 07:00 to 22:00. Sundays: Services will start from 08:00. Management may adjust the headway based on passenger patronage. A trial run must be conducted before revenue services begin. Dwell time at stations will be a minimum of 20 seconds for ventilation. Layover time at terminals will be a minimum of 5 minutes with saloon doors open. Stations in containment zones will be closed to the public. 3. Preparatory Works and System Fitness All departments must ensure systems are safe and healthy before service resumption. Dy HODs must provide fitness certificates for their respective systems to stations and the Operations Control Centre (OCC). This includes: Track, Structure, and SOD clearance from CTR. Traction fitness from PST. Electrical installations, lifts, and escalators fitness. Train fitness from RST. ATP, signaling equipment, and gears fitness from STC. Telecom (PIDS, PAS) and AFC system fitness from COM. 4. Cleaning and Disinfection of Trains All trains will be sent to the depot daily after service. The RST department must clean the air-conditioner ducts before a train is in service. AC filters must be cleaned weekly. The saloon AC temperature will be set to 26 degrees Celsius, with a relative humidity of 40-70%. Train interiors, including grab poles, handles, and seats, will be cleaned nightly with disinfectant. Metallic surfaces can be cleaned with a 70% alcohol-based cleaner. All trains in service will be sprayed with a hypochlorite-based disinfectant. 5. Passenger Screening, Sanitization, and Social Distancing All stations will be disinfected daily. Foot-pedal operated hand sanitizers will be available at all station entry points. All passengers must wear masks. Passengers will be screened for body temperature with an infrared thermometer. Thermal cameras will be used at high-footfall stations. If a person shows symptoms of COVID-19, they will be guided to an isolated area, and the Station Controller must email idspekm@gmail.com, call the Tele health Help Line at 8086882228, follow instructions, and report to the OCC. Lifts will be limited to 2-3 persons. Passengers are advised to stand on alternate steps on escalators. Public contact points like AFC gates, counters, and handrails must be cleaned with disinfectant every 4 hours or sooner. Contactless frisking will be performed. Usage of the Aarogya Setu App will be encouraged. 6. Crowd Control Crowds will be regulated, and entry may be restricted if platforms become crowded. A maximum of two entry gates per station will be kept open. Executives at the AM/Manager level will be deployed to monitor every three stations for cleanliness and social distancing. Liaison with state police and local administration is required to manage crowds outside stations. 7. Guidelines for Staff Breath Analyser (BA) tests are exempted until further orders; a declaration must be signed instead. Train Operators must wear masks and gloves while on duty. All staff must undergo thermal screening before their shift. Workplaces, especially frequently touched surfaces, must be frequently sanitized. Social distancing of at least 6 feet must be maintained in gatherings and meetings. Employees at higher risk, including pregnant employees, should not be assigned to front-line work.
    """
    
    index_document(parent_doc_id=PARENT_DOC_ID, document_content=full_document_content)


#     documents = [
#     Document(
#         content="Company: Kochi Metro Rail Ltd (KMRL) Document ID: KMRL-O&M-OPT-SOP-068 SOP Number: 15 Revision: 05 Title: SOP for Resumption of revenue service post lock down period Date: 01.09.2020 ",
#         meta={
#             "doc_id": "70c10cdc-624a-490f-96da-0b190d082893",
#             "title": "SOP for Resumption of Revenue Service Post Lockdown",
#             "doc_type": "SOP",
#             "source_system": "SharePoint",
#             "date": "2020-09-01",
#             "version": "Revision 05",
#             "language": "English",

#             "person_id": "EMP-UNKNOWN",
#             "person_name": "KMRL O&M Dept",
#             "person_role": "Operations",

#             # Department
#             "dept_id": "OPS-01",
#             "dept_name": "Operations",

#             "directive_id": None,
#             "directive_issued_by": None,
#             "directive_date": None,


#             "incident_id": None,
#             "incident_date": None,
#             "incident_summary": None,

#             # Equipment (not in doc)
#             "equipment_id": None,
#             "equipment_name": None,
#             "equipment_system": None
#         }
#     )
# ]
#     for doc in documents:
#         insert_into_graph(doc.meta)