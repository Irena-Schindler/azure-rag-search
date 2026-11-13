# azure-rag-search

**An internal policy assistant on Azure: Azure AI Search (hybrid + semantic ranker) and Azure OpenAI,
deployed keyless with Bicep and GitHub Actions.** Employees ask "How many vacation days do I have?"
and get a sourced answer, or a clear "not in our policies", never a guess.

```
docs/*.md ─► section chunks ─► Azure OpenAI embeddings ─► Azure AI Search index (BM25 + HNSW vectors, de.microsoft analyzer)

question ─► hybrid query ─► semantic re-ranking ─► relevance threshold ─► GPT with numbered sources
                                                        │                        │
                                                        └─► refuse                └─► citation check ─► answer + sources
```

## What it demonstrates

| Concern | How |
|---|---|
| Azure AI Search | Hybrid retrieval (keyword + vector) with the semantic ranker; German analyzer; index defined in code (`app/indexer.py`) |
| Azure OpenAI | Chat and embedding deployments, called through `AzureOpenAI` with an Entra ID token provider |
| Keyless security | Managed identity + RBAC only. `disableLocalAuth` on OpenAI and Search, no API keys anywhere, `AcrPull` via identity |
| Infrastructure as code | `infra/main.bicep`: OpenAI + deployments, AI Search, Container Apps, ACR, Log Analytics, App Insights, role assignments |
| CI/CD | OIDC login from GitHub (no secrets stored besides IDs), two-phase deploy, image built in ACR, indexing, smoke test, eval |
| Answer quality | Every statement cites `[n]`; answers citing unknown sources or nothing are rejected; refusal below the relevance threshold |
| Runs offline | BM25 retriever + extractive generator: tests, evals and local dev need no Azure subscription |
| Evals | hit@3, MRR and correct refusals incl. a prompt-injection question (`python -m evals.run`), enforced in CI |

## Run locally

```bash
pip install -r requirements.txt
pytest -q
python -m evals.run
# mode: local BM25
# hit@3 12/12 | MRR 1.00 | correct refusals 4/4
# paraphrases without shared words (need vector search): 0/2 found locally
uvicorn app.main:app --reload     # POST /ask {"question": "Wie hoch ist die Homeoffice-Pauschale?"}
```

The two paraphrases ("Krankschreibung" for "Arbeitsunfähigkeitsbescheinigung", "Reisebelege" for
"Belege nach Dienstreisen") are why the Azure setup uses hybrid search: keyword search alone cannot
find them. On Azure every eval case is enforced.

## Deploy to Azure

1. Create an app registration with a federated credential for this repository and give it
   *Contributor* and *User Access Administrator* (or *Role Based Access Control Administrator*) on the subscription or a resource group.
2. Add the repository secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
3. Run the **deploy** workflow. It creates the platform, builds the image in ACR, indexes `docs/`,
   rolls out the Container App (scale to zero) and runs the smoke test and the eval against Azure.

Choose a region where both models are available (default `swedencentral`, keeps data in the EU).
Rough cost while idle: AI Search *basic* is the main fixed cost; Container Apps scale to zero.
Delete the resource group after a demo.

## Honest scope

Tests and the offline eval run in CI on every push; the Bicep file is compiled in CI. The Azure path
(`AzureSearchRetriever`, `AzureOpenAIGenerator`, indexer, deploy workflow) runs against a live
subscription and needs calibration there, above all `MIN_SCORE` for the semantic reranker
(0–4 scale). For production add private endpoints, a VNet-integrated Container Apps environment
and Azure Front Door with WAF.

All companies, policies and numbers in `docs/` are fictional.
