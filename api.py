from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
import os
import uuid
import cv2
import numpy as np
from PIL import Image
import io
import tempfile
import logging
from datetime import datetime
from deepface import DeepFace
import pytesseract
from supabase import create_client
import re

# Configurações iniciais
app = FastAPI(title="API de Verificação de Identidade")
logging.basicConfig(level=logging.INFO)

# Configuração do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Modelos Pydantic
class VerificationResponse(BaseModel):
    success: bool
    face_match: dict
    extracted_info: dict
    user_exists: bool
    user_id: str = None
    message: str

# Funções de processamento de imagem
def bytes_to_cvimage(image_bytes):
    return cv2.cvtColor(np.array(Image.open(io.BytesIO(image_bytes))), cv2.COLOR_RGB2BGR)

def verify_faces(face_img, doc_img):
    with tempfile.NamedTemporaryFile(suffix='.jpg') as f1, tempfile.NamedTemporaryFile(suffix='.jpg') as f2:
        cv2.imwrite(f1.name, face_img)
        cv2.imwrite(f2.name, doc_img)
        result = DeepFace.verify(f1.name, f2.name, model_name="VGG-Face")
    return {
        "match": result["verified"],
        "confidence": 1 - result["distance"],
        "threshold": 0.6
    }

# Funções OCR
def extract_rg_info(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray, lang='por')
    
    def extract(pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else ""
    
    return {
        "nome": extract(r"NOME[\n\s]+([A-Z\s]+)"),
        "rg": extract(r"REGISTRO GERAL[\n\s]+(\d+\.?\d+\.?\d+-?\w?)"),
        "cpf": extract(r"(\d{3}\.\d{3}\.\d{3}-\d{2})"),
        "data_nascimento": extract(r"(\d{2}/\d{2}/\d{4})")
    }

# Endpoint principal
@app.post("/verify", response_model=VerificationResponse)
async def verify_identity(
    face_image: UploadFile = File(...),
    document_image: UploadFile = File(...)
):
    try:
        # Processar imagens
        face_img = bytes_to_cvimage(await face_image.read())
        doc_img = bytes_to_cvimage(await document_image.read())
        
        # Verificação facial
        face_result = verify_faces(face_img, doc_img)
        
        # Extrair dados do RG
        rg_data = extract_rg_info(doc_img)
        
        # Verificar no banco de dados
        user_exists = False
        if rg_data["rg"]:
            response = supabase.table('usuarios').select('*').eq('rg', rg_data["rg"]).execute()
            user_exists = len(response.data) > 0
        
        # Cadastrar usuário se necessário
        user_id = None
        if not user_exists and face_result["match"]:
            user_id = str(uuid.uuid4())
            supabase.table('usuarios').insert({
                "id": user_id,
                **rg_data,
                "data_cadastro": datetime.now().isoformat()
            }).execute()
        
        return VerificationResponse(
            success=True,
            face_match=face_result,
            extracted_info=rg_data,
            user_exists=user_exists,
            user_id=user_id,
            message="Usuário verificado com sucesso" if face_result["match"] else "Falha na verificação facial"
        )
        
    except Exception as e:
        logging.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8321)
