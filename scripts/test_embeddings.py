from langchain_huggingface import HuggingFaceEmbeddings

emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

question = emb.embed_query("Which project uses JWT tokens?")
unrelated = emb.embed_query("How do warehouse staff scan pallets?")
chunk = emb.embed_documents(["Project A implemented JWT authentication. Access tokens expire after 15 minutes."])[0]

dot = lambda x, y: sum(i * j for i, j in zip(x, y))
print("vector length:", len(chunk))
print("question vs auth chunk:   ", round(dot(question, chunk), 3))
print("unrelated vs auth chunk:  ", round(dot(unrelated, chunk), 3))