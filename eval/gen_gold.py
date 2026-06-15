"""Gerador programático de diagramas do gold set (Fase 5, 5.3b).

Renderiza diagramas de arquitetura realistas com `mingrammer/diagrams` (ícones oficiais
AWS/Azure/GCP, via Graphviz `dot`) e emite, junto, a **ground-truth NEUTRA** automática
(componentes em classes canônicas + arestas). Isso dá: (i) imagens p/ Cíclope/ARGUS analisarem,
(ii) a GT neutra que o juiz usa como contexto justo (resolve o confound do pairwise), (iii) GT de
topologia. Limitação: não emite bounding boxes → mAP do detector fica fora destes (há no sintético).

Pré-requisitos: `pip install diagrams` + Graphviz (`brew install graphviz`).
Uso: `.venv-ml/bin/python eval/gen_gold.py` → escreve eval/gold/<nome>.png + <nome>.gt.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from diagrams import Diagram, Edge
from diagrams.aws.analytics import ElasticsearchService
from diagrams.aws.compute import EC2, Lambda
from diagrams.aws.database import RDS, Dynamodb, ElastiCache
from diagrams.aws.engagement import SimpleEmailServiceSes
from diagrams.aws.general import General
from diagrams.aws.integration import SQS
from diagrams.aws.management import Cloudwatch
from diagrams.aws.network import ELB, APIGateway, CloudFront
from diagrams.aws.security import IAM, KMS, WAF
from diagrams.aws.storage import EFS, S3
from diagrams.azure.compute import FunctionApps, VM
from diagrams.azure.database import CacheForRedis, CosmosDb, SQLDatabases
from diagrams.azure.identity import ActiveDirectory
from diagrams.azure.integration import ServiceBus
from diagrams.azure.network import ApplicationGateway, CDNProfiles, LoadBalancers
from diagrams.azure.security import KeyVaults
from diagrams.azure.storage import BlobStorage
from diagrams.azure.web import AppServices, Search
from diagrams.gcp.analytics import Pubsub
from diagrams.gcp.api import APIGateway as GcpAPIGateway
from diagrams.gcp.compute import ComputeEngine, Functions
from diagrams.gcp.database import SQL, Firestore, Memorystore
from diagrams.gcp.network import CDN, LoadBalancing
from diagrams.gcp.operations import Monitoring
from diagrams.gcp.security import Iam, KeyManagementService
from diagrams.gcp.storage import Storage

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
from app.taxonomy import CANONICAL_ELEMENT_TYPE  # noqa: E402

OUT = Path(__file__).resolve().parent / "gold"

# canonical → classe de nó mingrammer, por nuvem (apenas classes validadas; `General` = genérico/externo)
NODES: dict[str, dict] = {
    "aws": {
        "actor_user": General, "cdn": CloudFront, "load_balancer": ELB, "api_gateway": APIGateway,
        "compute": EC2, "serverless_fn": Lambda, "database_sql": RDS, "database_nosql": Dynamodb,
        "cache": ElastiCache, "object_storage": S3, "file_storage": EFS, "message_queue": SQS,
        "edge_security": WAF, "identity": IAM, "secrets": KMS, "email_notify": SimpleEmailServiceSes,
        "monitoring": Cloudwatch, "backend_external": General, "app_service": EC2, "search": ElasticsearchService,
    },
    "azure": {
        "actor_user": General, "cdn": CDNProfiles, "load_balancer": LoadBalancers, "api_gateway": ApplicationGateway,
        "compute": VM, "serverless_fn": FunctionApps, "database_sql": SQLDatabases, "database_nosql": CosmosDb,
        "cache": CacheForRedis, "object_storage": BlobStorage, "identity": ActiveDirectory, "app_service": AppServices,
        "backend_external": General, "message_queue": ServiceBus, "secrets": KeyVaults, "search": Search,
    },
    "gcp": {
        "actor_user": General, "load_balancer": LoadBalancing, "compute": ComputeEngine, "serverless_fn": Functions,
        "database_sql": SQL, "database_nosql": Firestore, "object_storage": Storage, "backend_external": General,
        "app_service": ComputeEngine, "api_gateway": GcpAPIGateway, "message_queue": Pubsub, "cache": Memorystore,
        "cdn": CDN, "identity": Iam, "secrets": KeyManagementService, "monitoring": Monitoring,
    },
}


def _node(cloud: str, canonical: str):
    return NODES[cloud].get(canonical) or NODES[cloud]["backend_external"]


def render(spec: dict) -> Path:
    """Renderiza o PNG e escreve a GT neutra (<nome>.gt.json). Devolve o caminho do PNG."""
    cloud, name = spec["cloud"], spec["name"]
    OUT.mkdir(parents=True, exist_ok=True)
    nodes: dict[str, object] = {}
    with Diagram(spec["label"], filename=str(OUT / name), outformat="png", show=False, direction="LR"):
        for c in spec["components"]:
            nodes[c["id"]] = _node(cloud, c["canonical"])(c["label"])
        for src, dst, crosses in spec["edges"]:
            style = Edge(color="firebrick" if crosses else "black", style="dashed" if crosses else "solid")
            nodes[src] >> style >> nodes[dst]

    gt = {
        "system_name": spec["label"],
        "_note": "GT NEUTRA gerada por eval/gen_gold.py (mingrammer) — classes canônicas; contexto justo p/ o juiz.",
        "cloud": cloud,
        "complexity": spec["complexity"],
        "components": [
            {"id": c["id"], "canonical": c["canonical"],
             "element_type": CANONICAL_ELEMENT_TYPE.get(c["canonical"], "Process"), "label": c["label"]}
            for c in spec["components"]
        ],
        "edges": [{"source": s, "target": t, "crosses_boundary": x} for s, t, x in spec["edges"]],
    }
    (OUT / f"{name}.gt.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
    return OUT / f"{name}.png"


def _c(cid: str, canonical: str, label: str) -> dict:
    return {"id": cid, "canonical": canonical, "label": label}


# Specs estratificadas (amostra inicial; expandir até ~12 cobrindo simples/médio/denso × AWS/Azure/GCP)
SPECS: list[dict] = [
    {
        "name": "gold-aws-simples-web", "label": "Web app simples (AWS)", "cloud": "aws", "complexity": "simples",
        "components": [_c("C1", "actor_user", "Usuários"), _c("C2", "load_balancer", "ALB"),
                       _c("C3", "compute", "App EC2"), _c("C4", "database_sql", "RDS")],
        "edges": [("C1", "C2", True), ("C2", "C3", True), ("C3", "C4", False)],
    },
    {
        "name": "gold-gcp-simples-api", "label": "API serverless simples (GCP)", "cloud": "gcp", "complexity": "simples",
        "components": [_c("C1", "actor_user", "Cliente"), _c("C2", "load_balancer", "Cloud LB"),
                       _c("C3", "serverless_fn", "Cloud Functions"), _c("C4", "database_nosql", "Firestore"),
                       _c("C5", "object_storage", "GCS")],
        "edges": [("C1", "C2", True), ("C2", "C3", True), ("C3", "C4", False), ("C3", "C5", False)],
    },
    {
        "name": "gold-azure-medio-apim", "label": "API Management (Azure)", "cloud": "azure", "complexity": "medio",
        "components": [_c("C1", "actor_user", "Cliente"), _c("C2", "identity", "Entra ID"),
                       _c("C3", "api_gateway", "API Gateway"), _c("C4", "serverless_fn", "Functions"),
                       _c("C5", "database_sql", "Azure SQL"), _c("C6", "cache", "Redis"),
                       _c("C7", "backend_external", "SaaS externo")],
        "edges": [("C1", "C3", True), ("C1", "C2", True), ("C3", "C2", True), ("C3", "C4", False),
                  ("C4", "C5", False), ("C4", "C6", False), ("C4", "C7", True)],
    },
    {
        "name": "gold-aws-medio-3tier", "label": "3 camadas com fila (AWS)", "cloud": "aws", "complexity": "medio",
        "components": [_c("C1", "actor_user", "Usuários"), _c("C2", "cdn", "CloudFront"),
                       _c("C3", "load_balancer", "ALB"), _c("C4", "compute", "App EC2"),
                       _c("C5", "message_queue", "SQS"), _c("C6", "serverless_fn", "Worker Lambda"),
                       _c("C7", "database_sql", "RDS"), _c("C8", "object_storage", "S3")],
        "edges": [("C1", "C2", True), ("C2", "C3", True), ("C3", "C4", True), ("C4", "C5", False),
                  ("C5", "C6", False), ("C6", "C7", False), ("C4", "C8", False)],
    },
    {
        "name": "gold-aws-denso-microservices", "label": "Microsserviços densos (AWS)", "cloud": "aws", "complexity": "denso",
        "components": [_c("C1", "actor_user", "Usuários"), _c("C2", "edge_security", "WAF"),
                       _c("C3", "cdn", "CloudFront"), _c("C4", "api_gateway", "API Gateway"),
                       _c("C5", "compute", "Svc Pedidos"), _c("C6", "compute", "Svc Pagamentos"),
                       _c("C7", "serverless_fn", "Svc Notif (Lambda)"), _c("C8", "database_sql", "RDS Pedidos"),
                       _c("C9", "database_nosql", "DynamoDB Sessão"), _c("C10", "cache", "ElastiCache"),
                       _c("C11", "message_queue", "SQS"), _c("C12", "identity", "IAM"),
                       _c("C13", "secrets", "KMS"), _c("C14", "object_storage", "S3"),
                       _c("C15", "monitoring", "CloudWatch"), _c("C16", "email_notify", "SES")],
        "edges": [("C1", "C2", True), ("C2", "C3", True), ("C3", "C4", True), ("C4", "C5", True),
                  ("C4", "C6", True), ("C5", "C8", False), ("C5", "C10", False), ("C6", "C8", False),
                  ("C6", "C11", False), ("C11", "C7", False), ("C7", "C16", True), ("C5", "C9", False),
                  ("C6", "C13", False), ("C4", "C12", False), ("C5", "C14", False), ("C5", "C15", False)],
    },
    {
        "name": "gold-azure-denso-events", "label": "Orquestração de eventos densa (Azure)", "cloud": "azure", "complexity": "denso",
        "components": [_c("C1", "actor_user", "Cliente"), _c("C2", "identity", "Entra ID"),
                       _c("C3", "cdn", "Front Door/CDN"), _c("C4", "api_gateway", "API Management"),
                       _c("C5", "app_service", "Web App"), _c("C6", "serverless_fn", "Functions"),
                       _c("C7", "database_sql", "Azure SQL"), _c("C8", "database_nosql", "Cosmos DB"),
                       _c("C9", "cache", "Redis"), _c("C10", "object_storage", "Blob Storage"),
                       _c("C11", "backend_external", "SaaS externo"), _c("C12", "backend_external", "Web service legado")],
        "edges": [("C1", "C3", True), ("C3", "C4", True), ("C1", "C2", True), ("C4", "C2", True),
                  ("C4", "C5", False), ("C5", "C6", False), ("C6", "C7", False), ("C6", "C8", False),
                  ("C5", "C9", False), ("C6", "C10", False), ("C6", "C11", True), ("C6", "C12", True)],
    },
    {
        "name": "gold-azure-simples-static", "label": "Site estático simples (Azure)", "cloud": "azure", "complexity": "simples",
        "components": [_c("C1", "actor_user", "Usuários"), _c("C2", "cdn", "Azure CDN"),
                       _c("C3", "app_service", "Static Web App"), _c("C4", "object_storage", "Blob Storage")],
        "edges": [("C1", "C2", True), ("C2", "C3", True), ("C3", "C4", False)],
    },
    {
        "name": "gold-gcp-simples-functions", "label": "Função serverless simples (GCP)", "cloud": "gcp", "complexity": "simples",
        "components": [_c("C1", "actor_user", "Cliente"), _c("C2", "api_gateway", "API Gateway"),
                       _c("C3", "serverless_fn", "Cloud Functions"), _c("C4", "database_nosql", "Firestore")],
        "edges": [("C1", "C2", True), ("C2", "C3", False), ("C3", "C4", False)],
    },
    {
        "name": "gold-gcp-medio-pubsub", "label": "Pipeline de eventos (GCP)", "cloud": "gcp", "complexity": "medio",
        "components": [_c("C1", "actor_user", "Cliente"), _c("C2", "load_balancer", "Cloud LB"),
                       _c("C3", "compute", "App (GCE)"), _c("C4", "message_queue", "Pub/Sub"),
                       _c("C5", "serverless_fn", "Worker (Functions)"), _c("C6", "database_sql", "Cloud SQL"),
                       _c("C7", "cache", "Memorystore")],
        "edges": [("C1", "C2", True), ("C2", "C3", True), ("C3", "C4", False), ("C4", "C5", False),
                  ("C5", "C6", False), ("C3", "C7", False)],
    },
    {
        "name": "gold-azure-medio-events", "label": "Eventos com Service Bus (Azure)", "cloud": "azure", "complexity": "medio",
        "components": [_c("C1", "actor_user", "Cliente"), _c("C2", "api_gateway", "API Management"),
                       _c("C3", "identity", "Entra ID"), _c("C4", "serverless_fn", "Functions"),
                       _c("C5", "message_queue", "Service Bus"), _c("C6", "database_sql", "Azure SQL"),
                       _c("C7", "secrets", "Key Vault")],
        "edges": [("C1", "C2", True), ("C1", "C3", True), ("C2", "C3", True), ("C2", "C4", False),
                  ("C4", "C5", False), ("C5", "C6", False), ("C4", "C7", False)],
    },
    {
        "name": "gold-gcp-denso-microservices", "label": "Microsserviços densos (GCP)", "cloud": "gcp", "complexity": "denso",
        "components": [_c("C1", "actor_user", "Usuários"), _c("C2", "cdn", "Cloud CDN"),
                       _c("C3", "api_gateway", "API Gateway"), _c("C4", "compute", "Svc Pedidos (GKE)"),
                       _c("C5", "compute", "Svc Pagamentos (GKE)"), _c("C6", "serverless_fn", "Svc Notif (Functions)"),
                       _c("C7", "database_sql", "Cloud SQL"), _c("C8", "database_nosql", "Firestore"),
                       _c("C9", "cache", "Memorystore"), _c("C10", "message_queue", "Pub/Sub"),
                       _c("C11", "object_storage", "Cloud Storage"), _c("C12", "identity", "Cloud IAM"),
                       _c("C13", "secrets", "Cloud KMS"), _c("C14", "monitoring", "Cloud Monitoring")],
        "edges": [("C1", "C2", True), ("C2", "C3", True), ("C3", "C4", True), ("C3", "C5", True),
                  ("C4", "C7", False), ("C4", "C9", False), ("C5", "C7", False), ("C5", "C10", False),
                  ("C10", "C6", False), ("C4", "C8", False), ("C3", "C12", False), ("C5", "C13", False),
                  ("C4", "C11", False), ("C4", "C14", False)],
    },
    {
        "name": "gold-aws-denso-dataplatform", "label": "Plataforma de dados densa (AWS)", "cloud": "aws", "complexity": "denso",
        "components": [_c("C1", "actor_user", "Usuários"), _c("C2", "edge_security", "WAF"),
                       _c("C3", "cdn", "CloudFront"), _c("C4", "api_gateway", "API Gateway"),
                       _c("C5", "compute", "Ingest (EC2)"), _c("C6", "message_queue", "SQS"),
                       _c("C7", "serverless_fn", "ETL (Lambda)"), _c("C8", "database_sql", "RDS"),
                       _c("C9", "database_nosql", "DynamoDB"), _c("C10", "object_storage", "S3"),
                       _c("C11", "search", "OpenSearch"), _c("C12", "identity", "IAM"),
                       _c("C13", "secrets", "KMS"), _c("C14", "monitoring", "CloudWatch"),
                       _c("C15", "email_notify", "SES")],
        "edges": [("C1", "C2", True), ("C2", "C3", True), ("C3", "C4", True), ("C4", "C5", True),
                  ("C5", "C6", False), ("C6", "C7", False), ("C7", "C8", False), ("C7", "C9", False),
                  ("C7", "C10", False), ("C7", "C11", False), ("C7", "C15", True), ("C4", "C12", False),
                  ("C5", "C13", False), ("C5", "C14", False)],
    },
]


def main() -> int:
    for spec in SPECS:
        png = render(spec)
        n_c, n_e = len(spec["components"]), len(spec["edges"])
        print(f"  ✓ {spec['name']:34} [{spec['complexity']:7}] {n_c:2} comp · {n_e:2} arestas → {png.name}")
    print(f"\n✓ {len(SPECS)} diagramas + GT em {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
