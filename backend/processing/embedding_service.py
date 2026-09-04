import torch
from PIL import Image as PILImage
from transformers import CLIPProcessor, CLIPModel
from processing.vector_store import VectorStore

class EmbeddingService:
    def __init__(self):
        self.model_id = "openai/clip-vit-base-patch32"
        self.model = CLIPModel.from_pretrained(self.model_id)
        self.processor = CLIPProcessor.from_pretrained(self.model_id)

    def process_image_embedding(self, image_path: str, store: VectorStore) -> str:
        image = PILImage.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
        
        # We return the vector list
        vector = image_features.squeeze().tolist()
        # Add to FAISS and return ID
        return store.add_vector(vector)

    def process_text_embedding(self, text: str) -> list[float]:
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
        text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)
        return text_features.squeeze().tolist()

embedding_service = EmbeddingService()
