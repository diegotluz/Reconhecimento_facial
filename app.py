import streamlit as st
import requests
import os

# Configuração da interface
st.title("Verificação de Identidade")
API_URL = os.getenv("API_URL", "http://localhost:8322/verify")

# Componentes de upload
col1, col2 = st.columns(2)
with col1:
    face = st.file_uploader("Selfie", type=["jpg", "png"])
with col2:
    doc = st.file_uploader("Documento", type=["jpg", "png"])

# Processamento do formulário
if st.button("Verificar") and face and doc:
    with st.spinner("Processando..."):
        files = {
            "face_image": (face.name, face.getvalue()),
            "document_image": (doc.name, doc.getvalue())
        }
        
        try:
            response = requests.post(API_URL, files=files)
            if response.status_code == 200:
                data = response.json()
                st.success(data["message"])
                
                with st.expander("Detalhes"):
                    st.json(data)
                    
                    # Exibir comparação facial
                    cols = st.columns(2)
                    cols[0].image(face, caption="Selfie")
                    cols[1].image(doc, caption="Documento")
                    
                    # Exibir dados extraídos
                    st.subheader("Dados do Documento")
                    st.write(f"Nome: {data['extracted_info']['nome']}")
                    st.write(f"RG: {data['extracted_info']['rg']}")
                    st.write(f"CPF: {data['extracted_info']['cpf']}")
                    
            else:
                st.error(f"Erro: {response.text}")
                
        except Exception as e:
            st.error(f"Falha na comunicação: {str(e)}")
