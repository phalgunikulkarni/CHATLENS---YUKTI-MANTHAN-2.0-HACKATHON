import os
import faiss
import numpy as np

FAISS_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "storage", "chatlens.index")

class VectorStore:
    def __init__(self, dimension=512):
        self.dimension = dimension
        if os.path.exists(FAISS_INDEX_PATH):
            self.index = faiss.read_index(FAISS_INDEX_PATH)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            
    def add_vector(self, vector: list[float]) -> str:
        vec_np = np.array([vector], dtype=np.float32)
        current_id = self.index.ntotal
        self.index.add(vec_np)
        self.save()
        return str(current_id)
        
    def save(self):
        # Ensure storage directory exists
        os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
        faiss.write_index(self.index, FAISS_INDEX_PATH)

    def search_vectors(self, vector: list[float], top_k: int = 10):
        if self.index.ntotal == 0:
            return [], []
        vec_np = np.array([vector], dtype=np.float32)
        distances, indices = self.index.search(vec_np, top_k)
        return distances[0].tolist(), indices[0].tolist()

vector_store = VectorStore()
