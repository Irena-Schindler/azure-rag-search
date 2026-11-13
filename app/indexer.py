"""Create the Azure AI Search index (hybrid + semantic) and upload embedded chunks.

    python -m app.indexer            # needs AZURE_SEARCH_ENDPOINT, AZURE_OPENAI_ENDPOINT and az login
"""
from __future__ import annotations
from .chunking import load_corpus
from .config import Settings
from .pipeline import DOCS


def index_definition(name: str, dims: int):
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration, SearchableField, SearchField, SearchFieldDataType, SearchIndex,
        SemanticConfiguration, SemanticField, SemanticPrioritizedFields, SemanticSearch, SimpleField,
        VectorSearch, VectorSearchProfile)
    return SearchIndex(
        name=name,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="title", type=SearchFieldDataType.String, analyzer_name="de.microsoft"),
            SearchableField(name="section", type=SearchFieldDataType.String, analyzer_name="de.microsoft"),
            SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="de.microsoft"),
            SearchField(name="contentVector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True, vector_search_dimensions=dims, vector_search_profile_name="hnsw"),
        ],
        vector_search=VectorSearch(algorithms=[HnswAlgorithmConfiguration(name="hnsw-algo")],
                                   profiles=[VectorSearchProfile(name="hnsw", algorithm_configuration_name="hnsw-algo")]),
        semantic_search=SemanticSearch(configurations=[SemanticConfiguration(
            name="default", prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="section"),
                content_fields=[SemanticField(field_name="content")]))]),
    )


def main() -> None:  # pragma: no cover - needs Azure
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from openai import AzureOpenAI
    s = Settings()
    cred = DefaultAzureCredential()
    SearchIndexClient(s.search_endpoint, cred).create_or_update_index(index_definition(s.search_index, s.embedding_dimensions))
    client = AzureOpenAI(azure_endpoint=s.openai_endpoint, api_version=s.api_version,
                         azure_ad_token_provider=get_bearer_token_provider(cred, "https://cognitiveservices.azure.com/.default"))
    chunks = load_corpus(DOCS)
    vectors = client.embeddings.create(model=s.embedding_deployment,
                                       input=[f"{c.section}\n{c.content}" for c in chunks]).data
    docs = [{"id": c.id, "title": c.title, "section": c.section, "content": c.content,
             "contentVector": v.embedding} for c, v in zip(chunks, vectors)]
    result = SearchClient(s.search_endpoint, s.search_index, cred).upload_documents(docs)
    print(f"indexed {sum(r.succeeded for r in result)}/{len(docs)} chunks into {s.search_index}")


if __name__ == "__main__":
    main()
