from typing import List, Union
from haystack.dataclasses import Document
from haystack.components.embedders import SentenceTransformersTextEmbedder, SentenceTransformersDocumentEmbedder


class HaystackEmbeddingGenerator:
    """
    A Haystack-native class to handle generating embeddings.
    It uses Haystack's optimized components and loads the model only once.
    """
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        """
        Initializes the generator and pre-loads the Haystack embedder components.
        """
        print(f"Initializing Haystack embedders with model: {model_name}...")
        
        self.text_embedder = SentenceTransformersTextEmbedder(model=model_name)        
        self.doc_embedder = SentenceTransformersDocumentEmbedder(model=model_name)
        
        # Warm up the components to load the model into memory
        self.text_embedder.warm_up()
        self.doc_embedder.warm_up()
        print("Haystack embedders initialized successfully.")

    def embed(self, texts: Union[str, List[str]]):
        """
        Generates vector embeddings for the given text(s) using Haystack components.
        
        :param texts: A single string or a list of strings to be embedded.
        :return: A vector or a list of vectors.
        """
        if isinstance(texts, str): # It's a single string, use the text embedder
            result = self.text_embedder.run(text=texts)
            return result["embedding"]
        
        elif isinstance(texts, list): # It's a list of strings, use document embedder
            documents = [Document(content=t) for t in texts]
            
            result = self.doc_embedder.run(documents=documents)
            
            embeddings = [doc.embedding for doc in result["documents"]]
            return embeddings
        
        else:
            raise TypeError("Input must be a string or a list of strings.")


if __name__ == "__main__":
    embedder = HaystackEmbeddingGenerator()

    single_text = "This is a test sentence using a Haystack component."
    single_embedding = embedder.embed(single_text)
    print(f"\nEmbedding for a single sentence has {len(single_embedding)} dimensions.")

    list_of_texts = [
        "This is the first sentence in a batch.",
        "This is the second sentence, processed efficiently."
    ]
    list_embeddings = embedder.embed(list_of_texts)
    print(f"Generated {len(list_embeddings)} embeddings for the list of sentences.")