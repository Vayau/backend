from neo4j import GraphDatabase
import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()
# Setup Neo4j
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

# Setup Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
llm = genai.GenerativeModel("gemini-2.5-flash")

schema_context = """
You are an assistant that generates Cypher queries for Neo4j.
Database schema:
- Document(doc_id, title, doc_type, date, language)
- Person(person_id, name, role)
- Department(dept_id, name)
- Directive(directive_id, issued_by, date)
- Incident(incident_id, summary, date)
- Equipment(equipment_id, name, system)

Relationships:
(Document)-[:AUTHORED_BY]->(Person)
(Document)-[:BELONGS_TO]->(Department)
(Document)-[:MANDATED_BY]->(Directive)
(Document)-[:REFERENCES]->(Incident|Equipment)
"""

def run_dynamic_cypher(question: str):
    prompt = f"""{schema_context}

User request: "{question}"
Write a Cypher query to answer this request. Only return the Cypher query, nothing else.
"""
    response = llm.generate_content(prompt)
    cypher_query = response.text.strip()
    cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()

    print("Generated Cypher:", cypher_query)

    with driver.session(database="neo4j") as session:
        results = session.run(cypher_query).data()
    return results


# Example
print(run_dynamic_cypher("Find all documents authored by Anil Kumar"))
